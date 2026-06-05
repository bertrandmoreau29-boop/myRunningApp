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
