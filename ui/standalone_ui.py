"""Transparent click-through Windows HUD with global A/D focus switching."""
from __future__ import annotations
import ctypes,threading,time,tkinter as tk
from ctypes import wintypes

class StandaloneHUD:
 def __init__(self,provider):
  self.provider=provider;self.running=True;self.root=tk.Tk();self.root.overrideredirect(True);self.root.attributes("-topmost",True);self.root.attributes("-alpha",.82)
  self.canvas=tk.Canvas(self.root,bg="#101318",highlightthickness=0);self.canvas.pack(fill="both",expand=True);self._place();self._clickthrough()
  threading.Thread(target=self._keyboard_loop,daemon=True).start();self.root.after(50,self._render)
 def _place(self):
  u=ctypes.windll.user32;h=u.FindWindowW(None,"TrackMania Nations Forever")
  if h:
   r=wintypes.RECT();u.GetWindowRect(h,ctypes.byref(r));self.root.geometry(f"{r.right-r.left}x{r.bottom-r.top}+{r.left}+{r.top}")
  else:self.root.geometry("620x330+20+20")
 def _clickthrough(self):
  h=self.root.winfo_id();s=ctypes.windll.user32.GetWindowLongW(h,-20);ctypes.windll.user32.SetWindowLongW(h,-20,s|0x80000|0x20|0x08000000)
 def _keyboard_loop(self):
  u=ctypes.windll.user32;pa=pd=False
  while self.running:
   a=bool(u.GetAsyncKeyState(0x41)&0x8000);d=bool(u.GetAsyncKeyState(0x44)&0x8000)
   if a and not pa:self.provider(("focus_delta",-1))
   if d and not pd:self.provider(("focus_delta",1))
   pa,pd=a,d;time.sleep(.02)
 def _render(self):
  if not self.running:return
  s=self.provider(("snapshot",));self.canvas.delete("all")
  rows=[f"TMRL Generation {s.generation}",f"Best score: {s.best:.2f}    Active: {s.active}/50",f"Focused car: {s.focus}",f"Speed: {s.speed:.1f} km/h    Distance: {s.distance:.2f}",f"Fitness: {s.fitness:.2f}",f"LIDAR Front {s.front:.2f}  Left {s.left:.2f}  Right {s.right:.2f}"]
  y=14
  for row in rows:self.canvas.create_text(14,y,text=row,anchor="nw",fill="white",font=("Consolas",13));y+=25
  cx,cy=460,205
  for label,dx,dy,d in (("F",0,-110,s.front),("L",-110,0,s.left),("R",110,0,s.right)):
   q=max(.08,min(1.,d));self.canvas.create_line(cx,cy,cx+dx*q,cy+dy*q,fill="red" if d<.15 else "lime",width=3)
   self.canvas.create_text(cx+dx*q,cy+dy*q,text=label,fill="white")
  y0=225
  self.canvas.create_text(14,y0,text="HIDDEN-2 ACTIVATIONS",anchor="nw",fill="white",font=("Consolas",11))
  acts=list(s.activations)
  for i,a in enumerate(acts):
   x=150+(i%12)*34; yy=y0+18+(i//12)*18; mag=max(0.,min(1.,float(a)/4.))
   self.canvas.create_rectangle(x,yy,x+26,yy+10,fill="lime" if a>0 else "#444",outline="")
   self.canvas.create_text(x+13,yy,text=str(i),fill="white",font=("Consolas",7))
  self.root.after(50,self._render)
 def run(self):
  try:self.root.mainloop()
  finally:self.running=False
