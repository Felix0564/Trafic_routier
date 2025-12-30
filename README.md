# Traffic Simulation Application

Cette application permet de simuler et monitorer la circulation et de réguler les feux de circulation à un carrefour.

## Correction du problème d'accessibilité

L'application rencontrait un problème d'erreur d'assertion dans OpenCV avec la gestion des threads, provoquant un crash de l'application. Ce problème a été résolu en :

1. Désactivant le multithreading interne d'OpenCV
2. Ajoutant des locks pour protéger l'accès aux ressources vidéo
3. Améliorant la gestion des erreurs
4. Optimisant la consommation de mémoire

## Installation

1. Assurez-vous que Python 3.8 ou supérieur est installé
2. Installez les dépendances :
```
pip install -r requirements.txt
```

## Démarrage de l'application

### Méthode recommandée
Pour démarrer l'application correctement, utilisez le script `start_app.bat` qui configure les variables d'environnement nécessaires pour éviter les problèmes de threading OpenCV :

```
start_app.bat
```

### Méthode alternative
Ou démarrez directement l'application Python :

```
python app.py
```

L'application sera accessible à l'adresse : http://localhost:5000

## Structure des fichiers

- `app.py`: Application principale Flask
- `tracker.py`: Contient le système de suivi d'objets
- `traffic_manager.py`: Gère la logique de contrôle des feux
- `static/`: Contient les fichiers vidéos et ressources
- `templates/`: Contient les templates HTML de l'application

