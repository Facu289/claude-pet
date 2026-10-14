"""Claude Pet: mascota de escritorio (solo Windows, solo libreria estandar).

- Chiquita, camina por toda la pantalla y por arriba de tus ventanas abiertas.
- Interactua con las ventanas: se sube, se sienta en el borde con las patitas
  colgando, "surfea" una ventana moviendola un poco y comenta lo que tenes abierto.
- Duerme, programa, baila, toma cafe, te sigue, te lleva el mouse (poco), cuenta chistes.
- Habla poco: solo de vez en cuando (con pausas largas entre comentarios).
- Click: lo molestas. Arrastrar: lo agarras y lo tiras. Click derecho: menu.
"""
import ctypes
import math
import os
import random
import subprocess
import sys
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

# ---------- Windows / DPI ----------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
dwm = ctypes.windll.dwmapi
try:
    D = user32.GetDpiForSystem() / 96.0      # escala de la UI (texto, ventanita)
except Exception:
    D = 1.0
PET_SIZE = 0.55                               # tamaño de la mascota (1.0 = grande)
S = D * PET_SIZE

TITLE = "ClaudePetBody"
HERE = Path(__file__).parent

KEY = "#010101"          # color transparente
ORANGE, SHADE, DARK = "#D97757", "#b85c3e", "#2b1d16"
GRAV, TICK_MS = 1.0, 33
KEEP = ("follow", "grab", "travel")   # estados que sobreviven a un salto/caida

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

PHRASES = {
    "sleep": ["zzz...", "5 minutitos más..."],
    "code": ["compilando...", "tests en verde ✅", "funciona en mi máquina"],
    "dance": ["♪ ♫ ♪", "¡fiesta!"],
    "wave": ["¡hola!", "¿todo bien?"],
    "coffee": ["café ☕", "necesito cafeína"],
    "follow": ["¡voy con vos!", "te sigo"],
    "grab": ["¡te agarré el mouse!"],
    "surf": ["¡surfeando!", "¡agarrate ventana!"],
    "sit": ["qué vista", "a descansar un rato"],
}
QUIPS = ["hmm...", "¿seguimos?", "me aburro", "*mira alrededor*", "estiro las patitas"]
POKES = ["¡ey!", "¡cosquillas!", "auch", "¡no me toques!", "jaja"]
JOKES = [
    ("¿Por qué los programadores confunden Halloween con Navidad?", "Porque OCT 31 == DEC 25."),
    ("¿Cuántos programadores hacen falta para cambiar una bombita?", "Ninguno, es un problema de hardware."),
    ("Un SQL entra a un bar, ve dos mesas y pregunta...", "¿Puedo unirme?"),
    ("¿Qué le dice un bit a otro bit?", "Nos vemos en el bus."),
    ("Hay 10 tipos de personas.", "Las que entienden binario y las que no."),
    ("¿Por qué los desarrolladores odian la naturaleza?", "Demasiados bugs."),
    ("Le dicen al programador: 'comprá pan, y si hay huevos traé 6'.", "Volvió con 6 panes: había huevos."),
    ("Me dijeron que Git es fácil.", "Después del push --force me quedé sin amigos."),
    ("¿Qué le dice un String a otro String?", "Concatenemos."),
    ("¿Cuál es el colmo de un programador argentino?", "Que se le cuelgue el mate."),
    ("Mi código no tiene bugs.", "Solo tiene features inesperadas."),
    ("¿Cómo se llama un programador sin café?", "Un compilador sin errores: no existe."),
    ("¿Por qué el programador se quedó sin trabajo?", "No tenía clase."),
    ("Dos bytes se encuentran. Uno dice: 'te noto raro'.", "'Es que tengo un bit de más'."),
]
GREET = {
    "morning": ["¡Buen día! ☀️", "Buen día, ¿ya tomaste unos mates? 🧉", "Good morning! ☕",
                "¡Buenos días! Hoy se programa", "Bonjour! ☀️", "Rise and shine! 🌅"],
    "afternoon": ["¡Buenas tardes! 🌤️", "Good afternoon!", "Buenas tardes, ¿ya almorzaste?",
                  "¡Buenas! ¿Cómo va la tarde?", "Buona sera!"],
    "night": ["¡Buenas noches! 🌙", "Good evening! 🌆", "Buenas noches, ¿sesión nocturna?",
              "Bona nit... digo, ¡buenas noches!"],
    "late": ["¿Todavía despierto? 🦉", "Es tarde... andá a dormir 😴", "Night owl detectado 🦉",
             "Good night... o good morning, ya ni sé"],
}
BOOT_EXTRA = ["¡Se prendió la compu!", "Arrancamos el día 🚀", "Todo listo, jefe",
              "Systems online ✅", "Ya estoy acá con vos"]
BACK_EXTRA = ["¡Volviste! Te extrañé", "Welcome back!", "Ahí estás 👀", "¿Dormiste bien, compu?"]
TITLE_QUIPS = [
    (("youtube", "netflix", "twitch"), "¿otro video? ¡a laburar! 😏"),
    (("visual studio", "code", "pycharm", "claude"), "uh, acá se programa 👀"),
    (("excel", "sheets"), "cuántas celdas... qué claustrofobia"),
    (("whatsapp", "discord", "telegram"), "chusmeando chats, ¿eh?"),
    (("spotify",), "♪ buen gusto"),
    (("chrome", "edge", "firefox"), "¿cuántas pestañas tenés? 😬"),
]


# ---------- helpers de Windows ----------
class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
                                     ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)


def work_area():
    r = wintypes.RECT()
    user32.SystemParametersInfoW(48, 0, ctypes.byref(r), 0)
    return r.left, r.top, r.right, r.bottom


def monitors():
    """Areas de trabajo (sin barra de tareas) de todos los monitores: (izq, arriba, der, abajo)."""
    out = []

    def cb(hmon, hdc, rect, lparam):
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(mi)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            w = mi.rcWork
            out.append((w.left, w.top, w.right, w.bottom))
        return True

    try:
        user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
    except Exception:
        pass
    return sorted(out) or [work_area()]


def floors_from(mons):
    """Un piso por monitor; monitores contiguos y a la misma altura se fusionan en uno solo."""
    merged = []
    for l, t, r, b in mons:
        if merged and l <= merged[-1][1] + 2 and abs(b - merged[-1][2]) <= 10:
            merged[-1][1] = max(merged[-1][1], r)
        else:
            merged.append([l, r, b])
    return [(-(i + 1), l, r, b) for i, (l, r, b) in enumerate(merged)]   # ids negativos = pisos


def cursor_pos():
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def window_title(hwnd):
    n = user32.GetWindowTextLengthW(wintypes.HWND(hwnd))
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(wintypes.HWND(hwnd), buf, n + 1)
    return buf.value


def window_platforms(mons):
    """Tops de ventanas visibles como (hwnd, izq, der, y). Descarta lo tapado por otras ventanas."""
    out, higher = [], []

    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if buf.value == TITLE:
            return True
        cloaked = wintypes.DWORD(0)
        dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4)
        if cloaked.value:
            return True
        r = wintypes.RECT()
        if dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
            user32.GetWindowRect(hwnd, ctypes.byref(r))
        l, rt, top, bot = r.left, r.right, r.top, r.bottom
        segs = [(l, rt)]
        for hl, hr, ht, hb in higher:
            if ht <= top < hb:
                new = []
                for a, b in segs:
                    if hr <= a or hl >= b:
                        new.append((a, b))
                    else:
                        if hl > a:
                            new.append((a, hl))
                        if hr < b:
                            new.append((hr, b))
                segs = new
        cx = (l + rt) // 2
        mon = next((m for m in mons if m[0] <= cx < m[2] and m[1] <= top < m[3]), None)
        if mon and mon[1] + 80 <= top <= mon[3] - 30 and bot - top >= 60:
            for a, b in segs:
                if b - a >= 100:
                    out.append((int(hwnd or 0), a, b, top))
        higher.append((l, rt, top, bot))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


STARTUP_LNK = (Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" /
               "Start Menu" / "Programs" / "Startup" / "ClaudePet.lnk")


def set_autostart(on):
    """Crea o borra el acceso directo en la carpeta Inicio de Windows."""
    if not on:
        STARTUP_LNK.unlink(missing_ok=True)
        return
    pyw = Path(sys.executable).with_name("pythonw.exe")
    target = pyw if pyw.exists() else Path(sys.executable)
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
          "$s.TargetPath='%s';$s.Arguments='\"%s\" --startup';"
          "$s.WorkingDirectory='%s';$s.Save()"
          % (STARTUP_LNK, target, Path(__file__).resolve(), HERE))
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=0x08000000)


def single_instance():
    """True si somos la unica mascota corriendo."""
    global _mutex
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "ClaudePetSingleton")
    return ctypes.windll.kernel32.GetLastError() != 183


# ---------- la mascota ----------
class Pet:
    def __init__(self):
        self.root = root = tk.Tk()
        root.title(TITLE)
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-transparentcolor", KEY)
        root.configure(bg=KEY)

        bubble_h = int(70 * D)
        self.W = int(240 * D)
        self.FY = bubble_h + 100 * S                    # y de los pies dentro del canvas
        self.H = int(self.FY + 14 * S)
        self.CX = self.W / 2
        self.c = tk.Canvas(root, width=self.W, height=self.H, bg=KEY, highlightthickness=0)
        self.c.pack()

        self.mons = monitors()
        self.floors = floors_from(self.mons)
        self.wl = min(m[0] for m in self.mons)       # escritorio virtual (todos los monitores)
        self.wt = min(m[1] for m in self.mons)
        self.wr = max(m[2] for m in self.mons)
        self.wb = max(m[3] for m in self.mons)
        f = self.floors[0]
        self.x = random.randint(f[1] + 150, max(f[1] + 151, f[2] - 150))
        self.y = self.wt + 60
        self.vx = self.vy = 0.0
        self.grounded, self.plat, self.resume = False, 0, None
        self.facing, self.moving, self.ox = 1, False, 0
        self.state, self.timer, self.data = "fall", 0, {}
        self.t, self.cool = 0, 0
        self.last_quiet, self.last_joke = 0, 0
        self.speech, self.speech_t = "", 0
        self.dragging, self.moved, self.last_mx = False, False, 0
        self.platforms = []
        self.allow_grab = tk.BooleanVar(value=True)
        self.allow_windows = tk.BooleanVar(value=True)

        c = self.c
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_motion)
        c.bind("<ButtonRelease-1>", self.on_release)
        c.bind("<Button-3>", self.on_menu)
        self.build_menu()

        self.greet_q, self.last_wall = [], time.time()
        self.refresh_platforms()
        self.greeting(boot="--startup" in sys.argv)
        self.tick()

    # ----- saludos segun la hora -----
    def greeting(self, boot=False, back=False):
        now = time.localtime()
        h = now.tm_hour
        pool = ("late" if h < 5 else "morning" if h < 12 else
                "afternoon" if h < 20 else "night")
        lines = [random.choice(GREET[pool])]
        if boot:
            lines.append(random.choice(BOOT_EXTRA))
        elif back:
            lines = [random.choice(BACK_EXTRA), lines[0]]
        elif random.random() < 0.5:
            lines.append(f"Son las {now.tm_hour}:{now.tm_min:02d}")
        start = self.t + (300 if boot else 45)       # al arrancar la PC espera ~10 s
        for i, text in enumerate(lines):
            self.greet_q.append((start + i * 140, text, i == 0))

    def run_greeting(self):
        if not self.greet_q or self.t < self.greet_q[0][0]:
            return
        if not self.grounded or self.dragging:
            return
        _, text, wave = self.greet_q.pop(0)
        self.last_quiet = self.t
        self.say(text, 4)
        if wave:
            self.start("wave", 4)

    # ----- menu -----
    def build_menu(self):
        m = self.menu = tk.Menu(self.root, tearoff=0)
        m.add_command(label="Cambiar de monitor", command=self.next_monitor)
        m.add_command(label="Contame un chiste", command=lambda: self.begin("joke", True))
        m.add_separator()
        for label, kind in [("Dormir", "sleep"), ("Programar", "code"), ("Bailar", "dance"),
                            ("Saludar", "wave"), ("Tomar café", "coffee"), ("Seguime", "follow"),
                            ("Ir a otra ventana", "travel"), ("Sentarse en un borde", "sit"),
                            ("Surfear mi ventana", "surf"), ("Llevame el mouse", "grab")]:
            m.add_command(label=label, command=lambda k=kind: self.begin(k, True))
        m.add_command(label="Subir a una ventana", command=self.climb_now)
        m.add_separator()
        m.add_checkbutton(label="Puede llevarse el mouse", variable=self.allow_grab)
        m.add_checkbutton(label="Puede mover mis ventanas (surf)", variable=self.allow_windows)
        self.autostart = tk.BooleanVar(value=STARTUP_LNK.exists())
        m.add_checkbutton(label="Iniciar con Windows", variable=self.autostart,
                          command=lambda: set_autostart(self.autostart.get()))
        m.add_separator()
        m.add_command(label="Salir", command=self.root.destroy)

    def on_menu(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)

    # ----- mouse sobre la mascota -----
    def on_press(self, e):
        self.press, self.moved, self.last_mx = (e.x_root, e.y_root), False, e.x_root

    def on_motion(self, e):
        if not self.moved and math.hypot(e.x_root - self.press[0], e.y_root - self.press[1]) > 5:
            self.moved, self.dragging, self.resume = True, True, None
            self.start("drag")
            self.say("¡aaah!", 2)
        if self.dragging:
            self.vx = max(-25, min(25, (e.x_root - self.last_mx) * 0.8))
            self.last_mx = e.x_root
            self.x, self.y = e.x_root, e.y_root + 30 * S
            self.grounded = False

    def on_release(self, e):
        if self.dragging:
            self.dragging = False
            self.vy = -3
            self.start("fall")
        else:
            self.say(random.choice(POKES), 2)
            if self.grounded:
                self.jump(random.choice((-2, 2)), -9)

    # ----- habla (con moderacion) -----
    def say(self, text, secs=3.0):
        self.speech, self.speech_t = text, int(secs * 30)

    def quiet(self, text, p=1.0, secs=3.0):
        """Comentario espontaneo: como maximo uno cada ~45 s y no siempre."""
        if self.t - self.last_quiet < 1350 or random.random() > p:
            return
        self.last_quiet = self.t
        self.say(text, secs)

    def comment_window(self, hwnd):
        title = window_title(hwnd).lower()
        for words, text in TITLE_QUIPS:
            if any(w in title for w in words):
                self.quiet(text, 0.5)
                return

    # ----- plataformas / fisica -----
    def refresh_monitors(self):
        mons = monitors()
        if mons == self.mons:
            return
        old, self.mons = len(self.mons), mons
        self.floors = floors_from(mons)
        self.wl, self.wt = min(m[0] for m in mons), min(m[1] for m in mons)
        self.wr, self.wb = max(m[2] for m in mons), max(m[3] for m in mons)
        if len(mons) > old:
            self.say("¡Detecté otro monitor! 🖥️", 4)
        elif len(mons) < old:
            self.say("Se fue un monitor...", 3)

    def refresh_platforms(self):
        if self.t % 60 == 0:
            self.refresh_monitors()
        try:
            plats = window_platforms(self.mons)
        except Exception:
            plats = []
        self.platforms = plats + [(fid, l, r, b) for fid, l, r, b in self.floors]

    def warp_to_floor(self, floor):
        """Teletransporta a la mascota arriba de un piso (cae sola hasta aterrizar)."""
        _, l, r, b = floor
        self.x = random.uniform(l + 60, max(l + 61, r - 60))
        self.y = self.wt - 30
        self.vx = self.vy = 0
        self.grounded = False
        self.start("fall")

    def next_monitor(self):
        if len(self.floors) < 2 and len(self.mons) < 2:
            self.say("Solo veo un monitor 🤷")
            return
        mons = sorted(self.mons)
        cur = next((i for i, m in enumerate(mons) if m[0] <= self.x < m[2]), 0)
        l, t, r, b = mons[(cur + 1) % len(mons)]
        self.warp_to_floor((0, l, r, b))
        self.say("¡Me mudo de monitor!", 2.5)

    def bounds(self):
        for h, l, r, _ in self.platforms:
            if h == self.plat and l - 8 <= self.x <= r + 8:
                return max(l, self.wl + 20), min(r, self.wr - 20)
        return self.wl + 20, self.wr - 20

    def plat_top(self):
        for h, l, r, top in self.platforms:
            if h == self.plat and l - 8 <= self.x <= r + 8:
                return top
        return None

    def top_of(self, hwnd, x):
        for h, l, r, top in self.platforms:
            if h == hwnd and l - 8 <= x <= r + 8:
                return top
        return None

    def physics(self):
        if self.dragging:
            return
        if self.grounded:
            top = self.plat_top()
            if top is None:
                self.grounded, self.vy = False, 0
            else:
                self.y = top
        if not self.grounded:
            self.vy += GRAV
            ny = self.y + self.vy
            self.x = max(self.wl + 10, min(self.wr - 10, self.x + self.vx))
            if self.vy > 0:
                hit = [p for p in self.platforms
                       if p[1] + 5 <= self.x <= p[2] - 5 and self.y <= p[3] + 1 <= ny + 1]
                if hit:
                    self.land(min(hit, key=lambda q: q[3]))
                    return
            self.y = ny
            if self.y > self.wb + 250:               # se cayo fuera del escritorio: reaparece
                near = min(self.floors, key=lambda f: 0 if f[1] <= self.x <= f[2]
                           else min(abs(self.x - f[1]), abs(self.x - f[2])))
                self.warp_to_floor(near)

    def land(self, p):
        self.grounded, self.plat, self.y = True, p[0], p[3]
        self.vx = self.vy = 0
        if self.state in ("jump", "fall"):
            if self.resume:
                self.state, self.data, self.timer = self.resume
                self.resume = None
            else:
                self.start("idle", random.uniform(2, 5))
            if p[0] > 0:
                self.comment_window(p[0])

    def jump(self, vx, vy):
        if self.state in KEEP:
            self.resume = (self.state, self.data, self.timer)
        self.grounded, self.vx, self.vy = False, vx, vy
        self.state, self.timer, self.data = "jump", 0, {}

    def find_target(self, cy=None):
        best = None
        for h, l, r, top in self.platforms:
            if h == self.plat or not (self.y - 500 < top < self.y - 25):
                continue
            dist = 0 if l <= self.x <= r else min(abs(self.x - l), abs(self.x - r))
            if dist > 400:
                continue
            score = dist + (abs(top - cy) if cy is not None else random.random() * 200)
            if best is None or score < best[0]:
                best = (score, max(l + 30, min(r - 30, self.x)), top)
        return best

    def try_climb(self, cy=None):
        if self.cool > 0 or not self.grounded:
            return False
        t = self.find_target(cy)
        if not t:
            return False
        self.cool = 45
        _, tx, top = t
        h = self.y - top
        v0 = math.sqrt(2 * GRAV * (max(h, 0) + 30))
        T = v0 / GRAV + math.sqrt(2 * 30 / GRAV)
        vx = max(-24, min(24, (tx - self.x) / T))
        self.facing = 1 if vx >= 0 else -1
        self.jump(vx, -v0)
        return True

    def climb_now(self):
        if self.grounded and not self.try_climb():
            self.say("no hay nada para subir 🤷")

    # ----- maquina de estados -----
    def start(self, state, secs=None, **data):
        self.state, self.data = state, data
        self.timer = int(secs * 30) if secs else 0

    def begin(self, kind, loud=False):
        """Arranca una actividad. loud=True: la pidio el usuario (puede hablar)."""
        if self.dragging or not self.grounded:
            return
        d = random.choice((-1, 1))
        say = (lambda txt: self.say(txt)) if loud else (lambda txt: self.quiet(txt, 0.25))
        if kind in ("sit", "surf") and (self.plat <= 0 or
                                        (kind == "surf" and not self.allow_windows.get())):
            if loud:
                if self.plat <= 0 and self.try_climb():
                    self.say("primero subo a una ventana")
                else:
                    self.say("no puedo ahora 🤷")
                return
            kind = "walk"
        if kind == "grab" and not self.allow_grab.get():
            if loud:
                self.say("activá 'Puede llevarse el mouse' en el menú")
                return
            kind = "walk"

        if kind == "idle":
            self.start("idle", random.uniform(4, 14))
        elif kind == "walk":
            self.start("walk", random.uniform(4, 12), dir=d)
        elif kind == "climb":
            if not self.try_climb():
                self.start("walk", random.uniform(4, 9), dir=d)
        elif kind == "travel":
            others = [p for p in self.platforms if p[0] != self.plat and p[2] - p[1] > 120]
            if not others:
                self.start("walk", random.uniform(4, 9), dir=d)
            else:
                h, l, r, top = random.choice(others)
                self.start("travel", None, hwnd=h, tx=random.uniform(l + 40, r - 40), n=0)
        elif kind == "sit":
            self.start("sit", None, stage="walk", side=d)
            say(random.choice(PHRASES["sit"]))
        elif kind == "surf":
            self.start("surf", random.uniform(3, 6), dir=d, n=0)
            say(random.choice(PHRASES["surf"]))
        elif kind == "grab":
            self.start("grab", None, phase="approach", t=0)
            say(random.choice(PHRASES["grab"]))
        elif kind == "joke":
            setup, punch = random.choice(JOKES)
            self.last_joke = self.t
            self.start("joke", 4.5, stage=0, punch=punch)
            self.say(setup, 4.5)
        else:
            secs = {"sleep": random.uniform(10, 20), "code": random.uniform(8, 16),
                    "dance": 5, "wave": 3, "coffee": 7, "follow": 12}[kind]
            self.start(kind, secs)
            say(random.choice(PHRASES[kind]))

    def choose_next(self):
        opts = [("idle", 30), ("walk", 24), ("travel", 12), ("sit", 8), ("surf", 5),
                ("sleep", 6), ("code", 8), ("dance", 3), ("wave", 3), ("coffee", 5),
                ("follow", 4), ("climb", 8), ("grab", 2)]
        if self.t - self.last_joke > 3600:           # chistes: como mucho 1 cada 2 min
            opts.append(("joke", 5))
        self.begin(random.choices([o[0] for o in opts], [o[1] for o in opts])[0])

    def step(self, direction, speed):
        self.facing = direction
        self.x += direction * speed
        self.moving = True

    def go_toward(self, cx, cy, speed, stop):
        """Camina/salta hacia (cx, cy). True si llego."""
        dx = cx - self.x
        if cy < self.y - 100 and self.try_climb(cy):
            return False
        if abs(dx) <= stop:
            self.facing = 1 if dx >= 0 else -1
            if cy > self.y + 70 and self.plat > 0:   # objetivo mucho mas abajo: bajar
                self.grounded, self.vx = False, self.facing * 3
                return False
            return cy >= self.y - 100
        self.step(1 if dx > 0 else -1, speed)
        self.x = max(self.wl + 20, min(self.wr - 20, self.x))
        return False

    def behave(self):
        self.moving = False
        self.cool = max(0, self.cool - 1)
        st = self.state
        if st == "drag":
            return
        if not self.grounded:
            if st not in ("jump", "fall"):
                if st in KEEP:
                    self.resume = (st, self.data, self.timer)
                self.start("fall")
            return
        self.timer -= 1
        if st in ("idle", "walk") and random.random() < 0.0004:
            self.quiet(random.choice(QUIPS), 1.0, 2.5)
        getattr(self, "do_" + st, self.do_idle)()

    def do_idle(self):
        if self.timer <= 0:
            self.choose_next()

    def do_walk(self):
        d = self.data["dir"]
        l, r = self.bounds()
        if (self.x <= l + 10 and d < 0) or (self.x >= r - 10 and d > 0):
            if random.random() < 0.85:
                d = self.data["dir"] = -d
        self.step(d, 2.5)
        if self.timer <= 0:
            self.choose_next()

    def do_travel(self):
        d = self.data
        d["n"] += 1
        top = self.top_of(d["hwnd"], d["tx"])
        if d["n"] > 600:
            floor = next((f for f in self.floors if f[0] == d["hwnd"]), None)
            if floor:
                self.warp_to_floor(floor)
            else:
                self.start("idle", 2)
            return
        if top is None:
            self.start("idle", 2)
            return
        self.go_toward(d["tx"], top - 20 * S, 4.5, 12)
        if self.plat == d["hwnd"] and abs(self.x - d["tx"]) <= 14:
            self.start("idle", random.uniform(3, 8))

    def do_sit(self):
        d = self.data
        if d["stage"] == "walk":
            l, r = self.bounds()
            target = r - 4 if d["side"] > 0 else l + 4
            if abs(self.x - target) < 3:
                d["stage"], self.facing = "sit", d["side"]
                self.timer = int(random.uniform(8, 16) * 30)
            else:
                self.step(1 if target > self.x else -1, 2.5)
        elif self.timer <= 0:
            self.choose_next()

    def do_surf(self):
        d, hw = self.data, self.plat
        d["n"] += 1
        stop = d["n"] > 15 and (user32.GetAsyncKeyState(1) & 0x8000)   # click = parar
        r = wintypes.RECT()
        if (hw <= 0 or stop or self.timer <= 0 or user32.IsZoomed(wintypes.HWND(hw))
                or not user32.GetWindowRect(wintypes.HWND(hw), ctypes.byref(r))):
            self.start("idle", 2)
            return
        dx = d["dir"] * 2
        if r.left + dx < self.wl or r.right + dx > self.wr:
            d["dir"] = -d["dir"]
            dx = -dx
        user32.SetWindowPos(wintypes.HWND(hw), None, r.left + dx, r.top, 0, 0, 0x0001 | 0x0004 | 0x0010)
        self.x += dx
        self.facing = d["dir"]
        self.refresh_platforms()

    def do_follow(self):
        cx, cy = cursor_pos()
        self.go_toward(cx, cy, 4, 70)
        if self.timer <= 0:
            self.start("idle", 3)

    def do_sleep(self):
        cx, cy = cursor_pos()
        if math.hypot(cx - self.x, cy - self.y) < 60 and random.random() < 0.02:
            self.say("¡¿qué?!", 2)
            self.start("wave", 2)
        elif self.timer <= 0:
            self.start("idle", 3)

    def do_code(self):
        if self.timer <= 0:
            self.choose_next()

    do_dance = do_wave = do_coffee = do_code

    def do_joke(self):
        d = self.data
        if self.timer > 0:
            return
        if d["stage"] == 0:
            d["stage"] = 1
            self.timer = int(5 * 30)
            self.say(d["punch"], 5)
        else:
            self.start("idle", random.uniform(3, 6))

    def do_grab(self):
        d, (cx, cy) = self.data, cursor_pos()
        if d["phase"] == "approach":
            d["t"] += 1
            if d["t"] > 220:
                self.start("idle", 2)
            elif self.go_toward(cx, cy, 6, 25) and abs(cy - (self.y - 30 * S)) < 120:
                l, r = self.bounds()
                tx = random.uniform(l + 40, r - 40)
                for _ in range(5):
                    if abs(tx - self.x) > 250:
                        break
                    tx = random.uniform(l + 40, r - 40)
                d.update(phase="drag", tx=tx, n=0)
            return
        d["n"] += 1
        stop = d["n"] > 12 and (user32.GetAsyncKeyState(1) & 0x8000)   # click = te lo devuelve
        if stop or abs(d["tx"] - self.x) < 5 or d["n"] > 260:
            self.say("ok ok, te lo devuelvo 😅" if stop else "jaja ¡listo!", 2.5)
            self.start("wave", 2)
            return
        self.step(1 if d["tx"] > self.x else -1, 3)
        user32.SetCursorPos(int(self.x + self.facing * 40 * S), int(self.y - 30 * S))

    # ----- dibujo -----
    def X(self, dx):
        return self.CX + (dx + self.ox) * self.facing * S

    def Y(self, dy):
        return self.FY + dy * S

    def rect(self, x1, y1, x2, y2, fill):
        self.c.create_rectangle(self.X(x1), self.Y(y1), self.X(x2), self.Y(y2), fill=fill, outline="")

    def line(self, x1, y1, x2, y2, w, fill):
        self.c.create_line(self.X(x1), self.Y(y1), self.X(x2), self.Y(y2),
                           width=max(1, w * S), fill=fill, capstyle="butt")

    def eyes(self, kind, bob, e=3):
        if kind == "open":
            self.rect(-18 + e, -45 - bob, -12 + e, -31 - bob, DARK)
            self.rect(10 + e, -45 - bob, 16 + e, -31 - bob, DARK)
        elif kind == "wide":
            self.rect(-19 + e, -47 - bob, -11 + e, -29 - bob, DARK)
            self.rect(9 + e, -47 - bob, 17 + e, -29 - bob, DARK)
        elif kind == "closed":
            self.rect(-18 + e, -39 - bob, -12 + e, -36 - bob, DARK)
            self.rect(10 + e, -39 - bob, 16 + e, -36 - bob, DARK)
        else:  # happy ^ ^
            for cx in (-15 + e, 13 + e):
                self.line(cx - 5, -34 - bob, cx, -41 - bob, 3, DARK)
                self.line(cx, -41 - bob, cx + 5, -34 - bob, 3, DARK)

    def render(self):
        c, t, st = self.c, self.t, self.state
        c.delete("all")
        self.ox = 0
        ph = (t // 4) % 2
        bob, lift, eyes, e = 0, [0, 0, 0, 0], "open", 3
        armL, armR = (-47, -27), (47, -27)
        extra = None

        if self.moving:
            bob, lift = (2, [5, 0, 5, 0]) if ph else (0, [0, 5, 0, 5])
            armL = (-47, -27 + (-5 if ph else 5))
            armR = (47, -27 + (5 if ph else -5))
        else:
            bob = round(math.sin(t * 0.1) * 1.5)

        if st == "dance":
            up = math.sin(t * 0.35) > 0
            bob, self.ox, eyes = abs(math.sin(t * 0.35)) * 9, math.sin(t * 0.17) * 8, "happy"
            armL, armR = (-50, -70 if up else -45), (50, -45 if up else -70)
            lift = [0, 0, 0, 0] if up else [4, 0, 4, 0]
            extra = "note"
        elif st == "wave":
            armR, eyes = (52, -68 + math.sin(t * 0.6) * 8), "happy"
        elif st == "coffee":
            armR, eyes, extra = (30, -36), "happy", "cup"
        elif st == "joke":
            if self.data.get("stage") == 1:
                eyes, bob = "happy", abs(math.sin(t * 0.5)) * 4
        elif st in ("jump", "fall"):
            lift, armL, armR = [6, 6, 6, 6], (-50, -70), (50, -70)
        elif st == "drag":
            lift, bob, eyes = [-4] * 4, 6, "wide"
            armL, armR = (-48, -72), (48, -72)
        elif st == "surf":
            self.ox, eyes = math.sin(t * 0.25) * 2, "happy"
            armL, armR = (-54, -50 + math.sin(t * 0.3) * 5), (54, -50 - math.sin(t * 0.3) * 5)
        elif st == "grab":
            if self.data.get("phase") == "drag":
                armR, extra = (50, -72), "cursor"
            else:
                armR = (52, -52)
        elif st == "code":
            self.ox, e, bob = -35, 4, 0
            armR = (30 + (t // 3 % 3) * 4, -14 - (t // 2 % 2) * 3)
            armL = (36 - (t // 4 % 3) * 4, -14 - (t // 3 % 2) * 3)
            extra = "laptop"

        if st == "sleep":
            self.draw_sleep()
        elif st == "sit" and self.data.get("stage") == "sit":
            self.draw_sit()
        else:
            if t % 100 < 4 and eyes == "open":
                eyes = "closed"
            for lx, lf in zip((-30, -15, 5, 20), lift):
                self.rect(lx, -10 - bob, lx + 9, -lf, ORANGE)
            self.rect(-35, -55 - bob, 35, -10 - bob, ORANGE)
            self.rect(-35, -18 - bob, 35, -10 - bob, SHADE)
            self.eyes(eyes, bob, e)
            self.line(-35, -38 - bob, armL[0], armL[1] - bob * 0.5, 9, ORANGE)
            self.line(35, -38 - bob, armR[0], armR[1] - bob * 0.5, 9, ORANGE)
            if extra == "laptop":
                self.draw_laptop()
            elif extra == "cup":
                self.rect(24, -48, 38, -32, "#f4f4f4")
                self.rect(38, -45, 42, -37, "#f4f4f4")
                for k in range(2):
                    sx = 28 + k * 6 + math.sin(t * 0.3 + k) * 2
                    self.line(sx, -52, sx + 1, -62 - (t // 3 + k * 3) % 4, 2, "#dddddd")
            elif extra == "cursor":
                self.draw_cursor(armR[0], armR[1] - 6)
            elif extra == "note":
                c.create_text(self.X(-58), self.Y(-85 - abs(math.sin(t * 0.2)) * 8), text="♪",
                              fill="#89b4fa", font=("Segoe UI", -int(18 * D), "bold"))
                c.create_text(self.X(58), self.Y(-80 + math.sin(t * 0.25) * 6), text="♫",
                              fill="#f9e2af", font=("Segoe UI", -int(16 * D), "bold"))
        self.draw_bubble(bob)
        self.root.geometry(f"{self.W}x{self.H}+{int(self.x - self.W / 2)}+{int(self.y - self.FY)}")

    def draw_sleep(self):
        t = self.t
        self.rect(-38, -32, 38, -4, ORANGE)
        self.rect(-38, -10, 38, -4, SHADE)
        for lx in (-34, -20, 12, 26):
            self.rect(lx, -4, lx + 8, 0, ORANGE)
        self.eyes("closed", -14, 6)
        for k in range(3):
            p = (t // 2 + k * 12) % 36
            self.c.create_text(self.X(34 + p * 0.5), self.Y(-40 - p), text="zZz"[k],
                               fill="#cdd6f4", font=("Segoe UI", -int((10 + p * 0.25) * D), "bold"))

    def draw_sit(self):
        sw = math.sin(self.t * 0.15) * 3
        self.rect(-35, -47, 35, -2, ORANGE)
        self.rect(-35, -9, 35, -2, SHADE)
        self.eyes("open" if self.t % 120 > 4 else "closed", -8, 4)
        self.rect(10, -2, 19, 11 + sw, ORANGE)
        self.rect(24, -2, 33, 11 - sw, ORANGE)
        self.line(-35, -32, -43, -10, 9, ORANGE)
        self.line(35, -32, 43, -10, 9, ORANGE)

    def draw_laptop(self):
        t = self.t
        self.ox = 0
        self.rect(16, -56, 76, -12, "#c7c9cc")
        self.rect(19, -53, 73, -15, "#11182b")
        for i in range(4):
            w = 8 + ((t // 5 + i * 7) % 5) * 8
            self.rect(23, -49 + i * 8, 23 + w, -45 + i * 8, "#a6e3a1" if i % 2 else "#f5c2e7")
        self.rect(10, -12, 82, -6, "#9aa0a6")

    def draw_cursor(self, hx, hy):
        pts = [(0, 0), (0, 16), (4, 12), (8, 19), (11, 17), (7, 10), (12, 10)]
        flat = []
        for px, py in pts:
            flat += [self.X(hx) + px * S * 1.4 * self.facing, self.Y(hy) + py * S * 1.4 - 4 * S]
        self.c.create_polygon(*flat, fill="white", outline="black")

    def draw_bubble(self, bob):
        if self.speech_t <= 0:
            return
        self.speech_t -= 1
        c = self.c
        tid = c.create_text(self.CX, self.FY - 60 * S - 15 * D - max(bob, 0) * S, text=self.speech,
                            width=210 * D, anchor="s", justify="center", fill="#222",
                            font=("Segoe UI", -int(12 * D)))
        x1, y1, x2, y2 = c.bbox(tid)
        p = 6 * D
        tail = c.create_polygon(self.CX - 6 * D, y2 + p, self.CX + 6 * D, y2 + p,
                                self.CX, y2 + p + 9 * D, fill="white", outline="#444")
        box = c.create_rectangle(x1 - p, y1 - p, x2 + p, y2 + p, fill="white", outline="#444")
        c.tag_lower(box)
        c.tag_lower(tail)

    # ----- loop -----
    def tick(self):
        self.t += 1
        now = time.time()
        if now - self.last_wall > 90:                # la PC estuvo suspendida: saluda al volver
            self.greeting(back=True)
        self.last_wall = now
        self.run_greeting()
        if self.t % 10 == 0 and self.state != "surf":
            self.refresh_platforms()
        self.behave()
        self.physics()
        self.render()
        self.root.after(TICK_MS, self.tick)


if __name__ == "__main__":
    if single_instance():
        Pet().root.mainloop()
