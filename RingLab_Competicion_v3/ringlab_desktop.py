import time, threading, json, math, os, csv, datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2, numpy as np, mss, pyautogui
from PIL import Image, ImageTk

# RingLab Desktop: local, screen-based experimental shadow detection.
# Does not read game memory, intercept network traffic, or bypass anti-cheat.
pyautogui.FAILSAFE=True
CONFIG="ringlab_config.json"
class App:
    def __init__(self,root):
        self.root=root;root.title("RingLab Desktop — Sombras")
        self.cfg={"threshold":0.77,"radius":115,"interval":0.18,"burst":2,"gap":0.035,"mode":"proximity","roi":None,"self":None,"glove":None}
        if os.path.isfile(CONFIG):
            try:self.cfg.update(json.load(open(CONFIG,encoding="utf-8")))
            except Exception:pass
        self.template=None;self.self_template=None;self.running=False;self.last_status="Listo";self.preview=None
        p=ttk.Frame(root,padding=12);p.pack(fill="both",expand=True)
        ttk.Label(p,text="RingLab — Detector experimental de sombras",font=("Arial",15,"bold")).pack(anchor="w")
        ttk.Label(p,text="Primero definí el área de Ring, la sombra de referencia, tu posición y el guante.").pack(anchor="w",pady=5)
        for label,cmd in [
            ("1. Seleccionar área de Ring",self.set_roi),
            ("2. Capturar muestra de sombra",self.set_template),
            ("3. Marcar posición de mi personaje",self.set_self),
            ("3B. Capturar mi apariencia (seguimiento)",self.set_self_template),
            ("4. Marcar botón de upper",self.set_glove),
            ("5. Probar detección (sin clics)",self.test),
            ("6. INICIAR automatización",self.start),
            ("DETENER (también tecla F8)",self.stop)]:
            ttk.Button(p,text=label,command=cmd).pack(fill="x",pady=3)
        q=ttk.Frame(p);q.pack(fill="x",pady=8)
        self.vars={}
        for name,label,lo,hi in [('threshold','Coincidencia 0–1',0.4,0.99),('radius','Radio (px)',30,350),('interval','Pausa entre ataques (s)',0.08,1.5),('burst','Clics por ráfaga',1,6),('gap','Pausa entre clics (s)',0.015,0.15)]:
            row=ttk.Frame(q);row.pack(fill="x")
            ttk.Label(row,text=label,width=27).pack(side="left")
            v=tk.StringVar(value=str(self.cfg[name]));self.vars[name]=v
            ttk.Entry(row,textvariable=v,width=12).pack(side="left")
        self.mode_var=tk.StringVar(value=self.cfg.get("mode","proximity"))
        ttk.Label(p,text="Modo de ataque experimental").pack(anchor="w")
        ttk.Combobox(p,textvariable=self.mode_var,values=["proximity","continuous","short_burst","long_burst"],state="readonly").pack(fill="x")
        self.status=tk.StringVar(value="Sin calibrar");ttk.Label(p,textvariable=self.status,wraplength=500).pack(anchor="w",pady=8)
        ttk.Label(p,text="Seguridad: F8 detiene. Mover el mouse a la esquina superior izquierda activa el corte de emergencia de PyAutoGUI.",wraplength=510).pack(anchor="w")
        root.bind_all("<F8>",lambda e:self.stop());root.protocol("WM_DELETE_WINDOW",self.close)
        self.template_path=Path("shadow_template.png")
        if self.template_path.exists():self.template=cv2.imread(str(self.template_path),cv2.IMREAD_GRAYSCALE)
        self.self_path=Path("self_template.png")
        if self.self_path.exists():self.self_template=cv2.imread(str(self.self_path),cv2.IMREAD_GRAYSCALE)
    def save(self):
        for key,var in self.vars.items():
            try:self.cfg[key]=float(var.get()) if key not in ('burst',) else int(float(var.get()))
            except ValueError:pass
        self.cfg["mode"]=self.mode_var.get()
        with open(CONFIG,"w",encoding="utf-8") as f:json.dump(self.cfg,f,indent=2)
    def snap(self):
        with mss.mss() as s:
            monitor=s.monitors[1];arr=np.asarray(s.grab(monitor))[:,:,:3]
            return cv2.cvtColor(arr,cv2.COLOR_BGR2RGB),monitor
    def select(self,mode):
        self.stop();self.root.withdraw();time.sleep(.4)
        img,mon=self.snap()
        # cv2 selection coordinates relative to monitor; mss may use nonzero monitor origin.
        bgr=cv2.cvtColor(img,cv2.COLOR_RGB2BGR)
        if mode in ("roi","template"):
            r=cv2.selectROI("RingLab: arrastra un rectangulo y pulsa ENTER",bgr,showCrosshair=True,fromCenter=False)
            cv2.destroyAllWindows()
            if r[2]<8 or r[3]<8:return None,None
            return (int(r[0]+mon['left']),int(r[1]+mon['top']),int(r[2]),int(r[3])),img[r[1]:r[1]+r[3],r[0]:r[0]+r[2]]
        points=[]
        def cb(event,x,y,flags,param):
            if event==cv2.EVENT_LBUTTONDOWN:points.append((x+mon['left'],y+mon['top']))
        cv2.namedWindow("RingLab: clic en el punto, ESC para cerrar",cv2.WINDOW_NORMAL)
        cv2.setMouseCallback("RingLab: clic en el punto, ESC para cerrar",cb)
        while not points:
            cv2.imshow("RingLab: clic en el punto, ESC para cerrar",bgr)
            if cv2.waitKey(30)&255==27:break
        cv2.destroyAllWindows()
        return (points[0] if points else None),None
    def selection(self,mode):
        try:return self.select(mode)
        finally:self.root.deiconify()
    def set_roi(self):
        r,_=self.selection("roi")
        if r:self.cfg["roi"]=r;self.save();self.status.set("Área Ring configurada")
    def set_template(self):
        r,img=self.selection("template")
        if r:
            # Template is visual shadow sample; select tightly around shadow only.
            self.template=cv2.cvtColor(img,cv2.COLOR_RGB2GRAY)
            cv2.imwrite(str(self.template_path),self.template)
            self.status.set(f"Muestra guardada ({r[2]}×{r[3]} px)")
    def set_self(self):
        pt,_=self.selection("point")
        if pt:self.cfg["self"]=pt;self.save();self.status.set("Posición inicial marcada; actualizar si te movés")
    def set_self_template(self):
        r,img=self.selection("template")
        if r:
            self.self_template=cv2.cvtColor(img,cv2.COLOR_RGB2GRAY)
            cv2.imwrite(str(self.self_path),self.self_template)
            self.cfg["self"]=[r[0]+r[2]//2,r[1]+r[3]//2]
            self.save();self.status.set("Apariencia propia guardada; se intentará seguirla")
    def locate_self(self):
        if self.self_template is None:return self.cfg.get("self")
        roi=self.cfg["roi"]
        with mss.mss() as s:
            bgr=np.asarray(s.grab({"left":roi[0],"top":roi[1],"width":roi[2],"height":roi[3]}))[:,:,:3]
        gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
        h,w=self.self_template.shape
        if h>gray.shape[0] or w>gray.shape[1]:return None
        scores=cv2.matchTemplate(gray,self.self_template,cv2.TM_CCOEFF_NORMED)
        if np.std(self.self_template)<4:return None
        # Search near previous location first, avoiding identity swaps across arena.
        previous=self.cfg.get("self")
        if previous:
            xx=int(previous[0]-roi[0]-w//2);yy=int(previous[1]-roi[1]-h//2)
            y0=max(0,yy-95);y1=min(scores.shape[0],yy+96)
            x0=max(0,xx-95);x1=min(scores.shape[1],xx+96)
            patch=scores[y0:y1,x0:x1]
            if patch.size:
                _,val,_,pos=cv2.minMaxLoc(patch)
                if val>=0.70:
                    self.cfg["self"]=[roi[0]+x0+pos[0]+w//2,roi[1]+y0+pos[1]+h//2]
                    return self.cfg["self"]
        return None # Fail closed: do not attack if self identity is lost.
    def set_glove(self):
        pt,_=self.selection("point")
        if pt:self.cfg["glove"]=pt;self.save();self.status.set("Botón upper marcado")
    def find(self):
        roi=self.cfg["roi"]
        if not roi or self.template is None:raise ValueError("Falta área o muestra de sombra")
        with mss.mss() as s:
            bgr=np.asarray(s.grab({"left":roi[0],"top":roi[1],"width":roi[2],"height":roi[3]}))[:,:,:3]
        gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
        if gray.shape[0]<self.template.shape[0] or gray.shape[1]<self.template.shape[1]:raise ValueError("Muestra mayor que área")
        scores=cv2.matchTemplate(gray,self.template,cv2.TM_CCOEFF_NORMED)
        if np.std(self.template)<4:raise ValueError("Muestra casi uniforme: recortá una sombra con bordes")
        candidates=[]
        # Peak suppression avoids repeated detections of same shadow
        for _ in range(35):
            _,mx,_,pos=cv2.minMaxLoc(scores)
            if mx<float(self.cfg["threshold"]):break
            x,y=pos;w,h=self.template.shape[1],self.template.shape[0]
            candidates.append((roi[0]+x+w//2,roi[1]+y+h//2,float(mx)))
            cv2.rectangle(scores,(max(0,x-w//2),max(0,y-h//2)),(min(scores.shape[1]-1,x+w//2),min(scores.shape[0]-1,y+h//2)),-1,-1)
        return candidates
    def test(self):
        try:
            self.save();matches=self.find()
            own=self.locate_self()
            self.status.set(f"Personaje propio: {'ubicado' if own else 'sin localizar'}. Detectadas {len(matches)} coincidencias. Máx. confianza: {max([round(m[2],2) for m in matches],default='—')}. No prueba que sean personajes.")
        except Exception as e:messagebox.showerror("Detección",str(e))
    def start(self):
        self.save()
        if not all(self.cfg.get(k) for k in ("roi","self","glove")) or self.template is None:
            messagebox.showwarning("Falta calibración","Configurá área, sombra, personaje y guante.");return
        if self.running:return
        self.running=True;self.status.set("ACTIVO — F8 para detener")
        threading.Thread(target=self.worker,daemon=True).start()
    def worker(self):
        try:
            while self.running:
                start=time.monotonic()
                matches=self.find();me=self.locate_self()
                if me is None:
                    time.sleep(0.15);continue # Never attack without verified own position
                matches=[m for m in matches if 45<math.dist(m[:2],me)<float(self.cfg["radius"])]
                # These modes are hypotheses, not confirmed server optimizations.
                if matches:
                    target=min(matches,key=lambda m:math.dist(m[:2],me))
                    # Select target by its shadow and click glove. Server decides actual hits.
                    pyautogui.click(target[0],target[1])
                    mode=self.cfg.get("mode","proximity")
                    count={"continuous":1,"short_burst":3,"long_burst":5}.get(mode,int(self.cfg["burst"]))
                    for _ in range(max(1,min(6,count))):
                        if not self.running:break
                        pyautogui.click(*self.cfg["glove"])
                        time.sleep(max(0.015,float(self.cfg["gap"])))
                mode=self.cfg.get("mode","proximity")
                wait={"continuous":0.08,"short_burst":0.15,"long_burst":0.25}.get(mode,float(self.cfg["interval"]))
                time.sleep(max(0.01,wait-(time.monotonic()-start)))
        except pyautogui.FailSafeException:
            self.root.after(0,lambda:self.status.set("Corte de emergencia activado"))
        except Exception as e:
            self.root.after(0,lambda:self.status.set(f"Error: {e}"))
        finally:self.running=False
    def stop(self):
        self.running=False;self.status.set("DETENIDO")
    def close(self):
        self.stop();self.save();self.root.destroy()
if __name__=="__main__":
    root=tk.Tk();root.geometry("560x670");App(root);root.mainloop()
