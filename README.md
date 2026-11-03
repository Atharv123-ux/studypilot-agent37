# StudyPilot - Past-Paper-to-Revision-Plan Agent

Private working prototype. A separate project from LabMate, BriefBridge and InboxZero.
No public repository, no hosted run and no challenge submission exists yet.

StudyPilot turns a course syllabus plus past exam papers into a prioritized,
day-by-day revision plan, a generated practice paper with an answer key, and a
validation log that accounts for every input line.

## What it does
1. Parses a syllabus file: `Topic | weight | keywords` per line.
2. Parses past papers: `Qn [Topic hint] (marks): text` with a `# year: YYYY` header.
3. Maps every question to a syllabus topic (hint first, then keyword match).
   Questions that match nothing are logged as UNMAPPED, never silently dropped;
   unparseable lines are logged as ERROR.
4. Scores each topic: syllabus weight x (1 + appearances) x recency factor.
5. Emits: `revision_plan.md`, `practice_paper.md`, `answer_key.md`,
   `analysis.json`, `validation_log.md` and a self-contained `report.html`.

## Run
    python studypilot.py --syllabus samples/syllabus.txt \
        --papers-dir samples/papers --days-left 10 --out out_demo

## Test
    python tests/test_studypilot.py   # 14 tests

## Data
Everything in `samples/` is synthetic: a fictional "Data Structures 101" course
with invented papers. No real student data, no real exam content.

## Where Agent37 fits (planned)
The same pipeline is designed to run inside an Agent37-hosted agent: the agent
receives the archive, runs the analysis in its own sandboxed computer, keeps the
output files, and iterates (e.g. regenerate the plan when days-left changes).
See agent37/WORKFLOW.md. Not yet executed on Agent37.
