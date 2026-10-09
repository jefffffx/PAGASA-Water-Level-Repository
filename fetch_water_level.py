import re
import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

URL = "https://pasig-marikina-tullahanffws.pagasa.dost.gov.ph/water/table_list.do"
OUT = Path("data/water_level.csv")
PH = timezone(timedelta(hours=8))

def parse(v):
    """'12.10(*)' -> (12.10, True); '27.30' -> (27.30, False); None -> (None, False)"""
    if v is None:
        return None, False
    flagged = "(*)" in str(v)
    num = re.sub(r"[^\d.\-]", "", str(v))
    return (float(num) if num else None), flagged

def main():
    now = datetime.now(PH)
    obs_time = now.replace(minute=(now.minute // 10) * 10, second=0, microsecond=0) 
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
        wl, wl_flag = parse(s.get("wl"))
        rows.append({
            "observed_at": obs_time.strftime("%Y-%m-%d %H:%M"),
            "fetched_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "obscd": s.get("obscd"),
            "station": s.get("obsnm"),
            "agency_type": s.get("agctype"),
            "wl": wl,
            "wl_flagged": wl_flag,
            "wl_30m": parse(s.get("wl30m"))[0],
            "wl_1h": parse(s.get("wl1h"))[0],
            "wl_2h": parse(s.get("wl2h"))[0],
            "alert": s.get("alertwl"),
            "alarm": s.get("alarmwl"),
            "critical": s.get("criticalwl"),
        })

    OUT.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, mode="a", header=not OUT.exists(), index=False)
    print(f"Saved {len(rows)} stations for {ymdhm}")

if __name__ == "__main__":
    main()
