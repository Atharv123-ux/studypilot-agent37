"""StudyPilot: offline past-paper + syllabus -> revision plan pipeline.

No network access and no send capability. Every input row is accounted for:
unmappable questions are logged, never silently dropped.
"""
import argparse, hashlib, json, re
from collections import defaultdict
from pathlib import Path

QUESTION_RE = re.compile(r"^Q(\d+)\s*\[(.*?)\]\s*(?:\((\d+)\s*marks?\))?\s*:?\s*(.*)$", re.IGNORECASE)

def read_syllabus(path):
    """Parse syllabus lines 'Topic | weight | keyword,keyword'. Returns list of topic dicts."""
    topics = []
    for lineno, raw in enumerate(Path(path).read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            raise ValueError(f"syllabus line {lineno}: expected 'Topic | weight | keywords'")
        name = parts[0]
        try:
            weight = float(parts[1])
        except ValueError:
            raise ValueError(f"syllabus line {lineno}: weight '{parts[1]}' is not a number")
        keywords = [k.strip().lower() for k in parts[2].split(",") if k.strip()] if len(parts) > 2 else []
        keywords.append(name.lower())
        topics.append({"topic": name, "weight": weight, "keywords": sorted(set(keywords))})
    if not topics:
        raise ValueError("syllabus has no topics")
    return topics

def parse_paper(path):
    """Parse one past paper. Returns (year, questions, errors)."""
    questions, errors = [], []
    year = None
    for lineno, raw in enumerate(Path(path).read_text().splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^#\s*year\s*:\s*(\d{4})", line, re.IGNORECASE)
        if m:
            year = int(m.group(1)); continue
        if line.startswith("#"):
            continue
        q = QUESTION_RE.match(line)
        if not q:
            errors.append({"file": Path(path).name, "line": lineno, "text": line,
                           "reason": "unparseable question line"})
            continue
        marks = int(q.group(3)) if q.group(3) else None
        questions.append({"id": f"{Path(path).stem}-Q{q.group(1)}", "topic_hint": q.group(2).strip(),
                          "marks": marks, "text": q.group(4).strip(), "year": year})
    if year is None:
        errors.append({"file": Path(path).name, "line": 0, "text": "",
                       "reason": "missing '# year: YYYY' header"})
    return year, questions, errors

def map_topic(question, topics):
    """Map a question to a syllabus topic via hint/keywords. Returns topic name or None."""
    hint = question["topic_hint"].lower()
    for t in topics:
        if t["topic"].lower() == hint:
            return t["topic"]
    hay = (question["topic_hint"] + " " + question["text"]).lower()
    best, best_hits = None, 0
    for t in topics:
        hits = sum(1 for k in t["keywords"] if k in hay)
        if hits > best_hits:
            best, best_hits = t["topic"], hits
    return best

def analyze(topics, papers):
    """papers: list of (year, questions). Returns analysis dict + validation log."""
    stats = {t["topic"]: {"appearances": 0, "total_marks": 0, "unmarked": 0,
                          "years": [], "weight": t["weight"]} for t in topics}
    unmapped, all_errors = [], []
    max_year = max((y for y, qs in papers if y), default=0)
    for year, questions in papers:
        for q in questions:
            topic = map_topic(q, topics)
            if topic is None:
                unmapped.append({"id": q["id"], "hint": q["topic_hint"], "reason": "no syllabus topic matched"})
                continue
            s = stats[topic]
            s["appearances"] += 1
            if q["marks"] is None:
                s["unmarked"] += 1
            else:
                s["total_marks"] += q["marks"]
            if year and year not in s["years"]:
                s["years"].append(year)
    priority = {}
    for name, s in stats.items():
        recency = 1.0
        if s["years"] and max_year:
            recency = 1.0 + 0.25 * (max(s["years"]) - min(y for y, qs in papers if y))
        freq = s["appearances"]
        priority[name] = round(s["weight"] * (1 + freq) * recency, 3)
    never_asked = [n for n, s in stats.items() if s["appearances"] == 0]
    return {"topics": stats, "priority": priority, "never_asked": never_asked,
            "unmapped_questions": unmapped, "errors": all_errors,
            "max_paper_year": max_year}

def build_plan(analysis, days_left):
    """Day-by-day revision plan, highest priority first, one topic per day, repeat top third."""
    ordered = sorted(analysis["priority"], key=analysis["priority"].get, reverse=True)
    if days_left < 1:
        days_left = 1
    sequence = ordered[:]
    top_third = ordered[: max(1, len(ordered) // 3)]
    i = 0
    while len(sequence) < days_left:
        sequence.append("Revise again: " + top_third[i % len(top_third)])
        i += 1
    plan = []
    for day in range(1, days_left + 1):
        topic = sequence[(day - 1) % len(sequence)]
        plan.append({"day": day, "focus": topic})
    return plan

def build_practice_paper(topics, analysis, n_questions=8):
    """Deterministic practice paper: pick from highest-priority topics; answer key lists topic+keywords."""
    ordered = sorted(analysis["priority"], key=analysis["priority"].get, reverse=True)
    picked = (ordered * ((n_questions // max(1, len(ordered))) + 1))[:n_questions]
    kw = {t["topic"]: [k for k in t["keywords"] if k != t["topic"].lower()][:3] for t in topics}
    questions, key = [], []
    for i, topic in enumerate(picked, 1):
        hints = ", ".join(kw.get(topic) or [topic.lower()])
        questions.append(f"Q{i} [{topic}] (5 marks): Explain {hints.split(',')[0].strip()} and give one worked example.")
        key.append(f"Q{i}: Topic = {topic}. Award marks for: {hints}.")
    return questions, key

def render_html_report(topics, analysis, plan, days_left):
    """Self-contained HTML report of the analysis and plan."""
    rows = []
    for name in sorted(analysis["priority"], key=analysis["priority"].get, reverse=True):
        st = analysis["topics"][name]
        years = ", ".join(map(str, sorted(st["years"]))) or "-"
        rows.append(f"<tr><td>{name}</td><td>{st['weight']}</td><td>{st['appearances']}</td>"
                    f"<td>{st['total_marks']}</td><td>{years}</td><td>{analysis['priority'][name]}</td></tr>")
    plan_items = "\n".join(f"<li>Day {p['day']}: {p['focus']}</li>" for p in plan)
    never = "".join(f"<li>{n}</li>" for n in analysis["never_asked"]) or "<li>None</li>"
    unmapped = "".join(f"<li>{u['id']} [{u['hint']}]</li>" for u in analysis["unmapped_questions"]) or "<li>None</li>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>StudyPilot report</title>
<style>body{{font-family:system-ui,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;color:#1a1a2e}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px 10px;text-align:left}}
th{{background:#1a1a2e;color:#fff}}.note{{color:#666;font-size:.9em}}</style></head><body>
<h1>StudyPilot report</h1><p class="note">Synthetic demo data. {days_left} day(s) to exam.</p>
<h2>Topic priority</h2><table><tr><th>Topic</th><th>Weight</th><th>Appearances</th><th>Total marks</th><th>Years asked</th><th>Priority</th></tr>
{''.join(rows)}</table>
<h2>Revision plan</h2><ol>{plan_items}</ol>
<h2>Syllabus topics never asked in sample papers</h2><ul>{never}</ul>
<h2>Unmapped questions (kept, not dropped)</h2><ul>{unmapped}</ul>
</body></html>"""

def render_outputs(out_dir, topics, analysis, plan, questions, key, days_left, source_files):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    (out / "analysis.json").write_text(json.dumps({
        "synthetic": True, "days_left": days_left, "source_files": source_files,
        "topics": analysis["topics"], "priority": analysis["priority"],
        "never_asked": analysis["never_asked"], "plan": plan,
        "unmapped_questions": analysis["unmapped_questions"], "errors": analysis["errors"],
        "max_paper_year": analysis["max_paper_year"],
    }, indent=2))
    lines = ["# StudyPilot revision plan", "",
             f"Synthetic demo data. {days_left} day(s) to exam. Highest-priority topics first.", ""]
    for p in plan:
        lines.append(f"- Day {p['day']}: {p['focus']}")
    if analysis["never_asked"]:
        lines += ["", "## Never asked in the sample papers (still in syllabus)",
                  *[f"- {n}" for n in analysis["never_asked"]]]
    (out / "revision_plan.md").write_text("\n".join(lines) + "\n")
    (out / "practice_paper.md").write_text("# Practice paper (synthetic)\n\n" + "\n".join(questions) + "\n")
    (out / "answer_key.md").write_text("# Answer key\n\n" + "\n".join(key) + "\n")
    log = ["# Validation log", "",
           f"Parsed papers: {len(source_files)}",
           f"Mapped questions: {sum(s['appearances'] for s in analysis['topics'].values())}",
           f"Unmapped questions (kept, not dropped): {len(analysis['unmapped_questions'])}",
           f"Parse errors: {len(analysis['errors'])}"]
    for u in analysis["unmapped_questions"]:
        log.append(f"- UNMAPPED {u['id']} [{u['hint']}]: {u['reason']}")
    for e in analysis["errors"]:
        log.append(f"- ERROR {e['file']}:{e['line']}: {e['reason']}")
    (out / "validation_log.md").write_text("\n".join(log) + "\n")
    (out / "report.html").write_text(render_html_report(topics, analysis, plan, days_left))
    return sorted(p.name for p in out.iterdir())

def main():
    ap = argparse.ArgumentParser(description="StudyPilot offline revision planner")
    ap.add_argument("--syllabus", required=True)
    ap.add_argument("--papers-dir", required=True)
    ap.add_argument("--days-left", type=int, default=10)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    topics = read_syllabus(a.syllabus)
    papers, errors = [], []
    for f in sorted(Path(a.papers_dir).glob("*.txt")):
        year, qs, errs = parse_paper(f)
        papers.append((year, qs)); errors.extend(errs)
    if not papers:
        raise SystemExit("no papers found")
    analysis = analyze(topics, papers)
    analysis["errors"] = errors
    plan = build_plan(analysis, a.days_left)
    questions, key = build_practice_paper(topics, analysis)
    written = render_outputs(a.out, topics, analysis, plan, questions, key, a.days_left,
                             [f.name for f in sorted(Path(a.papers_dir).glob('*.txt'))])
    digest = hashlib.sha256(Path(a.out, "analysis.json").read_bytes()).hexdigest()[:12]
    print(json.dumps({"written": written, "mapped": sum(s["appearances"] for s in analysis["topics"].values()),
                      "unmapped": len(analysis["unmapped_questions"]), "errors": len(errors),
                      "analysis_sha256_12": digest}, indent=2))

if __name__ == "__main__":
    main()
