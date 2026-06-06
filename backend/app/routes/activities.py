from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.fit_parser import _intensity_factor, _training_stress_score, parse_fit_file
from app.models import Activity, AppSetting, Lap, Record
from app.schemas import ActivityDetail, ActivitySummary, ActivityUpdate, LapRead, RecordRead, ThresholdPowerUpdate


router = APIRouter(prefix="/activities", tags=["activities"])
UPLOAD_DIR = Path("uploads")


def _summary(activity: Activity, lap_count: int, record_count: int) -> ActivitySummary:
    data = ActivitySummary.model_validate(activity).model_dump()
    data.update({"lap_count": lap_count, "record_count": record_count})
    return ActivitySummary.model_validate(data)


def _detail(activity: Activity, lap_count: int, record_count: int) -> ActivityDetail:
    data = ActivityDetail.model_validate(activity).model_dump()
    data.update({"lap_count": lap_count, "record_count": record_count})
    return ActivityDetail.model_validate(data)


def _recalculate_threshold_metrics(activity: Activity) -> None:
    activity.intensity_factor = _intensity_factor(activity.normalized_power, activity.threshold_power)
    activity.training_stress_score = _training_stress_score(
        activity.total_timer_time,
        activity.normalized_power,
        activity.threshold_power,
    )


def _recalculate_distance_metrics(activity: Activity) -> None:
    if activity.total_distance is not None and activity.total_timer_time and activity.total_timer_time > 0:
        activity.avg_speed = activity.total_distance / activity.total_timer_time


def _default_threshold_power(db: Session) -> int | None:
    setting = db.get(AppSetting, "default_ftp")
    if setting is None:
        return None
    try:
        return int(setting.value)
    except ValueError:
        return None


def _default_shoe_type(db: Session) -> str | None:
    setting = db.get(AppSetting, "default_shoe_type")
    return setting.value if setting and setting.value else None


def _previous_threshold_power(db: Session, started_at: object) -> int | None:
    if started_at is not None:
        previous_by_date = db.scalar(
            select(Activity.threshold_power)
            .where(Activity.threshold_power.is_not(None), Activity.started_at < started_at)
            .order_by(Activity.started_at.desc(), Activity.created_at.desc())
            .limit(1)
        )
        if previous_by_date is not None:
            return previous_by_date

    return db.scalar(
        select(Activity.threshold_power)
        .where(Activity.threshold_power.is_not(None))
        .order_by(Activity.started_at.desc().nullslast(), Activity.created_at.desc())
        .limit(1)
    )


def _create_activity_from_fit(path: Path, original_filename: str, db: Session) -> tuple[Activity, int, int]:
    try:
        parsed = parse_fit_file(path)
    except Exception as exc:  # fitparse exposes several low-level exceptions depending on the file.
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Fichier FIT illisible ({original_filename}): {exc}") from exc

    default_threshold = _default_threshold_power(db) or _previous_threshold_power(db, parsed["summary"].get("started_at"))
    if default_threshold is not None:
        parsed["summary"]["threshold_power"] = default_threshold
        parsed["summary"]["intensity_factor"] = _intensity_factor(
            parsed["summary"].get("normalized_power"),
            default_threshold,
        )
        parsed["summary"]["training_stress_score"] = _training_stress_score(
            parsed["summary"].get("total_timer_time"),
            parsed["summary"].get("normalized_power"),
            default_threshold,
        )

    parsed["summary"]["shoe_type"] = _default_shoe_type(db)
    activity = Activity(filename=original_filename, **parsed["summary"])
    db.add(activity)
    db.flush()

    db.add_all(Lap(activity_id=activity.id, **lap) for lap in parsed["laps"])
    db.add_all(Record(activity_id=activity.id, **record) for record in parsed["records"])
    return activity, len(parsed["laps"]), len(parsed["records"])


def _store_fit_bytes(content: bytes, original_filename: str) -> Path:
    UPLOAD_DIR.mkdir(exist_ok=True)
    stored_name = f"{uuid4().hex}_{Path(original_filename).name}"
    stored_path = UPLOAD_DIR / stored_name
    stored_path.write_bytes(content)
    return stored_path


@router.post("/upload", response_model=ActivityDetail)
async def upload_activity(file: UploadFile = File(...), db: Session = Depends(get_db)) -> ActivityDetail:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier manquant")

    lower_filename = file.filename.lower()
    if not lower_filename.endswith((".fit", ".zip")):
        raise HTTPException(status_code=400, detail="Le fichier doit etre au format .fit ou .zip")

    content = await file.read()
    imported: list[tuple[Activity, int, int]] = []

    if lower_filename.endswith(".fit"):
        stored_path = _store_fit_bytes(content, file.filename)
        imported.append(_create_activity_from_fit(stored_path, file.filename, db))
    else:
        zip_path = _store_fit_bytes(content, file.filename)
        try:
            with ZipFile(zip_path) as archive:
                fit_members = [
                    member
                    for member in archive.infolist()
                    if not member.is_dir() and Path(member.filename).name.lower().endswith(".fit")
                ]
                if not fit_members:
                    raise HTTPException(status_code=400, detail="Aucun fichier .fit trouve dans le zip")

                for member in fit_members:
                    fit_name = Path(member.filename).name
                    stored_path = _store_fit_bytes(archive.read(member), fit_name)
                    imported.append(_create_activity_from_fit(stored_path, fit_name, db))
        except BadZipFile as exc:
            zip_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="Fichier zip illisible") from exc

    db.commit()
    activity, lap_count, record_count = imported[0]
    db.refresh(activity)

    return _detail(activity, lap_count, record_count)


@router.get("", response_model=list[ActivitySummary])
def list_activities(db: Session = Depends(get_db)) -> list[ActivitySummary]:
    stmt = (
        select(
            Activity,
            func.count(func.distinct(Lap.id)).label("lap_count"),
            func.count(func.distinct(Record.id)).label("record_count"),
        )
        .outerjoin(Lap)
        .outerjoin(Record)
        .group_by(Activity.id)
        .order_by(Activity.started_at.desc().nullslast(), Activity.created_at.desc())
    )
    return [_summary(activity, lap_count, record_count) for activity, lap_count, record_count in db.execute(stmt)]


@router.get("/{activity_id}", response_model=ActivityDetail)
def get_activity(activity_id: int, db: Session = Depends(get_db)) -> ActivityDetail:
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activite introuvable")

    lap_count = db.scalar(select(func.count()).select_from(Lap).where(Lap.activity_id == activity_id)) or 0
    record_count = db.scalar(select(func.count()).select_from(Record).where(Record.activity_id == activity_id)) or 0
    return _detail(activity, lap_count, record_count)


@router.patch("/{activity_id}/threshold-power", response_model=ActivityDetail)
def update_threshold_power(
    activity_id: int,
    payload: ThresholdPowerUpdate,
    db: Session = Depends(get_db),
) -> ActivityDetail:
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activite introuvable")

    activity.threshold_power = payload.threshold_power
    _recalculate_threshold_metrics(activity)
    db.commit()
    db.refresh(activity)

    lap_count = db.scalar(select(func.count()).select_from(Lap).where(Lap.activity_id == activity_id)) or 0
    record_count = db.scalar(select(func.count()).select_from(Record).where(Record.activity_id == activity_id)) or 0
    return _detail(activity, lap_count, record_count)


@router.patch("/{activity_id}", response_model=ActivityDetail)
def update_activity(activity_id: int, payload: ActivityUpdate, db: Session = Depends(get_db)) -> ActivityDetail:
    activity = db.get(Activity, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activite introuvable")

    for field in ("session_type", "route_location", "shoe_type", "comment"):
        value = getattr(payload, field)
        if value is not None:
            setattr(activity, field, value.strip() if isinstance(value, str) else value)

    if payload.total_distance is not None:
        activity.total_distance = payload.total_distance
        _recalculate_distance_metrics(activity)

    if payload.threshold_power is not None:
        activity.threshold_power = payload.threshold_power
        _recalculate_threshold_metrics(activity)

    db.commit()
    db.refresh(activity)

    lap_count = db.scalar(select(func.count()).select_from(Lap).where(Lap.activity_id == activity_id)) or 0
    record_count = db.scalar(select(func.count()).select_from(Record).where(Record.activity_id == activity_id)) or 0
    return _detail(activity, lap_count, record_count)


@router.get("/{activity_id}/laps", response_model=list[LapRead])
def get_laps(activity_id: int, db: Session = Depends(get_db)) -> list[LapRead]:
    if db.get(Activity, activity_id) is None:
        raise HTTPException(status_code=404, detail="Activite introuvable")
    laps = db.scalars(select(Lap).where(Lap.activity_id == activity_id).order_by(Lap.lap_index)).all()
    return [LapRead.model_validate(lap) for lap in laps]


@router.get("/{activity_id}/records", response_model=list[RecordRead])
def get_records(activity_id: int, limit: int = 2000, db: Session = Depends(get_db)) -> list[RecordRead]:
    if db.get(Activity, activity_id) is None:
        raise HTTPException(status_code=404, detail="Activite introuvable")
    safe_limit = min(max(limit, 1), 10000)
    records = db.scalars(
        select(Record).where(Record.activity_id == activity_id).order_by(Record.record_index).limit(safe_limit)
    ).all()
    return [RecordRead.model_validate(record) for record in records]
