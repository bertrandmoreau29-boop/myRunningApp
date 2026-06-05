from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db
from app.fit_parser import parse_fit_file
from app.fit_parser import _efficiency_factor
from app.models import Activity, Lap, Record


def _find_uploaded_file(filename: str) -> Path | None:
    upload_dir = Path("uploads")
    if not upload_dir.exists():
        return None

    matches = sorted(
        upload_dir.glob(f"*_{filename}"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def main() -> None:
    init_db()
    db = SessionLocal()
    updated_activities = 0
    updated_records = 0

    try:
        for activity in db.query(Activity).all():
            fit_path = _find_uploaded_file(activity.filename)
            if fit_path is None:
                continue

            parsed = parse_fit_file(fit_path)
            summary = parsed["summary"]
            for field in (
                "avg_cadence",
                "max_cadence",
                "avg_power",
                "max_power",
                "normalized_power",
                "threshold_power",
                "intensity_factor",
                "efficiency_factor",
                "training_stress_score",
                "avg_ground_contact_time",
                "avg_speed",
            ):
                value = summary.get(field)
                if value is not None:
                    setattr(activity, field, value)

            activity.efficiency_factor = _efficiency_factor(activity.normalized_power, activity.avg_heart_rate)

            laps = db.query(Lap).filter(Lap.activity_id == activity.id).order_by(Lap.lap_index).all()
            for lap, parsed_lap in zip(laps, parsed["laps"]):
                for field in (
                    "avg_cadence",
                    "max_cadence",
                    "avg_power",
                    "max_power",
                    "normalized_power",
                    "avg_ground_contact_time",
                    "avg_speed",
                ):
                    value = parsed_lap.get(field)
                    if value is not None:
                        setattr(lap, field, value)

            records = db.query(Record).filter(Record.activity_id == activity.id).order_by(Record.record_index).all()
            for record, parsed_record in zip(records, parsed["records"]):
                for field in ("cadence", "power", "ground_contact_time"):
                    value = parsed_record.get(field)
                    if value is not None:
                        setattr(record, field, value)
                        updated_records += 1

            updated_activities += 1

        db.commit()
    finally:
        db.close()

    print(f"updated_activities={updated_activities}")
    print(f"updated_record_values={updated_records}")


if __name__ == "__main__":
    main()
