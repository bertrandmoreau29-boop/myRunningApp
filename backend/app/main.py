from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes.activities import router as activities_router
from app.routes.config import router as config_router
from app.routes.strava import router as strava_router
from app.routes.training import router as training_router


app = FastAPI(title="MonAppliRunning API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(activities_router, prefix="/api")
app.include_router(config_router, prefix="/api")
app.include_router(strava_router, prefix="/api")
app.include_router(training_router, prefix="/api")
