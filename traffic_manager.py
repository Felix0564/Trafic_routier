from scoot import SCOOTController, Intersection, FeuTricolore
import threading
import time
import random
import math

class TrafficManager:
    def __init__(self):
        self.intersection = Intersection("Carrefour Principal", four_way=True)
        self.scoot = SCOOTController([self.intersection])
        self.detection_data = {
            'nord': {'count': 0, 'speed_avg': 0, 'objects': set()},
            'sud': {'count': 0, 'speed_avg': 0, 'objects': set()},
            'est': {'count': 0, 'speed_avg': 0, 'objects': set()},
            'ouest': {'count': 0, 'speed_avg': 0, 'objects': set()}
        }
        self.running = False
        self.thread = None
        # Add manual override mode
        self.manual_mode = False
        self.manual_override = {
            'nord': None,
            'sud': None,
            'est': None,
            'ouest': None
        }
       
        self.simulation_mode = False
        self.simulation_scenario = "normal"
        self.simulation_thread = None
        self.simulation_speed = 1.0  

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_traffic_control)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        self.stop_simulation()

    def _run_traffic_control(self):
        while self.running:
            if not self.manual_mode:
                self._update_scoot()
                self.intersection.mettre_a_jour()
            else:
                
                for direction, state in self.manual_override.items():
                    if state is not None:
                        dir_key = direction.capitalize()
                        if state != self.intersection.feux[dir_key].etat:
                            
                            self.intersection.feux[dir_key].etat = state
                            if state == "vert":
                                self.intersection.feux[dir_key].timer = self.intersection.feux[dir_key].temps_vert
                            elif state == "orange":
                                self.intersection.feux[dir_key].timer = self.intersection.feux[dir_key].temps_orange
                            elif state == "rouge":
                                self.intersection.feux[dir_key].timer = self.intersection.feux[dir_key].temps_rouge
            
            time.sleep(1)  

    def update_detection(self, direction, objects_count, current_objects, speed_avg):
        """
        Mise à jour des données de détection pour une direction
        """
      
        if self.simulation_mode:
            return
            
        
        print(f"Mise à jour des données de détection pour {direction}: {objects_count} objets")
            
        self.detection_data[direction]['count'] = objects_count
        self.detection_data[direction]['objects'] = current_objects
        self.detection_data[direction]['speed_avg'] = speed_avg

        # Mise à jour immédiate du capteur SCOOT correspondant
        self.intersection.capteurs[direction.capitalize()].file_attente = objects_count
        
        # Forcer une mise à jour immédiate de la logique de régulation
        # si les données ont significativement changé
        needs_update = False
        if direction == 'nord' and objects_count > 0:
            needs_update = True
        elif direction == 'sud' and objects_count > 0:
            needs_update = True
        elif direction == 'est' and objects_count > 0:
            needs_update = True
        elif direction == 'ouest' and objects_count > 0:
            needs_update = True
            
        if needs_update and not self.manual_mode:
            self._update_scoot()

    def _update_scoot(self):
        """
        Mise à jour du contrôleur SCOOT basée sur les données de détection
        """
        # Récupérer les comptages pour chaque direction
        nord_count = self.detection_data['nord']['count']
        sud_count = self.detection_data['sud']['count']
        est_count = self.detection_data['est']['count']
        ouest_count = self.detection_data['ouest']['count']
        
        # Vérifier que les données sont réellement mises à jour
        print(f"Données actuelles de comptage pour la régulation:")
        print(f"- Nord: {nord_count} objets")
        print(f"- Sud: {sud_count} objets")
        print(f"- Est: {est_count} objets")
        print(f"- Ouest: {ouest_count} objets")
        
        # Calculer les densités relatives
        total_count = max(1, nord_count + sud_count + est_count + ouest_count)
        
        # Éviter les divisions par zéro et garantir une équité de base
        if total_count == 0:
            nord_ratio = sud_ratio = est_ratio = ouest_ratio = 0.25
        else:
            nord_ratio = nord_count / total_count
            sud_ratio = sud_count / total_count
            est_ratio = est_count / total_count
            ouest_ratio = ouest_count / total_count
        
        # Déterminer les temps de feu vert pour chaque direction
        base_time = 10  # Temps de base en secondes
        min_time = 5    # Temps minimum en secondes
        max_time = 30   # Temps maximum en secondes
        
        # Facteur d'ajustement pour une meilleure réactivité aux densités
        adjustment_factor = 3.0
        
        # Formule améliorée pour le temps de feu vert
        nord_time = min(max(min_time, base_time * (1 + nord_ratio * adjustment_factor)), max_time)
        sud_time = min(max(min_time, base_time * (1 + sud_ratio * adjustment_factor)), max_time)
        est_time = min(max(min_time, base_time * (1 + est_ratio * adjustment_factor)), max_time)
        ouest_time = min(max(min_time, base_time * (1 + ouest_ratio * adjustment_factor)), max_time)
        
        # Imprimer des informations sur la mise à jour des temps pour le débogage
        print(f"Mise à jour des temps de feux:")
        print(f"Nord: {nord_count} objets -> {nord_time:.1f}s")
        print(f"Sud: {sud_count} objets -> {sud_time:.1f}s")
        print(f"Est: {est_count} objets -> {est_time:.1f}s")
        print(f"Ouest: {ouest_count} objets -> {ouest_time:.1f}s")
        
        # Mettre à jour les temps des feux
        self.intersection.feux["Nord"].temps_vert = int(nord_time)
        self.intersection.feux["Sud"].temps_vert = int(sud_time)
        self.intersection.feux["Est"].temps_vert = int(est_time)
        self.intersection.feux["Ouest"].temps_vert = int(ouest_time)

    def get_traffic_state(self):
        """
        Retourne l'état actuel du trafic
        """
        return {
            'feux': {
                'nord': {
                    'etat': self.intersection.feux["Nord"].etat,
                    'timer': self.intersection.feux["Nord"].timer,
                    'temps_vert': self.intersection.feux["Nord"].temps_vert
                },
                'sud': {
                    'etat': self.intersection.feux["Sud"].etat,
                    'timer': self.intersection.feux["Sud"].timer,
                    'temps_vert': self.intersection.feux["Sud"].temps_vert
                },
                'est': {
                    'etat': self.intersection.feux["Est"].etat,
                    'timer': self.intersection.feux["Est"].timer,
                    'temps_vert': self.intersection.feux["Est"].temps_vert
                },
                'ouest': {
                    'etat': self.intersection.feux["Ouest"].etat,
                    'timer': self.intersection.feux["Ouest"].timer,
                    'temps_vert': self.intersection.feux["Ouest"].temps_vert
                }
            },
            'detection': self.detection_data,
            'manual_mode': self.manual_mode,
            'simulation': {
                'active': self.simulation_mode,
                'scenario': self.simulation_scenario,
                'speed': self.simulation_speed
            }
        }
        
    def set_manual_mode(self, enabled):
        """
        Active ou désactive le mode manuel
        """
        
        if enabled and self.simulation_mode:
            return {'success': False, 'error': 'Désactivez le mode simulation avant d\'activer le mode manuel'}
            
        self.manual_mode = enabled
        if not enabled:
            
            self.manual_override = {
                'nord': None,
                'sud': None,
                'est': None,
                'ouest': None
            }
        return {'success': True, 'manual_mode': self.manual_mode}
    
    def set_light_state(self, direction, state):
        """
        Définit manuellement l'état d'un feu de circulation
        direction: 'nord', 'sud', 'est', 'ouest'
        state: 'vert', 'orange', 'rouge'
        """
        if direction not in ['nord', 'sud', 'est', 'ouest']:
            return {'success': False, 'error': 'Direction invalide'}
            
        if state not in ['vert', 'orange', 'rouge']:
            return {'success': False, 'error': 'État invalide'}
            
        self.manual_override[direction] = state
        return {'success': True, 'direction': direction, 'state': state}
    
    def start_simulation(self, scenario, speed=1.0):
        """
        Démarre une simulation de trafic selon un scénario prédéfini
        scenario: 'normal', 'rush_hour', 'night', 'north_congestion', 'east_west_heavy'
        speed: multiplicateur de vitesse de la simulation (1.0 = temps réel)
        """
        
        if self.manual_mode:
            return {'success': False, 'error': 'Désactivez le mode manuel avant de démarrer une simulation'}
            
        valid_scenarios = ['normal', 'rush_hour', 'night', 'north_congestion', 'east_west_heavy']
        if scenario not in valid_scenarios:
            return {'success': False, 'error': f'Scénario invalide. Options: {", ".join(valid_scenarios)}'}
            
        # Stop any existing simulation
        self.stop_simulation()
        
        
        self.simulation_mode = True
        self.simulation_scenario = scenario
        self.simulation_speed = max(0.1, min(5.0, speed))  
        
       
        self.simulation_thread = threading.Thread(target=self._run_simulation)
        self.simulation_thread.daemon = True
        self.simulation_thread.start()
        
        return {
            'success': True, 
            'simulation': {
                'active': self.simulation_mode,
                'scenario': self.simulation_scenario,
                'speed': self.simulation_speed
            }
        }
    
    def stop_simulation(self):
        """
        Arrête la simulation en cours
        """
        if self.simulation_mode:
            self.simulation_mode = False
            if self.simulation_thread:
                self.simulation_thread.join(timeout=2)
                self.simulation_thread = None
            
          
            for direction in self.detection_data:
                self.detection_data[direction]['count'] = 0
                self.detection_data[direction]['speed_avg'] = 0
                self.detection_data[direction]['objects'] = set()
                
            return {'success': True, 'message': 'Simulation arrêtée'}
        else:
            return {'success': True, 'message': 'Aucune simulation en cours'}
    
    def _run_simulation(self):
        """
        Exécute la simulation selon le scénario choisi
        """
        iteration = 0
        
        while self.simulation_mode and self.running:
            
            if self.simulation_scenario == 'normal':
                self._simulate_normal_traffic(iteration)
            elif self.simulation_scenario == 'rush_hour':
                self._simulate_rush_hour(iteration)
            elif self.simulation_scenario == 'night':
                self._simulate_night_traffic(iteration)
            elif self.simulation_scenario == 'north_congestion':
                self._simulate_north_congestion(iteration)
            elif self.simulation_scenario == 'east_west_heavy':
                self._simulate_east_west_heavy(iteration)
            
            
            for direction, data in self.detection_data.items():
                self.intersection.capteurs[direction.capitalize()].file_attente = data['count']
            
            
            sleep_time = 1.0 / self.simulation_speed
            time.sleep(sleep_time)
            iteration += 1
    
    def _simulate_normal_traffic(self, iteration):
        """
        Simule un trafic normal avec des variations légères
        """
        base_traffic = 5  
        variation = 3     
        
        
        cycle = (iteration % 60) / 60.0  
        
        self.detection_data['nord']['count'] = base_traffic + int(variation * (0.5 + 0.5 * math.sin(cycle * 2 * math.pi)))
        self.detection_data['sud']['count'] = base_traffic + int(variation * (0.5 + 0.5 * math.sin(cycle * 2 * math.pi + math.pi/2)))
        self.detection_data['est']['count'] = base_traffic + int(variation * (0.5 + 0.5 * math.sin(cycle * 2 * math.pi + math.pi)))
        self.detection_data['ouest']['count'] = base_traffic + int(variation * (0.5 + 0.5 * math.sin(cycle * 2 * math.pi + 3*math.pi/2)))
        
       
        for direction in self.detection_data:
            self.detection_data[direction]['speed_avg'] = 40 + random.randint(-5, 5)
            
            self.detection_data[direction]['objects'] = set(range(1, self.detection_data[direction]['count'] + 1))
    
    def _simulate_rush_hour(self, iteration):
        """
        Simule une heure de pointe avec beaucoup de trafic dans toutes les directions
        """
        base_traffic = 15  
        variation = 8      
        
        
        if (iteration % 120) < 60:  
            ns_multiplier = 1.5
            ew_multiplier = 1.0
        else:  
            ns_multiplier = 1.0
            ew_multiplier = 1.5
        
        cycle = (iteration % 60) / 60.0
        
        self.detection_data['nord']['count'] = int(ns_multiplier * (base_traffic + variation * (0.7 + 0.3 * math.sin(cycle * 2 * math.pi))))
        self.detection_data['sud']['count'] = int(ns_multiplier * (base_traffic + variation * (0.7 + 0.3 * math.sin(cycle * 2 * math.pi + math.pi/4))))
        self.detection_data['est']['count'] = int(ew_multiplier * (base_traffic + variation * (0.7 + 0.3 * math.sin(cycle * 2 * math.pi + math.pi/2))))
        self.detection_data['ouest']['count'] = int(ew_multiplier * (base_traffic + variation * (0.7 + 0.3 * math.sin(cycle * 2 * math.pi + 3*math.pi/4))))
        
        
        for direction in self.detection_data:
            count = self.detection_data[direction]['count']
            
            self.detection_data[direction]['speed_avg'] = max(10, 50 - count/2) + random.randint(-3, 3)
            self.detection_data[direction]['objects'] = set(range(1, count + 1))
    
    def _simulate_night_traffic(self, iteration):
        """
        Simule un trafic nocturne très léger
        """
        base_traffic = 1   
        max_variation = 2  
        
        
        for direction in self.detection_data:
            if random.random() < 0.3:  
                self.detection_data[direction]['count'] = random.randint(0, base_traffic + max_variation)
            else:
                self.detection_data[direction]['count'] = 0
                
           
            self.detection_data[direction]['speed_avg'] = 55 + random.randint(-10, 10)
            self.detection_data[direction]['objects'] = set(range(1, self.detection_data[direction]['count'] + 1))
    
    def _simulate_north_congestion(self, iteration):
        """
        Simule une congestion importante venant du nord
        """
        cycle = (iteration % 60) / 60.0
        
        
        self.detection_data['nord']['count'] = 15 + int(5 * math.sin(cycle * 2 * math.pi))
        
        self.detection_data['sud']['count'] = 5 + int(3 * math.sin(cycle * 2 * math.pi + math.pi/2))
        self.detection_data['est']['count'] = 3 + int(2 * math.sin(cycle * 2 * math.pi + math.pi))
        self.detection_data['ouest']['count'] = 4 + int(2 * math.sin(cycle * 2 * math.pi + 3*math.pi/2))
        
        
        self.detection_data['nord']['speed_avg'] = 15 + random.randint(-5, 5)
        
        for direction in ['sud', 'est', 'ouest']:
            self.detection_data[direction]['speed_avg'] = 40 + random.randint(-10, 10)
            
        
        for direction in self.detection_data:
            self.detection_data[direction]['objects'] = set(range(1, self.detection_data[direction]['count'] + 1))
    
    def _simulate_east_west_heavy(self, iteration):
        """
        Simule un trafic important sur l'axe est-ouest
        """
        cycle = (iteration % 60) / 60.0
        
        
        self.detection_data['nord']['count'] = 2 + int(2 * math.sin(cycle * 2 * math.pi))
        self.detection_data['sud']['count'] = 3 + int(2 * math.sin(cycle * 2 * math.pi + math.pi/4))
        
        self.detection_data['est']['count'] = 12 + int(6 * math.sin(cycle * 2 * math.pi + math.pi/2))
        self.detection_data['ouest']['count'] = 10 + int(5 * math.sin(cycle * 2 * math.pi + 3*math.pi/4))
        
    
        for direction in ['nord', 'sud']:
            self.detection_data[direction]['speed_avg'] = 45 + random.randint(-5, 5)
        for direction in ['est', 'ouest']:
            self.detection_data[direction]['speed_avg'] = 25 + random.randint(-10, 10)
            
        
        for direction in self.detection_data:
            self.detection_data[direction]['objects'] = set(range(1, self.detection_data[direction]['count'] + 1))
