# Étape 7 — Patient 360

```bash
cd ~/ai-agency/dentalflow-ai
unzip -o ~/Downloads/dentalflow-ai-step7-patient360.zip
chmod +x install-step7.sh
./install-step7.sh
```

Migration :

```bash
docker exec -i dentalflow-postgres \
  psql -U dentalflow -d dentalflow \
  < packages/database/migrations/004_patient360.sql
```

Reconstruction :

```bash
docker compose up -d --build api dashboard
```

Test :

1. Ouvrez `http://localhost:3000/patients`
2. Cliquez sur Karim Test
3. Ajoutez une note administrative
4. Vérifiez l’historique des rendez-vous
