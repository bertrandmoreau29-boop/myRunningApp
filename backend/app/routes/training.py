from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Activity, AppSetting, Lap, Record


router = APIRouter(prefix="/training", tags=["training"])

FITNESS_DAYS = 42
FATIGUE_DAYS = 7
CALENDAR_WEEKS = 12

# Baseline known by the user before a full historical import is available.
INITIAL_FITNESS = 44.0
INITIAL_FATIGUE = 41.0
WEEKDAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
HR_ZONE_DEFINITIONS = [
    {"key": "recovery", "label": "Endurance recuperation", "range": "60-75%", "min": 60, "max": 75, "color": "#4f8cc9"},
    {"key": "active", "label": "Endurance active", "range": "76-80%", "min": 76, "max": 80, "color": "#2fa66a"},
    {"key": "gray", "label": "Zone grise", "range": "80-82%", "min": 80, "max": 82, "color": "#8d99a6"},
    {"key": "marathon", "label": "Allure marathon", "range": "83-87%", "min": 83, "max": 87, "color": "#c7a223"},
    {"key": "threshold", "label": "Allure seuil lactique", "range": "88-92%", "min": 88, "max": 92, "color": "#d06b2d"},
    {"key": "vo2max", "label": "Allure Vo2Max", "range": "93-100%", "min": 93, "max": 100, "color": "#cf2f2f"},
]


def _apply_daily_load(current: float, tss: float, time_constant_days: int) -> float:
    return current + (tss - current) / time_constant_days


def _load_state_until(db: Session, last_day: date) -> tuple[float, float]:
    daily_tss_rows = _daily_tss_rows(db)
    if not daily_tss_rows:
        return INITIAL_FITNESS, INITIAL_FATIGUE

    daily_tss = {
        date.fromisoformat(str(activity_date)): float(value or 0)
        for activity_date, value in daily_tss_rows
        if activity_date is not None
    }
    first_day = min(daily_tss)

    fitness = INITIAL_FITNESS
    fatigue = INITIAL_FATIGUE
    current_day = first_day
    while current_day <= last_day:
        tss = daily_tss.get(current_day, 0.0)
        fitness = _apply_daily_load(fitness, tss, FITNESS_DAYS)
        fatigue = _apply_daily_load(fatigue, tss, FATIGUE_DAYS)
        current_day += timedelta(days=1)

    return fitness, fatigue


def _project_load_for_week(start_fitness: float, start_fatigue: float, target_fitness: float) -> dict[str, float]:
    fitness_decay = (1 - 1 / FITNESS_DAYS) ** 7
    fatigue_decay = (1 - 1 / FATIGUE_DAYS) ** 7
    daily_tss = (target_fitness - start_fitness * fitness_decay) / (1 - fitness_decay)
    weekly_tss = max(0.0, daily_tss * 7)
    daily_tss = weekly_tss / 7
    resulting_fitness = start_fitness
    resulting_fatigue = start_fatigue

    for _ in range(7):
        resulting_fitness = _apply_daily_load(resulting_fitness, daily_tss, FITNESS_DAYS)
        resulting_fatigue = _apply_daily_load(resulting_fatigue, daily_tss, FATIGUE_DAYS)

    return {
        "weekly_tss": weekly_tss,
        "resulting_fitness": resulting_fitness,
        "resulting_fatigue": resulting_fatigue,
        "resulting_form": resulting_fitness - resulting_fatigue,
        "fitness_decay": fitness_decay,
        "fatigue_decay": fatigue_decay,
    }


def _daily_tss_rows(db: Session, start_day: date | None = None, end_day: date | None = None) -> list[tuple[object, object]]:
    stmt = (
        select(
            func.date(Activity.started_at).label("activity_date"),
            func.sum(Activity.training_stress_score).label("daily_tss"),
        )
        .where(Activity.started_at.is_not(None), Activity.training_stress_score.is_not(None))
        .group_by(func.date(Activity.started_at))
        .order_by(func.date(Activity.started_at))
    )
    if start_day is not None:
        stmt = stmt.where(func.date(Activity.started_at) >= start_day.isoformat())
    if end_day is not None:
        stmt = stmt.where(func.date(Activity.started_at) <= end_day.isoformat())
    return db.execute(stmt).all()


def _daily_week_rows(db: Session, start_day: date, end_day: date) -> list[tuple[object, object, object, object]]:
    return db.execute(
        select(
            func.date(Activity.started_at).label("activity_date"),
            func.sum(Activity.training_stress_score).label("daily_tss"),
            func.sum(Activity.total_timer_time).label("daily_duration"),
            func.sum(Activity.total_distance).label("daily_distance"),
        )
        .where(
            Activity.started_at.is_not(None),
            func.date(Activity.started_at) >= start_day.isoformat(),
            func.date(Activity.started_at) <= end_day.isoformat(),
        )
        .group_by(func.date(Activity.started_at))
        .order_by(func.date(Activity.started_at))
    ).all()


def _default_max_hr(db: Session) -> int:
    setting = db.get(AppSetting, "default_max_hr")
    if setting is None:
        return 176
    try:
        return max(1, int(setting.value))
    except ValueError:
        return 176


def _weekly_record_rows(db: Session, start_day: date, end_day: date) -> list[tuple[int, object, int]]:
    return db.execute(
        select(Record.activity_id, Record.timestamp, Record.heart_rate)
        .join(Activity, Activity.id == Record.activity_id)
        .where(
            Activity.started_at.is_not(None),
            func.date(Activity.started_at) >= start_day.isoformat(),
            func.date(Activity.started_at) <= end_day.isoformat(),
            Record.timestamp.is_not(None),
            Record.heart_rate.is_not(None),
        )
        .order_by(Record.activity_id, Record.timestamp)
    ).all()


def _record_duration_seconds(current_timestamp: object, next_timestamp: object | None) -> float:
    if next_timestamp is None or current_timestamp is None:
        return 1.0
    delta = (next_timestamp - current_timestamp).total_seconds()
    if delta <= 0 or delta > 10:
        return 1.0
    return float(delta)


def _lap_efficiency_factor(lap: object) -> float | None:
    if not lap.avg_heart_rate:
        return None
    power = lap.normalized_power or lap.avg_power
    if power is None:
        return None
    return float(power) / float(lap.avg_heart_rate)


def _fraction_row(activity: Activity, lap: object, fraction_type: str) -> dict[str, object]:
    return {
        "activity_id": activity.id,
        "lap_id": lap.id,
        "fraction_type": fraction_type,
        "date": activity.started_at.isoformat() if activity.started_at else None,
        "session_type": activity.session_type,
        "route_location": activity.route_location,
        "lap_index": lap.lap_index,
        "total_elapsed_time": lap.total_elapsed_time,
        "total_timer_time": lap.total_timer_time,
        "total_distance": lap.total_distance,
        "avg_speed": lap.avg_speed,
        "max_speed": lap.max_speed,
        "avg_heart_rate": lap.avg_heart_rate,
        "max_heart_rate": lap.max_heart_rate,
        "avg_cadence": lap.avg_cadence,
        "max_cadence": lap.max_cadence,
        "avg_power": lap.avg_power,
        "max_power": lap.max_power,
        "normalized_power": lap.normalized_power,
        "avg_ground_contact_time": lap.avg_ground_contact_time,
        "efficiency_factor": _lap_efficiency_factor(lap),
    }


def _fraction_group(title: str, key: str, rows: list[dict[str, object]]) -> dict[str, object]:
    return {"key": key, "title": title, "rows": rows}


def _fraction_type_from_session_type(session_type: str | None) -> str | None:
    if not session_type:
        return None
    normalized = session_type.strip().lower()
    if "seuil" in normalized:
        return "threshold"
    if "marathon" in normalized or "allure m" in normalized:
        return "marathon"
    if "vo2" in normalized or "vma" in normalized:
        return "vo2max"
    return None


@router.get("/metrics")
def get_training_metrics(db: Session = Depends(get_db)) -> dict[str, float]:
    today = date.today()
    daily_tss_rows = _daily_tss_rows(db)

    if not daily_tss_rows:
        fatigue = INITIAL_FATIGUE
        fitness = INITIAL_FITNESS
        return {
            "fitness": round(fitness, 1),
            "fatigue": round(fatigue, 1),
            "form": round(fitness - fatigue, 1),
        }

    daily_tss = {
        date.fromisoformat(str(activity_date)): float(value or 0)
        for activity_date, value in daily_tss_rows
        if activity_date is not None
    }
    first_day = min(daily_tss)
    last_day = max(today, max(daily_tss))

    fitness = INITIAL_FITNESS
    fatigue = INITIAL_FATIGUE
    current_day = first_day

    while current_day <= last_day:
        tss = daily_tss.get(current_day, 0.0)
        fitness = _apply_daily_load(fitness, tss, FITNESS_DAYS)
        fatigue = _apply_daily_load(fatigue, tss, FATIGUE_DAYS)
        current_day += timedelta(days=1)

    return {
        "fitness": round(fitness, 1),
        "fatigue": round(fatigue, 1),
        "form": round(fitness - fatigue, 1),
    }


@router.get("/week")
def get_weekly_tss(db: Session = Depends(get_db)) -> dict[str, object]:
    today = date.today()
    start_day = today - timedelta(days=today.weekday())
    end_day = start_day + timedelta(days=6)
    daily_values = {
        date.fromisoformat(str(activity_date)): {
            "tss": float(tss or 0),
            "duration": float(duration or 0),
            "distance": float(distance or 0),
        }
        for activity_date, tss, duration, distance in _daily_week_rows(db, start_day, end_day)
        if activity_date is not None
    }
    days = [
        {
            "date": (start_day + timedelta(days=index)).isoformat(),
            "label": WEEKDAY_LABELS[index],
            "tss": round(daily_values.get(start_day + timedelta(days=index), {}).get("tss", 0.0), 1),
            "duration": round(daily_values.get(start_day + timedelta(days=index), {}).get("duration", 0.0), 1),
            "distance": round(daily_values.get(start_day + timedelta(days=index), {}).get("distance", 0.0), 1),
        }
        for index in range(7)
    ]
    return {
        "start_date": start_day.isoformat(),
        "end_date": end_day.isoformat(),
        "days": days,
        "total_tss": round(sum(day["tss"] for day in days), 1),
        "total_duration": round(sum(day["duration"] for day in days), 1),
        "total_distance": round(sum(day["distance"] for day in days), 1),
    }


@router.get("/calendar")
def get_training_calendar(db: Session = Depends(get_db)) -> dict[str, object]:
    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())
    previous_day = current_week_start - timedelta(days=1)
    start_fitness, start_fatigue = _load_state_until(db, previous_day)
    current_target = round(start_fitness, 1)
    weeks = []
    projected_fitness = start_fitness
    projected_fatigue = start_fatigue

    for index in range(CALENDAR_WEEKS):
        start_day = current_week_start + timedelta(days=index * 7)
        end_day = start_day + timedelta(days=6)
        week_number = start_day.isocalendar().week

        if index == 0:
            target_fitness = current_target
        else:
            cycle_increment = [3, 3, 0][(index - 1) % 3]
            target_fitness = round((weeks[-1]["target_fitness"] if weeks else current_target) + cycle_increment, 1)

        projection = _project_load_for_week(projected_fitness, projected_fatigue, target_fitness)
        actual_rows = _daily_week_rows(db, start_day, end_day)
        actual_tss = sum(float(row[1] or 0) for row in actual_rows)

        weeks.append(
            {
                "index": index,
                "week_number": week_number,
                "start_date": start_day.isoformat(),
                "end_date": end_day.isoformat(),
                "target_fitness": round(target_fitness, 1),
                "required_tss": round(projection["weekly_tss"], 1),
                "actual_tss": round(actual_tss, 1),
                "start_fitness": round(projected_fitness, 1),
                "start_fatigue": round(projected_fatigue, 1),
                "resulting_fitness": round(projection["resulting_fitness"], 1),
                "resulting_fatigue": round(projection["resulting_fatigue"], 1),
                "resulting_form": round(projection["resulting_form"], 1),
            }
        )
        projected_fitness = projection["resulting_fitness"]
        projected_fatigue = projection["resulting_fatigue"]

    return {
        "fitness_days": FITNESS_DAYS,
        "fatigue_days": FATIGUE_DAYS,
        "weeks": weeks,
    }


@router.get("/fractions")
def get_training_fractions(db: Session = Depends(get_db)) -> dict[str, object]:
    max_hr = _default_max_hr(db)
    threshold_rows: list[dict[str, object]] = []
    marathon_rows: list[dict[str, object]] = []
    vo2_rows_by_duration: dict[int, list[dict[str, object]]] = {}

    rows = db.execute(
        select(Activity, Lap)
        .join(Lap, Lap.activity_id == Activity.id)
        .order_by(Activity.started_at.asc().nullslast(), Activity.created_at.asc(), Lap.lap_index.asc())
    ).all()

    for activity, lap in rows:
        fraction_type = _fraction_type_from_session_type(activity.session_type)
        if fraction_type == "marathon":
            marathon_rows.append(_fraction_row(activity, lap, "marathon"))
        elif fraction_type == "threshold":
            threshold_rows.append(_fraction_row(activity, lap, "threshold"))
        elif fraction_type == "vo2max":
            duration_seconds = float(lap.total_timer_time or lap.total_elapsed_time or 0)
            if duration_seconds > 6 * 60:
                continue
            duration_minutes = max(1, round(duration_seconds / 60))
            vo2_rows_by_duration.setdefault(duration_minutes, []).append(_fraction_row(activity, lap, "vo2max"))

    groups = [
        _fraction_group("Seuils", "threshold", threshold_rows),
        _fraction_group("Allure marathon", "marathon", marathon_rows),
    ]
    groups.extend(
        _fraction_group(f"VO2Max - {duration} min", f"vo2max-{duration}", vo2_rows_by_duration[duration])
        for duration in sorted(vo2_rows_by_duration)
    )

    return {"max_hr": max_hr, "groups": groups}


@router.get("/week-zones")
def get_weekly_hr_distribution(db: Session = Depends(get_db)) -> dict[str, object]:
    today = date.today()
    start_day = today - timedelta(days=today.weekday())
    end_day = start_day + timedelta(days=6)
    max_hr = _default_max_hr(db)
    rows = _weekly_record_rows(db, start_day, end_day)

    zones = {
        definition["key"]: {**definition, "seconds": 0.0}
        for definition in HR_ZONE_DEFINITIONS
    }
    endurance_seconds = 0.0
    quality_weighted_seconds = 0.0
    quality_raw_seconds = 0.0

    for index, (activity_id, timestamp, heart_rate) in enumerate(rows):
        next_timestamp = None
        if index + 1 < len(rows) and rows[index + 1][0] == activity_id:
            next_timestamp = rows[index + 1][1]
        duration = _record_duration_seconds(timestamp, next_timestamp)
        percent = (float(heart_rate) / max_hr) * 100

        if percent <= 80:
            endurance_seconds += duration
        elif percent < 83:
            pass
        elif percent <= 87:
            quality_raw_seconds += duration
            quality_weighted_seconds += duration * 0.5
        else:
            quality_raw_seconds += duration
            quality_weighted_seconds += duration

        for definition in HR_ZONE_DEFINITIONS:
            if definition["key"] == "gray":
                is_in_zone = 80 < percent <= definition["max"]
            else:
                is_in_zone = definition["min"] <= percent <= definition["max"]
            if is_in_zone:
                zones[definition["key"]]["seconds"] += duration
                break

    denominator = endurance_seconds + quality_weighted_seconds
    endurance_ratio = (endurance_seconds / denominator) * 100 if denominator else 0.0
    quality_ratio = (quality_weighted_seconds / denominator) * 100 if denominator else 0.0

    zone_payload = [
        {
            "key": zone["key"],
            "label": zone["label"],
            "range": zone["range"],
            "seconds": round(zone["seconds"], 1),
            "color": zone["color"],
        }
        for zone in zones.values()
    ]

    return {
        "max_hr": max_hr,
        "start_date": start_day.isoformat(),
        "end_date": end_day.isoformat(),
        "endurance_seconds": round(endurance_seconds, 1),
        "quality_weighted_seconds": round(quality_weighted_seconds, 1),
        "quality_raw_seconds": round(quality_raw_seconds, 1),
        "endurance_ratio": round(endurance_ratio, 1),
        "quality_ratio": round(quality_ratio, 1),
        "zones": zone_payload,
        "tips": (
            "Endurance: chaque point jusqu'a 80% FCM compte en endurance. "
            "Zone grise: au-dessus de 80% et jusqu'a 82% FCM, non comptee dans la qualite. "
            "Qualite: 83-87% FCM compte avec un coefficient 0.5, "
            "88% FCM et plus compte avec un coefficient 1. "
            "Ratio = endurance / (endurance + qualite ponderee)."
        ),
    }
