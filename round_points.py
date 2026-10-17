#!/usr/bin/env python3
"""Calculate the EPRS handicap points for one round.

Usage:
    ./round_points.py baselines.csv round2.csv > round2_points.csv
    ./round_points.py --rank-by seconds baselines.csv round1.csv   # Kedron only

  baselines.csv   parkrun_id + baseline_seconds per runner (the agreed handicaps)
  roundN.csv      output of event_results.py for the round

Rules:
  * Handicap: each finisher's time is compared to their baseline as a
    percentage, (time - baseline) / baseline. Lowest wins.
    Round 1 (Kedron) was consolidated before this rule, ranking by seconds
    under the baseline instead: --rank-by seconds reproduces it.
  * Place points: 10, 8, 6, 5, 4, 3, 2, then 1 for every other finisher.
  * Speed bonus: first 3 runners across the line get +3, +2, +1.
  * PB bonus: +1 for a course PB ("New PB!"). A first run at that course
    ("First Timer!") doesn't count.
  * Age-grade bonus: +2 for the highest age grade among finishers without a
    speed bonus (shared if tied).
  * Tied runners share the higher place's points.
"""

import argparse
import csv
import sys

PLACE_POINTS = [10, 8, 6, 5, 4, 3, 2]
OTHER_FINISHER_POINTS = 1
SPEED_BONUS = [3, 2, 1]
PB_BONUS = 1
AGE_GRADE_BONUS = 2


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load_baselines(path):
    baselines = {}
    for row in read_csv(path):
        if row.get("baseline_seconds"):
            baselines[row["parkrun_id"]] = float(row["baseline_seconds"])
    return baselines


def load_finishers(path):
    return [r for r in read_csv(path) if r.get("time_seconds")]


def handicap(row, baselines, rank_by="percent"):
    """Difference vs baseline; negative means faster than usual.

    A fraction of the baseline, or plain seconds with rank_by="seconds".
    """
    base = baselines[row["parkrun_id"]]
    diff = int(row["time_seconds"]) - base
    return diff if rank_by == "seconds" else diff / base


def age_grade(row):
    return float(row["age_grade"].rstrip("%") or 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("baselines")
    ap.add_argument("results")
    ap.add_argument("--rank-by", choices=["percent", "seconds"], default="percent",
                    help="how to compare times to the baseline (default: percent; "
                         "seconds only for Kedron, scored under the old rule)")
    args = ap.parse_args()
    vs = lambda r: handicap(r, baselines, args.rank_by)

    baselines = load_baselines(args.baselines)
    finishers = load_finishers(args.results)

    ranked = []
    for r in finishers:
        if r["parkrun_id"] not in baselines:
            print(f"{r['parkrun_id']} ({r['name']}): no baseline, gets bonuses only",
                  file=sys.stderr)
            continue
        ranked.append(r)

    ranked.sort(key=vs)

    # Standard competition ranking: a tie shares the higher place.
    places = {}
    for i, r in enumerate(ranked):
        if i and vs(r) == vs(ranked[i - 1]):
            places[r["parkrun_id"]] = places[ranked[i - 1]["parkrun_id"]]
        else:
            places[r["parkrun_id"]] = i + 1

    speed = {}
    # Bonuses consider every finisher, including anyone without a baseline.
    for r, bonus in zip(sorted(finishers, key=lambda r: int(r["position"])), SPEED_BONUS):
        speed[r["parkrun_id"]] = bonus

    eligible = [r for r in finishers if r["parkrun_id"] not in speed and r["age_grade"]]
    top_grade = max((age_grade(r) for r in eligible), default=None)
    age_bonus = {r["parkrun_id"] for r in eligible if age_grade(r) == top_grade}

    out = csv.writer(sys.stdout)
    out.writerow([
        "place", "parkrun_id", "name", "position", "time", "baseline",
        "vs_baseline", "place_points", "speed_bonus", "pb_bonus", "age_grade",
        "age_grade_bonus", "total",
    ])
    unranked = [r for r in finishers if r["parkrun_id"] not in places]
    for r in ranked + unranked:
        rid = r["parkrun_id"]
        place = places.get(rid)
        if place is None:
            place_pts, base_str, vs_str = 0, "", ""
        else:
            place_pts = PLACE_POINTS[place - 1] if place <= len(PLACE_POINTS) else OTHER_FINISHER_POINTS
            base = round(baselines[rid])
            base_str = f"{base // 60}:{base % 60:02d}"
            vs_str = (f"{vs(r):+.0f}s" if args.rank_by == "seconds"
                      else f"{vs(r) * 100:+.2f}%")
        speed_pts = speed.get(rid, 0)
        pb_pts = PB_BONUS if r["achievement"] == "New PB!" else 0
        age_pts = AGE_GRADE_BONUS if rid in age_bonus else 0
        out.writerow([
            place or "", rid, r["name"], r["position"], r["time"], base_str,
            vs_str, place_pts, speed_pts, pb_pts,
            r["age_grade"], age_pts, place_pts + speed_pts + pb_pts + age_pts,
        ])


if __name__ == "__main__":
    main()
