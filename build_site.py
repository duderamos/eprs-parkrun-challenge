#!/usr/bin/env python3
"""Build the challenge's web page from the files in data/.

Usage:
    ./build_site.py            # writes site/index.html
    ./build_site.py -o out/    # somewhere else

Reads:
  data/rounds.csv              round,event,date,rank_by for each round run so far
                               (rank_by: percent, or seconds for Kedron)
  data/roundN-points.csv       round_points.py output for each round
  data/handicaps-roundN.csv    the handicaps used for each round (plus the
                               next round's, if it's been worked out)
"""

import argparse
import csv
import html
import os
from datetime import date, datetime, timezone

from standings import MIN_ROUNDS_TO_WIN, ROUNDS_COUNTED, standings

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RESULTS_URL = "https://www.parkrun.com.au/{event}/results/{date}/"

STYLE = """
:root {
  --bg: #f7f7f5; --card: #ffffff; --text: #1d1d1b; --muted: #6b6b66;
  --line: #e4e4df; --accent: #1f6f5c; --accent-soft: #e3f1ec;
  --gold: #b8860b; --good: #1f6f5c; --bad: #a23b2a; --stripe: #f0f7f3;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #141413; --card: #1d1d1b; --text: #ecece8; --muted: #9a9a93;
    --line: #2f2f2c; --accent: #6cc4a8; --accent-soft: #1f3530;
    --gold: #e0b44c; --good: #6cc4a8; --bad: #e58a78; --stripe: #1b2925;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
main { max-width: 920px; margin: 0 auto; padding: 32px 16px 64px; }
header h1 { margin: 0; font-size: 26px; letter-spacing: -0.01em; }
header p { margin: 4px 0 0; color: var(--muted); }
nav { display: flex; gap: 16px; flex-wrap: wrap; margin: 20px 0 8px; }
nav a { color: var(--accent); text-decoration: none; font-weight: 600; }
h2 { font-size: 19px; margin: 40px 0 4px; }
h2 + p, .note { color: var(--muted); margin: 0 0 12px; font-size: 14px; }
.card {
  background: var(--card); border: 1px solid var(--line); border-radius: 10px;
  overflow-x: auto;
}
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { padding: 8px 10px; text-align: right; white-space: nowrap; }
th { font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em;
     color: var(--muted); font-weight: 600; border-bottom: 1px solid var(--line); }
td { border-bottom: 1px solid var(--line); }
tr:last-child td { border-bottom: 0; }
tbody tr:nth-child(even) { background: var(--stripe); }
th.name, td.name { text-align: left; width: 100%; }
td.place { font-weight: 700; width: 1%; }
td.total { font-weight: 700; }
tr.podium td.place { color: var(--gold); }
tr.unqualified td { color: var(--muted); }
tr.divider td { background: var(--accent-soft); color: var(--accent); font-size: 12px;
                text-align: left; font-weight: 600; padding: 4px 10px; }
.dropped { text-decoration: line-through; color: var(--muted); }
.zero { color: var(--muted); }
.faster { color: var(--good); }
.slower { color: var(--bad); }
details { margin-top: 12px; }
summary { cursor: pointer; font-weight: 600; padding: 10px 0; }
summary span { color: var(--muted); font-weight: 400; }
.rules { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
         padding: 4px 20px; }
.rules li { margin: 6px 0; }
footer { margin-top: 48px; color: var(--muted); font-size: 13px; }
footer a { color: var(--muted); }
"""


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def fmt_time(secs):
    m, s = divmod(round(secs), 60)
    return f"{m}:{s:02d}"


def fmt_date(iso):
    return date.fromisoformat(iso).strftime("%-d %b %Y")


def esc(value):
    return html.escape(str(value))


def counted_rounds(points):
    """Indices of the rounds that make up a runner's best total."""
    run = sorted((i for i, p in enumerate(points) if p is not None), key=lambda i: -points[i])
    return set(run[:ROUNDS_COUNTED])


def standings_table(rounds, rows):
    head = "".join(f'<th title="{esc(r["event"].title())}">R{r["round"]}</th>' for r in rounds)
    out = [f'<table><thead><tr><th></th><th class="name">Runner</th>{head}'
           f'<th>Rounds</th><th>Best {ROUNDS_COUNTED}</th></tr></thead><tbody>']
    any_qualified = any(r["qualified"] for r in rows)
    for n, r in enumerate(rows):
        if any_qualified and not r["qualified"] and (n == 0 or rows[n - 1]["qualified"]):
            out.append(f'<tr class="divider"><td colspan="{len(rounds) + 4}">'
                       f'Not yet qualified (fewer than {MIN_ROUNDS_TO_WIN} rounds)</td></tr>')
        counted = counted_rounds(r["points"])
        cells = []
        for i, p in enumerate(r["points"]):
            if p is None:
                cells.append('<td class="zero">–</td>')
            elif i in counted:
                cells.append(f"<td>{p}</td>")
            else:
                cells.append(f'<td class="dropped" title="Not in best {ROUNDS_COUNTED}">{p}</td>')
        cls = []
        if r["place"] <= 3 and (r["qualified"] or not any_qualified):
            cls.append("podium")
        if any_qualified and not r["qualified"]:
            cls.append("unqualified")
        out.append(f'<tr class="{" ".join(cls)}"><td class="place">{r["place"]}</td>'
                   f'<td class="name">{esc(r["name"])}</td>{"".join(cells)}'
                   f'<td>{r["rounds_run"]}</td><td class="total">{r["best"]}</td></tr>')
    out.append("</tbody></table>")
    return "".join(out)


def bonus_cell(value):
    return '<td class="zero">0</td>' if value == "0" else f"<td>+{value}</td>"


def rank_note(r):
    if r.get("rank_by") != "seconds":
        return ""
    return ('<p class="note">This round was scored before the percentage rule: '
            'runners were ranked by seconds under their handicap.</p>')


def round_table(points):
    out = ['<table><thead><tr><th></th><th class="name">Runner</th><th>Time</th>'
           '<th>Handicap</th><th>vs handicap</th><th>Place</th><th>Speed</th>'
           '<th>PB</th><th>Age grade</th><th>AG bonus</th><th>Total</th></tr></thead><tbody>']
    for r in points:
        vs = r["vs_baseline"]
        vs_cls = "faster" if vs.startswith("-") else "slower" if vs else ""
        out.append(
            f'<tr><td class="place">{esc(r["place"]) or "–"}</td>'
            f'<td class="name">{esc(r["name"])}</td><td>{esc(r["time"])}</td>'
            f'<td>{esc(r["baseline"])}</td><td class="{vs_cls}">{esc(vs)}</td>'
            f'<td>{r["place_points"]}</td>{bonus_cell(r["speed_bonus"])}{bonus_cell(r["pb_bonus"])}'
            f'<td>{esc(r["age_grade"])}</td>{bonus_cell(r["age_grade_bonus"])}'
            f'<td class="total">{r["total"]}</td></tr>')
    out.append("</tbody></table>")
    return "".join(out)


def handicaps_table(current, start):
    before = {r["parkrun_id"]: float(r["baseline_seconds"]) for r in start}
    out = ['<table><thead><tr><th class="name">Runner</th><th>Round 1</th>'
           '<th>Now</th><th>Change</th></tr></thead><tbody>']
    for r in current:
        secs = float(r["baseline_seconds"])
        first = before.get(r["parkrun_id"], secs)
        # Handicaps only ever get tightened, so any change is a cut.
        change = (f'<td class="faster">−{first - secs:.0f}s</td>' if secs != first
                  else '<td class="zero">–</td>')
        out.append(f'<tr><td class="name">{esc(r["name"])}</td><td>{fmt_time(first)}</td>'
                   f'<td>{fmt_time(secs)}</td>{change}</tr>')
    out.append("</tbody></table>")
    return "".join(out)


def rules():
    return f"""
<div class="rules"><ul>
<li>You race against your own handicap, not each other. Each round your time is
compared to your handicap, and the more you beat it, the higher you place.</li>
<li><b>Points:</b> 1st = 10, 2nd = 8, 3rd = 6, 4th = 5, 5th = 4, 6th = 3, 7th = 2,
everyone else who finishes = 1.</li>
<li><b>Speed bonus:</b> the first 3 EPRS runners across the line get +3, +2, +1.</li>
<li><b>PB bonus:</b> +1 for a course PB. A first run at that course doesn't count.</li>
<li><b>Age-grade bonus:</b> +2 for the highest age grade among EPRS runners who
didn't get a speed bonus.</li>
<li>Your best {ROUNDS_COUNTED} rounds count. Minimum {MIN_ROUNDS_TO_WIN} rounds to win.
Ties are split by the better result in the most recent round.</li>
<li><b>Handicaps</b> are tightened after each round (except Bunya) for anyone who beat
their handicap by more than the median, by half the gap. Nobody gets loosened.</li>
</ul></div>"""


def build():
    rounds = read_csv(os.path.join(DATA, "rounds.csv"))
    points_paths = [os.path.join(DATA, f"round{r['round']}-points.csv") for r in rounds]
    handicaps = {}
    for n in range(1, len(rounds) + 2):
        path = os.path.join(DATA, f"handicaps-round{n}.csv")
        if os.path.exists(path):
            handicaps[n] = read_csv(path)

    latest = rounds[-1]
    title = f"EPRS Parkrun Challenge {rounds[0]['date'][:4]}"
    parts = [f"""<header>
<h1>{title}</h1>
<p>{len(rounds)} round{"s" if len(rounds) != 1 else ""} run · latest:
{esc(latest["event"].title())}, {fmt_date(latest["date"])}</p>
</header>
<nav><a href="#standings">Standings</a><a href="#rounds">Rounds</a>
<a href="#handicaps">Handicaps</a><a href="#rules">Rules</a></nav>

<h2 id="standings">Standings</h2>
<p>Best {ROUNDS_COUNTED} rounds count; at least {MIN_ROUNDS_TO_WIN} rounds needed to win.</p>
<div class="card">{standings_table(rounds, standings(points_paths))}</div>

<h2 id="rounds">Rounds</h2>
<p>Ranked by how far each runner beat their handicap.</p>"""]

    for i, (r, path) in reversed(list(enumerate(zip(rounds, points_paths)))):
        url = RESULTS_URL.format(event=r["event"], date=r["date"])
        open_attr = " open" if i == len(rounds) - 1 else ""
        parts.append(
            f'<details{open_attr}><summary>Round {esc(r["round"])}: {esc(r["event"].title())} '
            f'<span>· {fmt_date(r["date"])} · <a href="{esc(url)}">parkrun results</a></span>'
            f'</summary>{rank_note(r)}<div class="card">{round_table(read_csv(path))}</div></details>')

    upcoming = max(handicaps)
    if upcoming > 1:
        parts.append(
            f'<h2 id="handicaps">Handicaps for round {upcoming}</h2>'
            f'<p>How much each handicap has been tightened since round 1.</p>'
            f'<div class="card">{handicaps_table(handicaps[upcoming], handicaps[1])}</div>')

    parts.append(f'<h2 id="rules">Rules</h2>{rules()}')
    updated = datetime.now(timezone.utc).strftime("%-d %b %Y %H:%M UTC")
    parts.append(f'<footer>Updated {updated} · '
                 f'<a href="https://github.com/duderamos/eprs-parkrun-challenge">Source</a></footer>')

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{STYLE}</style>
</head>
<body><main>
{"".join(parts)}
</main></body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", default="site", help="output directory (default: site)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, "index.html")
    with open(path, "w") as f:
        f.write(build())
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
