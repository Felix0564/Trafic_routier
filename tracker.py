import math
import time
import numpy as np

class EuclideanDistTracker:
    def __init__(self):
        # Stockage des positions centrales des objets
        self.center_points = {}
        # Stockage des timestamps pour chaque objet
        self.time_points = {}
        # Stockage des vitesses
        self.speeds = {}
        # Compteur d'ID d'objets
        self.id_count = 0
        # Seuil de disparition
        self.disappear_threshold = 20
        # Dictionnaire pour suivre les frames depuis la dernière apparition
        self.frames_since_seen = {}
        # Échelle pixels vers mètres (à calibrer selon votre environnement)
        self.pixels_per_meter = 35  # exemple: 35 pixels = 1 mètre
        # Mémorisation des dernières positions pour filtrage
        self.position_history = {}
        # Nombre de positions à garder pour le lissage
        self.history_size = 5

    def calculate_speed(self, obj_id, new_center, current_time):
        if obj_id in self.center_points and obj_id in self.time_points:
            old_center = self.center_points[obj_id]
            old_time = self.time_points[obj_id]
            
            # Calcul de la distance en pixels
            distance_pixels = math.hypot(new_center[0] - old_center[0], 
                                      new_center[1] - old_center[1])
            
            # Conversion en mètres
            distance_meters = distance_pixels / self.pixels_per_meter
            
            # Calcul du temps écoulé en secondes
            time_diff = current_time - old_time
            
            if time_diff > 0:
                # Vitesse en mètres par seconde
                speed = distance_meters / time_diff
                # Conversion en km/h
                speed_kmh = speed * 3.6
                
                # Lissage de la vitesse avec moyenne mobile
                if obj_id in self.speeds:
                    # Lissage exponentiel
                    alpha = 0.3  # Facteur de lissage
                    self.speeds[obj_id] = (self.speeds[obj_id] * (1-alpha) + speed_kmh * alpha)
                    
                    # Limiter les valeurs aberrantes
                    if self.speeds[obj_id] > 120:  # Limite max en km/h
                        self.speeds[obj_id] = 120
                else:
                    self.speeds[obj_id] = min(speed_kmh, 120)
                
                return self.speeds[obj_id]
        return 0

    def update_position_history(self, obj_id, position):
        # Initialiser l'historique si nécessaire
        if obj_id not in self.position_history:
            self.position_history[obj_id] = []
        
        # Ajouter la nouvelle position
        self.position_history[obj_id].append(position)
        
        # Limiter la taille de l'historique
        if len(self.position_history[obj_id]) > self.history_size:
            self.position_history[obj_id].pop(0)
    
    def get_filtered_position(self, obj_id, current_position):
        # Si pas assez d'historique, retourner la position actuelle
        if obj_id not in self.position_history or len(self.position_history[obj_id]) < 3:
            return current_position
        
        # Sinon, calculer la position moyenne des dernières positions
        positions = self.position_history[obj_id] + [current_position]
        filtered_position = np.mean(positions, axis=0).astype(int)
        
        return filtered_position

    
    def update(self, objects_rect):
        objects_bbs_ids = []
        current_time = time.time()

        # Obtention du point central des nouveaux objets
        for rect in objects_rect:
            x, y, w, h = rect
            cx = (x + x + w) // 2
            cy = (y + y + h) // 2

            same_object_detected = False
            # Utiliser un seuil dynamique pour la distance en fonction de la taille de l'objet
            distance_threshold = max(25, min(w, h) // 2)
            
            for obj_id, pt in list(self.center_points.items()):
                dist = math.hypot(cx - pt[0], cy - pt[1])

                if dist < distance_threshold:
                    # Calcul de la vitesse
                    speed = self.calculate_speed(obj_id, (cx, cy), current_time)
                    
                    # Mettre à jour l'historique des positions
                    self.update_position_history(obj_id, (cx, cy))
                    
                    # Obtenir la position filtrée
                    filtered_pos = self.get_filtered_position(obj_id, (cx, cy))
                    cx_filtered, cy_filtered = filtered_pos
                    
                    self.center_points[obj_id] = (cx_filtered, cy_filtered)
                    self.time_points[obj_id] = current_time
                    objects_bbs_ids.append([x, y, w, h, obj_id, speed])
                    same_object_detected = True
                    self.frames_since_seen[obj_id] = 0
                    break

            if not same_object_detected:
                # Ne considérer que les objets d'une certaine taille
                min_size = 40  # Taille minimale (largeur ou hauteur) en pixels
                if w > min_size or h > min_size:
                    self.center_points[self.id_count] = (cx, cy)
                    self.time_points[self.id_count] = current_time
                    self.update_position_history(self.id_count, (cx, cy))
                    objects_bbs_ids.append([x, y, w, h, self.id_count, 0])
                    self.frames_since_seen[self.id_count] = 0
                    self.id_count += 1

        # Gestion des objets disparus
        for obj_id in list(self.frames_since_seen.keys()):
            if obj_id not in [item[4] for item in objects_bbs_ids]:
                self.frames_since_seen[obj_id] += 1
                if self.frames_since_seen[obj_id] > self.disappear_threshold:
                    del self.center_points[obj_id]
                    del self.time_points[obj_id]
                    if obj_id in self.speeds:
                        del self.speeds[obj_id]
                    if obj_id in self.position_history:
                        del self.position_history[obj_id]
                    del self.frames_since_seen[obj_id]

        return objects_bbs_ids
    