from flask import Flask, render_template, Response, jsonify, request
import cv2
import pandas as pd
import os
import time
import threading
import json
from datetime import datetime, timedelta
import numpy as np
from tracker import EuclideanDistTracker
from traffic_manager import TrafficManager
from queue import Queue

app = Flask(__name__)

# Variables globales pour chaque direction
frames_global = {
    'nord': None,
    'sud': None,
    'est': None,
    'ouest': None
}
objets_detectes = {
    'nord': set(),
    'sud': set(),
    'est': set(),
    'ouest': set()
}
# Stockage des vitesses pour chaque direction
vitesses_moyennes = {
    'nord': 0,
    'sud': 0,
    'est': 0,
    'ouest': 0
}
# Compteurs d'objets en temps réel sur l'image
compteurs_temps_reel = {
    'nord': 0,
    'sud': 0,
    'est': 0,
    'ouest': 0
}
donnees_csv = []
csv_file = "static/resultats.csv"
stop_thread = False
processing_active = False
video_ended = {
    'nord': False,
    'sud': False,
    'est': False,
    'ouest': False
}

# Variable pour stocker les captures vidéo
caps = {}

# Historical data storage
historical_data = {
    'nord': [],
    'sud': [],
    'est': [],
    'ouest': []
}

last_record_time = datetime.now()

record_interval = 10

# Initialisation du gestionnaire de trafic
traffic_manager = TrafficManager()

# Initialisation des trackers pour chaque direction
trackers = {
    'nord': EuclideanDistTracker(),
    'sud': EuclideanDistTracker(),
    'est': EuclideanDistTracker(),
    'ouest': EuclideanDistTracker()
}

# Configuration des vidéos
videos = {
    'nord': "static/vd1.mp4",
    'sud': "static/vd2.mp4",
    'est': "static/vd3.mp4",
    'ouest': "static/vd4.mp4"
}

# Couleurs pour l'affichage (BGR)
colors = {
    'nord': (0, 165, 255),  
    'sud': (0, 255, 0),     
    'est': (255, 0, 0),     
    'ouest': (0, 0, 255)    
}

# Ajout des frames buffers 
frame_buffers = {
    'nord': Queue(maxsize=30),  
    'sud': Queue(maxsize=30),
    'est': Queue(maxsize=30),
    'ouest': Queue(maxsize=30)
}

def process_video(direction, video_path, tracker):
    """
    Traite une source vidéo dans un thread dédié

    """
    global frames_global, objets_detectes, donnees_csv, stop_thread, vitesses_moyennes, compteurs_temps_reel, video_ended, caps
    

    cv2.setNumThreads(0)
    
    # Libéreration de l'ancienne capture si elle existe
    if direction in caps and caps[direction] is not None:
        try:
            caps[direction].release()
            
            time.sleep(0.1)
        except Exception as e:
            print(f"Erreur lors de la libération de la capture {direction}: {e}")

    try:
   
        abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), video_path)
        
        cap = cv2.VideoCapture(abs_path, cv2.CAP_FFMPEG)
        
        
        if not os.path.isfile(abs_path):
            print(f"ERREUR: Le fichier vidéo n'existe pas: {abs_path}")
            
            display_width, display_height = 400, 300
            error_frame = np.zeros((display_height + 30, display_width, 3), dtype=np.uint8)
            title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
            color = colors[direction]
            cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
            cv2.putText(title_bar, f"{direction.upper()}: ERREUR", (10, 20), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(error_frame[30:, :], "Fichier vidéo non trouvé", (int(display_width/2) - 120, int(display_height/2)), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            frame_with_title = np.vstack((title_bar, error_frame[30:, :]))
            frames_global[direction] = frame_with_title
            
            # La frame d'erreur dans le buffer
            if not frame_buffers[direction].full():
                
                while not frame_buffers[direction].empty():
                    try:
                        frame_buffers[direction].get(block=False)
                    except:
                        pass
                frame_buffers[direction].put(frame_with_title)
            
            video_ended[direction] = True
            return
    except Exception as e:
        print(f"Erreur lors de l'ouverture de la vidéo {direction}: {e}")
        video_ended[direction] = True
        return
    
    # Réduction de la taille du buffer interne pour éviter la consommation excessive de mémoire
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    caps[direction] = cap
    
    if not cap.isOpened():
        print(f"Erreur: Impossible d'ouvrir la vidéo {video_path} pour la direction {direction}")
        video_ended[direction] = True
        return
    
    
    target_fps = 15  
    cap.set(cv2.CAP_PROP_FPS, target_fps)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)  
    
    # Précharger quelques frames pour éviter les saccades au démarrage
    display_width, display_height = 400, 300
    preload_frames = 5
    for _ in range(preload_frames):
        if stop_thread:
            break
        ret, frame = cap.read()
        if not ret:
            break
        
        
        frame = cv2.resize(frame, (display_width, display_height))
        
       
        title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
        cv2.rectangle(title_bar, (0, 0), (display_width, 30), colors[direction], -1)
        
       
        title_text = f"{direction.upper()}: Préchargement..."
        cv2.putText(title_bar, title_text, (10, 20), 
                  cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
       
        frame_with_title = np.vstack((title_bar, frame))
        
       
        if not frame_buffers[direction].full():
            frame_buffers[direction].put(frame_with_title)
    
    # Paramètres de détection optimisés
    object_detector = cv2.createBackgroundSubtractorMOG2(
        history=100,  
        varThreshold=30,
        detectShadows=False
    )
    
    
    area_threshold = 400
    roi_top = int(display_height * 0.2)
    roi_bottom = int(display_height * 0.9)
    
    color = colors[direction]
    total_speed = 0
    speed_count = 0
    current_objects = set()
    
    
    frame_count = 0
    processing_interval = 2  # Traiter 1 frame sur 2 pour la détection
    
    print(f"Démarrage du traitement vidéo pour {direction}")
    
    while not stop_thread and not video_ended[direction]:
        try:
            ret, frame = cap.read()
            if not ret:
                video_ended[direction] = True
                final_frame = np.zeros((display_height + 30, display_width, 3), dtype=np.uint8)
                title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
                cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
                
                title_text = f"{direction.upper()}: {len(objets_detectes[direction])} objets"
                cv2.putText(title_bar, title_text, (10, 20), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                cv2.putText(final_frame[30:, :], "Vidéo terminée", (int(display_width/2) - 80, int(display_height/2)), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                
                frame_with_title = np.vstack((title_bar, final_frame[30:, :]))
                
                
                while not frame_buffers[direction].empty():
                    try:
                        frame_buffers[direction].get(block=False)
                    except:
                        pass
                frame_buffers[direction].put(frame_with_title)
                
                traffic_manager.update_detection(
                    direction, 
                    len(objets_detectes[direction]), 
                    objets_detectes[direction], 
                    vitesses_moyennes[direction]
                )
                
                if not all(video_ended.values()):
                    print(f"La vidéo {direction} est terminée. Arrêt synchronisé de toutes les vidéos.")
                    stop_all_videos_and_regulate()
                
                break
            
            # Redimension pour l'affichage
            frame = cv2.resize(frame, (display_width, display_height))
            
           
            title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
            cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
            
           
            title_text = f"{direction.upper()}: {len(objets_detectes[direction])} objets"
            cv2.putText(title_bar, title_text, (10, 20), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
           
            frame_with_title = np.vstack((title_bar, frame))
            
            
            frames_global[direction] = frame_with_title
            
            frame_count += 1
            if frame_count % processing_interval == 0:
                # Détection des objets
                mask = object_detector.apply(frame)
                _, mask = cv2.threshold(mask, 254, 255, cv2.THRESH_BINARY)
                
                # Extraction des contours
                contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
                
                # Définition de la région d'intérêt
                roi = mask[roi_top:roi_bottom, :]
                
                # Liste pour stocker les détections
                detections = []
                
                for cnt in contours:
                    # Calcul de l'aire du contour
                    area = cv2.contourArea(cnt)
                    
                    # Filtrage par taille
                    if area > area_threshold:
                        # Calcul du rectangle englobant
                        x, y, w, h = cv2.boundingRect(cnt)
                        
                        # Vérification que l'objet est dans la ROI
                        if y >= roi_top and y + h <= roi_bottom:
                            detections.append([x, y, w, h])
                
                # Mise à jour du tracker
                tracked_objects = tracker.update(detections)
                
                # Mise à jour des compteurs et l'affichage
                current_objects = set()
                current_total_speed = 0
                current_speed_count = 0
                
                # Affichage des détections sur la frame
                for box_id in tracked_objects:
                    x, y, w, h, object_id, speed = box_id
                    
                    # Dessiner le rectangle autour de l'objet
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                    
                    # Afficher l'ID et la vitesse
                    label = f"ID:{object_id} {int(speed)}km/h"
                    cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
                    # Mettre à jour les compteurs
                    objets_detectes[direction].add(object_id)
                    current_objects.add(object_id)
                    
                    # Calcul de la vitesse moyenne
                    if speed > 0:
                        current_total_speed += speed
                        current_speed_count += 1
                
                # Mise à jour des compteurs en temps réel
                compteurs_temps_reel[direction] = len(current_objects)
                
                # Calcul de la vitesse moyenne avec lissage
                if current_speed_count > 0:
                    current_avg_speed = current_total_speed / current_speed_count
                    alpha = 0.3  # facteur de lissage
                    if vitesses_moyennes[direction] == 0:
                        vitesses_moyennes[direction] = current_avg_speed
                    else:
                        vitesses_moyennes[direction] = (vitesses_moyennes[direction] * (1-alpha) + 
                                                      current_avg_speed * alpha)
                
                # Mettre à jour la barre de titre avec le nombre d'objets
                title_text = f"{direction.upper()}: {len(objets_detectes[direction])} objets"
                cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
                cv2.putText(title_bar, title_text, (10, 20), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                
                # Mettre à jour la frame avec les détections
                frame_with_title = np.vstack((title_bar, frame))
                frames_global[direction] = frame_with_title
                
                # Mettre à jour le buffer avec la frame contenant les détections
                if frame_buffers[direction].full():
                    try:
                        frame_buffers[direction].get(block=False)
                    except:
                        pass
                frame_buffers[direction].put(frame_with_title)
            
            # Délai adaptatif - réduire à 10ms pour plus de fluidité
            time.sleep(0.01)
            
        except Exception as e:
            print(f"Erreur lors du traitement de la vidéo {direction}: {e}")
            time.sleep(0.1)  # Pause en cas d'erreur
    
    # Libérer les ressources avant de quitter
    try:
        cap.release()
        caps[direction] = None
    except:
        pass
    
    print(f"Traitement vidéo pour {direction} terminé")

def record_historical_data():
    """
    Enregistre périodiquement les données de trafic pour l'analyse historique
    """
    global last_record_time, historical_data
    
    current_time = datetime.now()
    if (current_time - last_record_time).total_seconds() >= record_interval:
        timestamp = current_time.timestamp()
        
        for direction in ['nord', 'sud', 'est', 'ouest']:
            # Get current traffic data
            count = compteurs_temps_reel[direction]
            speed = vitesses_moyennes[direction]
            
            # Get traffic light state
            traffic_state = traffic_manager.get_traffic_state()
            light_state = traffic_state['feux'][direction]['etat']
            
            # Record the data point
            data_point = {
                'timestamp': timestamp,
                'count': count,
                'speed': speed,
                'light_state': light_state
            }
            
            # Add to historical data
            historical_data[direction].append(data_point)
            
            # Limit the size of historical data (keep last 24 hours max)
            cutoff = current_time - timedelta(hours=24)
            historical_data[direction] = [
                entry for entry in historical_data[direction]
                if entry['timestamp'] >= cutoff.timestamp()
            ]
        
        last_record_time = current_time

def update_traffic_manager():
    """
    Mettre à jour le gestionnaire de trafic avec les dernières données de détection
    """
   
    print(f"Mise à jour du traffic_manager avec les données actuelles:")
    print(f"Nord: {compteurs_temps_reel['nord']} objets actuels, {len(objets_detectes['nord'])} total")
    print(f"Sud: {compteurs_temps_reel['sud']} objets actuels, {len(objets_detectes['sud'])} total")
    print(f"Est: {compteurs_temps_reel['est']} objets actuels, {len(objets_detectes['est'])} total")
    print(f"Ouest: {compteurs_temps_reel['ouest']} objets actuels, {len(objets_detectes['ouest'])} total")
    
    for direction in ['nord', 'sud', 'est', 'ouest']:
        
        traffic_manager.update_detection(
            direction, 
            len(objets_detectes[direction]),  
            objets_detectes[direction], 
            vitesses_moyennes[direction]
        )
    
    
    traffic_manager._update_scoot()

def detection_thread():
    global processing_active, stop_thread, frames_global, objets_detectes, vitesses_moyennes, compteurs_temps_reel, caps, video_ended
    
    
    cv2.setNumThreads(0)
    
   
    if 'caps' not in globals():
        caps = {}
    
    
    for direction in caps:
        if caps[direction] is not None:
            try:
                caps[direction].release()
                caps[direction] = None
            except Exception as e:
                print(f"Erreur lors de la libération de la capture {direction}: {e}")
    
    # Réinitialisation de l'état des vidéos pour permettre leur lecture
    for direction in video_ended:
        video_ended[direction] = False
    
    
    for direction in videos:
        display_width, display_height = 400, 300
        color = colors[direction]
        wait_frame = np.zeros((display_height + 30, display_width, 3), dtype=np.uint8)
        title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
        cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
        
        title_text = f"{direction.upper()}: En attente de démarrage"
        cv2.putText(title_bar, title_text, (10, 20), 
                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        cv2.putText(wait_frame[30:, :], "Cliquez sur Play pour démarrer", (int(display_width/2) - 120, int(display_height/2)), 
                  cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        frame_with_title = np.vstack((title_bar, wait_frame[30:, :]))
        frames_global[direction] = frame_with_title
    
    print("Thread de détection démarré")
    
    try:
        
        last_update_traffic = time.time()
        last_record_historical = time.time()
        
       
        threads = []
        for direction, video_path in videos.items():
            try:
               
                thread = threading.Thread(
                    target=process_video, 
                    args=(direction, video_path, trackers[direction]),
                    daemon=True
                )
                thread.start()
                threads.append(thread)
                
                time.sleep(0.5)
            except Exception as e:
                print(f"Erreur lors du démarrage du thread vidéo {direction}: {e}")
        
        while processing_active and not stop_thread:
            current_time = time.time()
            
            
            if current_time - last_record_historical >= 5.0:
                try:
                    record_historical_data()
                    last_record_historical = current_time
                except Exception as e:
                    print(f"Erreur lors de l'enregistrement des données historiques: {e}")
            
           
            if current_time - last_update_traffic >= 1.0:
                try:
                    update_traffic_manager()
                    last_update_traffic = current_time
                except Exception as e:
                    print(f"Erreur lors de la mise à jour du gestionnaire de trafic: {e}")
            
            
            time.sleep(0.01)  
    except Exception as e:
        print(f"Erreur dans le thread de détection: {e}")
    finally:
       
        if 'caps' in globals():
            for cap in caps.values():
                if cap is not None:
                    try:
                        cap.release()
                    except:
                        pass
        print("Thread de détection terminé")

def generate_frames_nord():
    while True:
        try:
            if not frame_buffers['nord'].empty():
                frame = frame_buffers['nord'].get(block=False)
                ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                # Ne pas afficher la frame d'attente si la vidéo est en cours de lecture
                if not video_ended['nord']:
                    time.sleep(0.01)  # Réduire le délai d'attente
                    continue
                
                # Afficher la frame d'attente uniquement si la vidéo est terminée
                display_width, display_height = 400, 300
                wait_frame = np.zeros((display_height + 30, display_width, 3), dtype=np.uint8)
                title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
                color = colors['nord']
                cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
                cv2.putText(title_bar, "NORD: En attente...", (10, 20), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(wait_frame[30:, :], "En attente de vidéo...", (80, 150), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                frame_with_title = np.vstack((title_bar, wait_frame[30:, :]))
                ret, buffer = cv2.imencode('.jpg', frame_with_title, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                time.sleep(0.05)
        except Exception as e:
            print(f"Erreur dans generate_frames_nord: {e}")
            time.sleep(0.05)

def generate_frames_sud():
    while True:
        try:
            if not frame_buffers['sud'].empty():
                frame = frame_buffers['sud'].get(block=False)
                ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                # Ne pas afficher la frame d'attente si la vidéo est en cours de lecture
                if not video_ended['sud']:
                    time.sleep(0.01)  # Réduire le délai d'attente
                    continue
                
                # Afficher la frame d'attente uniquement si la vidéo est terminée
                display_width, display_height = 400, 300
                wait_frame = np.zeros((display_height + 30, display_width, 3), dtype=np.uint8)
                title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
                color = colors['sud']
                cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
                cv2.putText(title_bar, "SUD: En attente...", (10, 20), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(wait_frame[30:, :], "En attente de vidéo...", (80, 150), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                frame_with_title = np.vstack((title_bar, wait_frame[30:, :]))
                ret, buffer = cv2.imencode('.jpg', frame_with_title, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                time.sleep(0.05)
        except Exception as e:
            print(f"Erreur dans generate_frames_sud: {e}")
            time.sleep(0.05)

def generate_frames_est():
    while True:
        try:
            if not frame_buffers['est'].empty():
                frame = frame_buffers['est'].get(block=False)
                ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                # Ne pas afficher la frame d'attente si la vidéo est en cours de lecture
                if not video_ended['est']:
                    time.sleep(0.01)  # Réduire le délai d'attente
                    continue
                
                # Afficher la frame d'attente uniquement si la vidéo est terminée
                display_width, display_height = 400, 300
                wait_frame = np.zeros((display_height + 30, display_width, 3), dtype=np.uint8)
                title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
                color = colors['est']
                cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
                cv2.putText(title_bar, "EST: En attente...", (10, 20), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(wait_frame[30:, :], "En attente de vidéo...", (80, 150), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                frame_with_title = np.vstack((title_bar, wait_frame[30:, :]))
                ret, buffer = cv2.imencode('.jpg', frame_with_title, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                time.sleep(0.05)
        except Exception as e:
            print(f"Erreur dans generate_frames_est: {e}")
            time.sleep(0.05)

def generate_frames_ouest():
    while True:
        try:
            if not frame_buffers['ouest'].empty():
                frame = frame_buffers['ouest'].get(block=False)
                ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                # Ne pas afficher la frame d'attente si la vidéo est en cours de lecture
                if not video_ended['ouest']:
                    time.sleep(0.01)  # Réduire le délai d'attente
                    continue
                
                # Afficher la frame d'attente uniquement si la vidéo est terminée
                display_width, display_height = 400, 300
                wait_frame = np.zeros((display_height + 30, display_width, 3), dtype=np.uint8)
                title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
                color = colors['ouest']
                cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
                cv2.putText(title_bar, "OUEST: En attente...", (10, 20), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                cv2.putText(wait_frame[30:, :], "En attente de vidéo...", (80, 150), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                frame_with_title = np.vstack((title_bar, wait_frame[30:, :]))
                ret, buffer = cv2.imencode('.jpg', frame_with_title, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                time.sleep(0.05)
        except Exception as e:
            print(f"Erreur dans generate_frames_ouest: {e}")
            time.sleep(0.05)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_nord')
def video_feed_nord():
    return Response(generate_frames_nord(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_sud')
def video_feed_sud():
    return Response(generate_frames_sud(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_est')
def video_feed_est():
    return Response(generate_frames_est(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_ouest')
def video_feed_ouest():
    return Response(generate_frames_ouest(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_processing')
def start_processing():
    global processing_active, stop_thread
    if not processing_active:
        processing_active = True
        stop_thread = False
        threading.Thread(target=detection_thread, daemon=True).start()
        return jsonify({"status": "success", "message": "Traitement démarré"})
    return jsonify({"status": "error", "message": "Traitement déjà en cours"})

@app.route('/stop_processing')
def stop_processing():
    global stop_thread
    stop_thread = True
    return jsonify({"status": "success", "message": "Traitement arrêté"})

@app.route('/reset_detection')
def reset_detection():
    global objets_detectes, donnees_csv, compteurs_temps_reel, vitesses_moyennes
    
    
    for direction in objets_detectes:
        objets_detectes[direction] = set()
        compteurs_temps_reel[direction] = 0
        vitesses_moyennes[direction] = 0
    
    
    donnees_csv = []
    if os.path.exists(csv_file):
        pd.DataFrame(donnees_csv).to_csv(csv_file, index=False)
    
    
    for direction in trackers:
        trackers[direction] = EuclideanDistTracker()
    
    return jsonify({"status": "success", "message": "Détections réinitialisées"})

@app.route('/get_stats')
def get_stats():
   
    stats = {
        'directions': {
            'nord': {
                'total': len(objets_detectes['nord']),
                'actuel': compteurs_temps_reel['nord'],
                'vitesse_moyenne': round(vitesses_moyennes['nord'], 1)
            },
            'sud': {
                'total': len(objets_detectes['sud']),
                'actuel': compteurs_temps_reel['sud'],
                'vitesse_moyenne': round(vitesses_moyennes['sud'], 1)
            },
            'est': {
                'total': len(objets_detectes['est']),
                'actuel': compteurs_temps_reel['est'],
                'vitesse_moyenne': round(vitesses_moyennes['est'], 1)
            },
            'ouest': {
                'total': len(objets_detectes['ouest']),
                'actuel': compteurs_temps_reel['ouest'],
                'vitesse_moyenne': round(vitesses_moyennes['ouest'], 1)
            }
        },
        'total': sum(len(objets_detectes[d]) for d in objets_detectes),
        'processing_active': processing_active,
    }
    
    
    traffic_state = traffic_manager.get_traffic_state()
    for direction in traffic_state['detection']:
        if 'objects' in traffic_state['detection'][direction] and isinstance(traffic_state['detection'][direction]['objects'], set):
            traffic_state['detection'][direction]['objects'] = list(traffic_state['detection'][direction]['objects'])
    
    stats['traffic_state'] = traffic_state
    
    return jsonify(stats)

@app.route('/get_traffic_state')
def get_traffic_state():
    return jsonify(traffic_manager.get_traffic_state())


@app.route('/start_video/<direction>')
def start_video(direction):
    global video_ended
    if direction in videos:
        video_ended[direction] = False
        
        thread = threading.Thread(
            target=process_video, 
            args=(direction, videos[direction], trackers[direction])
        )
        thread.daemon = True
        thread.start()
        return jsonify({"status": "success", "message": f"Vidéo {direction} démarrée"})
    return jsonify({"status": "error", "message": "Direction invalide"})

@app.route('/stop_video/<direction>')
def stop_video(direction):
    global video_ended
    if direction in videos:
        video_ended[direction] = True
        
        display_width, display_height = 400, 300
        color = colors[direction]
        final_frame = np.zeros((display_height + 30, display_width, 3), dtype=np.uint8)
        title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
        cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
        
        title_text = f"{direction.upper()}: {len(objets_detectes[direction])} objets"
        cv2.putText(title_bar, title_text, (10, 20), 
                  cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        cv2.putText(final_frame[30:, :], "Vidéo arrêtée", (int(display_width/2) - 80, int(display_height/2)), 
                  cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        frame_with_title = np.vstack((title_bar, final_frame[30:, :]))
        frames_global[direction] = frame_with_title
        
        return jsonify({"status": "success", "message": f"Vidéo {direction} arrêtée"})
    return jsonify({"status": "error", "message": "Direction invalide"})

@app.route('/check_videos')
def check_videos():
    return jsonify({
        'nord': not video_ended['nord'],
        'sud': not video_ended['sud'],
        'est': not video_ended['est'],
        'ouest': not video_ended['ouest']
    })

@app.route('/set_manual_mode/<enabled>')
def set_manual_mode(enabled):
    """
    Active ou désactive le mode manuel de gestion des feux
    """
    is_enabled = enabled.lower() == 'true'
    result = traffic_manager.set_manual_mode(is_enabled)
    return jsonify(result)

@app.route('/set_light_state/<direction>/<state>')
def set_light_state(direction, state):
    """
    Définit manuellement l'état d'un feu de circulation
    """
    result = traffic_manager.set_light_state(direction, state)
    return jsonify(result)

@app.route('/start_simulation/<scenario>')
def start_simulation(scenario):
    """
    Démarre une simulation de trafic
    """
    speed = request.args.get('speed', 1.0, type=float)
    result = traffic_manager.start_simulation(scenario, speed)
    return jsonify(result)

@app.route('/stop_simulation')
def stop_simulation():
    """
    Arrête la simulation en cours
    """
    result = traffic_manager.stop_simulation()
    return jsonify(result)

@app.route('/get_historical_data')
def get_historical_data():
    """
    Retourne les données historiques pour l'analyse
    """
    duration = request.args.get('duration', '1h')  
    
    
    now = datetime.now()
    if duration == '1h':
        cutoff = now - timedelta(hours=1)
    elif duration == '3h':
        cutoff = now - timedelta(hours=3)
    elif duration == '24h':
        cutoff = now - timedelta(hours=24)
    elif duration == 'all':
        cutoff = datetime.min  
    else:
        cutoff = now - timedelta(hours=1)  
    
    
    filtered_data = {}
    for direction in ['nord', 'sud', 'est', 'ouest']:
        filtered_data[direction] = [
            entry for entry in historical_data[direction]
            if entry['timestamp'] >= cutoff.timestamp()
        ]
    
    return jsonify(filtered_data)

@app.route('/export_data/<format>')
def export_data(format):
    """
    Exporte les données de trafic dans le format spécifié
    format: 'csv' ou 'json'
    """
    if format == 'csv':
        
        all_data = []
        for direction in ['nord', 'sud', 'est', 'ouest']:
            for entry in historical_data[direction]:
                entry_copy = entry.copy()
                entry_copy['direction'] = direction
                entry_copy['timestamp'] = datetime.fromtimestamp(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                all_data.append(entry_copy)
        
        df = pd.DataFrame(all_data)
        
        # Enregistrement  dans le  CSV file
        export_file = "static/export_data.csv"
        df.to_csv(export_file, index=False)
        
        return jsonify({'success': True, 'file': export_file})
    
    elif format == 'json':
        
        export_data = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data': historical_data
        }
        
       
        export_file = "static/export_data.json"
        with open(export_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return jsonify({'success': True, 'file': export_file})
    
    else:
        return jsonify({'success': False, 'error': 'Format non supporté'})

@app.route('/get_app_state')
def get_app_state():
    """
    Retourne l'état actuel de l'application incluant le statut de traitement,
    les statistiques de détection et l'état du trafic
    """
    
    for direction in ['nord', 'sud', 'est', 'ouest']:
       
        traffic_manager.update_detection(
            direction, 
            len(objets_detectes[direction]),  
            objets_detectes[direction], 
            vitesses_moyennes[direction]
        )
    
    
    traffic_manager._update_scoot()
    

    traffic_state = traffic_manager.get_traffic_state()
    for direction in traffic_state['detection']:
        if 'objects' in traffic_state['detection'][direction] and isinstance(traffic_state['detection'][direction]['objects'], set):
            traffic_state['detection'][direction]['objects'] = list(traffic_state['detection'][direction]['objects'])
    
    state = {
        'processing_active': processing_active,
        'videos_active': {
            'nord': not video_ended['nord'],
            'sud': not video_ended['sud'],
            'est': not video_ended['est'],
            'ouest': not video_ended['ouest']
        },
        'detection_stats': {
            'nord': {
                'total': len(objets_detectes['nord']),
                'actuel': compteurs_temps_reel['nord'],
                'vitesse_moyenne': round(vitesses_moyennes['nord'], 1)
            },
            'sud': {
                'total': len(objets_detectes['sud']),
                'actuel': compteurs_temps_reel['sud'],
                'vitesse_moyenne': round(vitesses_moyennes['sud'], 1)
            },
            'est': {
                'total': len(objets_detectes['est']),
                'actuel': compteurs_temps_reel['est'],
                'vitesse_moyenne': round(vitesses_moyennes['est'], 1)
            },
            'ouest': {
                'total': len(objets_detectes['ouest']),
                'actuel': compteurs_temps_reel['ouest'],
                'vitesse_moyenne': round(vitesses_moyennes['ouest'], 1)
            }
        },
        'traffic_state': traffic_state
    }
    
    return jsonify(state)



def auto_start_processing():
    """
    Initialise et démarre automatiquement le traitement au démarrage de l'application
    """
    
    global objets_detectes, compteurs_temps_reel, vitesses_moyennes, video_ended, processing_active, stop_thread, caps
    
   
    for direction in caps:
        if caps[direction] is not None:
            try:
                caps[direction].release()
            except:
                pass
        caps[direction] = None
    
    
    traffic_manager.start()
    
    
    for direction in ['nord', 'sud', 'est', 'ouest']:
        objets_detectes[direction] = set()
        compteurs_temps_reel[direction] = 0
        vitesses_moyennes[direction] = 0
    
    
    for direction in video_ended:
        video_ended[direction] = True
    
    
    processing_active = True
    stop_thread = False
    
    
    thread = threading.Thread(target=detection_thread, daemon=True)
    thread.start()
    
    
    try:
        print("Initialisation du système de régulation des feux")
        traffic_manager._update_scoot()
        print("Système de régulation des feux initialisé avec succès")
    except Exception as e:
        print(f"Erreur lors de l'initialisation du système de régulation: {e}")


@app.route('/init')
def initialize_app():
    auto_start_processing()
    return jsonify({"status": "success", "message": "Application initialisée"})

@app.route('/restart', methods=['POST'])
def restart_app():
    """
    Route pour redémarrer proprement l'application en cas de problème
    """
    try:
        global processing_active, stop_thread
        
        
        stop_thread = True
        processing_active = False
        
        
        for direction in caps:
            if caps[direction] is not None:
                try:
                    caps[direction].release()
                    caps[direction] = None
                except Exception as e:
                    print(f"Erreur lors de la libération de la capture {direction}: {e}")
        
       
        for direction in frame_buffers:
            while not frame_buffers[direction].empty():
                try:
                    frame_buffers[direction].get(block=False)
                except:
                    pass
        
      
        for direction in ['nord', 'sud', 'est', 'ouest']:
            objets_detectes[direction] = set()
            compteurs_temps_reel[direction] = 0
            vitesses_moyennes[direction] = 0
            video_ended[direction] = True
        
        
        traffic_manager.stop()
        traffic_manager.start()
        
       
        processing_active = True
        stop_thread = False
        threading.Thread(target=detection_thread, daemon=True).start()
        
        return jsonify({
            'status': 'success',
            'message': 'Application redémarrée avec succès',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'Erreur lors du redémarrage de l\'application',
            'timestamp': datetime.now().isoformat()
        })

@app.route('/health')
def health_check():
    """
    Route de diagnostic pour vérifier l'état de l'application et faciliter le dépannage
    """
    try:
        # Statut des vidéos
        video_status = {
            'nord': not video_ended['nord'],
            'sud': not video_ended['sud'],
            'est': not video_ended['est'],
            'ouest': not video_ended['ouest']
        }
        
        # Statut des files d'attente
        queue_status = {
            'nord': {
                'size': frame_buffers['nord'].qsize(),
                'maxsize': frame_buffers['nord'].maxsize,
                'empty': frame_buffers['nord'].empty(),
                'full': frame_buffers['nord'].full()
            },
            'sud': {
                'size': frame_buffers['sud'].qsize(),
                'maxsize': frame_buffers['sud'].maxsize,
                'empty': frame_buffers['sud'].empty(),
                'full': frame_buffers['sud'].full()
            },
            'est': {
                'size': frame_buffers['est'].qsize(),
                'maxsize': frame_buffers['est'].maxsize,
                'empty': frame_buffers['est'].empty(),
                'full': frame_buffers['est'].full()
            },
            'ouest': {
                'size': frame_buffers['ouest'].qsize(),
                'maxsize': frame_buffers['ouest'].maxsize,
                'empty': frame_buffers['ouest'].empty(),
                'full': frame_buffers['ouest'].full()
            }
        }
        
        # Vérification des vidéos
        video_exists = {}
        for direction, path in videos.items():
            video_exists[direction] = os.path.isfile(path)
        
        
        app_status = {
            'processing_active': processing_active,
            'stop_thread': stop_thread,
            'traffic_manager_running': traffic_manager.running
        }
        
       
        health_data = {
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'videos': video_status,
            'queues': queue_status,
            'video_files': video_exists,
            'app_status': app_status,
            'object_counts': {
                'nord': len(objets_detectes['nord']),
                'sud': len(objets_detectes['sud']),
                'est': len(objets_detectes['est']),
                'ouest': len(objets_detectes['ouest'])
            }
        }
        
        return jsonify(health_data)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

def stop_all_videos_and_regulate():
    """
    Arrête toutes les vidéos en cours et utilise les comptages actuels
    pour optimiser la régulation des feux.
    """
    global video_ended, frames_global, objets_detectes, vitesses_moyennes, caps
    
    print("Synchronisation des arrêts de vidéo pour optimiser la régulation des feux")
    
    # Marquer toutes les vidéos comme terminées
    for direction in video_ended:
        video_ended[direction] = True
    
    # Libérer les ressources des captures vidéo
    for direction in caps:
        if caps[direction] is not None:
            try:
                caps[direction].release()
                caps[direction] = None
            except:
                pass
    
    
    for direction in ['nord', 'sud', 'est', 'ouest']:
        color = colors[direction]
        
        display_width, display_height = 400, 300
        final_frame = np.zeros((display_height + 30, display_width, 3), dtype=np.uint8)
        title_bar = np.zeros((30, display_width, 3), dtype=np.uint8)
        cv2.rectangle(title_bar, (0, 0), (display_width, 30), color, -1)
        
        title_text = f"{direction.upper()}: {len(objets_detectes[direction])} objets"
        cv2.putText(title_bar, title_text, (10, 20), 
                  cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        cv2.putText(final_frame[30:, :], "Synchronisation terminée", (int(display_width/2) - 120, int(display_height/2)), 
                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        frame_with_title = np.vstack((title_bar, final_frame[30:, :]))
        frames_global[direction] = frame_with_title
    
   
    print("Envoi des données de comptage au système de régulation")
    print("Comptages finaux utilisés pour la régulation:")
    
    for direction in ['nord', 'sud', 'est', 'ouest']:
        
        count = len(objets_detectes[direction])
        print(f"{direction.capitalize()}: {count} objets")
        
        
        traffic_manager.update_detection(
            direction,
            count,  
            objets_detectes[direction],
            vitesses_moyennes[direction]
        )
    
   
    traffic_manager._update_scoot()
    print("Le système de régulation des feux a été mis à jour avec les comptages finaux")

if __name__ == '__main__':
    
    from threading import Timer
    import logging
    
    
    cv2.setNumThreads(0)
    
   
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('traffic_app.log')
        ]
    )
    logger = logging.getLogger(__name__)
    
    logger.info("Démarrage de l'application de régulation de trafic")
    
    
    for direction, video_path in videos.items():
        if not os.path.isfile(video_path):
            logger.warning(f"Le fichier vidéo pour la direction {direction} n'existe pas: {video_path}")
            
            alt_path = os.path.join("static", os.path.basename(video_path))
            if os.path.isfile(alt_path):
                videos[direction] = alt_path
                logger.info(f"Chemin vidéo corrigé pour {direction}: {alt_path}")
            else:
                logger.error(f"Vidéo introuvable pour {direction}. Vérifiez que les fichiers existent.")
    
    
    def open_browser():
        import requests
        try:
            logger.info("Initialisation automatique de l'application...")
            requests.get('http://127.0.0.1:5000/init', timeout=5)
            logger.info("Application initialisée avec succès.")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation automatique: {e}")
    
    # Utiliser un délai plus long pour s'assurer que le serveur est prêt
    Timer(2.0, open_browser).start()
    
    
    logger.info("Démarrage du serveur Flask sur le port 5000...")
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)