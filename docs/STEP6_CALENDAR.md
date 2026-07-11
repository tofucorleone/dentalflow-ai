# Étape 6 — Calendrier interactif

## Fonctions

- vue semaine ;
- navigation semaine précédente/suivante ;
- glisser-déposer par pas de 15 minutes ;
- vérification backend des horaires, conflits et congés ;
- synchronisation PostgreSQL et Google Calendar ;
- annulation depuis le calendrier.

## Installation

```bash
cd ~/ai-agency/dentalflow-ai
unzip -o ~/Downloads/dentalflow-ai-step6-calendar.zip
chmod +x install-step6.sh
./install-step6.sh
docker compose up -d --build dashboard
```

Ouvrez :

```text
http://localhost:3000/appointments
```

## Test

1. Ouvrez la semaine qui contient un rendez-vous.
2. Glissez le rendez-vous vers un créneau libre.
3. Vérifiez que le déplacement apparaît aussi dans Google Calendar.
4. Essayez un créneau occupé : le backend doit refuser le déplacement.
5. Cliquez sur l’icône corbeille pour annuler.
