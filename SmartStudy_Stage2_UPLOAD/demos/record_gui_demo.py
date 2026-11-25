"""Automated offline GUI walkthrough from the real Tkinter program.

This video uses a TEST DOUBLE for the LLM: it does not prove live API service.
"""
from datetime import date, timedelta
from pathlib import Path
import tempfile
import subprocess
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageGrab, ImageDraw, ImageFont
from smartstudy.gui import SmartStudyGUI
from smartstudy.services import create_app


class TestLLM:
    def structured(self, system, user):
        if 'READ-ONLY' in system:
            return {'tool':'list_tasks'}
        if 'Extract only' in system:
            return {'items':[{'title':'Math quiz','due_at':'2026-11-19 16:00','effort_minutes':60,'importance':4,
                              'evidence':'Math quiz due Nov 19 at 4pm'},
                             {'title':'Exam date TBD','due_at':None,'effort_minutes':90,'importance':5,
                              'evidence':'Exam date to be announced'}]}
        if 'Explain' in system: return {'explanation':'Sessions are placed before deadlines in free time.'}
        return {'tool':'help'}


def setval(w, value):
    w.delete(0, 'end'); w.insert(0, value)


def main():
    dest = Path(__file__).with_name('gui_walkthrough.mp4')
    with tempfile.TemporaryDirectory() as temp:
        ctrl = create_app(db_path=str(Path(temp)/'demo.db'), llm=TestLLM())
        root = tk.Tk()
        gui = SmartStudyGUI(root,ctrl)
        messagebox.showinfo = lambda *a, **k: None  # Avoid blocking unattended capture.
        messagebox.askyesno = lambda *a, **k: True   # Automated local test approves the preview.
        shots = []
        def snap(title, sec=3):
            root.update_idletasks(); root.update()
            im = ImageGrab.grab(bbox=(0,0,1130,820)).convert('RGB')
            canvas = Image.new('RGB',(1130,870), '#131c2c'); canvas.paste(im,(0,0))
            dr = ImageDraw.Draw(canvas)
            dr.text((20,833),title,fill='white',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17))
            p = Path(temp)/f'{len(shots):02d}.png'; canvas.save(p)
            shots.append((p, sec))
        snap('REAL SMARTSTUDY GUI - Offline UI walkthrough (AI provider simulated)',4)
        setval(gui.course_code,'EECS3311');setval(gui.course_name,'Software Design')
        snap('F02: Enter course information',2)
        gui.add_course(); snap('F02: Course saved to SQLite',3)
        setval(gui.task_course,'1');setval(gui.task_title,'Project review');setval(gui.task_due,'2026-11-20 20:00')
        setval(gui.task_minutes,'120');setval(gui.task_importance,'5')
        snap('F02: Enter task, due date, effort and importance',2)
        gui.add_task();snap('F02: Task saved and displayed',3)
        setval(gui.task_title,'Midterm preparation');setval(gui.task_due,'2026-11-19 19:00')
        setval(gui.task_minutes,'90');setval(gui.task_importance,'4');gui.add_task()
        gui.rank_tasks();snap('F05: PriorityEngine ranked the pending tasks',3)
        first = gui.tasks_tree.get_children()[0]
        gui.tasks_tree.selection_set(first); setval(gui.remaining,'60')
        gui.update_progress();snap('F08: Remaining effort updated in the dashboard',3)
        gui.tabs.select(gui.calendar);setval(gui.block_title,'Work shift')
        setval(gui.block_start,'2026-11-16 13:00');setval(gui.block_end,'2026-11-16 17:00')
        gui.add_block();setval(gui.week,'2026-11-16')
        snap('F07: Fixed commitment blocks busy calendar time',3)
        gui.preview_plan(False);snap('F06/F07: Proposed plan avoids the shift and task deadlines',5)
        gui.approve_plan();snap('F06: Explicit approval saves study sessions',3)
        gui.preview_plan(True);snap('F09: Replanning is a separate reviewable proposal',4)
        gui.explain();snap('F11: AI explanation using an offline test double (NOT LIVE API)',3)
        gui.tabs.select(gui.importer)
        gui.notes_text.insert('1.0','Math quiz is due Nov 19, 2026 at 4pm; exam date is TBD.')
        gui.import_notes();snap('F04: Extracted drafts (SIMULATED LLM); ambiguous date flagged',5)
        gui.tabs.select(gui.assistant)
        gui.chat_input.insert('1.0','Show my tasks')
        gui.ask_ai();snap('F01: Agent selects read-only list_tasks command (SIMULATED LLM)',5)
        gui.tabs.select(gui.settings_tab)
        snap('F10/F12: Reminder, availability, priority and CSV export controls',5)
        root.destroy()
        concat = Path(temp)/'concat.txt'
        # Concat demuxer: each captured frame comes from the REAL running Tk application.
        with concat.open('w') as f:
            for shot, secs in shots:
                f.write(f"file '{shot}'\nduration {secs}\n")
            f.write(f"file '{shots[-1][0]}'\n")
        subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(concat),
                        '-r','5','-c:v','libx264','-preset','veryfast','-crf','27','-pix_fmt','yuv420p',
                        str(dest)],check=True)
        print(dest, 'frames',len(shots))


if __name__ == '__main__': main()
