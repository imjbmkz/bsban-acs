#!/usr/bin/env python3
"""Build the weekly learning plan from plan/config.yaml and plan/data/*.yaml.

Usage:
    python plan/build_plan.py          # regenerate plan/weeks, plan/courses, plan/schedule.csv
    python plan/build_plan.py --check  # fail if prerequisites break or generated files are stale

Generated files are overwritten. progress/transcript.csv is only created when missing,
so your recorded progress is never touched.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
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
    options: list[str] = field(default_factory=list)  # for undecided elective slots

    def weeks(self) -> list[dict]:
        """Every week of the course as {'type', 'learn', 'apply'}."""
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


def load_courses() -> dict[str, Course]:
    courses: dict[str, Course] = {}
    for path in sorted((PLAN / "data").glob("*.yaml")):
        for raw in yaml.safe_load(path.read_text(encoding="utf-8")):
            c = Course(**raw)
            if c.code in courses:
                sys.exit(f"Duplicate course code {c.code} in {path.name}")
            courses[c.code] = c
    return courses


def elective_slots(config: dict, courses: dict[str, Course]) -> list[Course]:
    track = str(config["track"])
    tracks = config["electives"]
    if track in tracks:
        return [courses[c] for c in tracks[track]]
    if track != "undecided":
        sys.exit(f"track must be one of {', '.join(tracks)} or 'undecided', got {track!r}")
    slots = []
    for i, options in enumerate(zip(*tracks.values()), start=1):
        opts = [courses[o] for o in options]
        prereqs = sorted({p for o in opts for p in o.prereqs})
        n_units = max(len(o.units) for o in opts)
        units = [
            {"learn": f"Week {k} of your track's elective {i}", "apply": "See the elective's page for this week's task"}
            for k in range(1, n_units + 1)
        ]
        slots.append(
            Course(
                code=f"E{i}",
                title=f"Track elective {i}: " + " / ".join(f"{o.code} {o.title}" for o in opts),
                level=4,
                lane="elective",
                kind="full",
                prereqs=prereqs,
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


class PlanError(Exception):
    pass


def schedule(config: dict, courses: dict[str, Course]) -> tuple[list[Week], dict[str, tuple[int, int]]]:
    start = config["start_date"]
    if start.weekday() != 0:
        raise PlanError(f"start_date {start} is not a Monday")
    done = set(config.get("completed") or [])
    queues = {
        "A": deque(courses[c] for c in config["lane_a"] if c not in done),
        "B": deque(courses[c] for c in config["lane_b"] if c not in done),
    }
    electives = deque(elective_slots(config, courses))
    capstone = deque(courses[c] for c in config["capstone"])
    for code in [*config["lane_a"], *config["lane_b"], *config["capstone"]]:
        if code not in courses:
            raise PlanError(f"{code} is in config.yaml but not in plan/data")

    current: dict[str, list | None] = {"A": None, "B": None}  # [course, index]
    cap: list | None = None
    span: dict[str, list[int]] = {}  # code -> [first week, last week]
    weeks: list[Week] = []
    since_review = 0
    n = 0

    def start_course(course: Course, week_no: int) -> None:
        for p in course.prereqs:
            if p in done:
                continue
            if p not in span or span[p][1] >= week_no:
                raise PlanError(
                    f"{course.code} would start in week {week_no} before its prerequisite {p} is finished"
                )
        span[course.code] = [week_no, week_no]

    def finished() -> bool:
        return cap is None and not any(current.values()) and not any(queues.values()) and not electives and not capstone

    while not finished():
        n += 1
        if n > 600:
            raise PlanError("schedule did not terminate; check config.yaml")
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
                    nxt = queues[lane].popleft() if queues[lane] else (electives.popleft() if electives else None)
                    if nxt is not None:
                        start_course(nxt, n)
                        current[lane] = [nxt, 0]
            if current["A"] is None and current["B"] is None and capstone:
                cap = [capstone.popleft(), 0]
                start_course(cap[0], n)

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
        weeks.append(week)
        since_review += 1

    return weeks, {k: (v[0], v[1]) for k, v in span.items()}


# ---------------------------------------------------------------- rendering


def year_of(week_no: int) -> int:
    return (week_no - 1) // WEEKS_PER_YEAR + 1


def week_link(week_no: int, from_dir: str) -> str:
    prefix = "" if from_dir == "weeks" else "../weeks/"
    return f"{prefix}year-{year_of(week_no)}.md#week-{week_no}"


def course_link(course: Course, from_dir: str) -> str:
    prefix = "" if from_dir == "courses" else "../courses/"
    return f"{prefix}{course.code}.md"


def unit_tasks(course: Course, idx: int, milestones: dict, from_dir: str) -> list[str]:
    w = course.weeks()[idx]
    if course.options and w["type"] == "study":
        links = " · ".join(f"[{o}]({course_link(Course(o, '', 0, '', '', []), from_dir)})" for o in course.options)
        return [f"- [ ] Learn and apply: week {idx + 1} of your elective ({links})"]
    if w["type"] == "study":
        return [f"- [ ] Learn: {w['learn']}", f"- [ ] Apply: {w['apply']}"]
    if w["type"] == "final":
        tasks = [
            f"- [ ] Exam (≥ 70%): {course.exam}",
            f"- [ ] Build: {course.build}",
            f"- [ ] Business memo: {course.memo}",
            "- [ ] Record the result in `progress/transcript.csv`",
        ]
    else:  # signoff
        tasks = [
            f"- [ ] Sign-off evidence: {course.signoff}",
            f"- [ ] Business memo: {course.memo}",
            "- [ ] Record the result in `progress/transcript.csv` as `test-out`",
        ]
    if course.code in milestones:
        tasks.append(f"- [ ] **Milestone:** {milestones[course.code]}")
    return tasks


def short(course: Course, idx: int) -> str:
    w = course.weeks()[idx]
    label = {"final": "final", "signoff": "sign-off"}.get(w["type"], f"{idx + 1}/{len(course.weeks())}")
    return f"{course.code} · {label}"


def render_year(year: int, weeks: list[Week], milestones: dict) -> str:
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
            course, idx = w.lanes["both"]
            a = b = short(course, idx)
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
        lanes = w.lanes
        if "both" in lanes:
            course, idx = lanes["both"]
            lines += [
                f"**Both lanes — [{course.code} {course.title}]({course_link(course, 'weeks')})** · "
                f"week {idx + 1} of {len(course.weeks())} · about 10 h",
                "",
                f"- [ ] {course.weeks()[idx]['learn']}: {course.weeks()[idx]['apply']}",
            ]
            if idx == len(course.weeks()) - 1 and course.code in milestones:
                lines.append(f"- [ ] **Milestone:** {milestones[course.code]}")
            lines.append("")
        else:
            for lane in ("A", "B"):
                slot = lanes.get(lane)
                if not slot:
                    lines += [f"**{LANE_NAMES[lane]} — free.** Use the hours for portfolio work or review.", ""]
                    continue
                course, idx = slot
                lines += [
                    f"**{LANE_NAMES[lane]} — [{course.code} {course.title}]({course_link(course, 'weeks')})** · "
                    f"week {idx + 1} of {len(course.weeks())}",
                    "",
                    *unit_tasks(course, idx, milestones, "weeks"),
                    "",
                ]
        lines.append(f"- [ ] Weekly log: `work/log/{iso.year}-W{iso.week:02d}.md`")
    return "\n".join(lines) + "\n"


def render_course(course: Course, span, weeks_by_no: dict[int, Week], milestones: dict) -> str:
    lane = {"A": "A — theory", "B": "B — applied", "both": "Both lanes", "elective": "Whichever lane is free"}[
        course.lane
    ]
    prereqs = ", ".join(f"[{p}]({p}.md)" for p in course.prereqs) or "–"
    if span:
        dates = f"{fmt_date(weeks_by_no[span[0]].start)} → {fmt_date(weeks_by_no[span[1]].end)}"
        plan_weeks = f"[{span[0]}]({week_link(span[0], 'courses')})–[{span[1]}]({week_link(span[1], 'courses')})"
    else:
        dates = "Scheduled once `track` is set in plan/config.yaml"
        plan_weeks = "–"
    folder = "<chosen elective code>" if course.options else course.code
    lines = [
        f"# {course.code} — {course.title}",
        "",
        "| Level | Lane | Type | Prerequisites | Planned dates | Plan weeks |",
        "| --- | --- | --- | --- | --- | --- |",
        f"| {course.level} | {lane} | {KIND_NAMES[course.kind]} | {prereqs} | {dates} | {plan_weeks} |",
        "",
    ]
    if course.resources:
        lines += [f"**Resources:** {course.resources}", ""]
    if course.kind == "full":
        lines += [
            "## Final deliverables",
            "",
            f"- **Exam (50%, pass at 70%):** {course.exam}",
            f"- **Build (30%):** {course.build} — in `work/{folder}/build/`",
            f"- **Business memo (20%):** {course.memo} — in `work/{folder}/memo.md`",
            "",
        ]
    elif course.kind == "test-out":
        lines += [
            "## Sign-off",
            "",
            f"- **Evidence:** {course.signoff}",
            f"- **Business memo:** {course.memo} — in `work/{course.code}/memo.md`",
            "",
        ]
    if course.code in milestones:
        lines += [f"**Milestone at the end:** {milestones[course.code]}", ""]

    lines += ["## Week by week", "", "| Week | Plan week | Learn | Apply |", "| --- | --- | --- | --- |"]
    plan_numbers = []
    if span:
        plan_numbers = [
            w.number
            for w in weeks_by_no.values()
            if w.kind == "content" and any(v and v[0].code == course.code for v in w.lanes.values())
        ]
    for i, w in enumerate(course.weeks()):
        pw = f"[{plan_numbers[i]}]({week_link(plan_numbers[i], 'courses')})" if i < len(plan_numbers) else "–"
        if w["type"] == "study":
            lines.append(f"| {i + 1} | {pw} | {w['learn']} | {w['apply']} |")
        elif w["type"] == "final":
            lines.append(f"| {i + 1} | {pw} | **Final week:** timed exam | Finish the build and the business memo |")
        else:
            lines.append(f"| {i + 1} | {pw} | **Sign-off week:** collect the evidence | Write the business memo |")
    lines += [
        "",
        "Each study week: work the reading or lectures, then the problems, and keep one page of notes in "
        f"`work/{folder}/notes/week-NN.md`. Commit the apply task to `work/{folder}/`.",
    ]
    return "\n".join(lines) + "\n"


def render_course_index(courses: dict[str, Course], spans, weeks_by_no) -> str:
    lines = [
        "# Course pages",
        "",
        "One page per course with planned dates and the week-by-week learn/apply units. "
        "Generated by `plan/build_plan.py`; edit `plan/data/*.yaml` instead of these files.",
        "",
    ]
    groups = [
        ("Level 1 — Foundations", lambda c: c.level == 1),
        ("Level 2 — Core I", lambda c: c.level == 2),
        ("Level 3 — Core II", lambda c: c.level == 3),
        ("Level 4 — Common courses and capstone", lambda c: c.level == 4 and c.lane != "elective"),
        ("Level 4 — Track electives", lambda c: c.lane == "elective"),
    ]
    for name, pred in groups:
        lines += [f"## {name}", "", "| Code | Course | Type | Start | End |", "| --- | --- | --- | --- | --- |"]
        for c in sorted((c for c in courses.values() if pred(c)), key=lambda c: (spans.get(c.code, (999,))[0], c.code)):
            s = spans.get(c.code)
            start = fmt_date(weeks_by_no[s[0]].start) if s else "–"
            end = fmt_date(weeks_by_no[s[1]].end) if s else "–"
            lines.append(f"| [{c.code}]({c.code}.md) | {c.title} | {KIND_NAMES[c.kind]} | {start} | {end} |")
        lines.append("")
    return "\n".join(lines)


def render_overview(config, weeks: list[Week], spans, courses) -> str:
    content = sum(w.kind == "content" for w in weeks)
    review = sum(w.kind == "review" for w in weeks)
    holiday = sum(w.kind == "holiday" for w in weeks)
    years = year_of(weeks[-1].number)
    by_no = {w.number: w for w in weeks}

    def level_end(level: int) -> str:
        ends = [s[1] for code, s in spans.items() if code in courses and courses[code].level == level]
        return f"week {max(ends)} ({fmt_date(by_no[max(ends)].end)})" if ends else "–"

    lines = [
        "# Weekly plan",
        "",
        f"The program runs **{len(weeks)} weeks**, from {fmt_date(weeks[0].start)} to "
        f"{fmt_date(weeks[-1].end)} (about {len(weeks) / 52.18:.1f} years at "
        f"{config['hours_per_week']} hours a week). Elective track: **{config['track']}**.",
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
    for w in weeks:
        row = [w.number, w.start.isoformat(), w.end.isoformat(), w.kind if w.kind == "content" else w.note]
        for lane in ("A", "B"):
            slot = w.lanes.get("both") or w.lanes.get(lane)
            if not slot:
                row += ["", "", "", ""]
                continue
            course, idx = slot
            u = course.weeks()[idx]
            learn = u.get("learn", {"final": "Final: exam", "signoff": "Sign-off"}.get(u["type"], ""))
            apply = u.get("apply", {"final": "Build and memo", "signoff": "Evidence and memo"}.get(u["type"], ""))
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
    order = [*config["lane_a"], *config["lane_b"]]
    order.sort(key=lambda c: spans.get(c, (0,))[0])
    done = set(config.get("completed") or [])
    slots = elective_slots(config, courses)
    rows = [courses[c] for c in order] + slots + [courses[c] for c in config["capstone"]]
    for c in rows:
        s = spans.get(c.code)
        wr.writerow([
            c.code, c.title, c.level,
            by_no[s[0]].start.isoformat() if s else "", by_no[s[1]].end.isoformat() if s else "",
            "", "", "completed" if c.code in done else "not started", "", "", "", "",
        ])
    return buf.getvalue()


# ---------------------------------------------------------------- main


def build() -> tuple[dict[Path, str], str]:
    config = yaml.safe_load((PLAN / "config.yaml").read_text(encoding="utf-8"))
    courses = load_courses()
    weeks, spans = schedule(config, courses)
    by_no = {w.number: w for w in weeks}
    milestones = config.get("milestones", {})
    all_courses = dict(courses)
    for slot in elective_slots(config, courses):
        all_courses.setdefault(slot.code, slot)

    files: dict[Path, str] = {}
    files[PLAN / "weeks" / "README.md"] = render_overview(config, weeks, spans, courses)
    for y in range(1, year_of(weeks[-1].number) + 1):
        files[PLAN / "weeks" / f"year-{y}.md"] = render_year(y, [w for w in weeks if year_of(w.number) == y], milestones)
    for c in all_courses.values():
        files[PLAN / "courses" / f"{c.code}.md"] = render_course(c, spans.get(c.code), by_no, milestones)
    files[PLAN / "courses" / "README.md"] = render_course_index(all_courses, spans, by_no)
    files[PLAN / "schedule.csv"] = render_schedule_csv(weeks)
    transcript = render_transcript(courses, config, spans, by_no)
    return files, transcript


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="verify without writing")
    args = ap.parse_args()
    try:
        files, transcript = build()
    except PlanError as e:
        print(f"Plan error: {e}", file=sys.stderr)
        return 1

    generated_dirs = [PLAN / "weeks", PLAN / "courses"]
    existing = {p for d in generated_dirs if d.exists() for p in d.glob("*.md")}
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
