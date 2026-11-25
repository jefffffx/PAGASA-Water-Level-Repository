# PAGASA Water Level Repository

Hourly water level readings from the PAGASA Pasig-Marikina-Tullahan Flood Forecasting and Warning System (FFWS), archived automatically for QCDRRMO - EOC (Quezon City).

- **Source:** https://pasig-marikina-tullahanffws.pagasa.dost.gov.ph (Water Level > Table)
- **Coverage:** March 8, 2024 (the earliest date on the PAGASA page) to present, one reading per station per hour
- **Time zone:** Philippine Standard Time (UTC+8)

The data belongs to PAGASA. This repository only keeps a copy for monitoring and analysis.

## Where things are

```
data/
├── YEARLY_SIMPLE/       one simple CSV per year (2024.csv, 2025.csv, ...)
└── MONTHLY_DETAILED/    one detailed CSV and one readable report per month
```

| File | Purpose |
|---|---|
| `fetch_water_level.py` | Fetches the latest readings and saves them (runs hourly) |
| `backfill.py` | Fetches past hours for a date range (run manually) |
| `build_yearly.py` | Rebuilds the yearly files from the monthly files (run manually) |
| `.github/workflows/` | `fetch.yml` (hourly update), `backfill.yml`, `build-yearly.yml` |

## Yearly files (`data/YEARLY_SIMPLE/YYYY.csv`)

For Excel, Google Sheets and dashboards. One row per station per hour, oldest first:

| date | time | station | agency | water level |
|---|---|---|---|---|
| 2026-11-19 | 08:00 | Angono | MMDA | 11.36(*) |
| 2026-11-19 | 08:00 | Burgos | PAGASA | 27.21 |

- `date`, `time`: the hour the reading is for (Philippine time, 24-hour clock)
- `agency`: `PAGASA` or `MMDA`, as the PAGASA page lists the station
- `water level`: in meters (EL.m), written as the PAGASA page shows it

A `(*)` means the station is not transmitting and the page is showing its most recent reading, so it is not a new measurement. Those cells are text in Excel, and formulas such as SUM or AVERAGE skip them. For plain numbers only, set `SHOW_STAR = False` in `fetch_water_level.py`, then run **Build yearly files**.

In Python:

```python
import pandas as pd
df = pd.read_csv("data/YEARLY_SIMPLE/2026.csv")
angono = df[df["station"] == "Angono"]
```

## Monthly files (`data/MONTHLY_DETAILED/`)

`YYYY-MM.csv` has the same hours with more detail. `YYYY-MM_report.md` shows the same month as a readable report, one table per hour, newest first. The yearly files are built from the CSVs.

| Column | Meaning |
|---|---|
| `observed_at` | The hour the reading is for |
| `fetched_at` | When the script saved it |
| `obscd` | Station ID in PAGASA's system |
| `station`, `agency_type` | Station name; `001` = PAGASA, `002` = MMDA |
| `wl` | Current water level (EL.m) |
| `wl_30m`, `wl_1h`, `wl_2h` | Water level 30 minutes, 1 hour and 2 hours earlier |
| `wl_flagged`, `wl_30m_flagged`, `wl_1h_flagged`, `wl_2h_flagged` | `True` if the page shows `(*)` for that reading |
| `alert`, `alarm`, `critical` | The station's warning levels, where defined |

## How it works

1. `fetch.yml` runs at minute 20 of every hour. It asks PAGASA's `/water/table_list.do` for the current hour and the previous hour, since the latest reading can still be revised for several minutes.
2. New rows go into the month's CSV. An hour that is already saved is replaced, so there are no duplicates. The month's report is rebuilt.
3. The year's file in `YEARLY_SIMPLE` is rebuilt from that year's monthly files. If this step fails, the monthly data is still saved and the log shows a warning.
4. The workflow commits the changes to `main`.

## Common tasks

- **Backfill:** **Actions > Backfill archive > Run workflow**. Enter a start and end date (`YYYY-MM-DD`). Leave **overwrite** unticked to fetch only missing hours, or tick it to replace saved hours. It handles about 1,000 to 1,500 hours per 30 minutes, so use ranges of 12 months or less (GitHub stops jobs after 6 hours). If a run stops early, run it again with the same dates; saved hours are skipped. It stops by itself after 5 failed hours in a row.
- **Rebuild the yearly files:** **Actions > Build yearly files > Run workflow**. No contact with PAGASA is needed.
- **Check a value:** set the PAGASA page's Search Time to the same date and time as the row, not the page's current time.

## Known limitations

- **Readings can be revised** after first publication, so a value saved earlier may differ slightly from what the page shows later.
- **Hours with no data are skipped.** The PAGASA site was unreachable from the evening of November 10, 2026 to early November 14, 2026; those hours were recovered with a backfill.
- **GitHub schedules are not exact.** Runs can start late or be skipped. Missing hours can be filled with a backfill.
- **Certificate verification is off.** The server does not send its full certificate chain, so the script uses `verify=False`. The data is public and read-only, but the script cannot prove it is talking to the real PAGASA server.
- **The station list can change.** There are currently 20 stations, matching the PAGASA table. A station added or removed later appears only in the months it existed.

## If updates stop

1. Open the **Actions** tab and check the latest **Fetch PAGASA water level** runs. GitHub emails the owner when a scheduled run fails.
2. A timeout means the PAGASA site is probably down. It recovers by itself, and a backfill fills the gap.
3. A `KeyError`, JSON error or empty result means PAGASA may have changed the page. Check the request in the browser (F12 > Network > `table_list.do`) and update `fetch_water_level.py`.

## Editing the scripts safely

- Test on a branch (for example `test`) and run the workflow from it before merging into `main`.
- Paste whole Python files rather than single lines, because a one-line edit once broke the hourly job through an indentation error.
- Avoid committing around minute 20 of the hour.
- After a change, check the run's log for `Saved ... stations` lines. A green check alone does not prove data was saved.

## Running locally

Python 3.12 with `requests` and `pandas`:

```
pip install requests pandas
python fetch_water_level.py
python build_yearly.py
```
