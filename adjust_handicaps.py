#!/usr/bin/env python3
"""Tighten handicaps after a round, for runners who beat the field.

Usage:
    ./adjust_handicaps.py handicaps-round1.csv round1-results.csv > handicaps-round2.csv

  handicaps-roundN.csv   the handicaps used for the round (parkrun_id, name,
                         baseline_seconds, baseline)
  roundN-results.csv     output of event_results.py for the round

Prints the handicaps for the next round, in the same format and order, and
a summary of the changes on stderr.

Rules:
  1. Work out how far each finisher beat their handicap, as a percentage.
  2. Take the median of those percentages across everyone who ran.
  3. Anyone above the median has their handicap tightened by half the gap
     between their result and the median.
  4. Nobody gets loosened.
  5. Changes apply from the next round. Points already won stand.

Don't run this after Bunya: reuse the same handicaps for the next round.
"""

import csv
import statistics
import sys


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def fmt_time(secs):
    h, rem = divmod(round(secs), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def main():
    if len(sys.argv) != 3 or sys.argv[1] in ("-h", "--help"):
        sys.exit(__doc__)
    handicaps = read_csv(sys.argv[1])
    results = read_csv(sys.argv[2])

    old = {h["parkrun_id"]: float(h["baseline_seconds"]) for h in handicaps}

    # How far each finisher beat their handicap, as a fraction (positive = faster).
    beat = {}
    for r in results:
        rid = r["parkrun_id"]
        if r.get("time_seconds") and rid in old:
            beat[rid] = (old[rid] - int(r["time_seconds"])) / old[rid]
    if not beat:
        sys.exit("no finishers with a handicap in the results")

    median = statistics.median(beat.values())
    print(f"median: beat handicap by {median * 100:+.2f}% ({len(beat)} finishers)",
          file=sys.stderr)

    out = csv.writer(sys.stdout)
    out.writerow(["parkrun_id", "name", "baseline_seconds", "baseline"])
    for h in handicaps:
        rid = h["parkrun_id"]
        secs = old[rid]
        if rid in beat and beat[rid] > median:
            adjustment = (beat[rid] - median) / 2
            new = round(secs * (1 - adjustment))
            print(f"  {h['name']}: beat by {beat[rid] * 100:.2f}%, "
                  f"-{adjustment * 100:.2f}%, {fmt_time(secs)} -> {fmt_time(new)}",
                  file=sys.stderr)
            secs = new
        out.writerow([rid, h["name"], round(secs), fmt_time(secs)])


if __name__ == "__main__":
    main()
