import json
import os
from datetime import date, datetime, time, timedelta
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.fit_parser import (
    _avg_int,
    _efficiency_factor,
    _efficiency_grade_adjusted_speed_ratio,
    _grade_adjusted_speed,
    _intensity_factor,
    _max_int,
    _normalized_power,
    _power_grade_adjusted_speed_ratio,
    _training_stress_score,
)
from app.models import Activity, AppSetting, Lap, Record
from app.routes.activities import recalculate_training_history
from app.schemas import StravaCredentialsUpdate, StravaImportRequest, StravaImportResult, StravaStatus


router = APIRouter(prefix="/strava", tags=["strava"])

STRAVA_API_BASE = "https://www.strava.com/api/v3"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_SCOPE = "read,activity:read_all"


def _client_id(db: Session | None = None) -> str | None:
    if db is not None:
        stored = _setting(db, "strava_client_id")
        if stored:
            return stored
    return os.getenv("STRAVA_CLIENT_ID")


def _client_secret(db: Session | None = None) -> str | None:
    if db is not None:
        stored = _setting(db, "strava_client_secret")
        if stored:
            return stored
    return os.getenv("STRAVA_CLIENT_SECRET")


def _redirect_uri() -> str:
    return os.getenv("STRAVA_REDIRECT_URI", "http://127.0.0.1:8000/api/strava/callback")


def _setting(db: Session, key: str) -> str | None:
    setting = db.get(AppSetting, key)
    return setting.value if setting and setting.value else None


def _set_setting(db: Session, key: str, value: str) -> None:
    setting = db.get(AppSetting, key)
    if setting is None:
        db.add(AppSetting(key=key, value=value))
    else:
        setting.value = value


def _json_request(url: str, method: str = "GET", token: str | None = None, data: dict[str, Any] | None = None) -> Any:
    body = None if data is None else urlencode(data).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=502, detail=f"Erreur Strava: {detail}") from exc


def _auth_url(db: Session | None = None) -> str | None:
    client_id = _client_id(db)
    if not client_id:
        return None
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": _redirect_uri(),
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": STRAVA_SCOPE,
        }
    )
    return f"{STRAVA_AUTH_URL}?{query}"


def _store_token_response(db: Session, payload: dict[str, Any]) -> None:
    _set_setting(db, "strava_access_token", str(payload["access_token"]))
    _set_setting(db, "strava_refresh_token", str(payload["refresh_token"]))
    _set_setting(db, "strava_expires_at", str(payload["expires_at"]))
    athlete = payload.get("athlete") or {}
    if athlete.get("id") is not None:
        _set_setting(db, "strava_athlete_id", str(athlete["id"]))


def _access_token(db: Session) -> str:
    access_token = _setting(db, "strava_access_token")
    refresh_token = _setting(db, "strava_refresh_token")
    expires_at = _setting(db, "strava_expires_at")
    if not access_token or not refresh_token or not expires_at:
        raise HTTPException(status_code=401, detail="Compte Strava non connecte")

    try:
        expires_timestamp = int(expires_at)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Token Strava invalide") from exc

    if expires_timestamp > int(datetime.utcnow().timestamp()) + 60:
        return access_token

    client_id = _client_id(db)
    client_secret = _client_secret(db)
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="STRAVA_CLIENT_ID/STRAVA_CLIENT_SECRET manquants")

    payload = _json_request(
        STRAVA_TOKEN_URL,
        method="POST",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    _store_token_response(db, payload)
    db.commit()
    return str(payload["access_token"])


def _date_timestamp(value: date, end_of_day: bool = False) -> int:
    selected_time = time.max if end_of_day else time.min
    return int(datetime.combine(value, selected_time).timestamp())


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _stream_map(payload: Any) -> dict[str, list[Any]]:
    if isinstance(payload, dict):
        return {key: value.get("data", []) for key, value in payload.items() if isinstance(value, dict)}
    if isinstance(payload, list):
        return {item.get("type"): item.get("data", []) for item in payload if isinstance(item, dict)}
    return {}


def _stream_value(streams: dict[str, list[Any]], key: str, index: int) -> Any:
    values = streams.get(key) or []
    return values[index] if index < len(values) else None


def _record_payloads(started_at: datetime | None, streams: dict[str, list[Any]]) -> list[dict[str, Any]]:
    times = streams.get("time") or []
    max_length = max((len(values) for values in streams.values()), default=0)
    records: list[dict[str, Any]] = []
    for index in range(max_length):
        seconds = _stream_value(streams, "time", index)
        latlng = _stream_value(streams, "latlng", index)
        records.append(
            {
                "record_index": index + 1,
                "timestamp": started_at + timedelta(seconds=float(seconds)) if started_at and seconds is not None else None,
                "distance": _stream_value(streams, "distance", index),
                "speed": _stream_value(streams, "velocity_smooth", index),
                "heart_rate": _stream_value(streams, "heartrate", index),
                "cadence": _stream_value(streams, "cadence", index),
                "power": _stream_value(streams, "watts", index),
                "ground_contact_time": None,
                "altitude": _stream_value(streams, "altitude", index),
                "latitude": latlng[0] if isinstance(latlng, list) and len(latlng) == 2 else None,
                "longitude": latlng[1] if isinstance(latlng, list) and len(latlng) == 2 else None,
                "temperature": _stream_value(streams, "temp", index),
            }
        )
    if records or not times:
        return records
    return []


def _records_for_lap(lap: dict[str, Any], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    started_at = lap.get("started_at")
    timer_time = lap.get("total_timer_time")
    if not started_at or not timer_time:
        return []
    start_timestamp = started_at.timestamp()
    end_timestamp = start_timestamp + float(timer_time)
    return [
        record
        for record in records
        if record["timestamp"] is not None and start_timestamp <= record["timestamp"].timestamp() <= end_timestamp
    ]


def _descent(records: list[dict[str, Any]]) -> float | None:
    descent = 0.0
    previous_altitude = None
    for record in records:
        altitude = record.get("altitude")
        if altitude is None:
            continue
        if previous_altitude is not None and altitude < previous_altitude:
            descent += previous_altitude - altitude
        previous_altitude = altitude
    return round(descent, 1) if descent > 0 else None


def _activity_duplicate(db: Session, strava_id: int, started_at: datetime | None, distance: float | None) -> Activity | None:
    existing = db.scalar(select(Activity).where(Activity.strava_activity_id == strava_id).limit(1))
    if existing is not None:
        return existing
    if started_at is None or distance is None:
        return None

    nearby = db.scalars(
        select(Activity).where(
            Activity.started_at >= started_at - timedelta(seconds=90),
            Activity.started_at <= started_at + timedelta(seconds=90),
        )
    ).all()
    for activity in nearby:
        if activity.total_distance is None:
            continue
        tolerance = max(50.0, distance * 0.02)
        if abs(activity.total_distance - distance) <= tolerance:
            return activity
    return None


def _activity_summary_from_strava(activity: dict[str, Any], streams: dict[str, list[Any]], threshold_power: int) -> dict[str, Any]:
    started_at = _parse_datetime(activity.get("start_date_local") or activity.get("start_date"))
    records = _record_payloads(started_at, streams)
    powers = [record["power"] for record in records if record.get("power") is not None]
    heart_rates = [record["heart_rate"] for record in records if record.get("heart_rate") is not None]
    cadences = [record["cadence"] for record in records if record.get("cadence") is not None]

    avg_power = activity.get("average_watts") or _avg_int(powers)
    normalized_power = activity.get("weighted_average_watts") or _normalized_power(powers)
    avg_heart_rate = activity.get("average_heartrate") or _avg_int(heart_rates)
    grade_adjusted_speed = _grade_adjusted_speed(records, activity.get("average_speed"))
    efficiency_factor = _efficiency_factor(normalized_power, avg_heart_rate)

    summary = {
        "filename": f"strava-{activity['id']}-{activity.get('name', 'activity')}",
        "strava_activity_id": int(activity["id"]),
        "sport": activity.get("sport_type") or activity.get("type"),
        "sub_sport": activity.get("workout_type"),
        "started_at": started_at,
        "total_elapsed_time": activity.get("elapsed_time"),
        "total_timer_time": activity.get("moving_time"),
        "total_distance": activity.get("distance"),
        "avg_speed": activity.get("average_speed"),
        "grade_adjusted_speed": grade_adjusted_speed,
        "max_speed": activity.get("max_speed"),
        "avg_heart_rate": round(avg_heart_rate) if avg_heart_rate is not None else None,
        "max_heart_rate": round(activity["max_heartrate"]) if activity.get("max_heartrate") is not None else _max_int(heart_rates),
        "avg_cadence": round(activity.get("average_cadence") or _avg_int(cadences) or 0) or None,
        "max_cadence": _max_int(cadences),
        "avg_power": round(avg_power) if avg_power is not None else None,
        "max_power": round(activity["max_watts"]) if activity.get("max_watts") is not None else _max_int(powers),
        "normalized_power": round(normalized_power) if normalized_power is not None else None,
        "threshold_power": threshold_power,
        "intensity_factor": _intensity_factor(normalized_power, threshold_power),
        "efficiency_factor": efficiency_factor,
        "power_grade_adjusted_speed_ratio": _power_grade_adjusted_speed_ratio(avg_power, grade_adjusted_speed),
        "efficiency_grade_adjusted_speed_ratio": _efficiency_grade_adjusted_speed_ratio(efficiency_factor, grade_adjusted_speed),
        "training_stress_score": _training_stress_score(activity.get("moving_time"), normalized_power, threshold_power),
        "avg_ground_contact_time": None,
        "ascent": activity.get("total_elevation_gain"),
        "descent": _descent(records),
        "raw_summary": json.dumps(activity, ensure_ascii=True),
    }
    return {"summary": summary, "records": records}


def _lap_payloads(activity: dict[str, Any], detailed: dict[str, Any], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_laps = detailed.get("laps") if isinstance(detailed.get("laps"), list) else []
    started_at = _parse_datetime(activity.get("start_date_local") or activity.get("start_date"))
    if not raw_laps:
        raw_laps = [
            {
                "start_date_local": activity.get("start_date_local") or activity.get("start_date"),
                "elapsed_time": activity.get("elapsed_time"),
                "moving_time": activity.get("moving_time"),
                "distance": activity.get("distance"),
                "average_speed": activity.get("average_speed"),
                "max_speed": activity.get("max_speed"),
                "average_heartrate": activity.get("average_heartrate"),
                "max_heartrate": activity.get("max_heartrate"),
                "average_cadence": activity.get("average_cadence"),
                "average_watts": activity.get("average_watts"),
                "max_watts": activity.get("max_watts"),
            }
        ]

    laps: list[dict[str, Any]] = []
    for index, raw_lap in enumerate(raw_laps, start=1):
        lap_started_at = _parse_datetime(raw_lap.get("start_date_local") or raw_lap.get("start_date")) or started_at
        lap = {
            "lap_index": index,
            "started_at": lap_started_at,
            "total_elapsed_time": raw_lap.get("elapsed_time"),
            "total_timer_time": raw_lap.get("moving_time"),
            "total_distance": raw_lap.get("distance"),
            "avg_speed": raw_lap.get("average_speed"),
            "max_speed": raw_lap.get("max_speed"),
            "avg_heart_rate": round(raw_lap["average_heartrate"]) if raw_lap.get("average_heartrate") is not None else None,
            "max_heart_rate": round(raw_lap["max_heartrate"]) if raw_lap.get("max_heartrate") is not None else None,
            "avg_cadence": raw_lap.get("average_cadence"),
            "max_cadence": None,
            "avg_power": raw_lap.get("average_watts"),
            "max_power": round(raw_lap["max_watts"]) if raw_lap.get("max_watts") is not None else None,
            "normalized_power": raw_lap.get("weighted_average_watts"),
            "avg_ground_contact_time": None,
        }
        lap_records = _records_for_lap(lap, records)
        lap_powers = [record["power"] for record in lap_records if record.get("power") is not None]
        lap_cadences = [record["cadence"] for record in lap_records if record.get("cadence") is not None]
        lap["avg_cadence"] = round(lap["avg_cadence"] or _avg_int(lap_cadences) or 0) or None
        lap["max_cadence"] = _max_int(lap_cadences)
        lap["avg_power"] = round(lap["avg_power"] or _avg_int(lap_powers) or 0) or None
        lap["max_power"] = lap["max_power"] or _max_int(lap_powers)
        lap["normalized_power"] = lap["normalized_power"] or _normalized_power(lap_powers)
        lap_efficiency = _efficiency_factor(lap["normalized_power"] or lap["avg_power"], lap["avg_heart_rate"])
        lap["grade_adjusted_speed"] = _grade_adjusted_speed(lap_records, lap["avg_speed"])
        lap["power_grade_adjusted_speed_ratio"] = _power_grade_adjusted_speed_ratio(
            lap["avg_power"],
            lap["grade_adjusted_speed"],
        )
        lap["efficiency_grade_adjusted_speed_ratio"] = _efficiency_grade_adjusted_speed_ratio(
            lap_efficiency,
            lap["grade_adjusted_speed"],
        )
        laps.append(lap)
    return laps


@router.get("/status", response_model=StravaStatus)
def strava_status(db: Session = Depends(get_db)) -> StravaStatus:
    missing = []
    if not _client_id(db):
        missing.append("STRAVA_CLIENT_ID")
    if not _client_secret(db):
        missing.append("STRAVA_CLIENT_SECRET")
    return StravaStatus(
        configured=not missing,
        connected=bool(_setting(db, "strava_refresh_token")),
        auth_url=_auth_url(db),
        missing=missing,
    )


@router.patch("/credentials", response_model=StravaStatus)
def update_strava_credentials(payload: StravaCredentialsUpdate, db: Session = Depends(get_db)) -> StravaStatus:
    _set_setting(db, "strava_client_id", payload.client_id.strip())
    _set_setting(db, "strava_client_secret", payload.client_secret.strip())
    db.commit()
    return strava_status(db)


@router.get("/connect")
def connect_strava(db: Session = Depends(get_db)) -> RedirectResponse:
    auth_url = _auth_url(db)
    if not auth_url or not _client_secret(db):
        raise HTTPException(status_code=400, detail="STRAVA_CLIENT_ID/STRAVA_CLIENT_SECRET manquants")
    return RedirectResponse(auth_url)


@router.get("/callback")
def strava_callback(code: str | None = None, db: Session = Depends(get_db)) -> HTMLResponse:
    if not code:
        raise HTTPException(status_code=400, detail="Code Strava manquant")
    client_id = _client_id(db)
    client_secret = _client_secret(db)
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail="STRAVA_CLIENT_ID/STRAVA_CLIENT_SECRET manquants")

    payload = _json_request(
        STRAVA_TOKEN_URL,
        method="POST",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    _store_token_response(db, payload)
    db.commit()
    return HTMLResponse(
        "<!doctype html><title>Strava connecte</title>"
        "<body style='font-family: sans-serif; padding: 2rem'>"
        "<h1>Strava connecte</h1><p>Tu peux fermer cette fenetre et relancer l'import.</p>"
        "</body>"
    )


@router.post("/import", response_model=StravaImportResult)
def import_strava(payload: StravaImportRequest, db: Session = Depends(get_db)) -> StravaImportResult:
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="La date de fin doit etre apres la date de debut")

    token = _access_token(db)
    after = _date_timestamp(payload.start_date)
    before = _date_timestamp(payload.end_date, end_of_day=True)
    warnings: list[str] = []
    imported_ids: list[int] = []
    page = 1

    while True:
        query = urlencode({"after": after, "before": before, "page": page, "per_page": 100})
        activities = _json_request(f"{STRAVA_API_BASE}/athlete/activities?{query}", token=token)
        if not activities:
            break

        for activity in activities:
            sport = str(activity.get("sport_type") or activity.get("type") or "").lower()
            if "run" not in sport:
                warnings.append(f"{activity.get('name', activity.get('id'))}: ignoree, sport={sport or '-'}")
                continue

            started_at = _parse_datetime(activity.get("start_date_local") or activity.get("start_date"))
            duplicate = _activity_duplicate(db, int(activity["id"]), started_at, activity.get("distance"))
            if duplicate is not None:
                warnings.append(
                    f"{activity.get('name', activity['id'])}: deja presente "
                    f"(activite locale #{duplicate.id}, {duplicate.started_at})"
                )
                continue

            detailed = _json_request(f"{STRAVA_API_BASE}/activities/{activity['id']}", token=token)
            stream_query = urlencode(
                {
                    "keys": "time,distance,altitude,velocity_smooth,heartrate,cadence,watts,latlng,temp",
                    "key_by_type": "true",
                }
            )
            streams = _stream_map(
                _json_request(f"{STRAVA_API_BASE}/activities/{activity['id']}/streams?{stream_query}", token=token)
            )
            built = _activity_summary_from_strava(detailed or activity, streams, payload.threshold_power)
            built["summary"]["shoe_type"] = payload.shoe_type
            built["summary"]["cycle"] = payload.cycle

            imported = Activity(**built["summary"])
            db.add(imported)
            db.flush()
            db.add_all(Lap(activity_id=imported.id, **lap) for lap in _lap_payloads(detailed or activity, detailed or {}, built["records"]))
            db.add_all(Record(activity_id=imported.id, **record) for record in built["records"])
            imported_ids.append(imported.id)

        if len(activities) < 100:
            break
        page += 1

    recalculate_training_history(db)
    db.commit()
    return StravaImportResult(
        imported_count=len(imported_ids),
        skipped_count=len(warnings),
        warnings=warnings,
        imported_activity_ids=imported_ids,
    )
