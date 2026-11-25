from pathlib import Path
from datetime import datetime,timedelta,date
import tempfile, tkinter as tk
from tkinter import messagebox,filedialog
from PIL import ImageGrab
from smartstudy.gui import SmartStudyGUI
from smartstudy.services import create_app
from demos.record_gui_demo import TestLLM,setval
import subprocess
out=Path('docs/screenshots').resolve(); demo=Path('demos').resolve()
with tempfile.TemporaryDirectory() as tmp:
 root=tk.Tk(); app=create_app(db_path=tmp+'/gui.db',llm=TestLLM()); g=SmartStudyGUI(root,app)
 messagebox.showinfo=lambda *a,**k: None
 messagebox.askyesno=lambda *a,**k: True
 def fail(*a,**k): raise RuntimeError(str(a))
 messagebox.showerror=fail
 def snap(name):
  root.update_idletasks();root.update();ImageGrab.grab(bbox=(0,0,1120,780)).save(out/(name+'.png'))
 monday=date.today()-timedelta(days=date.today().weekday()); due=(monday+timedelta(days=6)).isoformat()+' 20:00'
 setval(g.course_code,'EECS3311');setval(g.course_name,'Software Design');g.add_course()
 setval(g.task_course,'1');setval(g.task_title,'Project review');setval(g.task_due,due);setval(g.task_minutes,'120');setval(g.task_importance,'5');snap('F02-entry');g.add_task();snap('F02')
 g.rank_tasks();snap('F05');g.tasks_tree.selection_set(g.tasks_tree.get_children()[0]);setval(g.remaining,'60');g.update_progress();snap('F08')
 g.tabs.select(g.calendar);setval(g.block_title,'Work shift');setval(g.block_start,(monday+timedelta(days=5)).isoformat()+' 13:00');setval(g.block_end,(monday+timedelta(days=5)).isoformat()+' 17:00');g.add_block();setval(g.week,monday.isoformat());g.preview_plan(False);snap('F07');g.approve_plan();snap('F06');g.preview_plan(True);snap('F09');g.explain();snap('F11-mock')
 g.tabs.select(g.importer);filedialog.askopenfilename=lambda **k: str(Path('sample_data/demo_course_outline.pdf').resolve());g.import_pdf();snap('F03-mock');g.notes_text.insert('1.0','Math quiz is due Nov 19, 2026 at 4pm; exam date is TBD.');g.import_notes();snap('F04-mock')
 g.tabs.select(g.assistant);g.chat_input.insert('1.0','Show my tasks');g.ask_ai();snap('F01-mock')
 g.tabs.select(g.settings_tab);filedialog.asksaveasfilename=lambda **k: tmp+'/plan.csv';g.export();assert Path(tmp+'/plan.csv').exists();snap('F12');
 app.add_task(1,'Reminder demonstration',(datetime.now()+timedelta(hours=1)).strftime('%Y-%m-%d %H:%M'),30,3)
 def alert(title,msg,**k):
  if title=='Upcoming deadline':
   w=tk.Toplevel(root);w.title(title);tk.Label(w,text=title,font=('Arial',16,'bold')).pack(padx=20,pady=10);tk.Label(w,text=msg,wraplength=550).pack(padx=20,pady=20);w.geometry('+200+200');snap('F10');w.destroy()
 messagebox.showinfo=alert;g.check_reminders();root.destroy()
 # Capture actual terminal output for same task, using a fresh database.
 cmds=[['course','add','EECS3311','Software Design'],['task','add','1','Project review','--due',due,'--minutes','120','--importance','5'],['task','list']]
 import shlex
 script=Path(tmp)/'terminal.sh'; script.write_text('clear\n'+ '\n'.join('echo '+shlex.quote('$ python -m smartstudy '+shlex.join(c))+'\n'+shlex.join(['python','-m','smartstudy','--db',tmp+'/cli.db']+c) for c in cmds)+'\nsleep 20\n')
 p=subprocess.Popen(['xterm','-geometry','120x35+0+0','-fa','Monospace','-fs','12','-e','bash',str(script)])
 import time;time.sleep(3);ImageGrab.grab(bbox=(0,0,1120,780)).save(out/'CLI-matched.png');p.terminate();p.wait()
 # Actual captured frames, not continuous screen recording.
 seq=[out/'F02-entry.png',out/'F02.png',out/'CLI-matched.png']; f=Path(tmp)/'frames.txt';f.write_text(''.join(f"file '{x}'\nduration 5\n" for x in seq)+f"file '{seq[-1]}'\n")
 subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(f),'-r','10','-c:v','libx264','-pix_fmt','yuv420p',str(demo/'matched_gui_cli.mp4')],check=True)
