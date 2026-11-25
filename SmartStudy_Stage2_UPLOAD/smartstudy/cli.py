"""Command-line interface; shares AgentController with the Tkinter GUI."""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from .services import create_app
from .models import ValidationError
from .ai import AIUnavailable


def parser():
    p = argparse.ArgumentParser(prog='smartstudy', description='SmartStudy AI Academic Planning Agent')
    p.add_argument('--db', default=None, help='Override SQLite database file')
    groups = p.add_subparsers(dest='action', required=True)

    course = groups.add_parser('course', help='Add or list courses')
    c = course.add_subparsers(dest='verb', required=True)
    a = c.add_parser('add'); a.add_argument('code'); a.add_argument('name')
    c.add_parser('list')

    task = groups.add_parser('task', help='Manage tasks')
    t = task.add_subparsers(dest='verb', required=True)
    a = t.add_parser('add'); a.add_argument('course_id', type=int); a.add_argument('title')
    a.add_argument('--due', default=None); a.add_argument('--minutes', type=int, default=60)
    a.add_argument('--importance', type=int, default=3)
    t.add_parser('list')
    a = t.add_parser('edit'); a.add_argument('task_id', type=int)
    a.add_argument('--title'); a.add_argument('--due'); a.add_argument('--importance', type=int)
    a = t.add_parser('complete'); a.add_argument('task_id', type=int)
    a = t.add_parser('progress'); a.add_argument('task_id', type=int); a.add_argument('remaining', type=int)
    a = t.add_parser('rank'); a.add_argument('--strategy', choices=['deadline', 'balanced'])

    block = groups.add_parser('block', help='Manage fixed time commitments')
    b = block.add_subparsers(dest='verb', required=True)
    a = b.add_parser('add'); a.add_argument('title'); a.add_argument('start'); a.add_argument('end')
    b.add_parser('list')

    plan = groups.add_parser('plan', help='Preview, confirm, or replan a study week')
    q = plan.add_subparsers(dest='verb', required=True)
    for verb in ('week', 'replan', 'explain'):
        a = q.add_parser(verb)
        a.add_argument('monday', nargs='?', default=None, help='YYYY-MM-DD, must be Monday')
        a.add_argument('--approve', action='store_true', help='Commit the generated proposal (not valid with explain)')

    ai = groups.add_parser('ask', help='Use a model to select read-only planning tools')
    ai.add_argument('text', nargs='*', help='Natural-language request')
    ai.add_argument('--input', type=Path, help='Read a UTF-8 natural-language request from a file')
    notes = groups.add_parser('notes', help='Extract draft deadlines from text')
    notes.add_argument('text', nargs='+')
    notes.add_argument('--course', type=int, help='Course to add confirmed drafts to')
    notes.add_argument('--confirm', action='store_true', help='Save drafts with complete dates after displaying')
    pdf = groups.add_parser('import', help='Extract deadlines from a course outline PDF')
    pdf.add_argument('file'); pdf.add_argument('--course', type=int)
    pdf.add_argument('--confirm', action='store_true', help='Save drafts with complete dates after displaying')
    reminder = groups.add_parser('remind', help='Deadline reminders')
    r = reminder.add_subparsers(dest='verb', required=True)
    r.add_parser('check')
    a = r.add_parser('settings'); a.add_argument('--enabled', choices=['yes', 'no'])
    a.add_argument('--lead-hours', type=int)
    availability = groups.add_parser('availability', help='Set daily available study hours')
    av = availability.add_subparsers(dest='verb', required=True)
    a = av.add_parser('set'); a.add_argument('start_hour', type=int); a.add_argument('end_hour', type=int)
    av.add_parser('show')
    ex = groups.add_parser('export', help='Export saved sessions to CSV')
    ex.add_argument('filename')
    groups.add_parser('status', help='Show progress summary')
    return p


def print_drafts(controller, drafts, course=None, confirm=False):
    if not drafts:
        print('No supported deadlines were found.'); return
    for i, d in enumerate(drafts, 1):
        print(f'{i}. {d.title} | due={d.due_at or "NEEDS CONFIRMATION"} | {d.effort_minutes}min | {d.warning}')
        print(f'   Evidence: {d.source}')
    if confirm:
        if course is None:
            raise ValidationError('Provide --course ID with --confirm.')
        saved = 0
        for d in drafts:
            if d.due_at:
                controller.confirm_draft(course, d)
                saved += 1
        print(f'Confirmed and saved {saved} draft(s); ambiguous dates were not saved.')
    else:
        print('PREVIEW ONLY. Review dates carefully; use --confirm --course ID to save unambiguous items.')


def execute(args, controller):
    v = getattr(args, 'verb', None)
    if args.action == 'course':
        if v == 'add': print('Added course', controller.add_course(args.code, args.name))
        else:
            for c in controller.store.list_courses(): print(f'[{c.id}] {c.code} - {c.name}')
    elif args.action == 'task':
        if v == 'add': print('Added task', controller.add_task(args.course_id, args.title, args.due, args.minutes, args.importance))
        elif v == 'list':
            for t in controller.store.list_tasks():
                print(f'[{t.id}] {t.course_code}: {t.title} | due={t.due_at or "unset"} | remaining={t.remaining_minutes} | status={t.status}')
        elif v == 'edit':
            kwargs = {}
            if args.title is not None: kwargs['title'] = args.title
            if args.due is not None: kwargs['due_at'] = args.due
            if args.importance is not None: kwargs['importance'] = args.importance
            controller.edit_task(args.task_id, **kwargs); print('Task updated.')
        elif v == 'complete': controller.progress(args.task_id, complete=True); print('Task completed.')
        elif v == 'progress': controller.progress(args.task_id, remaining=args.remaining); print('Progress updated.')
        elif v == 'rank':
            if args.strategy: controller.set_strategy(args.strategy)
            for idx, (t, score) in enumerate(controller.ranked_tasks(), 1):
                print(f'{idx}. [{t.id}] {t.title} | score: {score if score is not None else "missing deadline"}')
    elif args.action == 'block':
        if v == 'add': print('Added commitment', controller.add_commitment(args.title, args.start, args.end))
        else:
            for b in controller.store.list_commitments(): print(f'[{b.id}] {b.title}: {b.starts_at} to {b.ends_at}')
    elif args.action == 'plan':
        monday = args.monday or (date.today() - timedelta(days=date.today().weekday())).isoformat()
        proposal = controller.preview(monday)
        print(proposal.summary())
        if v == 'explain':
            if args.approve: raise ValidationError('explain cannot be used with --approve')
            print('\nWhy this plan?\n' + controller.explain_plan(proposal))
        elif args.approve:
            count = controller.approve(proposal, replan=(v == 'replan'))
            print(f'APPROVED: saved {count} study sessions to the database.')
        else:
            print('PREVIEW ONLY. Run with --approve to commit this proposal.')
    elif args.action == 'ask':
        if bool(args.text) == bool(args.input):
            raise ValidationError('Provide either request text or --input FILE, not both.')
        request = args.input.read_text(encoding='utf-8').strip() if args.input else ' '.join(args.text).strip()
        if not request:
            raise ValidationError('Request must not be empty.')
        print(controller.handle_request(request))
    elif args.action == 'notes':
        print_drafts(controller, controller.extract_notes(' '.join(args.text)), args.course, args.confirm)
    elif args.action == 'import':
        print_drafts(controller, controller.import_outline(args.file), args.course, args.confirm)
    elif args.action == 'remind':
        if v == 'check':
            controller.reminders.check_deadlines(deliver=lambda msg: print('REMINDER:', msg))
            print('Reminder check completed.')
        else:
            controller.settings(reminders_enabled=(args.enabled == 'yes') if args.enabled is not None else None,
                                lead_hours=args.lead_hours)
            print('Reminder settings saved.')
    elif args.action == 'availability':
        if v == 'set':
            controller.set_availability(args.start_hour, args.end_hour)
            print('Study availability saved.')
        else:
            print('Daily study hours:', controller.store.preference('study_start_hour', '9'),
                  'to', controller.store.preference('study_end_hour', '21'))
    elif args.action == 'export':
        print('Exported to', controller.export_csv(args.filename))
    elif args.action == 'status':
        print(controller.tools.execute_tool(controller, {'tool': 'progress_summary'}))


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        execute(args, create_app(db_path=args.db))
        return 0
    except (ValidationError, AIUnavailable, ValueError, OSError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
