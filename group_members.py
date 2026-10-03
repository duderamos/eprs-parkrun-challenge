#!/usr/bin/env python3
"""Build a CSV (id,name) of the parkrunners listed on a parkrun group page.

Usage:
    ./group_members.py > runners.csv
    ./group_members.py https://www.parkrun.com.au/mitchelton/groups/27404/ > runners.csv
    ./group_members.py | ./baseline-avg.py --before 2026-10-04 > baselines.csv
"""

import csv
import re
import sys
import urllib.request
from html.parser import HTMLParser

DEFAULT_URL = "https://www.parkrun.com.au/mitchelton/groups/27404/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class GroupParser(HTMLParser):
    """Collects (id, name) from the parkrunner links in the results table."""

    def __init__(self):
        super().__init__()
        self.members = []
        self._in_table = False
        self._current_id = None
        self._name = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and attrs.get("id") == "results":
            self._in_table = True
        elif self._in_table and tag == "a":
            m = re.search(r"/parkrunner/(\d+)", attrs.get("href") or "")
            if m:
                self._current_id = m.group(1)
                self._name = ""

    def handle_endtag(self, tag):
        if tag == "table":
            self._in_table = False
        elif tag == "a" and self._current_id:
            self.members.append((self._current_id, " ".join(self._name.split())))
            self._current_id = None

    def handle_data(self, data):
        if self._current_id:
            self._name += data


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    p = GroupParser()
    p.feed(fetch(url))

    out = csv.writer(sys.stdout)
    out.writerow(["id", "name"])
    seen = set()
    for rid, name in p.members:
        if rid not in seen:
            seen.add(rid)
            out.writerow([rid, name])
    print(f"{len(seen)} parkrunners found", file=sys.stderr)


if __name__ == "__main__":
    main()
