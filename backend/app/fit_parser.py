import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fitparse import FitFile


SEMICIRCLES = 2**31


def _field_dict(message: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for field in message:
        if field.name:
            data[field.name] = field.value
    return data


def _get(data: dict[str, Any], *names: str) -> Any:
    lowered = {key.lower(): value for key, value in data.items()}
    for name in names:
        if name in data:
            return data[name]
        value = lowered.get(name.lower())
        if value is not None:
            return value
    return None


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _positive_int(value: Any) -> int | None:
    parsed = _int(value)
    return parsed if parsed is not None and parsed > 0 else None


def _str(value: Any) -> str | None:
    return None if value is None else str(value)


def _datetime(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _latlon(value: Any) -> float | None:
    number = _float(value)
    if number is None:
        return None
    if abs(number) > 180:
        return number * 180 / SEMICIRCLES
    return number


def _avg_speed(distance: Any, timer_time: Any, explicit_speed: Any = None) -> float | None:
    parsed_speed = _float(explicit_speed)
    if parsed_speed and parsed_speed > 0:
        return parsed_speed

    parsed_distance = _float(distance)
    parsed_timer_time = _float(timer_time)
    if parsed_distance is None or parsed_timer_time is None or parsed_timer_time <= 0:
        return None
    return parsed_distance / parsed_timer_time


def _avg_int(values: list[int | None]) -> int | None:
    clean_values = [value for value in values if value is not None and value > 0]
    if not clean_values:
        return None
    return round(sum(clean_values) / len(clean_values))


def _max_int(values: list[int | None]) -> int | None:
    clean_values = [value for value in values if value is not None and value > 0]
    return max(clean_values) if clean_values else None


def _normalized_power(values: list[int | None], window_size: int = 30) -> int | None:
    clean_values = [value if value is not None and value > 0 else 0 for value in values]
    if len(clean_values) < window_size:
        return _avg_int(values)

    rolling_averages = [
        sum(clean_values[index - window_size : index]) / window_size
        for index in range(window_size, len(clean_values) + 1)
    ]
    if not rolling_averages:
        return None

    fourth_power_mean = sum(value**4 for value in rolling_averages) / len(rolling_averages)
    return round(fourth_power_mean**0.25)


def _efficiency_factor(normalized_power: Any, avg_heart_rate: Any) -> float | None:
    power = _float(normalized_power)
    heart_rate = _float(avg_heart_rate)
    if power is None or heart_rate is None or heart_rate <= 0:
        return None
    return round(power / heart_rate, 3)


def _intensity_factor(normalized_power: Any, threshold_power: Any) -> float | None:
    power = _float(normalized_power)
    threshold = _float(threshold_power)
    if power is None or threshold is None or threshold <= 0:
        return None
    return round(power / threshold, 3)


def _training_stress_score(timer_time: Any, normalized_power: Any, threshold_power: Any) -> float | None:
    seconds = _float(timer_time)
    power = _float(normalized_power)
    threshold = _float(threshold_power)
    if seconds is None or power is None or threshold is None or seconds <= 0 or threshold <= 0:
        return None
    intensity = power / threshold
    return round((seconds * power * intensity) / (threshold * 3600) * 100, 1)


def _cadence_from_cycles(total_cycles: Any, timer_time: Any) -> int | None:
    cycles = _float(total_cycles)
    seconds = _float(timer_time)
    if cycles is None or seconds is None or seconds <= 0:
        return None
    return round(cycles / seconds * 60)


def _records_for_lap(lap: dict[str, Any], parsed_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    started_at = _datetime(_get(lap, "start_time", "timestamp"))
    timer_time = _float(_get(lap, "total_timer_time"))
    if started_at is None or timer_time is None or timer_time <= 0:
        return []

    ended_at = started_at.timestamp() + timer_time
    return [
        record
        for record in parsed_records
        if record["timestamp"] is not None and started_at.timestamp() <= record["timestamp"].timestamp() <= ended_at
    ]


def _avg_float(values: list[float | None]) -> float | None:
    clean_values = [value for value in values if value is not None and value > 0]
    if not clean_values:
        return None
    return sum(clean_values) / len(clean_values)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def parse_fit_file(path: Path) -> dict[str, Any]:
    fit_file = FitFile(str(path))
    sessions: list[dict[str, Any]] = []
    laps: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    zones_targets: list[dict[str, Any]] = []

    for message in fit_file.get_messages():
        fields = _field_dict(message)
        if message.name == "session":
            sessions.append(fields)
        elif message.name == "lap":
            laps.append(fields)
        elif message.name == "record":
            records.append(fields)
        elif message.name == "zones_target":
            zones_targets.append(fields)

    session = sessions[-1] if sessions else {}
    zones_target = zones_targets[-1] if zones_targets else {}
    record_cadences = [_positive_int(_get(record, "cadence")) for record in records]
    record_powers = [_positive_int(_get(record, "power", "Power")) for record in records]
    record_ground_contact_times = [
        _float(_get(record, "stance_time", "ground_contact_time")) for record in records
    ]
    avg_power = _positive_int(_get(session, "avg_power")) or _avg_int(record_powers)
    avg_heart_rate = _int(_get(session, "avg_heart_rate"))
    normalized_power = _positive_int(_get(session, "normalized_power")) or _normalized_power(record_powers)
    threshold_power = _positive_int(
        _get(session, "threshold_power", "functional_threshold_power")
    ) or _positive_int(_get(zones_target, "functional_threshold_power", "threshold_power"))
    intensity_factor = _intensity_factor(normalized_power, threshold_power)
    summary = {
        "sport": _str(_get(session, "sport")),
        "sub_sport": _str(_get(session, "sub_sport")),
        "started_at": _datetime(_get(session, "start_time", "timestamp")),
        "total_elapsed_time": _float(_get(session, "total_elapsed_time")),
        "total_timer_time": _float(_get(session, "total_timer_time")),
        "total_distance": _float(_get(session, "total_distance")),
        "avg_speed": _avg_speed(
            _get(session, "total_distance"),
            _get(session, "total_timer_time"),
            _get(session, "avg_speed", "enhanced_avg_speed"),
        ),
        "max_speed": _float(_get(session, "max_speed", "enhanced_max_speed")),
        "avg_heart_rate": avg_heart_rate,
        "max_heart_rate": _int(_get(session, "max_heart_rate")),
        "avg_cadence": (
            _positive_int(_get(session, "avg_cadence"))
            or _cadence_from_cycles(_get(session, "total_cycles"), _get(session, "total_timer_time"))
            or _avg_int(record_cadences)
        ),
        "max_cadence": _positive_int(_get(session, "max_cadence")) or _max_int(record_cadences),
        "avg_power": avg_power,
        "max_power": _positive_int(_get(session, "max_power")) or _max_int(record_powers),
        "normalized_power": normalized_power,
        "threshold_power": threshold_power,
        "intensity_factor": intensity_factor,
        "efficiency_factor": _efficiency_factor(normalized_power, avg_heart_rate),
        "training_stress_score": _training_stress_score(
            _get(session, "total_timer_time"),
            normalized_power,
            threshold_power,
        ),
        "avg_ground_contact_time": (
            _float(_get(session, "avg_stance_time", "avg_ground_contact_time"))
            or _avg_int(record_ground_contact_times)
        ),
        "ascent": _float(_get(session, "total_ascent")),
        "descent": _float(_get(session, "total_descent")),
        "raw_summary": json.dumps({key: _json_safe(value) for key, value in session.items()}, ensure_ascii=True),
    }

    parsed_records = [
        {
            "record_index": index,
            "timestamp": _datetime(_get(record, "timestamp")),
            "distance": _float(_get(record, "distance")),
            "speed": _float(_get(record, "speed", "enhanced_speed")),
            "heart_rate": _int(_get(record, "heart_rate")),
            "cadence": _positive_int(_get(record, "cadence")),
            "power": _positive_int(_get(record, "power", "Power")),
            "ground_contact_time": _float(_get(record, "stance_time", "ground_contact_time")),
            "altitude": _float(_get(record, "altitude", "enhanced_altitude")),
            "latitude": _latlon(_get(record, "position_lat")),
            "longitude": _latlon(_get(record, "position_long")),
            "temperature": _int(_get(record, "temperature")),
        }
        for index, record in enumerate(records, start=1)
    ]

    parsed_laps = []
    for index, lap in enumerate(laps, start=1):
        lap_records = _records_for_lap(lap, parsed_records)
        lap_cadences = [record["cadence"] for record in lap_records]
        lap_powers = [record["power"] for record in lap_records]
        lap_ground_contact_times = [record["ground_contact_time"] for record in lap_records]

        parsed_laps.append(
            {
            "lap_index": index,
            "started_at": _datetime(_get(lap, "start_time", "timestamp")),
            "total_elapsed_time": _float(_get(lap, "total_elapsed_time")),
            "total_timer_time": _float(_get(lap, "total_timer_time")),
            "total_distance": _float(_get(lap, "total_distance")),
            "avg_speed": _avg_speed(
                _get(lap, "total_distance"),
                _get(lap, "total_timer_time"),
                _get(lap, "avg_speed", "enhanced_avg_speed"),
            ),
            "max_speed": _float(_get(lap, "max_speed", "enhanced_max_speed")),
            "avg_heart_rate": _int(_get(lap, "avg_heart_rate")),
            "max_heart_rate": _int(_get(lap, "max_heart_rate")),
            "avg_cadence": _positive_int(_get(lap, "avg_cadence"))
            or _cadence_from_cycles(_get(lap, "total_cycles"), _get(lap, "total_timer_time"))
            or _avg_int(lap_cadences),
            "max_cadence": _positive_int(_get(lap, "max_cadence")) or _max_int(lap_cadences),
            "avg_power": _positive_int(_get(lap, "avg_power", "Lap Power")) or _avg_int(lap_powers),
            "max_power": _positive_int(_get(lap, "max_power")) or _max_int(lap_powers),
            "normalized_power": _positive_int(_get(lap, "normalized_power")) or _normalized_power(lap_powers),
            "avg_ground_contact_time": _float(_get(lap, "avg_stance_time", "avg_ground_contact_time"))
            or _avg_float(lap_ground_contact_times),
            }
        )

    if summary["started_at"] is None and parsed_records:
        summary["started_at"] = parsed_records[0]["timestamp"]

    return {"summary": summary, "laps": parsed_laps, "records": parsed_records}
