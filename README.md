# Traffic Simulation Application


## Description
Cette application est un système de monitoring et de régulation intelligente du trafic routier. Elle utilise la vision par ordinateur pour analyser des flux vidéos de carrefours en temps réel, compter les véhicules et ajuster dynamiquement la durée des feux de circulation pour réduire les embouteillages.

## Fonctionnalités Clés
Détection Multi-objets : Identification en temps réel des voitures, camions, bus et motos.

Tracking (Suivi) : Attribution d'identifiants uniques aux véhicules pour un comptage précis.

Gestion Adaptative des Feux : Logique de contrôle qui donne la priorité aux voies les plus encombrées.

Interface Dashboard : Visualisation en direct du flux vidéo traité et des statistiques de trafic via une interface web.

## Architecture du Projet
L'application est structurée de manière modulaire :

app.py : Point d'entrée. Gère le serveur Flask, le streaming vidéo et les routes de l'interface utilisateur.

tracker.py : Moteur d'IA. Implémente le suivi d'objets pour maintenir la continuité de détection entre les frames.

traffic_manager.py : Cerveau logique. Analyse les données du tracker pour décider de l'état des feux (Rouge/Vert) selon des seuils de densité.

static/ & templates/ : Ressources frontend (CSS/JS) et vues HTML pour le tableau de bord.


## Installation

1. Python 3.8 ou supérieur est installé
2. Installez les dépendances :
```
pip install -r requirements.txt
```


python app.py
```

L'application sera accessible à l'adresse : http://localhost:5000

