# Fast track

**Test first, then skip what you already know.** A fast-tracked course takes 3 weeks instead of 9:

1. **Diagnostic (week 1):** take the course's final assessment cold: timed, closed book.
   Links for every course are in [assessments.md](assessments.md).
2. **Project (week 2):** do the course build, and review only the units you missed.
3. **Wrap-up (week 3):** finish the build and write the business memo.

Score **70% or more** on the diagnostic and the course counts. The build and the memo are never
skipped: they are your evidence for admissions and your portfolio.

**Below 70%,** switch to the full course:

1. Remove the course from `fast_track` in [config.yaml](config.yaml).
2. Add the courses you have already finished to `completed`.
3. Set `start_date` to the coming Monday and rebuild.

**Or test everything up front.** Sit the diagnostics for all your candidates in your first few
weeks, then put only the ones you passed in `fast_track`. Then nothing needs rescheduling later.

## How to use it

In [config.yaml](config.yaml), list the courses and rebuild:

```yaml
fast_track: [M101, S101, B101, B102, B103, B201, B203, C202, C203]
share_lanes: true
```

```bash
python plan/build_plan.py
```

`share_lanes: true` matters once you fast-track. Most fast-track candidates are in Lane B, which
then runs out of work; with sharing, a free Lane B picks up the next ready math or statistics
course instead of sitting idle. That means two theory courses at once, so expect heavier weeks.

Already finished something outside this plan, like a for-credit course? Put it under `completed`
instead; it disappears from the calendar.

## Recommended candidates

Based on your background: six years of data engineering, consulting work, part-time analyst work
and a BSBA in marketing.

| Course | Why it's a candidate | Diagnostic |
| --- | --- | --- |
| M101 Precalculus | Placement only; skip if the course challenge goes well | [Khan Academy Precalculus course challenge](https://www.khanacademy.org/math/precalculus) |
| S101 Intro Statistics | Daily analyst work covers most of it | [Khan Academy Statistics and probability course challenge](https://www.khanacademy.org/math/statistics-probability) |
| B101 Microeconomics | Covered in your BSBA | [MIT 14.01SC final with solutions](https://ocw.mit.edu/courses/14-01sc-principles-of-microeconomics-fall-2011/) |
| B102 Financial Accounting | Covered in your BSBA | [OpenStax Principles of Accounting Vol. 1, end-of-chapter questions](https://open.umn.edu/opentextbooks/textbooks/principles-of-accounting-volume-1-financial-accounting) |
| B103 Problem Solving & Communication | Consulting is your full-time job | [Timed case rubric](../templates/assessment-rubrics.md#timed-case) |
| B201 Macroeconomics | Covered in your BSBA | [MIT 14.02 exams with solutions](https://ocw.mit.edu/courses/14-02-principles-of-macroeconomics-spring-2014/pages/exams) |
| B203 Marketing Analytics | Your BSBA major, plus analyst work | [Timed case rubric](../templates/assessment-rubrics.md#timed-case) |
| C202 Database Internals | You tune Spark and Delta daily; this checks the theory underneath | [CMU 15-445 homework with solutions](https://15445.courses.cs.cmu.edu/fall2024/assignments.html) |
| C203 Systems & OS | Cluster sizing and profiling are part of your job | [OSTEP chapter homework](https://pages.cs.wisc.edu/~remzi/OSTEP/) |
| C201 Data Structures & Algorithms *(optional)* | Try it if you practise coding interviews; it's core for a CS master's, so only skip with a strong score | [Princeton COS 226 past exams](https://www.cs.princeton.edu/courses/archive/fall13/cos226/exams.php) |

C101, C103 and C301 are already short test-outs (3 weeks each).

## Don't fast-track these

- **Every math and statistics course from M102 on.** Calculus, linear algebra, probability and
  mathematical statistics are what master's admissions check first, and they are new to you. Take
  them in full; their timed finals are the proof.
- **C102 Software Engineering Practices.** CI/CD is a gap you named; the full course closes it.
- **C302 Data Products & MLOps.** New material, and its build is a portfolio piece.
- **The capstone.**

## What it saves

Starting 12 Oct 2026, 10 hours a week, track undecided:

| Scenario | Weeks | Level 1 done | Level 2 done | Level 3 done | Program done |
| --- | --- | --- | --- | --- | --- |
| No fast track (current plan) | 198 | Aug 2027 | Oct 2028 | Jun 2029 | Jul 2030 |
| Recommended candidates | 175 | Apr 2027 | Jan 2028 | Mar 2029 | Feb 2030 |
| Recommended + `share_lanes` | 171 | Apr 2027 | Jan 2028 | Jan 2029 | Jan 2030 |
| Recommended + C201 + `share_lanes` | 163 | Apr 2027 | Jan 2028 | Jan 2029 | Nov 2029 |

These assume you pass every diagnostic. Each one you don't pass adds about 7 weeks back to its lane.
Level 2, the math and statistics core, finishes about nine months earlier under any fast-track
scenario, which matters most for a master's application.

## Other ways to go faster

- **Take a diagnostic any time.** Even in a full course, if you are ahead by week 5, sit the final
  early; a pass lets you move to the build and memo.
- **Use for-credit versions for the admissions core.** A graded MITx or university course in
  calculus, linear algebra or probability can replace the matching course here; list it under
  `completed` and record it in the transcript.
