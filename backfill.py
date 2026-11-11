import sys
import time
import pandas as pd
from datetime import datetime, timedelta

from fetch_water_level import DATA_DIR, PH, fetch, write_report


def already_saved(month):
    """Hours already stored for this month, so a re-run skips them."""
    path = DATA_DIR / f"{month}.csv"
    if path.exists():
        return set(pd.read_csv(path, dtype=str)["observed_at"])
    return set()


def get_hour(t):
    for attempt in range(3):
        try:
            df = fetch(t, datetime.now(PH))
            if df.empty or df["wl"].isna().all():
                print(f"{t:%Y-%m-%d %H:%M} no data")
                return None
            return df
        except Exception as e:
            print(f"{t:%Y-%m-%d %H:%M} attempt {attempt + 1} failed: {e}")
            time.sleep(5)
    return None


def flush(month, frames):
    """Write one month's new hours into its CSV and report."""
    if month is None or not frames:
        return
    DATA_DIR.mkdir(exist_ok=True)
    csv_path = DATA_DIR / f"{month}.csv"
    new_df = pd.concat(frames, ignore_index=True)
    if csv_path.exists():
        old = pd.read_csv(csv_path, dtype=str)
        old = old[~old["observed_at"].isin(new_df["observed_at"])]
        df = pd.concat([old, new_df], ignore_index=True)
    else:
        df = new_df
    df = df.sort_values(["observed_at", "station"]).reset_index(drop=True)
    df.to_csv(csv_path, index=False)
    label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
    write_report(df, DATA_DIR / f"{month}_report.md", label)
    print(f"Saved {month}: {len(new_df)} new rows")


def main():
    start = datetime.strptime(sys.argv[1], "%Y-%m-%d").replace(tzinfo=PH)
    end = datetime.strptime(sys.argv[2], "%Y-%m-%d").replace(hour=23, tzinfo=PH)
    last_done = datetime.now(PH).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    end = min(end, last_done)  # never go past the last completed hour

    frames, current_month, done = [], None, set()
    t = start
    while t <= end:
        month = t.strftime("%Y-%m")
        if month != current_month:
            flush(current_month, frames)
            current_month, frames = month, []
            done = already_saved(month)
        if t.strftime("%Y-%m-%d %H:%M") not in done:
            df = get_hour(t)
            if df is not None:
                frames.append(df)
            time.sleep(0.5)  # be gentle with PAGASA's server
        t += timedelta(hours=1)
    flush(current_month, frames)


if __name__ == "__main__":
    main()
