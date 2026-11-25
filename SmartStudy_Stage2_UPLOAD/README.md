# SmartStudy — AI Academic Planning Agent

**EECS3311 Stage 2 | Implementation based on the Stage 1 SmartStudy design**

SmartStudy helps a student enter courses and academic tasks, import tentative deadlines from text/PDF, rank remaining work, create conflict-checked study sessions, update progress, replan, receive reminders, explain plans, and export CSV. The GUI and command-line interface share the `AgentController` façade and one SQLite database.

**Submission integrity note:** This source package is a generated implementation, **not** a history of student development. Review, test, and understand it before using it. It does not include historical GitHub commits, verified token costs, external live-model test evidence, or a public repository URL; do not claim that it does. For grading, upload the actual project to your own public course repository, verify links, and document genuine development history.

## Requirements

- Python 3.10+; Tkinter for the GUI (included with standard Python on many systems; Linux may require `python3-tk`).
- A local writable folder for SQLite.
- For selectable-text PDF course outline import: `PyMuPDF` from `requirements.txt`.
- For **live AI** features F01, F03, F04 and LLM-based F11: your own OpenAI API key and internet access. The deterministic planner and rule-based F11 explanation work without it.

## Setup

```bash
cd SmartStudy_Stage2_UPLOAD
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
cp .env.example .env              # Windows: copy .env.example .env
```

Edit `.env` locally and replace the placeholder:

```ini
OPENAI_API_KEY=YOUR_ACTUAL_KEY
OPENAI_MODEL=gpt-4o-mini
```

**Never push `.env` to GitHub, show it in a video, or paste your key into a report.** The `.gitignore` excludes it; `.env.example` is intentionally safe to commit. `OPENAI_ENDPOINT` optionally overrides the chat-completions endpoint for testing, but only use trusted servers because your key would be sent to that URL. The repository does not store or display API tokens. Without a working key, requests requiring the LLM show an error, not simulated answers.

## Run the GUI

```bash
python run_gui.py
```

Use **Courses & Tasks** to add courses, assignments, progress, and sort priority; **Weekly Planner** to add commitments and preview/approve a plan; **Deadline Import** to import an outline or paste an announcement, review drafts and manually confirm dates; **AI Assistant** for LLM-selected read-only actions; **Reminders & Export** to configure study hours, reminders and save CSV.

The GUI has a preview-then-confirm flow: **nothing is scheduled or imported before user approval.** Times use the machine's local wall clock. For the course project, use the Toronto time zone as required; run with `TZ=America/Toronto` on Unix if necessary.

## Run the CLI

All commands run from the repository folder. The example dates below are *synthetic*; replace with your own real deadlines. `--db` can be placed before the command to select an isolated database.

```bash
python -m smartstudy course add EECS3311 'Software Design'
python -m smartstudy course list
python -m smartstudy task add 1 'Stage 3 review' --due '2026-12-05 20:00' --minutes 180 --importance 5
python -m smartstudy task list
python -m smartstudy task rank --strategy deadline
python -m smartstudy task progress 1 120
python -m smartstudy task complete 1

python -m smartstudy block add 'Work shift' '2026-11-16 13:00' '2026-11-16 17:00'
python -m smartstudy block list
python -m smartstudy availability set 9 21
python -m smartstudy availability show
python -m smartstudy plan week 2026-11-16              # PREVIEW only
python -m smartstudy plan week 2026-11-16 --approve    # saves explicitly
python -m smartstudy plan replan 2026-11-16            # PREVIEW after a change
python -m smartstudy plan replan 2026-11-16 --approve  # rejects incomplete replan, retains old plan
python -m smartstudy plan explain 2026-11-16
python -m smartstudy export weekly_plan.csv
python -m smartstudy status

python -m smartstudy remind settings --enabled yes --lead-hours 48
python -m smartstudy remind check

# The following need a real local API key; neither command saves immediately:
python -m smartstudy ask 'Show my urgent assignments'
python -m smartstudy notes 'Lab 2 is due 2026-12-08 at 17:00'
python -m smartstudy import /path/to/selectable-course-outline.pdf
# To explicitly save drafts whose dates were unambiguous:
python -m smartstudy notes 'Lab 2 is due 2026-12-08 at 17:00' --course 1 --confirm
python -m smartstudy import /path/to/outline.pdf --course 1 --confirm
```

### Run a natural-language task from a file

```bash
python -m smartstudy ask --input sample_data/task.txt
```

The UTF-8 file contains `Show my tasks`. Configure a real API key first. The agent reads the file, selects an allowed read-only tool through the LLM, and prints its result. Use either positional request text or `--input FILE`, not both. Empty files are rejected. Use `--db PATH` before `ask` to select a database. `python -m smartstudy ask --help` lists the options. The Python module is the standalone terminal entry point; no Java JAR is required.

### CLI command summary

| Group | Operations | Feature IDs |
|---|---|---|
| `course`, `task` | add, list, edit, progress, complete, rank | F02, F05, F08 |
| `block`, `availability`, `plan` | fixed commitments, free hours, preview, approve, replan, explain | F06, F07, F09, F11 |
| `notes`, `import` | extract draft deadlines, confirm to save | F03, F04 |
| `ask` | LLM interprets intent and executes an allowed read-only tool | F01 |
| `remind` | configure, check and retry alerts | F10 |
| `export`, `status` | CSV, status output | F08, F12 |

## Implementation architecture and patterns

- `smartstudy/models.py`: `Course`, `Task`, `StudySession`, `Commitment`, `DraftTask`, validation.
- `smartstudy/storage.py`: SQLite repositories, transaction boundary, parameterized SQL.
- `smartstudy/planning.py`: `IPriorityStrategy`, `DeadlinePriorityStrategy` and `BalancedPriorityStrategy` (**Strategy**).
- The same planning module implements `PriorityEngine`, `SchedulePlanner`, `ConflictChecker`, and `Proposal`.
- `smartstudy/ai.py`: `ILLMClient`, `OpenAILLMAdapter`, `DeadlineExtractor`, `IntentInterpreter`, `ExplanationService` (**Adapter**).
- `smartstudy/services.py`: `AgentController` (**Facade**), `TaskEventPublisher` with `ReminderScheduler` and `CalendarRefreshListener` (**Observer**), PDF processor.
- `smartstudy/commands.py`: `ICommand`, task query commands, `ToolManager` (**Command**); `ToolFactory`/`StudyToolFactory.create()` (**Factory Method**).
- `smartstudy/gui.py` and `smartstudy/cli.py`: both call shared service methods rather than duplicate application logic.

**Agent behavior:** The OpenAI adapter interprets natural-language intent into a whitelisted tool, then the agent actually invokes the approved application service using the Command pattern. The LLM also extracts tentative task drafts and explains planner decisions. The LLM does **not** directly add, delete, or reschedule data. Rules compute timing and conflicts. This is more than a prompt-in/response-out chatbot.

## Deterministic and AI-dependent functions

The **core scheduler is deterministic**. It only schedules pending tasks with explicit due dates; missing dates are flagged. It ranks tasks by the selected strategy, uses the user's daily study-hour range and blocked commitments, does not schedule past due times, and reports unplaced minutes when a week is full. All sessions are stored only after approval. Replanning refuses a partial replacement and retains the original sessions. Scheduled sessions in the selected Monday-Sunday week are replaced atomically; sessions outside the week remain. The earliest plausible planning slot starts on the current date if the selected week is current.

**AI integration needs user configuration** and requires a paid or free-compatible provider account. The Stage 1 adapter targets OpenAI chat completions using JSON output; models with that capability are required. Drafts are candidates, **not guaranteed extraction accuracy**. Users must inspect dates, especially relative phrases or missing years; a non-selectable/scanned PDF produces a meaningful error instead of fabricated output.

## Test suite / verification

```bash
python -m pip install pytest
python -m pytest -q
python -m compileall -q smartstudy
```

The suite uses a controlled mock LLM to verify routing, extraction and explanation **without claiming a live OpenAI call**; other tests cover SQLite persistence, invalid input, priorities, commitments, non-overlap, incomplete scheduling, preservation of a previous plan when replanning fails, the observer, reminder suppression, CSV export, PDF text extraction, and a real CLI subprocess round-trip.

### Current limitations

- The real OpenAI API has **not** been exercised in this delivered environment because no personal API key was supplied. Provide your own key and demonstrate it, then capture authentic costs from provider usage.
- PDF import supports *selectable text* only; it does not OCR scanned PDFs. It accepts up to 80 pages and sends at most 26,000 characters to the LLM.
- All reminders are in-app or CLI checks; there are no OS-level push notifications or email integrations.
- Scheduling uses a shared daily time window (e.g., 09:00-21:00) plus fixed commitments, not different weekly availability per day. Sessions have a practical 30/60-minute allocation heuristic and may be partial.
- The GUI displays a dated session list, not a drag-and-drop calendar.
- The AI agent deliberately restricts autonomous tool execution to read-only tools; writes require an explicit GUI or CLI confirmation.
- No public GitHub URL, historic commits, or proof of demonstration link accessibility has been supplied. These **cannot** be constructed retroactively.

## Deliverables and grading evidence

The `stage2-report.pdf` and `stage2-report.docx` describe implementation and discrepancies from Stage 1. The `demos/` directory contains instructions and, where present, actual locally captured GUI/CLI demonstration media. Video samples using a controlled FakeLLM must be **identified as such**, not presented as proof of live model integration. User-recorded evidence is indexed in demos/README.md.

Stage 2 requires **five meaningful code commits in each period**: Oct 20-26, Oct 27-Nov 2, and Nov 3-9, 2026 (Toronto local time). Those periods and the Nov 10 submission deadline have already passed as of project preparation. Do **not** backdate commits or invent history. Document your real repository's records and contact your instructor about a late submission if applicable.

**Before submitting:** run locally; understand/review the code; set your actual `.env` privately; make your own meaningful commits; test GUI and CLI; record genuine feature demonstrations; upload to the existing public GitHub repository; verify sample commands, `.gitignore`, report and video links; and submit the repository URL through the course system.

## Additional Stage 2 evidence

See [feature documentation](docs/FEATURES.md) and [new demo recording index](demos/README.md). The report screenshots are sampled from user recordings. The demo index lists the new user recordings and remaining verification caveats.
