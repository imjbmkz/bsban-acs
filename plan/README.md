# Weekly learning plan

The plan turns the [curriculum](../curriculum/) into a calendar: every week names what to learn,
what to build with it, and what to hand in. It runs from **12 Oct 2026** for 198 weeks at
10 hours a week. Dates, totals and milestones are in [weeks/README.md](weeks/README.md).

| Where | What |
| --- | --- |
| [weeks/](weeks/) | The calendar, one file per year, with a checklist for every week |
| [courses/](courses/) | One page per course, in folders by domain: mathematics, statistics, computer_science, business_and_economics, capstone |
| [assessments.md](assessments.md) | Every course's final exam or assessment, with links |
| [fast-track.md](fast-track.md) | How to test out of courses you already know, and which ones to try |
| [schedule.csv](schedule.csv) | The same calendar as one table, for a spreadsheet or a dashboard |
| [../progress/transcript.csv](../progress/transcript.csv) | Your record of each course: dates, exam score, links |
| [../templates/](../templates/) | Templates for notes, the weekly log, a course README and the business memo |

## How a week works

Each week has two lanes running side by side, about 5 hours each:

- **Lane A — theory:** mathematics and statistics.
- **Lane B — applied:** computer science and business.

Every study week in a lane has two parts, and both are deliverables:

1. **Learn** (about 3 h): watch or read the material, work the problems, check them against the
   solutions, and write one page of notes in your own words.
2. **Apply** (about 2 h): use that week's concept on a real or realistic task and commit the result.

A suggested rhythm, adjust to your work hours:

| Day | Lane A — theory | Lane B — applied |
| --- | --- | --- |
| Mon | 1 h lecture or reading | |
| Tue | | 1 h reading |
| Wed | 1 h problems | |
| Thu | | 1 h start the apply task |
| Sat | 3 h problems, notes, apply task | |
| Sun | | 3 h finish the apply task; 15 min weekly log |

The 9th week of a full course is the **final week**: a timed exam, the finished build and the
one-page business memo. A test-out course takes 3 weeks: two catch-up weeks, then a sign-off week
with evidence. The capstone takes both lanes, all 10 hours, for 15 weeks.

Every 13th week or so is a **review week** with no new material, and the weeks of Holy Week,
Christmas and New Year are breaks.

## Weekly deliverables

| Deliverable | Where it goes | Done when |
| --- | --- | --- |
| Notes | `work/<code>/notes/week-NN.md` ([template](../templates/notes.md)) | One page in your own words, plus the problems you got wrong and why |
| Problem set | Same notes file | Worked and checked against the solutions |
| Apply task | `work/<code>/` | Committed, runs from a clean clone |
| Weekly log | `work/log/YYYY-Www.md` ([template](../templates/weekly-log.md)) | Learned, applied, stuck, next week |

At the end of each course:

| Deliverable | Where it goes | Done when |
| --- | --- | --- |
| Exam | Score in `progress/transcript.csv` | Timed, closed book, at least 70% |
| Build | `work/<code>/build/` with a README ([template](../templates/course-readme.md)) | Tests pass; results reproduce |
| Business memo | `work/<code>/memo.md` ([template](../templates/business-memo.md)) | One page, read by someone who would make that decision |

Keep course work in this repo under `work/`, or in its own repo for larger builds and link it from
the transcript. Commit through pull requests: it is practice for C102 and leaves a clean history.

## Changing the plan

The calendar is generated. Edit the inputs, then rebuild:

```bash
pip install pyyaml
python plan/build_plan.py          # regenerate weeks/, courses/, assessments.md and schedule.csv
python plan/build_plan.py --check  # what CI runs: prerequisites hold and files are current
```

- **Start later, or reschedule after falling behind:** change `start_date` in [config.yaml](config.yaml)
  (it must be a Monday) and list the courses you have finished under `completed`.
- **Choose an elective track** at the end of Level 2: set `track` to `A`, `B` or `C`.
- **Fast-track courses you already know:** list them under `fast_track` and set `share_lanes: true`.
  Each becomes a diagnostic, the build and the memo. See [fast-track.md](fast-track.md).
- **Change a course's weekly units:** edit [data/](data/). Each unit is one week.
- **Change the order:** reorder `lane_a` / `lane_b`. A course never starts before its prerequisites
  finish: the lane takes the next ready course, or stays free that week.

The generator never overwrites `progress/transcript.csv` once it exists.
