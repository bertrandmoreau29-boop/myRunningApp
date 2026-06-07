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
            "cycle": "VARCHAR(160)",
            "comment": "TEXT",
            "distance_manually_edited": "INTEGER",
            "avg_power": "INTEGER",
            "max_power": "INTEGER",
            "normalized_power": "INTEGER",
            "threshold_power": "INTEGER",
            "intensity_factor": "FLOAT",
            "efficiency_factor": "FLOAT",
            "grade_adjusted_speed": "FLOAT",
            "power_grade_adjusted_speed_ratio": "FLOAT",
            "efficiency_grade_adjusted_speed_ratio": "FLOAT",
            "training_stress_score": "FLOAT",
            "fitness": "FLOAT",
            "form": "FLOAT",
            "fatigue": "FLOAT",
            "avg_ground_contact_time": "FLOAT",
            "avg_temperature": "FLOAT",
        },
        "laps": {
            "avg_power": "INTEGER",
            "max_power": "INTEGER",
            "normalized_power": "INTEGER",
            "grade_adjusted_speed": "FLOAT",
            "power_grade_adjusted_speed_ratio": "FLOAT",
            "efficiency_grade_adjusted_speed_ratio": "FLOAT",
            "avg_ground_contact_time": "FLOAT",
            "avg_temperature": "FLOAT",
        },
        "records": {
            "power": "INTEGER",
            "ground_contact_time": "FLOAT",
        },
        "option_values": {
            "abbreviation": "VARCHAR(16)",
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
        "default_max_hr": "176",
        "default_shoe_type": "New Balance 860 2026 bleues",
        "default_cycle": "Prepa_marathon_Lille_2026",
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
        "cycle": [
            "Intercyle",
            "Prepa_marathon_Lille_2026",
            "Prepra_Marathon_Saumur_2026",
        ],
    }
    option_abbreviations = {
        "cycle": {
            "Intercyle": "INT",
            "Prepa_marathon_Lille_2026": "L26",
            "Prepra_Marathon_Saumur_2026": "S26",
        },
    }

    for key, value in settings.items():
        exists = connection.execute(text("SELECT 1 FROM app_settings WHERE key = :key"), {"key": key}).fetchone()
        if not exists:
            connection.execute(text("INSERT INTO app_settings(key, value) VALUES (:key, :value)"), {"key": key, "value": value})

    default_cycle = settings["default_cycle"]
    configured_cycle = connection.execute(
        text("SELECT value FROM app_settings WHERE key = 'default_cycle'")
    ).fetchone()
    if configured_cycle and configured_cycle[0]:
        default_cycle = configured_cycle[0]
    connection.execute(
        text("UPDATE activities SET cycle = :cycle WHERE cycle IS NULL OR TRIM(cycle) = ''"),
        {"cycle": default_cycle},
    )

    for category, values in options.items():
        for value in values:
            abbreviation = option_abbreviations.get(category, {}).get(value)
            exists = connection.execute(
                text("SELECT 1 FROM option_values WHERE category = :category AND value = :value"),
                {"category": category, "value": value},
            ).fetchone()
            if not exists:
                connection.execute(
                    text("INSERT INTO option_values(category, value, abbreviation) VALUES (:category, :value, :abbreviation)"),
                    {"category": category, "value": value, "abbreviation": abbreviation},
                )
            elif abbreviation:
                connection.execute(
                    text(
                        "UPDATE option_values SET abbreviation = :abbreviation "
                        "WHERE category = :category AND value = :value AND (abbreviation IS NULL OR TRIM(abbreviation) = '')"
                    ),
                    {"category": category, "value": value, "abbreviation": abbreviation},
                )
