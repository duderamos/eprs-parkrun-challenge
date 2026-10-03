#!/usr/bin/env python3
"""Look up the results of a list of parkrunners at one parkrun event.

Usage:
    cat ids.txt | ./event_results.py kedron 2026-10-03 > round1.csv
    ./group_members.py | ./event_results.py mitchelton 2026-10-10
    ./event_results.py --sheet kedron 2026-10-03 < baselines.csv   # for the spreadsheet

Input (stdin): one parkrunner per line. Accepts "7949802", "A7949802", a full
profile URL or an "id,name" CSV line. Blank lines and lines starting with #
are ignored. Output rows keep the input order; runners who didn't run at
that event get an empty row.

--sheet prints the layout of the round tab in the spreadsheet instead:
Name, Age grade, Parkrun time (as HH:MM:SS so Sheets reads it as a
duration), PB? ("Yes" for a course PB; a first timer doesn't count).
Names for runners who didn't run are taken from the second column of the
input when it is a CSV (e.g. baselines.csv).
"""

import argparse
import csv
import re
import sys
import urllib.request
from datetime import date
from html.parser import HTMLParser

RESULTS_URL = "https://www.parkrun.com.au/{event}/results/{date}/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class ResultsParser(HTMLParser):
    """Collects one dict per finisher row of the results table, keyed by parkrunner id."""

    def __init__(self):
        super().__init__()
        self.results = {}
        self._row = None
        self._in_time_td = False
        self._time = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        cls = attrs.get("class") or ""
        if tag == "tr" and "Results-table-row" in cls:
            self._row = attrs
        elif self._row is None:
            return
        elif tag == "a" and "id" not in self._row:
            m = re.search(r"/parkrunner/(\d+)", attrs.get("href") or "")
            if m:
                self._row["id"] = m.group(1)
        elif tag == "td" and "Results-table-td--time" in cls:
            self._in_time_td = True
        elif self._in_time_td and tag == "div" and "compact" in cls:
            self._time = ""

    def handle_endtag(self, tag):
        if self._row is None:
            return
        if tag == "div" and self._time is not None:
            self._row["time"] = self._time.strip()
            self._time = None
        elif tag == "td":
            self._in_time_td = False
        elif tag == "tr":
            if "id" in self._row:  # "Unknown" finishers have no parkrunner link
                self.results[self._row["id"]] = self._row
            self._row = None

    def handle_data(self, data):
        if self._time is not None:
            self._time += data


def parse_id(line):
    m = re.search(r"(\d+)", line)
    return m.group(1) if m else None


def to_seconds(t):
    secs = 0
    for p in t.split(":"):
        secs = secs * 60 + int(p)
    return secs


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def sheet_time(t):
    secs = to_seconds(t)
    return f"{secs // 3600:02d}:{secs % 3600 // 60:02d}:{secs % 60:02d}"


def write_sheet(out, ids, input_names, results):
    out.writerow(["Name", "Age grade", "Parkrun time", "PB?"])
    for rid in ids:
        r = results.get(rid)
        if r is None:
            out.writerow([input_names.get(rid, rid), "", "", ""])
            continue
        time_str = r.get("time", "")
        out.writerow([
            r.get("data-name", ""), r.get("data-agegrade", ""),
            sheet_time(time_str) if time_str else "",
            "Yes" if r.get("data-achievement") == "New PB!" else "",
        ])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("event", help="parkrun event name as in the URL, e.g. kedron")
    ap.add_argument("date", type=date.fromisoformat, help="event date, YYYY-MM-DD")
    ap.add_argument("--sheet", action="store_true", help="spreadsheet layout (see above)")
    args = ap.parse_args()

    ids = []
    input_names = {}
    for line in sys.stdin:
        line = line.strip()
        if line and not line.startswith("#"):
            rid = parse_id(line)
            if rid:
                ids.append(rid)
                fields = next(csv.reader([line]))
                if len(fields) > 1:
                    input_names[rid] = fields[1]
            elif not line.startswith(("id,", "parkrun_id,")):
                print(f"skipping unrecognised line: {line!r}", file=sys.stderr)

    url = RESULTS_URL.format(event=args.event, date=args.date.isoformat())
    p = ResultsParser()
    p.feed(fetch(url))
    if not p.results:
        sys.exit(f"no results found at {url}")

    out = csv.writer(sys.stdout)
    if args.sheet:
        write_sheet(out, ids, input_names, p.results)
        found = sum(rid in p.results for rid in ids)
        print(f"{found}/{len(ids)} runners found at {url}", file=sys.stderr)
        return

    out.writerow([
        "parkrun_id", "name", "position", "time", "time_seconds",
        "age_grade", "age_group", "gender", "achievement",
    ])
    found = 0
    for rid in ids:
        r = p.results.get(rid)
        if r is None:
            out.writerow([rid, "", "", "", "", "", "", "", ""])
            continue
        found += 1
        time_str = r.get("time", "")
        out.writerow([
            rid, r.get("data-name", ""), r.get("data-position", ""), time_str,
            to_seconds(time_str) if time_str else "",
            r.get("data-agegrade", ""), r.get("data-agegroup", ""),
            r.get("data-gender", ""), r.get("data-achievement", ""),
        ])
    print(f"{found}/{len(ids)} runners found at {url}", file=sys.stderr)


if __name__ == "__main__":
    main()
