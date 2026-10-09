#!/usr/bin/env python3
"""Build the weekly learning plan from plan/config.yaml and plan/data/*.yaml.

Usage:
    python plan/build_plan.py          # regenerate plan/weeks, plan/courses, plan/assessments.md, plan/schedule.csv
    python plan/build_plan.py --check  # fail if the plan cannot be scheduled or generated files are stale

Generated files are overwritten. progress/transcript.csv is only created when missing,
so your recorded progress is never touched.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import os
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "plan"
WEEKS_PER_YEAR = 52
LANE_NAMES = {"A": "Lane A — theory", "B": "Lane B — applied"}
KIND_NAMES = {"full": "Full course", "test-out": "Test-out", "capstone": "Capstone"}
DOMAINS = {
    "mathematics": "Mathematics",
    "statistics": "Statistics",
    "computer_science": "Computer Science",
    "business_and_economics": "Business & Economics",
    "capstone": "Capstone",
    "track_electives": "Track elective slots",
}
PREFIX_DOMAIN = {"M": "mathematics", "S": "statistics", "C": "computer_science", "B": "business_and_economics", "X": "capstone"}
PASS_MARK = 70


# ---------------------------------------------------------------- data model


@dataclass
class Course:
    code: str
    title: str
    level: int
    lane: str
    kind: str
    prereqs: list[str]
    resources: str = ""
    units: list[dict] = field(default_factory=list)
    build: str = ""
    memo: str = ""
    exam: str = ""
    signoff: str = ""
    assessment: list[dict] = field(default_factory=list)  # [{label, url}]
    domain: str = ""
    options: list[str] = field(default_factory=list)  # for undecided elective slots
    fast: bool = False  # set from config.fast_track

    def __post_init__(self) -> None:
        if not self.domain:
            self.domain = "track_electives" if self.options else PREFIX_DOMAIN[self.code[0]]
        if self.domain not in DOMAINS:
            raise SystemExit(f"{self.code}: unknown domain {self.domain!r}")

    @property
    def path(self) -> str:
        """Path of the course page relative to plan/courses."""
        return f"{self.domain}/{self.code}.md"

    def weeks(self) -> list[dict]:
        """Every week of the course as {'type', 'learn'?, 'apply'?}."""
        if self.fast:
            return [{"type": "diagnostic"}, {"type": "project"}, {"type": "fastfinal"}]
        out = [{"type": "study", **u} for u in self.units]
        if self.kind == "full":
            out.append({"type": "final"})
        elif self.kind == "test-out":
            out.append({"type": "signoff"})
        return out


@dataclass
class Week:
    number: int
    start: dt.date
    kind: str  # content | review | holiday
    note: str = ""
    lanes: dict = field(default_factory=dict)  # lane -> (Course, index) or None

    @property
    def end(self) -> dt.date:
        return self.start + dt.timedelta(days=6)


class PlanError(Exception):
    pass


def load_courses() -> dict[str, Course]:
    courses: dict[str, Course] = {}
    for path in sorted((PLAN / "data").glob("*.yaml")):
        for raw in yaml.safe_load(path.read_text(encoding="utf-8")):
            c = Course(**raw)
            if c.code in courses:
                raise PlanError(f"Duplicate course code {c.code} in {path.name}")
            courses[c.code] = c
    return courses


def apply_fast_track(config: dict, courses: dict[str, Course]) -> None:
    for code in config.get("fast_track") or []:
        if code not in courses:
            raise PlanError(f"fast_track lists {code}, which is not a course")
        if courses[code].kind != "full":
            raise PlanError(f"fast_track lists {code}; only full courses can be fast-tracked")
        courses[code].fast = True


def elective_slots(config: dict, courses: dict[str, Course]) -> list[Course]:
    track = str(config["track"])
    tracks = config["electives"]
    if track in tracks:
        return [courses[c] for c in tracks[track]]
    if track != "undecided":
        raise PlanError(f"track must be one of {', '.join(tracks)} or 'undecided', got {track!r}")
    slots = []
    for i, options in enumerate(zip(*tracks.values()), start=1):
        opts = [courses[o] for o in options]
        units = [
            {"learn": f"Week {k} of your track's elective {i}", "apply": "See the elective's page for this week's task"}
            for k in range(1, max(len(o.units) for o in opts) + 1)
        ]
        slots.append(
            Course(
                code=f"E{i}",
                title=f"Track elective {i}: " + " / ".join(f"{o.code} {o.title}" for o in opts),
                level=4,
                lane="elective",
                kind="full",
                prereqs=sorted({p for o in opts for p in o.prereqs}),
                units=units,
                build="See the chosen elective's page",
                memo="See the chosen elective's page",
                exam="See the chosen elective's page",
                options=list(options),
            )
        )
    return slots


# ---------------------------------------------------------------- calendar


def easter(year: int) -> dt.date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(year, month, day)


def holiday_in(start: dt.date) -> str:
    end = start + dt.timedelta(days=6)
    for year in {start.year, end.year}:
        for day, name in (
            (dt.date(year, 12, 25), "Christmas"),
            (dt.date(year, 1, 1), "New Year"),
            (easter(year), "Holy Week"),
        ):
            if start <= day <= end:
                return name
    return ""


def fmt_range(start: dt.date, end: dt.date) -> str:
    if start.year != end.year:
        return f"{start.day} {start:%b %Y} – {end.day} {end:%b %Y}"
    if start.month != end.month:
        return f"{start.day} {start:%b} – {end.day} {end:%b %Y}"
    return f"{start.day}–{end.day} {end:%b %Y}"


def fmt_date(d: dt.date) -> str:
    return f"{d.day} {d:%b %Y}"


# ---------------------------------------------------------------- scheduler


def schedule(config: dict, courses: dict[str, Course]) -> tuple[list[Week], dict[str, tuple[int, int]]]:
    """Place courses week by week.

    Each lane takes the first course in its queue whose prerequisites have finished. With
    share_lanes, a lane with nothing ready takes the next ready course from the other lane;
    otherwise it is free that week. A lane takes track electives only after its own queue is
    empty. The capstone starts once everything else is done.
    """
    start = config["start_date"]
    if start.weekday() != 0:
        raise PlanError(f"start_date {start} is not a Monday")
    done = set(config.get("completed") or [])
    for code in [*config["lane_a"], *config["lane_b"], *config["capstone"], *done]:
        if code not in courses:
            raise PlanError(f"{code} is in config.yaml but not in plan/data")
    queues = {
        "A": deque(courses[c] for c in config["lane_a"] if c not in done),
        "B": deque(courses[c] for c in config["lane_b"] if c not in done),
    }
    electives = deque(c for c in elective_slots(config, courses) if c.code not in done)
    capstone = deque(courses[c] for c in config["capstone"] if c not in done)

    share = bool(config.get("share_lanes", False))
    other = {"A": "B", "B": "A"}
    current: dict[str, list | None] = {"A": None, "B": None}  # [course, index]
    cap: list | None = None
    span: dict[str, list[int]] = {}  # code -> [first week, last week]
    weeks: list[Week] = []
    since_review = 0
    idle_streak = 0
    n = 0

    def ready(course: Course, week_no: int) -> bool:
        return all(p in done or (p in span and span[p][1] < week_no) for p in course.prereqs)

    def take(queue: deque, week_no: int) -> Course | None:
        for i, course in enumerate(queue):
            if ready(course, week_no):
                del queue[i]
                span[course.code] = [week_no, week_no]
                return course
        return None

    def finished() -> bool:
        return cap is None and not any(current.values()) and not any(queues.values()) and not electives and not capstone

    while not finished():
        n += 1
        wstart = start + dt.timedelta(weeks=n - 1)
        holiday = holiday_in(wstart) if config.get("holiday_breaks", True) else ""
        if holiday:
            weeks.append(Week(n, wstart, "holiday", holiday))
            since_review = 0
            continue
        if since_review >= config["review_after"]:
            weeks.append(Week(n, wstart, "review", "Quarterly review"))
            since_review = 0
            continue

        week = Week(n, wstart, "content")
        if cap is None:
            for lane in ("A", "B"):
                if current[lane] is None:
                    nxt = take(queues[lane], n) if queues[lane] else None
                    if nxt is None and share and queues[other[lane]]:
                        nxt = take(queues[other[lane]], n)  # help the other lane instead of sitting free
                    if nxt is None and not queues[lane]:
                        nxt = take(electives, n)
                    if nxt is not None:
                        current[lane] = [nxt, 0]
            nothing_left = not any(current.values()) and not any(queues.values()) and not electives
            if nothing_left and capstone:
                nxt = take(capstone, n)
                if nxt is not None:
                    cap = [nxt, 0]

        if cap is not None:
            course, idx = cap
            week.lanes = {"both": (course, idx)}
            span[course.code][1] = n
            cap[1] += 1
            if cap[1] == len(course.weeks()):
                cap = None
        else:
            for lane in ("A", "B"):
                slot = current[lane]
                if slot is None:
                    week.lanes[lane] = None
                    continue
                course, idx = slot
                week.lanes[lane] = (course, idx)
                span[course.code][1] = n
                slot[1] += 1
                if slot[1] == len(course.weeks()):
                    current[lane] = None

        if not any(week.lanes.values()):
            idle_streak += 1
            if idle_streak > 2:
                waiting = [c.code for q in (*queues.values(), electives, capstone) for c in q]
                raise PlanError(f"no course can start in week {n}; check prerequisites of: {', '.join(waiting)}")
        else:
            idle_streak = 0
        weeks.append(week)
        since_review += 1
        if n > 600:
            raise PlanError("schedule did not terminate; check config.yaml")

    return weeks, {k: (v[0], v[1]) for k, v in span.items()}


# ---------------------------------------------------------------- rendering helpers


def year_of(week_no: int) -> int:
    return (week_no - 1) // WEEKS_PER_YEAR + 1


def rel(target: str, from_dir: str) -> str:
    """Relative link from a directory under plan/ (e.g. 'weeks', 'courses/statistics') to a plan/ path."""
    return os.path.relpath(target, from_dir).replace(os.sep, "/")


def week_link(week_no: int, from_dir: str) -> str:
    return rel(f"weeks/year-{year_of(week_no)}.md", from_dir) + f"#week-{week_no}"


def course_link(course: Course, from_dir: str) -> str:
    return rel(f"courses/{course.path}", from_dir)


def links_md(course: Course) -> str:
    return " · ".join(f"[{a['label']}]({a['url']})" for a in course.assessment)


def unit_tasks(course: Course, idx: int, milestones: dict, from_dir: str, lookup: dict) -> list[str]:
    w = course.weeks()[idx]
    t = w["type"]
    links = f" — {links_md(course)}" if course.assessment else ""
    if course.options and t == "study":
        opts = " · ".join(f"[{o}]({course_link(lookup[o], from_dir)})" for o in course.options)
        return [f"- [ ] Learn and apply: week {idx + 1} of your elective ({opts})"]
    if t == "study":
        return [f"- [ ] Learn: {w['learn']}", f"- [ ] Apply: {w['apply']}"]
    if t == "diagnostic":
        return [
            f"- [ ] Diagnostic, timed and closed book: {course.exam}{links}",
            f"- [ ] Score ≥ {PASS_MARK}%: stay on the fast track and note the units you were weakest in. "
            f"Below {PASS_MARK}%: switch {course.code} to the full course "
            f"([how]({rel('fast-track.md', from_dir)}#fast-track))",
        ]
    if t == "project":
        return [
            f"- [ ] Build: {course.build}",
            f"- [ ] Review only the weak units from the diagnostic ([course page]({course_link(course, from_dir)}))",
        ]
    if t == "final":
        tasks = [
            f"- [ ] Exam (≥ {PASS_MARK}%): {course.exam}{links}",
            f"- [ ] Build: {course.build}",
            f"- [ ] Business memo: {course.memo}",
            "- [ ] Record the result in `progress/transcript.csv`",
        ]
    elif t == "fastfinal":
        tasks = [
            f"- [ ] Finish the build: {course.build}",
            f"- [ ] Business memo: {course.memo}",
            "- [ ] Record the diagnostic score in `progress/transcript.csv` with status `fast-track`",
        ]
    else:  # signoff
        tasks = [
            f"- [ ] Sign-off evidence: {course.signoff}{links}",
            f"- [ ] Business memo: {course.memo}",
            "- [ ] Record the result in `progress/transcript.csv` as `test-out`",
        ]
    if course.code in milestones:
        tasks.append(f"- [ ] **Milestone:** {milestones[course.code]}")
    return tasks


def short(course: Course, idx: int) -> str:
    t = course.weeks()[idx]["type"]
    label = {
        "final": "final",
        "signoff": "sign-off",
        "diagnostic": "fast track: diagnostic",
        "project": "fast track: project",
        "fastfinal": "fast track: wrap-up",
    }.get(t, f"{idx + 1}/{len(course.weeks())}")
    return f"{course.code} · {label}"


# ---------------------------------------------------------------- pages


def render_year(year: int, weeks: list[Week], milestones: dict, lookup: dict) -> str:
    first, last = weeks[0], weeks[-1]
    lines = [
        f"# Year {year} — weeks {first.number}–{last.number}",
        "",
        f"{fmt_date(first.start)} → {fmt_date(last.end)}. Each week has about 5 hours in Lane A (theory) "
        "and 5 hours in Lane B (applied). Tick the boxes as you go; see [plan/README.md](../README.md) "
        "for the weekly routine and where each deliverable lives.",
        "",
        "| Week | Dates | Lane A — theory | Lane B — applied |",
        "| --- | --- | --- | --- |",
    ]
    for w in weeks:
        if w.kind != "content":
            a = b = f"*{w.note}*"
        elif "both" in w.lanes:
            a = b = short(*w.lanes["both"])
        else:
            a, b = (short(*w.lanes[l]) if w.lanes.get(l) else "*free*" for l in ("A", "B"))
        lines.append(f"| [{w.number}](#week-{w.number}) | {fmt_range(w.start, w.end)} | {a} | {b} |")

    for w in weeks:
        iso = w.start.isocalendar()
        lines += ["", f"## Week {w.number}", "", f"*{fmt_range(w.start, w.end)}*", ""]
        if w.kind == "holiday":
            lines += [
                f"**{w.note} break.** No new material.",
                "",
                "- [ ] Rest",
                "- [ ] Optional: 20 minutes of flashcard review on two days",
            ]
            continue
        if w.kind == "review":
            lines += [
                "**Quarterly review week.** No new material.",
                "",
                "- [ ] Redo the problems you missed in the last 12 weeks",
                "- [ ] Finish any overdue deliverables",
                f"- [ ] Quarterly retrospective in `work/log/review-week-{w.number:03d}.md`",
                "- [ ] Update `progress/transcript.csv`",
            ]
            continue
        if "both" in w.lanes:
            course, idx = w.lanes["both"]
            u = course.weeks()[idx]
            lines += [
                f"**Both lanes — [{course.code} {course.title}]({course_link(course, 'weeks')})** · "
                f"week {idx + 1} of {len(course.weeks())} · about 10 h",
                "",
                f"- [ ] {u['learn']}: {u['apply']}",
            ]
            if idx == len(course.weeks()) - 1 and course.code in milestones:
                lines.append(f"- [ ] **Milestone:** {milestones[course.code]}")
            lines.append("")
        else:
            for lane in ("A", "B"):
                slot = w.lanes.get(lane)
                if not slot:
                    lines += [f"**{LANE_NAMES[lane]} — free.** Use the hours for portfolio work or review.", ""]
                    continue
                course, idx = slot
                fast = " · **fast track**" if course.fast else ""
                lines += [
                    f"**{LANE_NAMES[lane]} — [{course.code} {course.title}]({course_link(course, 'weeks')})** · "
                    f"week {idx + 1} of {len(course.weeks())}{fast}",
                    "",
                    *unit_tasks(course, idx, milestones, "weeks", lookup),
                    "",
                ]
        lines.append(f"- [ ] Weekly log: `work/log/{iso.year}-W{iso.week:02d}.md`")
    return "\n".join(lines) + "\n"


def render_course(course: Course, span, weeks: list[Week], milestones: dict, lookup: dict) -> str:
    here = f"courses/{course.domain}"
    by_no = {w.number: w for w in weeks}
    lane = {"A": "A — theory", "B": "B — applied", "both": "Both lanes", "elective": "Whichever lane is free"}[
        course.lane
    ]
    prereqs = ", ".join(f"[{p}]({course_link(lookup[p], here)})" for p in course.prereqs) or "–"
    kind = KIND_NAMES[course.kind] + (" (fast track)" if course.fast else "")
    if span:
        dates = f"{fmt_date(by_no[span[0]].start)} → {fmt_date(by_no[span[1]].end)}"
        plan_weeks = f"[{span[0]}]({week_link(span[0], here)})–[{span[1]}]({week_link(span[1], here)})"
    else:
        dates = "Not scheduled (completed, or set `track` in plan/config.yaml)"
        plan_weeks = "–"
    folder = "<chosen elective code>" if course.options else course.code
    lines = [
        f"# {course.code} — {course.title}",
        "",
        "| Level | Domain | Lane | Type | Prerequisites | Planned dates | Plan weeks |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        f"| {course.level} | {DOMAINS[course.domain]} | {lane} | {kind} | {prereqs} | {dates} | {plan_weeks} |",
        "",
    ]
    if course.resources:
        lines += [f"**Resources:** {course.resources}", ""]
    if course.options:
        opts = ", ".join(f"[{o}]({course_link(lookup[o], here)})" for o in course.options)
        lines += [f"Choose your track in plan/config.yaml; the options for this slot are {opts}.", ""]
    if course.kind == "full":
        lines += [
            "## Final deliverables",
            "",
            f"- **Exam (50%, pass at {PASS_MARK}%):** {course.exam}",
            f"- **Build (30%):** {course.build} — in `work/{folder}/build/`",
            f"- **Business memo (20%):** {course.memo} — in `work/{folder}/memo.md`",
            "",
        ]
    elif course.kind == "test-out":
        lines += [
            "## Sign-off",
            "",
            f"- **Evidence:** {course.signoff}",
            f"- **Business memo:** {course.memo} — in `work/{folder}/memo.md`",
            "",
        ]
    if course.assessment:
        lines += ["## Assessment", "", "| Assessment | Link |", "| --- | --- |"]
        lines += [f"| {a['label']} | [{a['url'].split('/')[2]}]({a['url']}) |" for a in course.assessment]
        lines.append("")
    if course.fast:
        lines += [
            "## Fast track",
            "",
            f"This course is on the fast track: a timed diagnostic using the assessment above, then the build, "
            f"then the memo, in 3 weeks. Below {PASS_MARK}% on the diagnostic, switch to the full course. "
            "See [the fast-track guide](" + rel("fast-track.md", here) + ").",
            "",
        ]
    elif course.kind == "full" and not course.options:
        lines += [
            "## Fast track",
            "",
            f"Confident in this material? Add `{course.code}` to `fast_track` in plan/config.yaml. The course "
            f"then takes 3 weeks instead of {len(course.units) + 1}: a timed diagnostic using the assessment above, "
            f"the build, then the memo. Below {PASS_MARK}% on the diagnostic, switch to the full course. "
            "See [the fast-track guide](" + rel("fast-track.md", here) + ").",
            "",
        ]
        if course.domain in ("mathematics", "statistics") and course.level >= 1 and course.code not in ("M101", "S101"):
            lines += [
                "Caution: this is part of the math and statistics core that master's admissions check first. "
                "The guide recommends taking it in full; its timed final is your proof.",
                "",
            ]
    if course.code in milestones:
        lines += [f"**Milestone at the end:** {milestones[course.code]}", ""]

    lines += ["## Week by week", "", "| Week | Plan week | Learn | Apply |", "| --- | --- | --- | --- |"]
    plan_numbers = [
        w.number for w in weeks if w.kind == "content" and any(v and v[0].code == course.code for v in w.lanes.values())
    ]
    rows = course.weeks() if course.fast else [{"type": "study", **u} for u in course.units] + (
        [{"type": "final"}] if course.kind == "full" else [{"type": "signoff"}] if course.kind == "test-out" else []
    )
    for i, w in enumerate(rows):
        pw = f"[{plan_numbers[i]}]({week_link(plan_numbers[i], here)})" if i < len(plan_numbers) else "–"
        label = {
            "final": ("**Final week:** timed exam", "Finish the build and the business memo"),
            "signoff": ("**Sign-off week:** collect the evidence", "Write the business memo"),
            "diagnostic": ("**Fast track:** timed diagnostic", "Note your weakest units"),
            "project": ("**Fast track:** review weak units only", "Build"),
            "fastfinal": ("**Fast track:** wrap-up", "Finish the build and the business memo"),
        }.get(w["type"], (w.get("learn", ""), w.get("apply", "")))
        lines.append(f"| {i + 1} | {pw} | {label[0]} | {label[1]} |")
    if course.fast:
        lines += ["", "Full syllabus, for reviewing the units you missed on the diagnostic:", ""]
        lines += [f"{i}. **{u['learn']}** — {u['apply']}" for i, u in enumerate(course.units, start=1)]
    lines += [
        "",
        "Each study week: work the reading or lectures, then the problems, and keep one page of notes in "
        f"`work/{folder}/notes/week-NN.md`. Commit the apply task to `work/{folder}/`.",
    ]
    return "\n".join(lines) + "\n"


def course_order(c: Course, spans) -> tuple:
    return (spans.get(c.code, (999,))[0], c.code)


def render_course_index(courses: dict[str, Course], spans, by_no) -> str:
    lines = [
        "# Course pages",
        "",
        "One page per course, grouped by domain, with planned dates, assessment links and the week-by-week "
        "units. Generated by `plan/build_plan.py`; edit `plan/data/*.yaml` instead of these files.",
        "",
    ]
    for domain, name in DOMAINS.items():
        group = sorted((c for c in courses.values() if c.domain == domain), key=lambda c: course_order(c, spans))
        if not group:
            continue
        lines += [f"## [{name}]({domain}/README.md)", "", "| Code | Course | Level | Type | Start | End |", "| --- | --- | --- | --- | --- | --- |"]
        for c in group:
            s = spans.get(c.code)
            start = fmt_date(by_no[s[0]].start) if s else "–"
            end = fmt_date(by_no[s[1]].end) if s else "–"
            kind = KIND_NAMES[c.kind] + (" (fast track)" if c.fast else "")
            lines.append(f"| [{c.code}]({c.path}) | {c.title} | {c.level} | {kind} | {start} | {end} |")
        lines.append("")
    return "\n".join(lines)


def render_domain_index(domain: str, courses: dict[str, Course], spans, by_no) -> str:
    group = sorted((c for c in courses.values() if c.domain == domain), key=lambda c: course_order(c, spans))
    lines = [f"# {DOMAINS[domain]}", "", "| Code | Course | Level | Type | Start | End |", "| --- | --- | --- | --- | --- | --- |"]
    for c in group:
        s = spans.get(c.code)
        start = fmt_date(by_no[s[0]].start) if s else "–"
        end = fmt_date(by_no[s[1]].end) if s else "–"
        kind = KIND_NAMES[c.kind] + (" (fast track)" if c.fast else "")
        lines.append(f"| [{c.code}]({c.code}.md) | {c.title} | {c.level} | {kind} | {start} | {end} |")
    return "\n".join(lines + ["", "[All courses](../README.md)", ""])


def render_assessments(courses: dict[str, Course]) -> str:
    lines = [
        "# Assessments and final exams",
        "",
        f"Every course's final assessment, with links. Use the same assessment as a timed diagnostic when "
        f"fast-tracking (see [fast-track.md](fast-track.md)); pass mark {PASS_MARK}%. Courses without a public "
        "exam use a rubric in [templates/assessment-rubrics.md](../templates/assessment-rubrics.md).",
        "",
        "Generated from `plan/data/*.yaml`.",
        "",
    ]
    for domain, name in DOMAINS.items():
        group = sorted((c for c in courses.values() if c.domain == domain and not c.options), key=lambda c: c.code)
        if not group:
            continue
        lines += [f"## {name}", "", "| Course | Final assessment | Links |", "| --- | --- | --- |"]
        for c in group:
            what = c.exam or c.signoff or "Graded on the client outcome, the repo and a client testimonial"
            lines.append(f"| [{c.code} {c.title}](courses/{c.path}) | {what} | {links_md(c) or '–'} |")
        lines.append("")
    return "\n".join(lines)


def render_overview(config, weeks: list[Week], spans, courses) -> str:
    content = sum(w.kind == "content" for w in weeks)
    review = sum(w.kind == "review" for w in weeks)
    holiday = sum(w.kind == "holiday" for w in weeks)
    years = year_of(weeks[-1].number)
    by_no = {w.number: w for w in weeks}
    fast = config.get("fast_track") or []
    done = config.get("completed") or []

    def level_end(level: int) -> str:
        ends = [s[1] for code, s in spans.items() if code in courses and courses[code].level == level]
        return f"week {max(ends)} ({fmt_date(by_no[max(ends)].end)})" if ends else "–"

    lines = [
        "# Weekly plan",
        "",
        f"The program runs **{len(weeks)} weeks**, from {fmt_date(weeks[0].start)} to "
        f"{fmt_date(weeks[-1].end)} (about {len(weeks) / 52.18:.1f} years at "
        f"{config['hours_per_week']} hours a week). Elective track: **{config['track']}**. "
        f"Fast-tracked: {', '.join(fast) or 'none'}. Completed before the plan: {', '.join(done) or 'none'}.",
        "",
        "| Year | Weeks | Dates |",
        "| --- | --- | --- |",
    ]
    for y in range(1, years + 1):
        ws = [w for w in weeks if year_of(w.number) == y]
        lines.append(f"| [Year {y}](year-{y}.md) | {ws[0].number}–{ws[-1].number} | {fmt_date(ws[0].start)} → {fmt_date(ws[-1].end)} |")
    lines += [
        "",
        f"{content} study weeks, {review} quarterly review weeks and {holiday} holiday weeks "
        "(Holy Week, Christmas, New Year).",
        "",
        "| Milestone | When |",
        "| --- | --- |",
        f"| Level 1 complete | {level_end(1)} |",
        f"| Level 2 complete | {level_end(2)} |",
        f"| Level 3 complete | {level_end(3)} |",
        f"| Program complete | {level_end(4)} |",
        "",
        "Generated by `plan/build_plan.py`; edit `plan/config.yaml` or `plan/data/*.yaml` and rebuild.",
        "",
    ]
    return "\n".join(lines)


def render_schedule_csv(weeks: list[Week]) -> str:
    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator="\n")
    wr.writerow(
        ["week", "start", "end", "kind", "a_course", "a_week", "a_learn", "a_apply", "b_course", "b_week", "b_learn", "b_apply"]
    )
    fixed = {
        "final": ("Final: exam", "Build and memo"),
        "signoff": ("Sign-off", "Evidence and memo"),
        "diagnostic": ("Fast track: diagnostic", "Note weak units"),
        "project": ("Fast track: review weak units", "Build"),
        "fastfinal": ("Fast track: wrap-up", "Build and memo"),
    }
    for w in weeks:
        row = [w.number, w.start.isoformat(), w.end.isoformat(), w.kind if w.kind == "content" else w.note]
        for lane in ("A", "B"):
            slot = w.lanes.get("both") or w.lanes.get(lane)
            if not slot:
                row += ["", "", "", ""]
                continue
            course, idx = slot
            u = course.weeks()[idx]
            learn, apply = fixed.get(u["type"], (u.get("learn", ""), u.get("apply", "")))
            row += [course.code, idx + 1, learn, apply]
        wr.writerow(row)
    return buf.getvalue()


def render_transcript(courses: dict[str, Course], config: dict, spans, by_no) -> str:
    buf = io.StringIO()
    wr = csv.writer(buf, lineterminator="\n")
    wr.writerow(
        ["code", "title", "level", "planned_start", "planned_end", "actual_start", "actual_end",
         "status", "exam_score", "build_link", "memo_link", "notes"]
    )
    done = set(config.get("completed") or [])
    order = sorted([*config["lane_a"], *config["lane_b"]], key=lambda c: spans.get(c, (0,))[0])
    rows = [courses[c] for c in order] + elective_slots(config, courses) + [courses[c] for c in config["capstone"]]
    for c in rows:
        s = spans.get(c.code)
        wr.writerow([
            c.code, c.title, c.level,
            by_no[s[0]].start.isoformat() if s else "", by_no[s[1]].end.isoformat() if s else "",
            "", "", "completed" if c.code in done else "not started", "", "", "", "",
        ])
    return buf.getvalue()


# ---------------------------------------------------------------- main


def load_config() -> dict:
    return yaml.safe_load((PLAN / "config.yaml").read_text(encoding="utf-8"))


def build(config: dict | None = None) -> tuple[dict[Path, str], str, list[Week]]:
    config = config or load_config()
    courses = load_courses()
    apply_fast_track(config, courses)
    weeks, spans = schedule(config, courses)
    by_no = {w.number: w for w in weeks}
    milestones = config.get("milestones", {})
    lookup = dict(courses)
    for slot in elective_slots(config, courses):
        lookup.setdefault(slot.code, slot)

    files: dict[Path, str] = {PLAN / "weeks" / "README.md": render_overview(config, weeks, spans, courses)}
    for y in range(1, year_of(weeks[-1].number) + 1):
        files[PLAN / "weeks" / f"year-{y}.md"] = render_year(
            y, [w for w in weeks if year_of(w.number) == y], milestones, lookup
        )
    for c in lookup.values():
        files[PLAN / "courses" / c.path] = render_course(c, spans.get(c.code), weeks, milestones, lookup)
    files[PLAN / "courses" / "README.md"] = render_course_index(lookup, spans, by_no)
    for domain in {c.domain for c in lookup.values()}:
        files[PLAN / "courses" / domain / "README.md"] = render_domain_index(domain, lookup, spans, by_no)
    files[PLAN / "assessments.md"] = render_assessments(courses)
    files[PLAN / "schedule.csv"] = render_schedule_csv(weeks)
    return files, render_transcript(courses, config, spans, by_no), weeks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="verify without writing")
    args = ap.parse_args()
    try:
        files, transcript, _ = build()
    except PlanError as e:
        print(f"Plan error: {e}", file=sys.stderr)
        return 1

    existing = {p for d in (PLAN / "weeks", PLAN / "courses") if d.exists() for p in d.rglob("*.md")}
    stale = sorted(existing - set(files))

    if args.check:
        changed = [p for p, text in files.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        if changed or stale:
            for p in changed + stale:
                print(f"out of date: {p.relative_to(ROOT)}", file=sys.stderr)
            print("Run: python plan/build_plan.py", file=sys.stderr)
            return 1
        print(f"Plan OK: {len(files)} generated files are current and all prerequisites are respected.")
        return 0

    for p in stale:
        p.unlink()
    for d in sorted((PLAN / "courses").rglob("*"), reverse=True) if (PLAN / "courses").exists() else []:
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    for p, text in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    transcript_path = ROOT / "progress" / "transcript.csv"
    if not transcript_path.exists():
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text(transcript, encoding="utf-8")
        print(f"created {transcript_path.relative_to(ROOT)}")
    print(f"wrote {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
