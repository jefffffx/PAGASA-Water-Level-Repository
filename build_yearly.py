import sys

from fetch_water_level import DETAILED_DIR, build_yearly


def main():
    if len(sys.argv) > 1:
        years = [int(y) for y in sys.argv[1:]]
    else:
        years = sorted({int(p.name[:4]) for p in DETAILED_DIR.glob("????-??.csv")})
    if not years:
        sys.exit("No monthly files found in data/MONTHLY_DETAILED")
    for year in years:
        rows = build_yearly(year)
        print(f"Built YEARLY_SIMPLE/{year}.csv: {rows} rows")


if __name__ == "__main__":
    main()
