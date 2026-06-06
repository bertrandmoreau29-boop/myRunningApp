from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AppSetting, OptionValue
from app.schemas import AppConfigRead, AppConfigUpdate, OptionCreate, OptionRead


router = APIRouter(prefix="/config", tags=["config"])

OPTION_CATEGORIES = {
    "session_type": "session_types",
    "route_location": "route_locations",
    "shoe_type": "shoe_types",
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


@router.get("", response_model=AppConfigRead)
def get_config(db: Session = Depends(get_db)) -> AppConfigRead:
    return AppConfigRead(
        default_ftp=int(_setting(db, "default_ftp", "221")),
        default_shoe_type=_setting(db, "default_shoe_type", ""),
        session_types=_options(db, "session_type"),
        route_locations=_options(db, "route_location"),
        shoe_types=_options(db, "shoe_type"),
    )


@router.patch("", response_model=AppConfigRead)
def update_config(payload: AppConfigUpdate, db: Session = Depends(get_db)) -> AppConfigRead:
    if payload.default_ftp is not None:
        _set_setting(db, "default_ftp", str(payload.default_ftp))
    if payload.default_shoe_type is not None:
        _set_setting(db, "default_shoe_type", payload.default_shoe_type)
    db.commit()
    return get_config(db)


@router.post("/options", response_model=OptionRead)
def add_option(payload: OptionCreate, db: Session = Depends(get_db)) -> OptionRead:
    if payload.category not in OPTION_CATEGORIES:
        raise HTTPException(status_code=400, detail="Categorie inconnue")

    value = payload.value.strip()
    if not value:
        raise HTTPException(status_code=400, detail="Valeur vide")

    existing = db.scalar(
        select(OptionValue)
        .where(OptionValue.category == payload.category, OptionValue.value == value)
        .limit(1)
    )
    if existing is not None:
        return OptionRead.model_validate(existing)

    option = OptionValue(category=payload.category, value=value)
    db.add(option)
    db.commit()
    db.refresh(option)
    return OptionRead.model_validate(option)
