from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sport: Mapped[str | None] = mapped_column(String(80))
    sub_sport: Mapped[str | None] = mapped_column(String(80))
    session_type: Mapped[str | None] = mapped_column(String(160))
    route_location: Mapped[str | None] = mapped_column(String(160))
    shoe_type: Mapped[str | None] = mapped_column(String(160))
    cycle: Mapped[str | None] = mapped_column(String(160))
    comment: Mapped[str | None] = mapped_column(Text)
    distance_manually_edited: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    total_elapsed_time: Mapped[float | None] = mapped_column(Float)
    total_timer_time: Mapped[float | None] = mapped_column(Float)
    total_distance: Mapped[float | None] = mapped_column(Float)
    avg_speed: Mapped[float | None] = mapped_column(Float)
    grade_adjusted_speed: Mapped[float | None] = mapped_column(Float)
    max_speed: Mapped[float | None] = mapped_column(Float)
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer)
    max_heart_rate: Mapped[int | None] = mapped_column(Integer)
    avg_cadence: Mapped[int | None] = mapped_column(Integer)
    max_cadence: Mapped[int | None] = mapped_column(Integer)
    avg_power: Mapped[int | None] = mapped_column(Integer)
    max_power: Mapped[int | None] = mapped_column(Integer)
    normalized_power: Mapped[int | None] = mapped_column(Integer)
    threshold_power: Mapped[int | None] = mapped_column(Integer)
    intensity_factor: Mapped[float | None] = mapped_column(Float)
    efficiency_factor: Mapped[float | None] = mapped_column(Float)
    power_grade_adjusted_speed_ratio: Mapped[float | None] = mapped_column(Float)
    efficiency_grade_adjusted_speed_ratio: Mapped[float | None] = mapped_column(Float)
    training_stress_score: Mapped[float | None] = mapped_column(Float)
    fitness: Mapped[float | None] = mapped_column(Float)
    form: Mapped[float | None] = mapped_column(Float)
    fatigue: Mapped[float | None] = mapped_column(Float)
    avg_ground_contact_time: Mapped[float | None] = mapped_column(Float)
    avg_temperature: Mapped[float | None] = mapped_column(Float)
    ascent: Mapped[float | None] = mapped_column(Float)
    descent: Mapped[float | None] = mapped_column(Float)
    raw_summary: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    laps: Mapped[list["Lap"]] = relationship(cascade="all, delete-orphan", back_populates="activity")
    records: Mapped[list["Record"]] = relationship(cascade="all, delete-orphan", back_populates="activity")


class Lap(Base):
    __tablename__ = "laps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), index=True)
    lap_index: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    total_elapsed_time: Mapped[float | None] = mapped_column(Float)
    total_timer_time: Mapped[float | None] = mapped_column(Float)
    total_distance: Mapped[float | None] = mapped_column(Float)
    avg_speed: Mapped[float | None] = mapped_column(Float)
    grade_adjusted_speed: Mapped[float | None] = mapped_column(Float)
    max_speed: Mapped[float | None] = mapped_column(Float)
    avg_heart_rate: Mapped[int | None] = mapped_column(Integer)
    max_heart_rate: Mapped[int | None] = mapped_column(Integer)
    avg_cadence: Mapped[int | None] = mapped_column(Integer)
    max_cadence: Mapped[int | None] = mapped_column(Integer)
    avg_power: Mapped[int | None] = mapped_column(Integer)
    max_power: Mapped[int | None] = mapped_column(Integer)
    normalized_power: Mapped[int | None] = mapped_column(Integer)
    power_grade_adjusted_speed_ratio: Mapped[float | None] = mapped_column(Float)
    efficiency_grade_adjusted_speed_ratio: Mapped[float | None] = mapped_column(Float)
    avg_ground_contact_time: Mapped[float | None] = mapped_column(Float)
    avg_temperature: Mapped[float | None] = mapped_column(Float)

    activity: Mapped[Activity] = relationship(back_populates="laps")


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), index=True)
    record_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    distance: Mapped[float | None] = mapped_column(Float)
    speed: Mapped[float | None] = mapped_column(Float)
    heart_rate: Mapped[int | None] = mapped_column(Integer)
    cadence: Mapped[int | None] = mapped_column(Integer)
    power: Mapped[int | None] = mapped_column(Integer)
    ground_contact_time: Mapped[float | None] = mapped_column(Float)
    altitude: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    temperature: Mapped[int | None] = mapped_column(Integer)

    activity: Mapped[Activity] = relationship(back_populates="records")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class OptionValue(Base):
    __tablename__ = "option_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    abbreviation: Mapped[str | None] = mapped_column(String(16))
