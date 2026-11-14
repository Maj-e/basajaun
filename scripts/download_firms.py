import io
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
import pandas as pd
from config import BBOX, END_DATE, FIRMS_MAP_KEY, RAW, START_DATE

BASE_SOURCES = ["MODIS", "VIIRS_SNPP", "VIIRS_NOAA20", "VIIRS_NOAA21"]


def api_source(base_source: str, start: datetime) -> str:
    """Use _NRT for recent data (< 60 days old) and _SP for the historical archive."""
    age_days = (datetime.now(timezone.utc).date() - start.date()).days
    suffix = "NRT" if age_days < 60 else "SP"
    return f"{base_source}_{suffix}"


def download_chunk(source: str, bbox_str: str, days: int, date_str: str) -> pd.DataFrame:
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_MAP_KEY}/{source}/{bbox_str}/{days}/{date_str}"
    print(f"  -> Downloading {source} ({days} days from {date_str})...")
    req = urllib.request.Request(url, headers={"User-Agent": "Ulinautas-SpaceApps/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8").strip()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore").strip()
        print(f"     [HTTP warning {e.code}] {detail[:150]}")
        return pd.DataFrame()

    if not text or "Invalid" in text or "Error" in text:
        print(f"     [Warning] Unexpected response: {text[:120]}")
        return pd.DataFrame()

    return pd.read_csv(io.StringIO(text))


def main():
    if not FIRMS_MAP_KEY:
        print("Error: FIRMS_MAP_KEY is not set in .env or the environment.", file=sys.stderr)
        sys.exit(1)

    RAW.mkdir(parents=True, exist_ok=True)
    west, south, east, north = BBOX
    bbox_str = f"{west},{south},{east},{north}"

    start = datetime.strptime(START_DATE, "%Y-%m-%d")
    end = datetime.strptime(END_DATE, "%Y-%m-%d")
    total_days = (end - start).days + 1

    print(f"BBOX: {bbox_str} | Period: {START_DATE} to {END_DATE} ({total_days} days)")

    for base_source in BASE_SOURCES:
        source = api_source(base_source, start)
        output = RAW / f"{source}_{START_DATE}_{END_DATE}.csv"

        if output.exists() and output.stat().st_size > 100:
            print(f"[OK] Already cached: {output.name}")
            df_total = pd.read_csv(output)
        else:
            chunks = []
            cursor = start
            while cursor <= end:
                remaining = (end - cursor).days + 1
                chunk_days = min(5, remaining)
                df_chunk = download_chunk(source, bbox_str, chunk_days, cursor.strftime("%Y-%m-%d"))
                if not df_chunk.empty:
                    chunks.append(df_chunk)
                cursor += timedelta(days=chunk_days)

            if chunks:
                df_total = pd.concat(chunks, ignore_index=True)
                df_total.to_csv(output, index=False)
                print(f"[SAVED] {output.name} ({len(df_total)} rows)")
            else:
                print(f"[EMPTY] No rows returned for {source}")
                continue

        if "satellite" in df_total.columns and not df_total.empty:
            sats = df_total["satellite"].unique().tolist()
            print(f"   Actual 'satellite' codes in {source}: {sats}")


if __name__ == "__main__":
    main()
