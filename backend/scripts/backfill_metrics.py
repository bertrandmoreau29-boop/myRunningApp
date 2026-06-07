from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db
from app.fit_parser import parse_fit_file
from app.fit_parser import _efficiency_factor
from app.fit_parser import _efficiency_grade_adjusted_speed_ratio
from app.fit_parser import _grade_adjusted_speed
from app.fit_parser import _intensity_factor
from app.fit_parser import _power_grade_adjusted_speed_ratio
from app.fit_parser import _training_stress_score
from app.models import Activity, Lap, Record
from app.routes.activities import recalculate_training_history


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


def _record_dict(record: Record) -> dict[str, object]:
    return {
        "timestamp": record.timestamp,
        "distance": record.distance,
        "speed": record.speed,
        "altitude": record.altitude,
    }


def _records_for_lap(lap: Lap, records: list[Record]) -> list[dict[str, object]]:
    if lap.started_at is None or not lap.total_timer_time or lap.total_timer_time <= 0:
        return []
    started_at = lap.started_at.timestamp()
    ended_at = started_at + lap.total_timer_time
    return [
        _record_dict(record)
        for record in records
        if record.timestamp is not None and started_at <= record.timestamp.timestamp() <= ended_at
    ]


def _backfill_from_records(db, activity: Activity) -> int:
    records = db.query(Record).filter(Record.activity_id == activity.id).order_by(Record.record_index).all()
    record_dicts = [_record_dict(record) for record in records]
    activity.grade_adjusted_speed = _grade_adjusted_speed(record_dicts, activity.avg_speed)
    activity.power_grade_adjusted_speed_ratio = _power_grade_adjusted_speed_ratio(
        activity.avg_power,
        activity.grade_adjusted_speed,
    )
    activity.efficiency_grade_adjusted_speed_ratio = _efficiency_grade_adjusted_speed_ratio(
        activity.efficiency_factor,
        activity.grade_adjusted_speed,
    )

    laps = db.query(Lap).filter(Lap.activity_id == activity.id).order_by(Lap.lap_index).all()
    for lap in laps:
        lap_efficiency = _efficiency_factor(lap.normalized_power or lap.avg_power, lap.avg_heart_rate)
        lap.grade_adjusted_speed = _grade_adjusted_speed(_records_for_lap(lap, records), lap.avg_speed)
        lap.power_grade_adjusted_speed_ratio = _power_grade_adjusted_speed_ratio(
            lap.avg_power,
            lap.grade_adjusted_speed,
        )
        lap.efficiency_grade_adjusted_speed_ratio = _efficiency_grade_adjusted_speed_ratio(
            lap_efficiency,
            lap.grade_adjusted_speed,
        )

    return len(records)


def main() -> None:
    init_db()
    db = SessionLocal()
    updated_activities = 0
    updated_records = 0

    try:
        for activity in db.query(Activity).all():
            fit_path = _find_uploaded_file(activity.filename)
            if fit_path is None:
                updated_records += _backfill_from_records(db, activity)
                updated_activities += 1
                continue

            parsed = parse_fit_file(fit_path)
            summary = parsed["summary"]
            for field in (
                "avg_cadence",
                "max_cadence",
                "avg_power",
                "max_power",
                "normalized_power",
                "efficiency_factor",
                "grade_adjusted_speed",
                "power_grade_adjusted_speed_ratio",
                "efficiency_grade_adjusted_speed_ratio",
                "avg_ground_contact_time",
            ):
                value = summary.get(field)
                if value is not None:
                    setattr(activity, field, value)

            if not activity.distance_manually_edited:
                value = summary.get("avg_speed")
                if value is not None:
                    activity.avg_speed = value

            activity.efficiency_factor = _efficiency_factor(activity.normalized_power, activity.avg_heart_rate)
            activity.intensity_factor = _intensity_factor(activity.normalized_power, activity.threshold_power)
            activity.training_stress_score = _training_stress_score(
                activity.total_timer_time,
                activity.normalized_power,
                activity.threshold_power,
            )

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
                    "grade_adjusted_speed",
                    "power_grade_adjusted_speed_ratio",
                    "efficiency_grade_adjusted_speed_ratio",
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

        recalculate_training_history(db)
        db.commit()
    finally:
        db.close()

    print(f"updated_activities={updated_activities}")
    print(f"updated_record_values={updated_records}")


if __name__ == "__main__":
    main()
