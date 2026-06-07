from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AppSetting, OptionValue
from app.schemas import AppConfigRead, AppConfigUpdate, CycleOptionRead, OptionCreate, OptionRead


router = APIRouter(prefix="/config", tags=["config"])

OPTION_CATEGORIES = {
    "session_type": "session_types",
    "route_location": "route_locations",
    "shoe_type": "shoe_types",
    "cycle": "cycles",
}


def _setting(db: Session, key: str, default: str = "") -> str:
    value = db.get(AppSetting, key)
    return value.value if value else default


def _set_setting(db: Session, key: str, value: str) -> None:
    setting = db.get(AppSetting, key)
    if setting is None:
        db.add(AppSetting(key=key, value=value))
    else:
        setting.value = value


def _options(db: Session, category: str) -> list[str]:
    return list(
        db.scalars(
            select(OptionValue.value)
            .where(OptionValue.category == category)
            .order_by(OptionValue.value)
        )
    )


def _cycle_options(db: Session) -> list[CycleOptionRead]:
    options = db.scalars(
        select(OptionValue)
        .where(OptionValue.category == "cycle")
        .order_by(OptionValue.value)
    ).all()
    return [
        CycleOptionRead(value=option.value, abbreviation=(option.abbreviation or option.value[:3]).upper())
        for option in options
    ]


@router.get("", response_model=AppConfigRead)
def get_config(db: Session = Depends(get_db)) -> AppConfigRead:
    return AppConfigRead(
        default_ftp=int(_setting(db, "default_ftp", "221")),
        default_max_hr=int(_setting(db, "default_max_hr", "176")),
        default_shoe_type=_setting(db, "default_shoe_type", ""),
        default_cycle=_setting(db, "default_cycle", "Prepa_marathon_Lille_2026"),
        session_types=_options(db, "session_type"),
        route_locations=_options(db, "route_location"),
        shoe_types=_options(db, "shoe_type"),
        cycles=_cycle_options(db),
    )


@router.patch("", response_model=AppConfigRead)
def update_config(payload: AppConfigUpdate, db: Session = Depends(get_db)) -> AppConfigRead:
    if payload.default_ftp is not None:
        _set_setting(db, "default_ftp", str(payload.default_ftp))
    if payload.default_max_hr is not None:
        _set_setting(db, "default_max_hr", str(payload.default_max_hr))
    if payload.default_shoe_type is not None:
        _set_setting(db, "default_shoe_type", payload.default_shoe_type)
    if payload.default_cycle is not None:
        _set_setting(db, "default_cycle", payload.default_cycle)
    db.commit()
    return get_config(db)


@router.post("/options", response_model=OptionRead)
def add_option(payload: OptionCreate, db: Session = Depends(get_db)) -> OptionRead:
    if payload.category not in OPTION_CATEGORIES:
        raise HTTPException(status_code=400, detail="Categorie inconnue")

    value = payload.value.strip()
    if not value:
        raise HTTPException(status_code=400, detail="Valeur vide")
    abbreviation = payload.abbreviation.strip().upper() if payload.abbreviation else None
    if payload.category == "cycle" and not abbreviation:
        raise HTTPException(status_code=400, detail="Abreviation obligatoire pour un cycle")

    existing = db.scalar(
        select(OptionValue)
        .where(OptionValue.category == payload.category, OptionValue.value == value)
        .limit(1)
    )
    if existing is not None:
        if abbreviation and not existing.abbreviation:
            existing.abbreviation = abbreviation
            db.commit()
            db.refresh(existing)
        return OptionRead.model_validate(existing)

    option = OptionValue(category=payload.category, value=value, abbreviation=abbreviation)
    db.add(option)
    db.commit()
    db.refresh(option)
    return OptionRead.model_validate(option)
