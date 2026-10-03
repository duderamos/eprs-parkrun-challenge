# eprs-parkrun-challenge

Scripts for running the EPRS (Everton Park Running Squad) parkrun handicap
challenge: pulling runners from parkrun, setting handicaps, fetching each
round's results and scoring them.

## Requirements

Python 3.9+. No packages to install, only the standard library is used.

## Files

| File | What it is |
|---|---|
| `runners.txt` | parkrun IDs of everyone in the challenge, one per line |
| `baselines.csv` | The agreed handicap for each runner (`parkrun_id,name,baseline_seconds,baseline`) |
| `group_members.py` | Lists the members of a parkrun group (club) page |
| `baseline-avg.py` | Handicap suggestion: average of the last 3 parkruns |
| `baseline_fastest.py` | Handicap suggestion: fastest parkrun of a given year |
| `event_results.py` | Fetches the results of the runners at one parkrun event |
| `round_points.py` | Scores a round according to the rules |
| `standings.py` | Season standings from the round scores (best 4 rounds) |

## The rules

You race against your own handicap, not each other. Each round, your time is
compared to your handicap and ranked: the more you beat it, the higher you
place.

- **Points:** 1st = 10, 2nd = 8, 3rd = 6, 4th = 5, 5th = 4, 6th = 3,
  7th = 2, everyone else who finishes = 1.
- **Speed bonus:** the first 3 EPRS runners across the line get +3, +2, +1.
- **PB bonus:** +1 for a course PB. A first run at that course doesn't count.
- **Age-grade bonus:** +2 for the highest age grade among EPRS runners who
  didn't get a speed bonus.
- Your best 4 rounds count. Minimum 3 rounds to win. Ties are split by the
  better result in the most recent round.

## Runner input

Every script that reads runners accepts one per line, in any of these forms:

```
7949802
A7949802
https://www.parkrun.com.au/parkrunner/7949802/
7949802,Eduardo RAMOS
```

Blank lines and lines starting with `#` are ignored, as are CSV header lines.
This means the output of one script can be piped straight into the next.

## Typical workflow

### 1. Get the runners

```sh
./group_members.py > runners.csv
```

Prints `id,name` for everyone on the EPRS group page
(<https://www.parkrun.com.au/mitchelton/groups/27404/>). Pass another group's
URL as an argument to use a different group. Remove anyone who isn't in the
challenge.

### 2. Set the handicaps

The handicaps in `baselines.csv` were agreed by the team (fastest parkrun of
2026 plus 2%, with some adjusted by hand), so this step is already done. The
scripts below help when working out suggestions for new runners or a new
season:

```sh
# Fastest parkrun in 2026, only counting runs before Round 1
./baseline_fastest.py --before 2026-10-03 runners.txt > fastest.csv
./baseline_fastest.py --year 2025 runners.txt > fastest-2025.csv

# Average of the last 3 parkruns before Round 1
./baseline-avg.py --before 2026-10-03 runners.txt > average.csv
```

Both print each runner's run(s) used, so the numbers can be checked, plus
`baseline_seconds` and `baseline`.

If you edit `baselines.csv` by hand, keep the `parkrun_id` and
`baseline_seconds` columns: `round_points.py` uses them.

### 3. Fetch a round's results

The event name is the one in the parkrun URL, e.g. `kedron` for
<https://www.parkrun.com.au/kedron/results/2026-10-03/>.

**For the spreadsheet:**

```sh
./event_results.py --sheet kedron 2026-10-03 < baselines.csv > round1.csv
```

```
Name,Age grade,Parkrun time,PB?
Leo HARRINGTON,,,
Chris FAAST,81.28%,00:17:27,Yes
...
```

Rows follow the order of `baselines.csv` (which matches the spreadsheet), and
runners who didn't run get an empty row. Times are written as `HH:MM:SS` so
Google Sheets reads them as durations. Paste columns A–D into the round's tab.

**For `round_points.py`:**

```sh
./event_results.py kedron 2026-10-03 < runners.txt > round1-results.csv
```

```
parkrun_id,name,position,time,time_seconds,age_grade,age_group,gender,achievement
2651054,Chris FAAST,1,17:27,1047,81.28%,VM45-49,Male,New PB!
```

### 4. Score the round

```sh
./round_points.py baselines.csv round1-results.csv > round1-points.csv
```

Needs the plain `event_results.py` output, not the `--sheet` one. Prints
each finisher's place, how far they were from their handicap and the points
broken down (place, speed, PB, age grade, total).

The script compares times to handicaps as a **percentage**, while the
spreadsheet's Delta column uses **seconds**. The two can rank runners
differently, so pick one and stick to it.

### 5. Update the standings

```sh
./standings.py round1-points.csv round2-points.csv round3-points.csv > standings.csv
```

Give the `round_points.py` outputs in round order, oldest first. The round
columns are named after the files (`round1-points.csv` becomes `round1`).

```
place,parkrun_id,name,round1,round2,round3,rounds_run,best_4,qualified
1,7949802,Eduardo RAMOS,4,4,8,3,16,yes
2,2634230,Jason HARTWICH,11,1,3,3,15,yes
...
6,2651054,Chris FAAST,6,,14,2,20,no
```

- **best_4** adds up each runner's 4 highest round scores.
- **qualified** is `yes` once a runner has run at least 3 rounds. Only
  qualified runners can win, so they're listed first, followed by everyone
  else. Early in the season nobody is qualified yet, so the table is just
  ordered by points.
- **Ties** in best_4 (within each group) are split by points in the most recent round, then the
  round before, and so on. A missed round counts as 0. Runners still tied
  after that share the place.

## Spreadsheet formulas

Each round's tab has the runners in rows 2–40. Columns A–D are pasted from
`event_results.py --sheet`, and E–K are formulas (row 2 shown, fill down):

| Col | Header | Formula |
|---|---|---|
| A | Name | *(pasted)* |
| B | Age grade | *(pasted)* |
| C | Parkrun time | *(pasted)* |
| D | PB? | *(pasted)* |
| E | Delta | `=IF(C2="", "", C2-handicaps!C2)` |
| F | Rank | `=IF(E2="", "", RANK(E2, E$2:E$40, 1))` |
| G | Score | `=IF(F2="", 0, SWITCH(F2, 1, 10, 2, 8, 3, 6, 4, 5, 5, 4, 6, 3, 7, 2, 1))` |
| H | Bonus - Top 3? | `=IF(C2="", 0, IFERROR(CHOOSE(RANK(C2, C$2:C$40, 1), 3, 2, 1), 0))` |
| I | Bonus - PB? | `=IF(D2="Yes", 1, 0)` |
| J | Bonus - Age grade | `=IF(OR(B2="", H2>0), 0, IF(B2=MAXIFS(B$2:B$40, H$2:H$40, 0), 2, 0))` |
| K | Total Score | `=G2+H2+I2+J2` |

For Delta as a percentage instead, use `=IF(C2="", "", C2/handicaps!C2-1)`.

## Notes

- **Be gentle with parkrun.** The site starts refusing requests (HTTP 405)
  after too many in a short time. The baseline scripts wait 1 second between
  runners; use `--delay 3` for big batches. If you get blocked, wait a few
  hours.
- **"First Timer!"** in parkrun's results means the first run *at that
  course*, not the first parkrun ever.
- `baseline-avg.py` reads the "Most Recent parkruns" table, which only shows
  about the last 10 runs, so `--before` can't reach far into the past.
  `baseline_fastest.py` reads the full results history.
