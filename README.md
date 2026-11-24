# PAGASA Water Level Repository

An automatically updated archive of hourly water level readings from the PAGASA Pasig-Marikina-Tullahan Flood Forecasting and Warning System (FFWS), kept for QCDRRMO - EOC (Quezon City).

- **Source:** https://pasig-marikina-tullahanffws.pagasa.dost.gov.ph (Water Level > Table)
- **Coverage:** March 8, 2024 to present (the earliest date available on the PAGASA page)
- **Frequency:** one reading per station per hour, plus the readings 30 minutes, 1 hour and 2 hours earlier
- **Time zone:** all times are Philippine Standard Time (UTC+8)

The data belongs to PAGASA. This repository only stores a copy for monitoring and analysis.

## What is in this repository

| Path | What it is |
|---|---|
| `data/YEARLY_SIMPLE/YYYY.csv` | **The simple files** (folder `data/YEARLY_SIMPLE/`). One file per year with four columns (`datetime`, `station`, `agency`, `water level`), laid out like the PAGASA table. Use these in Excel or Google Sheets and for dashboards. |
| `data/MONTHLY_DETAILED/YYYY-MM.csv` | Detailed raw data for one month: also has the station ID, the readings 30 minutes, 1 hour and 2 hours earlier, the warning levels and the fetch time. The yearly files are built from these. |
| `data/MONTHLY_DETAILED/YYYY-MM_report.md` | The same month as a readable report, with one table per hour (newest first) headed "PAGASA Water Level as of (date and time) (weekday)". |
| `fetch_water_level.py` | Fetches the latest readings and saves them. Run every hour by GitHub Actions. |
| `backfill.py` | Fetches past hours for a date range. Run manually. |
| `build_yearly.py` | Rebuilds the yearly files from the monthly files. Run manually when needed. |
| `.github/workflows/fetch.yml` | Schedules the hourly update. |
| `.github/workflows/backfill.yml` | Lets you run the backfill from the Actions tab. |
| `.github/workflows/build-yearly.yml` | Lets you rebuild the yearly files from the Actions tab. |

## How the data is collected

The PAGASA page loads its table from a request to `/water/table_list.do`. The script sends the same request with a single form field, `ymdhm`, the time to look up in the format `YYYYMMDDHHMM`, and receives the stations as JSON.
 
1. **Hourly update.** `fetch.yml` runs at minute 20 of every hour. Each run saves the current hour and also refreshes the previous hour, because the most recent reading can still be revised for several minutes after it is published.
2. **Saving.** New rows are added to the month's CSV. If an hour is already saved, it is replaced by the newer fetch, so there are no duplicate hours. The month's report is then rebuilt from the CSV.
3. **Monthly files.** The month comes from the reading's date, so a new pair of files starts on the 1st of each month and earlier months are left untouched.
4. **Yearly files.** After saving, the script rebuilds the year's file in `data/YEARLY_SIMPLE/` from that year's monthly files. If this step fails, the run still saves the monthly data and prints a warning. The yearly files can be rebuilt at any time.
5. **Commit.** The workflow commits the changed files to `main` ("Update water level data").

## CSV columns

| Column | Meaning |
|---|---|
| `observed_at` | The hour the reading is for (`YYYY-MM-DD HH:MM`) |
| `fetched_at` | When the script actually saved it |
| `obscd` | Station code |
| `station` | Station name |
| `agency_type` | `001` or `002`. Stations with `002` are the ones the PAGASA page labels `[MMDA]`; reports add that label. |
| `wl` | Current water level, in meters (EL.m, as shown on the page) |
| `wl_30m`, `wl_1h`, `wl_2h` | Water level 30 minutes, 1 hour and 2 hours before `observed_at` |
| `wl_flagged`, `wl_30m_flagged`, `wl_1h_flagged`, `wl_2h_flagged` | `True` if PAGASA marked that reading with `(*)` |
| `alert`, `alarm`, `critical` | The station's warning thresholds, where defined |

In the reports, values are shown the way the PAGASA page shows them (two decimals, `(*)` where flagged, `-` where empty).

## Using the data

- **In Excel:** open a monthly CSV directly. Sort or filter by `observed_at` and `station`.
- **In Python:**

  ```python
  import pandas as pd
  df = pd.read_csv("data/2026-10.csv")
  angono = df[df["station"] == "Angono"]
  ```

- **Across several months:** read each `data/YYYY-MM.csv` and join them with `pd.concat`.
- **Checking a value:** set the PAGASA page's Search Time to the same hour as `observed_at`. Do not compare against the page's current time.

## Running a backfill

1. Go to the **Actions** tab, choose **Backfill archive**, and click **Run workflow**.
2. Enter a start date and an end date (`YYYY-MM-DD`).
3. Leave **overwrite** unticked to fetch only hours that are not saved yet, or tick it to re-fetch and replace hours that are already saved.

Notes:

- The run fetches about 1,000 to 1,500 hours per 30 minutes. GitHub stops a job after 6 hours, so use ranges of about 12 months or less.
- If a run stops early, run it again with the same dates. Saved hours are skipped, and the run stops by itself after 5 hours in a row cannot be fetched (for example when the PAGASA site is down).
- Hours for which PAGASA returns no data are skipped and not saved.
- Do not shorten the delay between requests in `backfill.py`. It keeps the load on PAGASA's server low.

## Known limitations

- **Readings may be revised.** A reading can change in the minutes after it is first published. The hourly job re-fetches the previous hour to catch this, but values saved at other times can differ slightly from what the page shows later. When checking against the website, set its Search Time to the same hour as `observed_at`.
- **Meaning of `(*)`.** The mark is copied as published. Its exact meaning has not been confirmed with PAGASA, so treat flagged values with care until it is.
- **Scheduled runs are not exact.** GitHub can start scheduled runs several minutes late and sometimes skips them. `fetched_at` shows when a row was really saved, and hours that were missed can be filled with a backfill.
- **Source outages.** The PAGASA site was unreachable from the evening of November 10, 2026 until the night of November 13 to early November 14, 2026. The hours from that period were re-fetched with a backfill and are complete.
- **Certificate verification is turned off.** The server does not send its full certificate chain, so Python refuses the connection unless `verify=False` is used. The data is public and read-only, but this means the script cannot prove it is talking to the real PAGASA server.
- **Some stations show constant or zero values** for long periods and are marked with `(*)`. This may mean the sensor is offline or the data is stale, but it has not been confirmed with PAGASA. Check these readings before using them.
- **The station list can change.** The archive and the live data both show 20 stations per hour, matching the PAGASA table. If PAGASA adds or removes a station, it will appear only in the months it existed.

## If the data stops updating

1. Open the **Actions** tab and check the latest **Fetch PAGASA water level** runs.
2. If they fail with a timeout, the PAGASA site is probably down. It will recover by itself, and the missed hours can be filled with a backfill afterwards.
3. If they fail with a `KeyError`, a JSON error or an empty result, PAGASA may have changed the page. Check the request in your browser (F12 > Network > `table_list.do`) and update `fetch_water_level.py`.
4. GitHub emails the repository owner when a scheduled run fails.

## Editing the scripts safely

A mistake on `main` breaks the hourly job, so:

1. Create a branch (for example `test`) and make the change there.
2. Run the workflow from that branch (choose it under **Use workflow from**), then merge into `main` once it works.
3. When changing a Python file, paste the whole file instead of a single line. Python is strict about indentation, and a one-line edit once broke the hourly job.
4. Avoid committing around minute 20 of the hour, since a scheduled run may start at that time.
5. After any change, open the run's log and look for `Saved ... stations` lines. A green check alone does not prove data was saved.

## Requirements (if running locally)

Python 3.12 with `requests` and `pandas`:

```
pip install requests pandas
python fetch_water_level.py
python backfill.py 2024-03-08 2024-03-08
```
