from datetime import datetime
from pydantic import BaseModel, ConfigDict
from pydantic import Field


class ActivitySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    is_rest_day: bool = False
    sport: str | None = None
    sub_sport: str | None = None
    session_type: str | None = None
    route_location: str | None = None
    shoe_type: str | None = None
    cycle: str | None = None
    comment: str | None = None
    distance_manually_edited: int | None = None
    started_at: datetime | None = None
    total_elapsed_time: float | None = None
    total_timer_time: float | None = None
    total_distance: float | None = None
    avg_speed: float | None = None
    grade_adjusted_speed: float | None = None
    max_speed: float | None = None
    avg_heart_rate: int | None = None
    max_heart_rate: int | None = None
    avg_cadence: int | None = None
    max_cadence: int | None = None
    avg_power: int | None = None
    max_power: int | None = None
    normalized_power: int | None = None
    threshold_power: int | None = None
    intensity_factor: float | None = None
    efficiency_factor: float | None = None
    power_grade_adjusted_speed_ratio: float | None = None
    efficiency_grade_adjusted_speed_ratio: float | None = None
    training_stress_score: float | None = None
    fitness: float | None = None
    form: float | None = None
    fatigue: float | None = None
    avg_ground_contact_time: float | None = None
    avg_temperature: float | None = None
    ascent: float | None = None
    descent: float | None = None
    created_at: datetime
    lap_count: int = 0
    record_count: int = 0


class ActivityDetail(ActivitySummary):
    raw_summary: str | None = None


class ThresholdPowerUpdate(BaseModel):
    threshold_power: int = Field(ge=1, le=2000)


class ActivityUpdate(BaseModel):
    session_type: str | None = None
    route_location: str | None = None
    shoe_type: str | None = None
    cycle: str | None = None
    comment: str | None = None
    total_distance: float | None = Field(default=None, ge=0)
    threshold_power: int | None = Field(default=None, ge=1, le=2000)


class OptionCreate(BaseModel):
    category: str
    value: str = Field(min_length=1, max_length=200)
    abbreviation: str | None = Field(default=None, max_length=16)


class OptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    value: str
    abbreviation: str | None = None


class CycleOptionRead(BaseModel):
    value: str
    abbreviation: str


class AppConfigRead(BaseModel):
    default_ftp: int
    default_max_hr: int
    default_shoe_type: str | None = None
    default_cycle: str | None = None
    session_types: list[str]
    route_locations: list[str]
    shoe_types: list[str]
    cycles: list[CycleOptionRead]


class AppConfigUpdate(BaseModel):
    default_ftp: int | None = Field(default=None, ge=1, le=2000)
    default_max_hr: int | None = Field(default=None, ge=1, le=250)
    default_shoe_type: str | None = None
    default_cycle: str | None = None


class LapRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lap_index: int
    started_at: datetime | None = None
    total_elapsed_time: float | None = None
    total_timer_time: float | None = None
    total_distance: float | None = None
    avg_speed: float | None = None
    grade_adjusted_speed: float | None = None
    max_speed: float | None = None
    avg_heart_rate: int | None = None
    max_heart_rate: int | None = None
    avg_cadence: int | None = None
    max_cadence: int | None = None
    avg_power: int | None = None
    max_power: int | None = None
    normalized_power: int | None = None
    power_grade_adjusted_speed_ratio: float | None = None
    efficiency_grade_adjusted_speed_ratio: float | None = None
    avg_ground_contact_time: float | None = None
    avg_temperature: float | None = None


class RecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    record_index: int
    timestamp: datetime | None = None
    distance: float | None = None
    speed: float | None = None
    heart_rate: int | None = None
    cadence: int | None = None
    power: int | None = None
    ground_contact_time: float | None = None
    altitude: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    temperature: int | None = None
