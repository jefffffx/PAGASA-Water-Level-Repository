import re
import requests
import pandas as pd
import urllib3
from datetime import datetime, timezone, timedelta
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://pasig-marikina-tullahanffws.pagasa.dost.gov.ph/water/table_list.do"
DATA_DIR = Path("data")
PH = timezone(timedelta(hours=8))

READINGS = [("wl", "wl"), ("wl_30m", "wl30m"), ("wl_1h", "wl1h"), ("wl_2h", "wl2h")]


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
    csv_path.parent.mkdir(exist_ok=True)
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
            cells = [str(r["station"])]
            for col, _key in READINGS:
                cells.append(fmt(r[col], r[col + "_flagged"]))
            cells += [fmt(r["alert"]), fmt(r["alarm"]), fmt(r["critical"])]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    now = datetime.now(PH)
    obs_time = now.replace(minute=0, second=0, microsecond=0)

    month = obs_time.strftime("%Y-%m")            # e.g. 2026-10
    csv_path = DATA_DIR / f"{month}.csv"
    report_path = DATA_DIR / f"{month}_report.md"

    new_df = fetch(obs_time, now)
    df = save_csv(new_df, csv_path)
    write_report(df, report_path, obs_time.strftime("%B %Y"))
    print(f"Saved {len(new_df)} stations for {obs_time:%Y-%m-%d %H:%M} into {csv_path.name}")


if __name__ == "__main__":
    main()
