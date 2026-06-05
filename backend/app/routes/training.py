from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Activity


router = APIRouter(prefix="/training", tags=["training"])

FITNESS_DAYS = 42
FATIGUE_DAYS = 7

# Baseline known by the user before a full historical import is available.
INITIAL_FITNESS = 44.0
INITIAL_FATIGUE = 41.0
WEEKDAY_LABELS = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]


def _apply_daily_load(current: float, tss: float, time_constant_days: int) -> float:
    return current + (tss - current) / time_constant_days


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
