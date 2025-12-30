import cv2
import numpy as np
import threading
import os
import time
import logging
from queue import Queue, Empty

logger = logging.getLogger(__name__)

class VideoProcessor:
    """
    Une classe pour gérer le traitement des vidéos de manière thread-safe
    """
    def __init__(self):
        self.caps = {}
        self.locks = {}
        self.frame_buffers = {}
        self.threads = {}
        self.video_ended = {}
        self.stop_flags = {}
    
    def initialize(self, directions, video_paths, buffer_size=30):
        """
        Initialise les ressources pour chaque direction
        """
        for direction in directions:
            self.locks[direction] = threading.Lock()
            self.frame_buffers[direction] = Queue(maxsize=buffer_size)
            self.video_ended[direction] = True
            self.stop_flags[direction] = False
            self.caps[direction] = None
    
    def create_error_frame(self, direction, message, colors):
        """
        Crée une frame d'erreur avec un message pour une direction donnée
        """
        display_width, display_height = 400, 300
        error_frame = np.zeros((display_height + 30, display_width, 3), dtype=np.uint8)
        title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
        color = colors[direction]
        cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
        cv2.putText(title_bar, f"{direction.upper()}: ERREUR", (10, 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(error_frame[30:, :], message, (int(display_width/2) - 120, int(display_height/2)), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return np.vstack((title_bar, error_frame[30:, :]))
    
    def start_video(self, direction, video_path, colors):
        """
        Démarre le traitement d'une vidéo pour une direction donnée
        """
        if self.threads.get(direction) and self.threads[direction].is_alive():
            self.stop_flags[direction] = True
            self.threads[direction].join(timeout=1.0)
        
        # Réinitialiser les flags
        self.stop_flags[direction] = False
        self.video_ended[direction] = False
        
        # Libérer la capture existante s'il y en a une
        with self.locks[direction]:
            if self.caps.get(direction) is not None:
                try:
                    self.caps[direction].release()
                except Exception as e:
                    logger.error(f"Erreur lors de la libération de la capture {direction}: {e}")
            self.caps[direction] = None
        
        # Vérifier l'existence du fichier vidéo
        abs_path = os.path.abspath(video_path)
        if not os.path.isfile(abs_path):
            logger.error(f"Le fichier vidéo n'existe pas: {abs_path}")
            error_frame = self.create_error_frame(direction, "Fichier vidéo non trouvé", colors)
            
            # Mettre la frame d'erreur dans le buffer
            while not self.frame_buffers[direction].empty():
                try:
                    self.frame_buffers[direction].get(block=False)
                except:
                    pass
            self.frame_buffers[direction].put(error_frame)
            
            self.video_ended[direction] = True
            return False
        
        # Démarrer un nouveau thread pour le traitement vidéo
        thread = threading.Thread(
            target=self._process_video_frames, 
            args=(direction, abs_path, colors),
            daemon=True
        )
        self.threads[direction] = thread
        thread.start()
        
        return True
    
    def _process_video_frames(self, direction, video_path, colors):
        """
        Traite les frames d'une vidéo et les met dans la file d'attente
        """
        try:
            # Ouvrir la vidéo avec CV_CAP_DSHOW pour Windows
            capture = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
            
            if not capture.isOpened():
                logger.error(f"Impossible d'ouvrir la vidéo {video_path}")
                error_frame = self.create_error_frame(direction, "Impossible d'ouvrir la vidéo", colors)
                
                # Mettre la frame d'erreur dans le buffer
                while not self.frame_buffers[direction].empty():
                    try:
                        self.frame_buffers[direction].get(block=False)
                    except:
                        pass
                self.frame_buffers[direction].put(error_frame)
                
                self.video_ended[direction] = True
                return
            
            # Stocker la capture dans le dictionnaire
            with self.locks[direction]:
                self.caps[direction] = capture
            
            display_width, display_height = 400, 300
            color = colors[direction]
            
            while not self.stop_flags[direction]:
                # Lire une frame
                with self.locks[direction]:
                    if self.caps[direction] is None:
                        break
                    ret, frame = self.caps[direction].read()
                
                # Vérifier si la vidéo est terminée
                if not ret:
                    final_frame = self.create_error_frame(direction, "Vidéo terminée", colors)
                    
                    # Vider la file d'attente et ajouter la frame finale
                    while not self.frame_buffers[direction].empty():
                        try:
                            self.frame_buffers[direction].get(block=False)
                        except:
                            pass
                    self.frame_buffers[direction].put(final_frame)
                    
                    self.video_ended[direction] = True
                    break
                
                # Redimensionner pour l'affichage
                frame = cv2.resize(frame, (display_width, display_height))
                
                # Créer la barre de titre
                title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
                cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
                cv2.putText(title_bar, f"{direction.upper()}", (10, 20), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # Combiner la barre de titre et la frame
                frame_with_title = np.vstack((title_bar, frame))
                
                # Mettre la frame dans le buffer sans bloquer
                if self.frame_buffers[direction].full():
                    try:
                        self.frame_buffers[direction].get(block=False)
                    except:
                        pass
                self.frame_buffers[direction].put(frame_with_title)
                
                # Délai pour éviter d'écraser le CPU
                time.sleep(0.03)
        
        except Exception as e:
            logger.error(f"Erreur dans _process_video_frames pour {direction}: {e}")
        finally:
            # Libérer les ressources
            try:
                with self.locks[direction]:
                    if self.caps.get(direction) is not None:
                        self.caps[direction].release()
                        self.caps[direction] = None
            except Exception as e:
                logger.error(f"Erreur lors de la libération des ressources pour {direction}: {e}")
            
            self.video_ended[direction] = True
    
    def stop_video(self, direction, colors):
        """
        Arrête le traitement d'une vidéo pour une direction donnée
        """
        if direction in self.stop_flags:
            self.stop_flags[direction] = True
            
            # Créer une frame finale
            final_frame = self.create_error_frame(direction, "Vidéo arrêtée", colors)
            
            # Mettre la frame finale dans le buffer
            if not self.frame_buffers[direction].full():
                while not self.frame_buffers[direction].empty():
                    try:
                        self.frame_buffers[direction].get(block=False)
                    except:
                        pass
                self.frame_buffers[direction].put(final_frame)
            
            return True
        return False
    
    def get_frame(self, direction, colors):
        """
        Récupère une frame de la file d'attente ou génère une frame d'attente
        """
        try:
            if not self.frame_buffers[direction].empty():
                return self.frame_buffers[direction].get(block=False)
            else:
                # Générer une frame d'attente
                display_width, display_height = 400, 300
                wait_frame = np.zeros((display_height + 30, display_width, 3), dtype=np.uint8)
                title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
                color = colors[direction]
                cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
                cv2.putText(title_bar, f"{direction.upper()}: En attente...", (10, 20), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(wait_frame[30:, :], "En attente de vidéo...", (80, 150), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                return np.vstack((title_bar, wait_frame[30:, :]))
        except Empty:
            # Gérer le cas où la queue est vide entre le check et le get
            display_width, display_height = 400, 300
            wait_frame = np.zeros((display_height + 30, display_width, 3), dtype=np.uint8)
            return wait_frame
    
    def cleanup(self):
        """
        Nettoie toutes les ressources vidéo
        """
        for direction in self.caps:
            self.stop_flags[direction] = True
            with self.locks[direction]:
                if self.caps[direction] is not None:
                    try:
                        self.caps[direction].release()
                        self.caps[direction] = None
                    except Exception as e:
                        logger.error(f"Erreur lors du nettoyage {direction}: {e}") 