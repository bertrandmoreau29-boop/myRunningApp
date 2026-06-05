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
