# DentalFlow AI v0.1

Version complète et cohérente du backend multi-clinique.

## Ce qui fonctionne

- PostgreSQL et Redis
- liste et modification des soins
- praticiens
- patients
- rendez-vous
- calcul automatique de la durée
- attribution automatique d’un praticien
- horaires d’ouverture
- congés
- détection des chevauchements
- endpoint de disponibilité
- documentation Swagger

## Remplacement propre

Cette archive doit remplacer entièrement le code actuel, tout en gardant le volume PostgreSQL.

### 1. Sauvegarder l’ancien dossier

```bash
cd ~/ai-agency
mv dentalflow-ai dentalflow-ai-backup
```

### 2. Décompresser

```bash
unzip ~/Downloads/dentalflow-ai-v0.1-clean.zip
mv dentalflow-ai-v0.1 dentalflow-ai
cd dentalflow-ai
```

### 3. Conserver le fichier `.env`

```bash
cp ../dentalflow-ai-backup/.env .env
```

### 4. Appliquer la migration 003

```bash
docker exec -i dentalflow-postgres   psql -U dentalflow -d dentalflow   < packages/database/migrations/003_availability.sql
```

### 5. Reconstruire

```bash
docker compose up -d --build --force-recreate api
```

### 6. Vérifier

```bash
docker compose ps
curl http://localhost:8001/health
```

Documentation :

```text
http://localhost:8001/docs
```

## Test anti-chevauchement

```bash
curl -X POST   -H "Content-Type: application/json"   -H "X-Clinic-Id: $CLINIC_ID"   http://localhost:8001/appointments/availability   -d "{
    \"treatment_id\": \"$TREATMENT_ID\",
    \"start_at\": \"2026-07-20T14:00:00+01:00\"
  }"
```
