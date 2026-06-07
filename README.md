# MonAppliRunning

Application locale pour importer des fichiers Garmin FIT, les decoder cote serveur, stocker les donnees en SQLite, puis les consulter dans un client web.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy, SQLite, fitparse
- Frontend: React, TypeScript, Vite

## Demarrage

Dans deux terminaux separes:

```powershell
cd backend
..\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

```powershell
cd frontend
npm run dev
```

Le backend ecoute sur `http://127.0.0.1:8000`.
Le frontend ecoute sur `http://127.0.0.1:5173`.

## API principale

- `POST /api/activities/upload` upload d'un fichier `.fit`
- `GET /api/activities` liste des activites importees
- `GET /api/activities/{activity_id}` detail d'une activite
- `GET /api/activities/{activity_id}/laps` tours/laps
- `GET /api/activities/{activity_id}/records` points temporels

## Import Strava

Creer une application Strava puis saisir le Client ID et le Client Secret dans la fenetre `Importer Strava`.
Alternative: definir les variables d'environnement avant de lancer le backend:

```powershell
$env:STRAVA_CLIENT_ID="..."
$env:STRAVA_CLIENT_SECRET="..."
$env:STRAVA_REDIRECT_URI="http://127.0.0.1:8000/api/strava/callback"
```

Dans l'application Strava, l'Authorization Callback Domain doit correspondre au domaine du backend local ou heberge.
En local, utiliser `127.0.0.1`.

Le bouton `Importer Strava` ouvre une fenetre de preparation: dates debut/fin, chaussure, cycle et FTP a appliquer aux seances importees.
Les doublons Strava ou les activites deja importees depuis FIT avec date/distance proches sont ignorees avec un warning.
