import re
import sys
import requests
import pandas as pd
import urllib3
from datetime import datetime, timezone, timedelta
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://pasig-marikina-tullahanffws.pagasa.dost.gov.ph/water/table_list.do"
DATA_DIR = Path("data")
DETAILED_DIR = DATA_DIR / "MONTHLY_DETAILED"   # monthly csv + report files
YEARLY_DIR = DATA_DIR / "YEARLY_SIMPLE"        # simple yearly csv files
PH = timezone(timedelta(hours=8))

READINGS = [("wl", "wl"), ("wl_30m", "wl30m"), ("wl_1h", "wl1h"), ("wl_2h", "wl2h")]

# Agency codes in the PAGASA table, named as the website labels them
AGENCIES = {"001": "PAGASA", "002": "MMDA"}

# True:  water level is written as on the website, e.g. 12.10(*)
# False: water level is written as a plain number, e.g. 12.10
SHOW_STAR = True


def parse(v):
    """'12.10(*)' -> (12.10, True); '27.30' -> (27.30, False); None -> (None, False)"""
    if v is None:
        return None, False
    flagged = "(*)" in str(v)
    num = re.sub(r"[^\d.\-]", "", str(v))
    return (float(num) if num else None), flagged


def fmt(v, flagged=False):
    """Show a value like the website: 2 decimals, (*) if flagged, '-' if empty."""
    if v is None or pd.isna(v) or v == "":
        return "-"
    return f"{float(v):.2f}" + ("(*)" if str(flagged) == "True" else "")


def fetch(obs_time, now):
    ymdhm = obs_time.strftime("%Y%m%d%H%M")
    r = requests.post(
        URL,
        data={"ymdhm": ymdhm},
        timeout=30,
        verify=False,
        headers={"User-Agent": "QCDRRMO-EOC-logger"},
    )
    r.raise_for_status()

    rows = []
    for s in r.json():
        row = {
            "observed_at": obs_time.strftime("%Y-%m-%d %H:%M"),
            "fetched_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "obscd": s.get("obscd"),
            "station": s.get("obsnm"),
            "agency_type": s.get("agctype"),
        }
        for col, key in READINGS:
            num, flag = parse(s.get(key))
            row[col] = num
            row[col + "_flagged"] = flag
        row["alert"] = s.get("alertwl")
        row["alarm"] = s.get("alarmwl")
        row["critical"] = s.get("criticalwl")
        rows.append(row)
    return pd.DataFrame(rows)


def save_csv(new_df, csv_path):
    """Add the new hour. If that hour is already saved, replace it with the newer fetch."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if csv_path.exists():
        old = pd.read_csv(csv_path, dtype=str)
        old = old[old["observed_at"] != new_df["observed_at"].iloc[0]]
        df = pd.concat([old, new_df], ignore_index=True)
    else:
        df = new_df
    df.to_csv(csv_path, index=False)
    return df


def write_report(df, report_path, month_label):
    lines = [f"# PAGASA Water Level Report - {month_label}", "",
             "Values are shown as on the PAGASA website. (*) is the mark PAGASA puts on a reading.", ""]
    for observed_at in sorted(df["observed_at"].unique(), reverse=True):  # newest first
        block = df[df["observed_at"] == observed_at]
        t = datetime.strptime(observed_at, "%Y-%m-%d %H:%M")
        lines.append(f"## PAGASA Water Level as of {t.strftime('%B %d, %Y %I:%M %p')} ({t.strftime('%A')})")
        lines.append("")
        lines.append("| Station | Current | -30 min | -1 hr | -2 hr | Alert | Alarm | Critical |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for _, r in block.iterrows():
            name = str(r["station"])
            if str(r["agency_type"]) == "002":
                name += " [MMDA]"
            cells = [name]
            for col, _key in READINGS:
                cells.append(fmt(r[col], r[col + "_flagged"]))
            cells += [fmt(r["alert"]), fmt(r["alarm"]), fmt(r["critical"])]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def agency_name(code):
    code = str(code).strip()
    return AGENCIES.get(code, code)


def level_text(v, flagged):
    """Water level as text with 2 decimals, plus (*) when the website shows it."""
    if v is None or pd.isna(v) or v == "":
        return ""
    text = f"{float(v):.2f}"
    if SHOW_STAR and str(flagged) == "True":
        text += "(*)"
    return text


def simple_rows(raw):
    """Turn a detailed monthly table into: datetime, station, agency, water level."""
    return pd.DataFrame({
        "datetime": raw["observed_at"],
        "station": raw["station"],
        "agency": raw["agency_type"].map(agency_name),
        "water level": [level_text(v, f) for v, f in zip(raw["wl"], raw["wl_flagged"])],
    })


def build_yearly(year):
    """Rebuild data/YEARLY_SIMPLE/<year>.csv from the monthly files. Returns the number of rows."""
    files = sorted(DETAILED_DIR.glob(f"{year}-??.csv"))
    if not files:
        return 0
    frames = [simple_rows(pd.read_csv(f, dtype=str)) for f in files]
    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset=["datetime", "station"], keep="last")
    out = out.sort_values(["datetime", "station"]).reset_index(drop=True)
    YEARLY_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(YEARLY_DIR / f"{year}.csv", index=False)
    return len(out)


def main():
    now = datetime.now(PH)
    this_hour = now.replace(minute=0, second=0, microsecond=0)
    failed = False
    years = set()

    # Also re-fetch the previous hour, whose reading should be final by now.
    for obs_time in (this_hour - timedelta(hours=1), this_hour):
        month = obs_time.strftime("%Y-%m")
        csv_path = DETAILED_DIR / f"{month}.csv"
        report_path = DETAILED_DIR / f"{month}_report.md"
        try:
            new_df = fetch(obs_time, now)
        except Exception as e:
            print(f"{obs_time:%Y-%m-%d %H:%M} failed: {e}")
            failed = True
            continue
        if new_df.empty or new_df["wl"].isna().all():
            print(f"{obs_time:%Y-%m-%d %H:%M} no data, keeping what is saved")
            continue
        df = save_csv(new_df, csv_path)
        write_report(df, report_path, obs_time.strftime("%B %Y"))
        years.add(obs_time.year)
        print(f"Saved {len(new_df)} stations for {obs_time:%Y-%m-%d %H:%M} into {csv_path.name}")

    # The monthly files are the source of truth, so a problem here must not
    # stop the hour from being saved. The yearly files can be rebuilt any time.
    for year in sorted(years):
        try:
            rows = build_yearly(year)
            print(f"Updated YEARLY_SIMPLE/{year}.csv ({rows} rows)")
        except Exception as e:
            print(f"WARNING: could not update YEARLY_SIMPLE/{year}.csv: {e}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
