import json, shutil, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studypilot import (read_syllabus, parse_paper, analyze, build_plan,
                        build_practice_paper, render_outputs, map_topic)

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"

class StudyPilotTests(unittest.TestCase):
    def setUp(self):
        self.topics = read_syllabus(SAMPLES / "syllabus.txt")
        self.papers, self.errors = [], []
        for f in sorted((SAMPLES / "papers").glob("*.txt")):
            y, qs, errs = parse_paper(f)
            self.papers.append((y, qs)); self.errors.extend(errs)
        self.analysis = analyze(self.topics, self.papers)
        self.analysis["errors"] = self.errors

    def test_syllabus_parses_six_topics(self):
        self.assertEqual(len(self.topics), 6)
        self.assertEqual(self.topics[0]["topic"], "Arrays and Strings")
        self.assertIn("prefix sum", self.topics[0]["keywords"])

    def test_bad_syllabus_line_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("Broken line without separator\n"); p = f.name
        with self.assertRaises(ValueError):
            read_syllabus(p)

    def test_three_papers_and_years(self):
        self.assertEqual(len(self.papers), 3)
        self.assertEqual([y for y, _ in self.papers], [2024, 2025, 2026])

    def test_question_counts(self):
        total = sum(len(qs) for _, qs in self.papers)
        self.assertEqual(total, 22)  # 8 + 7 + 7 valid question lines

    def test_unparseable_line_logged_not_dropped(self):
        reasons = [e["reason"] for e in self.errors]
        self.assertIn("unparseable question line", reasons)

    def test_unmapped_question_kept(self):
        unmapped = self.analysis["unmapped_questions"]
        self.assertEqual(len(unmapped), 1)
        self.assertEqual(unmapped[0]["hint"], "Guest Lecture")

    def test_topic_mapping_by_hint_and_keywords(self):
        q = {"topic_hint": "unknown", "text": "run bfs on a graph"}
        self.assertEqual(map_topic(q, self.topics), "Trees and Graphs")

    def test_dp_is_top_priority(self):
        top = max(self.analysis["priority"], key=self.analysis["priority"].get)
        self.assertEqual(top, "Dynamic Programming")

    def test_marks_totaled(self):
        dp = self.analysis["topics"]["Dynamic Programming"]
        self.assertEqual(dp["appearances"], 7)
        self.assertEqual(dp["total_marks"], 54)

    def test_never_asked_flag(self):
        # Hashing appears only once (2026), so no topic has zero appearances here;
        # remove one topic's questions and confirm the flag works.
        stats = {t["topic"]: dict(appearances=0, total_marks=0, unmarked=0, years=[], weight=t["weight"])
                 for t in self.topics}
        fake = {"topics": stats, "priority": {}, "never_asked": [], "unmapped_questions": [], "errors": [], "max_paper_year": 2026}
        a = analyze(self.topics, [(2026, [])])
        self.assertEqual(len(a["never_asked"]), 6)

    def test_plan_covers_all_days(self):
        plan = build_plan(self.analysis, 10)
        self.assertEqual(len(plan), 10)
        self.assertEqual([p["day"] for p in plan], list(range(1, 11)))

    def test_plan_starts_with_highest_priority(self):
        plan = build_plan(self.analysis, 10)
        self.assertEqual(plan[0]["focus"], "Dynamic Programming")

    def test_practice_paper_and_key_match(self):
        qs, key = build_practice_paper(self.topics, self.analysis, n_questions=8)
        self.assertEqual(len(qs), 8)
        self.assertEqual(len(key), 8)
        for i in range(8):
            self.assertTrue(qs[i].startswith(f"Q{i+1} "))
            self.assertTrue(key[i].startswith(f"Q{i+1}:"))

    def test_render_outputs_complete(self):
        out = Path(tempfile.mkdtemp())
        plan = build_plan(self.analysis, 7)
        qs, key = build_practice_paper(self.topics, self.analysis)
        written = render_outputs(out, self.topics, self.analysis, plan, qs, key, 7,
                                 ["paper2024.txt", "paper2025.txt", "paper2026.txt"])
        self.assertEqual(sorted(written), sorted(["analysis.json", "revision_plan.md",
                                                  "practice_paper.md", "answer_key.md",
                                                  "validation_log.md", "report.html"]))
        html = (out / "report.html").read_text()
        self.assertIn("StudyPilot report", html)
        self.assertIn("Dynamic Programming", html)
        self.assertIn("<table>", html)
        data = json.loads((out / "analysis.json").read_text())
        self.assertTrue(data["synthetic"])
        self.assertEqual(data["max_paper_year"], 2026)
        log = (out / "validation_log.md").read_text()
        self.assertIn("UNMAPPED", log)
        self.assertIn("ERROR", log)
        shutil.rmtree(out)

if __name__ == "__main__":
    unittest.main(verbosity=2)
