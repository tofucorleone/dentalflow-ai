# Étape 5 — Dashboard DentalFlow AI

## Installation

```bash
cd ~/ai-agency/dentalflow-ai
unzip -o ~/Downloads/dentalflow-ai-step5-dashboard.zip
```

Ajoutez dans `.env` :

```env
DASHBOARD_PORT=3000
CLINIC_ID=UUID_DE_LA_CLINIQUE
```

Pour récupérer l'UUID :

```bash
docker exec dentalflow-postgres   psql -U dentalflow -d dentalflow   -tAc "SELECT id FROM clinics WHERE slug='clinique-demo';"
```

Démarrez :

```bash
docker compose up -d --build dashboard
docker compose ps
```

Ouvrez :

```text
http://localhost:3000
```
