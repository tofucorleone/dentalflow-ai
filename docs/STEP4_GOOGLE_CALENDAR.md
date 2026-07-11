# Étape 4 — Google Calendar

Cette étape synchronise les rendez-vous de l’API avec Google Calendar.

## Fonctionnalités

- création d’un événement Google lors de `POST /appointments`;
- sauvegarde de `google_calendar_event_id`;
- déplacement via `PATCH /appointments/{id}/reschedule`;
- annulation via `DELETE /appointments/{id}`;
- rollback PostgreSQL si Google Calendar échoue pendant la création.

## 1. Google Cloud

1. Créez ou choisissez un projet Google Cloud.
2. Activez **Google Calendar API**.
3. Créez un compte de service.
4. Créez une clé JSON.
5. Enregistrez-la sous :

```text
secrets/google/service-account.json
```

6. Dans Google Calendar, partagez le calendrier avec l’adresse `client_email`
du fichier JSON et donnez-lui le droit de modifier les événements.

Le compte de service et sa clé privée doivent être protégés. Pour une plateforme
SaaS publique, une connexion OAuth propre à chaque clinique remplacera cette
méthode lors d’une étape ultérieure.

## 2. Installer les fichiers

```bash
cd ~/ai-agency/dentalflow-ai
unzip -o ~/Downloads/dentalflow-ai-step4-google-calendar.zip
```

Ajoutez dans `.env` :

```env
GOOGLE_CALENDAR_ENABLED=true
GOOGLE_SERVICE_ACCOUNT_FILE=/run/secrets/google-service-account.json
```

## 3. Configurer l’ID du calendrier

Pour le praticien de démonstration :

```bash
docker exec -it dentalflow-postgres   psql -U dentalflow -d dentalflow   -c "
UPDATE practitioners
SET google_calendar_id =
'55885b38b8b40f9fbc6411498581aa9eded7bdc19957be9f1dcbcc66ffcc7600@group.calendar.google.com'
WHERE full_name = 'Dr Ahmed';
"
```

## 4. Reconstruire

```bash
docker compose up -d --build --force-recreate api
curl http://localhost:8001/health
```

## 5. Créer un rendez-vous synchronisé

Utilisez un créneau libre :

```bash
curl -X POST   -H "Content-Type: application/json"   -H "X-Clinic-Id: $CLINIC_ID"   http://localhost:8001/appointments   -d "{
    \"patient_id\": \"$PATIENT_ID\",
    \"treatment_id\": \"$TREATMENT_ID\",
    \"channel\": \"dashboard\",
    \"status\": \"confirmed\",
    \"start_at\": \"2026-07-20T15:00:00+01:00\"
  }"
```

La réponse doit contenir :

- `google_calendar_event_id`;
- `google_calendar_html_link`.

## 6. Déplacer

```bash
APPOINTMENT_ID="ID_RETOURNE"

curl -X PATCH   -H "Content-Type: application/json"   -H "X-Clinic-Id: $CLINIC_ID"   http://localhost:8001/appointments/$APPOINTMENT_ID/reschedule   -d '{
    "start_at": "2026-07-20T16:00:00+01:00"
  }'
```

## 7. Annuler

```bash
curl -X DELETE   -H "X-Clinic-Id: $CLINIC_ID"   http://localhost:8001/appointments/$APPOINTMENT_ID
```
