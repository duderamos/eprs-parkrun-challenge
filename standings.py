#!/usr/bin/env python3
"""Build the season standings from the round points files.

Usage:
    ./standings.py round1-points.csv round2-points.csv round3-points.csv > standings.csv

Each file is the output of round_points.py, given in round order (oldest
first). Column headers for the rounds are taken from the file names.

Rules:
  * Your best 4 rounds count.
  * Minimum 3 rounds to win: runners who have run enough rounds
    ("qualified") are listed first, then everyone else.
  * Ties are split by the better result in the most recent round, then the
    round before that, and so on. A tie that still can't be split shares
    the place.
"""

import csv
import os
import sys

ROUNDS_COUNTED = 4
MIN_ROUNDS_TO_WIN = 3


def round_label(path):
    name = os.path.splitext(os.path.basename(path))[0]
    return name.removesuffix("-points").removesuffix("_points")


def main():
    paths = sys.argv[1:]
    if not paths or any(p in ("-h", "--help") for p in paths):
        sys.exit(__doc__)

    labels = [round_label(p) for p in paths]
    names = {}
    points = {}  # parkrun_id -> {round index: total}
    for i, path in enumerate(paths):
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                rid = row["parkrun_id"]
                names[rid] = row["name"]
                points.setdefault(rid, {})[i] = int(row["total"])

    def best(rid):
        return sum(sorted(points[rid].values(), reverse=True)[:ROUNDS_COUNTED])

    def qualified(rid):
        return len(points[rid]) >= MIN_ROUNDS_TO_WIN

    # Qualified runners first. Tie-break: points in the most recent round
    # first, a missed round counts as 0.
    def sort_key(rid):
        recent_first = [points[rid].get(i, 0) for i in reversed(range(len(paths)))]
        return [not qualified(rid), -best(rid)] + [-p for p in recent_first]

    ranked = sorted(points, key=sort_key)

    out = csv.writer(sys.stdout)
    out.writerow(["place", "parkrun_id", "name", *labels, "rounds_run",
                  f"best_{ROUNDS_COUNTED}", "qualified"])
    place = 0
    for n, rid in enumerate(ranked):
        if not n or sort_key(rid) != sort_key(ranked[n - 1]):
            place = n + 1
        rounds = points[rid]
        out.writerow([
            place, rid, names[rid],
            *[rounds.get(i, "") for i in range(len(paths))],
            len(rounds), best(rid),
            "yes" if qualified(rid) else "no",
        ])


if __name__ == "__main__":
    main()
