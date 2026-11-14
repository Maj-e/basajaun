from datetime import datetime, timezone
import pandas as pd

CONFIDENCE_COLORS = {
    "high": "#d7301f",
    "medium": "#fc8d59",
    "low": "#fdcc8a",
}

SENSOR_BORDERS = {
    "MODIS": "#ffffff",
    "VIIRS": "#222222",
}

MODIS_SATELLITE_MAP = {
    "T": "Terra",
    "TERRA": "Terra",
    "A": "Aqua",
    "AQUA": "Aqua",
}

MODIS_SATELLITE_CODES = {
    "Terra": "T",
    "Aqua": "A",
}

VIIRS_SATELLITE_MAP = {
    "N": "S-NPP",
    "SNPP": "S-NPP",
    "S-NPP": "S-NPP",
    "N20": "NOAA-20",
    "1": "NOAA-20",
    "NOAA-20": "NOAA-20",
    "NOAA20": "NOAA-20",
    "N21": "NOAA-21",
    "2": "NOAA-21",
    "NOAA-21": "NOAA-21",
    "NOAA21": "NOAA-21",
}

VIIRS_SATELLITE_CODES = {
    "S-NPP": "N",
    "NOAA-20": "N20",
    "NOAA-21": "N21",
}

CONTRACT_COLUMNS = [
    "id",
    "lat",
    "lon",
    "sensor",
    "satellite",
    "timestamp_utc",
    "date",
    "t",
    "confidence",
    "frp",
    "brightness_k",
    "day_night",
    "resolution_m",
    "detected_by",
    "fire_id",
    "color",
    "radius",
    "border",
]


def parse_datetime(acq_date: str, acq_time: int | float | str) -> datetime:
    """Convert FIRMS acq_date ('YYYY-MM-DD') and acq_time (e.g., 742 -> '0742') to UTC datetime."""
    clean_date = str(acq_date).strip()
    padded_time = str(int(float(acq_time))).zfill(4)
    dt = datetime.strptime(f"{clean_date} {padded_time}", "%Y-%m-%d %H%M")
    return dt.replace(tzinfo=timezone.utc)


def calculate_radius(frp: float) -> float:
    """Interpolate circle radius between 3 and 16 px based on FRP (0 to 500 MW)."""
    clamped_frp = max(0.0, min(500.0, float(frp)))
    if clamped_frp <= 50.0:
        return round(3.0 + (clamped_frp / 50.0) * 5.0, 1)
    return round(8.0 + ((clamped_frp - 50.0) / 450.0) * 8.0, 1)


def _normalize_modis_confidence(value: int | float | str) -> str:
    score = float(value)
    if score < 30:
        return "low"
    if score < 80:
        return "medium"
    return "high"


def _normalize_viirs_confidence(value: str) -> str:
    label = str(value).strip().lower()
    if label in ("l", "low"):
        return "low"
    if label in ("n", "nominal"):
        return "medium"
    if label in ("h", "high"):
        return "high"
    raise ValueError(f"Unknown VIIRS confidence value: {value!r}")


def normalize_modis(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a raw MODIS FIRMS DataFrame into the English data contract schema."""
    if df.empty:
        return pd.DataFrame(columns=CONTRACT_COLUMNS)

    records = []
    for _, row in df.iterrows():
        dt = parse_datetime(row["acq_date"], row["acq_time"])
        date_str = dt.strftime("%Y-%m-%d")
        hhmm = dt.strftime("%H%M")

        raw_sat = str(row["satellite"]).strip().upper()
        satellite_name = MODIS_SATELLITE_MAP.get(raw_sat, str(row["satellite"]).strip())
        satellite_code = MODIS_SATELLITE_CODES.get(satellite_name, raw_sat)

        lat = round(float(row["latitude"]), 4)
        lon = round(float(row["longitude"]), 4)
        confidence = _normalize_modis_confidence(row["confidence"])
        frp = round(float(row["frp"]), 1)
        brightness_k = round(float(row["brightness"]), 1)
        day_night = str(row["daynight"]).strip().upper()

        hotspot_id = f"MODIS_{satellite_code}_{date_str.replace('-', '')}_{hhmm}_{lat}_{lon}"

        records.append({
            "id": hotspot_id,
            "lat": lat,
            "lon": lon,
            "sensor": "MODIS",
            "satellite": satellite_name,
            "timestamp_utc": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date": date_str,
            "t": round(dt.timestamp() / 3600.0, 2),
            "confidence": confidence,
            "frp": frp,
            "brightness_k": brightness_k,
            "day_night": day_night,
            "resolution_m": 1000,
            "detected_by": ["MODIS"],
            "fire_id": None,
            "color": CONFIDENCE_COLORS[confidence],
            "radius": calculate_radius(frp),
            "border": SENSOR_BORDERS["MODIS"],
        })

    return pd.DataFrame(records, columns=CONTRACT_COLUMNS)


def normalize_viirs(df: pd.DataFrame, satellite: str | None = None) -> pd.DataFrame:
    """
    Normalize a raw VIIRS FIRMS DataFrame into the English data contract schema.
    If `satellite` is explicitly provided (e.g., 'NOAA-20'), it overrides the CSV column.
    """
    if df.empty:
        return pd.DataFrame(columns=CONTRACT_COLUMNS)

    records = []
    for _, row in df.iterrows():
        dt = parse_datetime(row["acq_date"], row["acq_time"])
        date_str = dt.strftime("%Y-%m-%d")
        hhmm = dt.strftime("%H%M")

        raw_sat = str(satellite if satellite is not None else row["satellite"]).strip().upper()
        satellite_name = VIIRS_SATELLITE_MAP.get(raw_sat, raw_sat)
        satellite_code = VIIRS_SATELLITE_CODES.get(satellite_name, raw_sat)

        lat = round(float(row["latitude"]), 4)
        lon = round(float(row["longitude"]), 4)
        confidence = _normalize_viirs_confidence(row["confidence"])
        frp = round(float(row["frp"]), 1)
        brightness_k = round(float(row["bright_ti4"]), 1)
        day_night = str(row["daynight"]).strip().upper()

        hotspot_id = f"VIIRS_{satellite_code}_{date_str.replace('-', '')}_{hhmm}_{lat}_{lon}"

        records.append({
            "id": hotspot_id,
            "lat": lat,
            "lon": lon,
            "sensor": "VIIRS",
            "satellite": satellite_name,
            "timestamp_utc": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date": date_str,
            "t": round(dt.timestamp() / 3600.0, 2),
            "confidence": confidence,
            "frp": frp,
            "brightness_k": brightness_k,
            "day_night": day_night,
            "resolution_m": 375,
            "detected_by": ["VIIRS"],
            "fire_id": None,
            "color": CONFIDENCE_COLORS[confidence],
            "radius": calculate_radius(frp),
            "border": SENSOR_BORDERS["VIIRS"],
        })

    return pd.DataFrame(records, columns=CONTRACT_COLUMNS)


# Backward-compatible aliases in case other pipeline scripts import TODO names
parse_fecha = parse_datetime
normalizar_modis = normalize_modis
normalizar_viirs = normalize_viirs