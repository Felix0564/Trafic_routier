# code de scoot sans interface 
import random
import time
class FeuTricolore:
    def __init__(self, nom):
        self.nom = nom
        self.etat = "rouge"
        self.temps_vert = 10
        self.temps_orange = 3
        self.temps_rouge = 10
        self.timer = 0

    def changer_etat(self):
        if self.etat == "rouge":
            self.etat = "vert"
            self.timer = self.temps_vert
        elif self.etat == "vert":
            self.etat = "orange"
            self.timer = self.temps_orange
        elif self.etat == "orange":
            self.etat = "rouge"
            self.timer = self.temps_rouge

    def decrementer_timer(self):
        self.timer -= 1
        if self.timer <= 0:
            self.changer_etat()

    def __str__(self):
        return f"{self.nom} : {self.etat} ({self.timer}s)"


class Capteur:
    def __init__(self, nom):
        self.nom = nom
        self.file_attente = 0

    def detecter_vehicules(self):
        # simulation aléatoire
        self.file_attente = random.randint(0, 20)

    def __str__(self):
        return f"{self.nom} : {self.file_attente} véhicules"


class Intersection:
    def __init__(self, nom, four_way=False):
        self.nom = nom
        self.four_way = four_way
        
        if four_way:
            # Mode carrefour à quatre feux indépendants
            self.feux = {
                "Nord": FeuTricolore("Nord"),
                "Sud": FeuTricolore("Sud"),
                "Est": FeuTricolore("Est"),
                "Ouest": FeuTricolore("Ouest")
            }
            
            # Initialiser les états des feux pour éviter les collisions
            self.feux["Nord"].etat = "vert"
            self.feux["Nord"].timer = self.feux["Nord"].temps_vert
            self.feux["Sud"].etat = "rouge"
            self.feux["Sud"].timer = self.feux["Sud"].temps_rouge
            self.feux["Est"].etat = "rouge"
            self.feux["Est"].timer = self.feux["Est"].temps_rouge
            self.feux["Ouest"].etat = "rouge"
            self.feux["Ouest"].timer = self.feux["Ouest"].temps_rouge
            
            # Définir l'ordre de passage
            self.sequence = ["Nord", "Est", "Sud", "Ouest"]
            self.current_index = 0
        else:
            # Mode carrefour classique à deux groupes de feux
            self.feux = {
                "Nord-Sud": FeuTricolore("Nord-Sud"),
                "Est-Ouest": FeuTricolore("Est-Ouest")
            }
            
            # Initialiser les états des feux
            self.feux["Nord-Sud"].etat = "vert"
            self.feux["Nord-Sud"].timer = self.feux["Nord-Sud"].temps_vert
            self.feux["Est-Ouest"].etat = "rouge"
            self.feux["Est-Ouest"].timer = self.feux["Est-Ouest"].temps_rouge
        
        self.capteurs = {
            "Nord": Capteur("Nord"),
            "Sud": Capteur("Sud"),
            "Est": Capteur("Est"),
            "Ouest": Capteur("Ouest")
        }

    def mettre_a_jour(self):
        if self.four_way:
            
            # Mettre à jour tous les feux
            for direction, feu in self.feux.items():
                # Décrémenter le timer seulement si le feu est actif
                if feu.timer > 0:
                    feu.decrementer_timer()
                # Sinon, passer à l'état suivant si nécessaire
                else:
                    feu.changer_etat()
            
            # Assurer qu'il y a toujours au moins un feu vert actif
            has_green = False
            for feu in self.feux.values():
                if feu.etat == "vert":
                    has_green = True
                    break
            
            # Si aucun feu n'est vert, forcer le feu suivant à passer au vert
            if not has_green:
                self.current_index = (self.current_index + 1) % len(self.sequence)
                next_direction = self.sequence[self.current_index]
                self.feux[next_direction].etat = "vert"
                self.feux[next_direction].timer = self.feux[next_direction].temps_vert
        else:
            # Mode carrefour classique
            for feu in self.feux.values():
                feu.decrementer_timer()

    def detecter_traffic(self):
        for capteur in self.capteurs.values():
            capteur.detecter_vehicules()

    def __str__(self):
        etats = "\n".join(str(feu) for feu in self.feux.values())
        capteurs = "\n".join(str(c) for c in self.capteurs.values())
        return f"--- {self.nom} ---\nFeux:\n{etats}\nCapteurs:\n{capteurs}"


class SCOOTController:
    def __init__(self, intersections):
        self.intersections = intersections

    def ajuster_cycles(self):
        for intersection in self.intersections:
            intersection.detecter_traffic()
            
            if intersection.four_way:
                # Mode carrefour à quatre feux indépendants
                nord_count = intersection.capteurs["Nord"].file_attente
                sud_count = intersection.capteurs["Sud"].file_attente
                est_count = intersection.capteurs["Est"].file_attente
                ouest_count = intersection.capteurs["Ouest"].file_attente
                
                # Ajustement des temps en fonction du trafic
                intersection.feux["Nord"].temps_vert = max(5, min(30, 10 + nord_count // 2))
                intersection.feux["Sud"].temps_vert = max(5, min(30, 10 + sud_count // 2))
                intersection.feux["Est"].temps_vert = max(5, min(30, 10 + est_count // 2))
                intersection.feux["Ouest"].temps_vert = max(5, min(30, 10 + ouest_count // 2))
            else:
                # Mode carrefour classique
                total_NS = intersection.capteurs["Nord"].file_attente + intersection.capteurs["Sud"].file_attente
                total_EO = intersection.capteurs["Est"].file_attente + intersection.capteurs["Ouest"].file_attente

                if total_NS > total_EO:
                    intersection.feux["Nord-Sud"].temps_vert = 12
                    intersection.feux["Est-Ouest"].temps_vert = 8
                else:
                    intersection.feux["Nord-Sud"].temps_vert = 8
                    intersection.feux["Est-Ouest"].temps_vert = 12


"""
# Simulation
intersection = Intersection("Carrefour A")
scoot = SCOOTController([intersection])

for t in range(30):
    print(f"\n--- Temps : {t} ---")
    scoot.ajuster_cycles()
    intersection.mettre_a_jour()
    print(intersection)
    time.sleep(0.5)

def test_traffic_light_control():
    # Test de contrôle des feux de circulation
    intersection = Intersection("Carrefour Test")
    scoot = SCOOTController([intersection])
    
    print("Test de contrôle des feux")
    for t in range(10):
        print(f"\n--- Temps : {t} ---")
        scoot.ajuster_cycles()
        intersection.mettre_a_jour()
        print(intersection)
        time.sleep(0.5)

def debug_traffic_flow():
    # Fonction de débogage du flux de trafic
    intersection = Intersection("Carrefour Debug")
    scoot = SCOOTController([intersection])
    
    print("Débogage du flux de trafic")
    for t in range(20):
        print(f"\n--- Temps : {t} ---")
        intersection.detecter_traffic()
        scoot.ajuster_cycles()
        intersection.mettre_a_jour()
        print(intersection)
        time.sleep(0.5)
"""
