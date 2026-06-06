from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL = "sqlite:///./running.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    additions = {
        "activities": {
            "session_type": "VARCHAR(160)",
            "route_location": "VARCHAR(160)",
            "shoe_type": "VARCHAR(160)",
            "comment": "TEXT",
            "avg_power": "INTEGER",
            "max_power": "INTEGER",
            "normalized_power": "INTEGER",
            "threshold_power": "INTEGER",
            "intensity_factor": "FLOAT",
            "efficiency_factor": "FLOAT",
            "training_stress_score": "FLOAT",
            "avg_ground_contact_time": "FLOAT",
        },
        "laps": {
            "avg_power": "INTEGER",
            "max_power": "INTEGER",
            "normalized_power": "INTEGER",
            "avg_ground_contact_time": "FLOAT",
        },
        "records": {
            "power": "INTEGER",
            "ground_contact_time": "FLOAT",
        },
    }

    with engine.begin() as connection:
        for table_name, columns in additions.items():
            existing = {
                row[1]
                for row in connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
            }
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))
        _seed_defaults(connection)


def _seed_defaults(connection) -> None:
    settings = {
        "default_ftp": "221",
        "default_shoe_type": "New Balance 860 2026 bleues",
    }
    options = {
        "session_type": [
            "Endurance+ lignes droites",
            "Endurance",
            "Sortie allure Marathon",
            "Sortie allure seuil",
            "Tapis endurance",
        ],
        "route_location": [
            "Brest domicile",
            "Ifremer Plouzane",
            "Marregues-Gouesnou 10km",
        ],
        "shoe_type": [
            "New Balance 860 2026 bleues",
        ],
    }

    for key, value in settings.items():
        exists = connection.execute(text("SELECT 1 FROM app_settings WHERE key = :key"), {"key": key}).fetchone()
        if not exists:
            connection.execute(text("INSERT INTO app_settings(key, value) VALUES (:key, :value)"), {"key": key, "value": value})

    for category, values in options.items():
        for value in values:
            exists = connection.execute(
                text("SELECT 1 FROM option_values WHERE category = :category AND value = :value"),
                {"category": category, "value": value},
            ).fetchone()
            if not exists:
                connection.execute(
                    text("INSERT INTO option_values(category, value) VALUES (:category, :value)"),
                    {"category": category, "value": value},
                )
