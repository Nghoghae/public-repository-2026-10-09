"""Deterministic verification; no external API, network, or student credentials needed."""
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys

import pytest

from smartstudy.models import ValidationError, parse_dt
from smartstudy.storage import SQLiteRepository
from smartstudy.services import AgentController
from smartstudy.ai import AIUnavailable
from smartstudy.planning import ConflictChecker, DeadlinePriorityStrategy, BalancedPriorityStrategy


class FakeLLM:
    """Injectable provider for a controlled test of the AI adapter contract."""
    def structured(self, system_message, user_message):
        if 'READ-ONLY' in system_message:
            return {'tool': 'list_tasks'}
        if 'Extract only explicitly' in system_message:
            return {'items': [
              {'title': 'Homework 7', 'due_at': '2027-01-07 20:00', 'effort_minutes': 90,
               'importance': 4, 'evidence': 'Homework 7 due Jan 7 2027 at 8pm'},
              {'title': 'Quiz TBD', 'due_at': None, 'effort_minutes': 60,
               'importance': 3, 'evidence': 'Quiz date TBD'},
            ]}
        if 'Explain this schedule' in system_message:
            return {'explanation': 'The planner put Homework 7 before its due date.'}
        raise AssertionError('unexpected prompt')


@pytest.fixture
def app(tmp_path):
    return AgentController(SQLiteRepository(tmp_path / 'test.db'), llm=FakeLLM())


def seed(app):
    c = app.add_course('EECS3311','Software Design')
    t = app.add_task(c, 'Homework 7', '2027-01-07 20:00', 90, 4)
    return c, t


def test_course_task_progress_persist(app):
    c, t = seed(app)
    assert app.store.list_courses()[0].code == 'EECS3311'
    assert app.store.get_task(t).remaining_minutes == 90
    app.progress(t, remaining=40)
    assert app.store.get_task(t).remaining_minutes == 40
    app.progress(t, complete=True)
    assert app.store.get_task(t).status == 'done'
    assert app.store.list_tasks(False) == []


def test_invalid_input_rejected(app):
    c = app.add_course('EECS3221', 'Operating Systems')
    with pytest.raises(ValidationError):
        app.add_task(c, '', '2027-01-08 17:00')
    with pytest.raises(ValidationError):
        app.add_task(c, 'Task', '2027-99-01 17:00')
    with pytest.raises(ValidationError):
        app.add_task(c, 'Task', '2027-01-08 17:00', 10, 8)
    task = app.add_task(c, 'Task', None)
    with pytest.raises(ValidationError):
        app.progress(task, remaining=-1)
    with pytest.raises(ValidationError):
        app.add_commitment('Class', '2027-01-06 12:00', '2027-01-06 11:00')


def test_strategy_switch_changes_score(app):
    _, t = seed(app)
    a = app.ranked_tasks()[0][1]
    app.set_strategy('balanced')
    b = app.ranked_tasks()[0][1]
    assert a != b
    assert app.store.preference('priority_strategy') == 'balanced'


def test_plan_respects_commitments_deadlines_and_confirmation(app):
    _, t = seed(app)
    app.add_commitment('Work shift','2027-01-04 09:00','2027-01-04 12:00')
    p = app.planner.generate('2027-01-04', app.store.list_tasks(False), app.store.list_commitments(),
                             now=datetime(2027, 1, 1))
    assert p.sessions and p.conflicts == []
    assert not app.store.list_sessions()  # preview did not commit anything
    assert all(parse_dt(end) <= parse_dt('2027-01-07 20:00') for _,_,_,end in p.sessions)
    assert all(not ('2027-01-04 09:' <= start < '2027-01-04 12:') for _,_,start,_ in p.sessions)
    app.approve(p)
    assert len(app.store.list_sessions()) == len(p.sessions)


def test_unavailable_slots_report_partial_work(app):
    c = app.add_course('EECS2001','Theory')
    app.add_task(c, 'Big project', '2027-01-04 10:00', 600, 5)
    p = app.planner.generate('2027-01-04', app.store.list_tasks(False), [], now=datetime(2026,12,31))
    assert p.unscheduled and p.scheduled_minutes < 600
    assert p.conflicts == []


def test_replan_failed_preserves_existing_schedule(app):
    c,t = seed(app)
    initial = app.planner.generate('2027-01-04',app.store.list_tasks(False), [], now=datetime(2027,1,1))
    app.approve(initial)
    old = app.store.list_sessions()
    app.add_task(c, 'Impossible', '2027-01-04 09:15', 600, 5)
    new = app.planner.generate('2027-01-04',app.store.list_tasks(False), [], now=datetime(2027,1,1))
    assert new.unscheduled
    with pytest.raises(ValidationError):
        app.approve(new, replan=True)
    assert app.store.list_sessions() == old


def test_conflict_checker_reports_overlap(app):
    checker = ConflictChecker()
    blocks = []
    s = [(1,'A','2027-01-04 10:00','2027-01-04 11:00'),
         (2,'B','2027-01-04 10:30','2027-01-04 11:30')]
    assert any('overlaps' in item for item in checker.validate(s,blocks))


def test_notes_confirmation_and_agent_tool(app):
    c, _ = seed(app)
    drafts = app.extract_notes('Homework 7 due Jan 7 2027 at 8pm; quiz date TBD')
    assert len(drafts) == 2
    assert drafts[0].due_at == '2027-01-07 20:00'
    assert drafts[1].due_at is None and drafts[1].warning
    with pytest.raises(ValidationError):
        app.confirm_draft(c,drafts[1])
    app.confirm_draft(c,drafts[0])
    assert len(app.store.list_tasks()) == 2
    answer = app.handle_request('List my tasks')
    assert 'Agent selected tool: list_tasks' in answer and 'Homework 7' in answer
    assert app.refresh.change_counter >= 2
    assert app.reminders.should_check


def test_explanation_and_fallback(app):
    _, _ = seed(app)
    p = app.planner.generate('2027-01-04',app.store.list_tasks(False), [], now=datetime(2027,1,1))
    assert 'Homework 7' in app.explain_plan(p)
    class FailedLLM:
        def structured(self, system, user): raise AIUnavailable('offline')
    offline = AgentController(app.store, llm=FailedLLM())
    assert 'rule-based explanation' in offline.explain_plan(p)
    with pytest.raises(AIUnavailable): offline.handle_request('Show tasks')


def test_reminder_suppression_and_observer(app):
    c = app.add_course('EECS3221','OS')
    now = datetime(2027, 1, 4, 12)
    t = app.add_task(c, 'Report', '2027-01-05 12:00', 30)
    assert app.reminders.should_check
    assert len(app.reminders.check_deadlines(now)) == 1
    assert app.reminders.check_deadlines(now) == []
    app.settings(reminders_enabled=False)
    assert app.reminders.check_deadlines(now) == []


def test_export_csv(app,tmp_path):
    seed(app)
    p = app.planner.generate('2027-01-04',app.store.list_tasks(False), [], now=datetime(2027,1,1))
    app.approve(p)
    output = tmp_path / 'sessions.csv'
    app.export_csv(output)
    lines = output.read_text().splitlines()
    assert lines[0] == 'task_id,title,starts_at,ends_at'
    assert 'Homework 7' in lines[1]


def test_pdf_import_mock_model(app,tmp_path):
    fitz = pytest.importorskip('fitz')
    pdf = tmp_path / 'outline.pdf'
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((40,80), 'Course outline: Homework 7 due Jan 7 2027 at 8pm; quiz date TBD.')
        doc.save(pdf)
    drafts = app.import_outline(pdf)
    assert len(drafts) == 2
    with fitz.open() as doc:
        doc.new_page().insert_text((40,80), 'Tiny')
        doc.save(tmp_path / 'scanned.pdf')
    with pytest.raises(ValidationError): app.import_outline(tmp_path / 'scanned.pdf')


def test_cli_end_to_end(tmp_path):
    cwd = Path(__file__).resolve().parents[1]
    db = tmp_path / 'cli.db'
    def run(*args):
        completed = subprocess.run([sys.executable,'-m','smartstudy','--db',str(db),*args],
            cwd=cwd, text=True,capture_output=True)
        assert completed.returncode == 0, completed.stderr
        return completed.stdout
    assert 'Added course 1' in run('course','add','EECS101','Introduction')
    assert 'Added task 1' in run('task','add','1','Lab','--due','2027-01-07 18:00','--minutes','90')
    assert 'PREVIEW ONLY' in run('plan','week','2027-01-04') or 'PREVIEW ONLY' in run('plan','week','2027-01-04')
    assert 'APPROVED' in run('plan','week','2027-01-04','--approve')
    assert 'Progress updated' in run('task','progress','1','30')
    assert '1' in run('course','list')


def test_reminder_failed_delivery_retries(app):
    c = app.add_course('EECS2200', 'Econ')
    app.add_task(c, 'Exam', '2027-01-05 12:00', 60)
    now = datetime(2027, 1, 4, 12)
    assert app.reminders.check_deadlines(now, deliver=lambda msg: False) == []
    delivered = []
    assert len(app.reminders.check_deadlines(now, deliver=lambda msg: delivered.append(msg))) == 1
    assert len(delivered) == 1
    assert app.reminders.check_deadlines(now) == []


def test_availability_window(app):
    seed(app)
    app.set_availability(17, 20)
    p = app.preview('2027-01-04')
    assert all(17 <= parse_dt(s).hour < 20 and parse_dt(e).hour <= 20 for _,_,s,e in p.sessions)
    with pytest.raises(ValidationError): app.set_availability(21, 9)


def test_cli_input_file(app, tmp_path, capsys):
    from smartstudy.cli import parser, execute
    seed(app)
    request = tmp_path / 'task.txt'
    request.write_text('Show my tasks', encoding='utf-8')
    execute(parser().parse_args(['ask', '--input', str(request)]), app)
    assert 'Homework 7' in capsys.readouterr().out
    with pytest.raises(ValidationError):
        execute(parser().parse_args(['ask', 'text', '--input', str(request)]), app)
    request.write_text('  ', encoding='utf-8')
    with pytest.raises(ValidationError):
        execute(parser().parse_args(['ask', '--input', str(request)]), app)
