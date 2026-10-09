# Progress

[`transcript.csv`](transcript.csv) is your transcript: one row per course, created by
`plan/build_plan.py` and never overwritten after that. Fill it in as you go.

| Column | What to enter |
| --- | --- |
| `planned_start`, `planned_end` | From the plan; leave as is |
| `actual_start`, `actual_end` | The real dates |
| `status` | `not started`, `in progress`, `passed`, `test-out`, `retake` |
| `exam_score` | Percent on the timed final (pass at 70) |
| `build_link`, `memo_link` | Links to the build and the memo |
| `notes` | Anything an admissions reader should know, e.g. a for-credit version you took |

The elective rows `E1`–`E5` are placeholders until you choose a track; rename them to the course
codes you take.
