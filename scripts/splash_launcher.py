"""
Propel ERP - Splash Screen Launcher
Muestra una GUI elegante mientras Django arranca en background.
Diseño: Modern Indigo (coincide con templates/base.html)
"""

import tkinter as tk
import subprocess
import threading
import sys
import os
import time
import webbrowser
import socket
import queue

# ─── CONFIG ────────────────────────────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 8000

# Paleta "Modern Indigo" (base.html)
BG_COLOR    = "#1e1b4b"   # Indigo 950 (Sidebar color)
ACCENT      = "#4f46e5"   # Indigo 600 (Primary)
ACCENT_LIGHT= "#818cf8"   # Indigo 400
SURFACE     = "#312e81"   # Indigo 900 (Ligeramente más claro que BG)
TEXT_WHITE  = "#f8fafc"   # Slate 50
TEXT_MUTED  = "#94a3b8"   # Slate 400

STEPS = [
    (10,  "Verificando entorno..."),
    (30,  "Cargando configuraciones..."),
    (50,  "Conectando base de datos..."),
    (70,  "Iniciando servidor Django..."),
    (90,  "Preparando interfaz..."),
    (100, "¡Bienvenido!"),
]

W, H = 480, 260


# ─── HELPERS ───────────────────────────────────────────────────────────────────

def get_base_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_venv_python(base_dir: str) -> str:
    computername = os.environ.get("COMPUTERNAME", "LOCAL")
    for name in (f"venv_{computername}", "venv"):
        candidate = os.path.join(base_dir, name, "Scripts", "python.exe")
        if os.path.exists(candidate):
            return candidate
    return sys.executable


def wait_for_server(host: str, port: int, timeout: int = 90) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.4)
    return False


# ─── SPLASH UI ─────────────────────────────────────────────────────────────────

class SplashScreen:
    """Ventana de carga: Modern Indigo, minimalista."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=BG_COLOR)

        # Centrar con sombra simulada (Tkinter no tiene sombras reales nativas fáciles)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - W) // 2
        y = (sh - H) // 2
        self.root.geometry(f"{W}x{H}+{x}+{y}")

        self._pct   = 0.0
        self._target = 0.0
        self._bar_total  = W
        self._queue = queue.Queue()

        self._build_ui()
        self._poll_queue()
        self._animate_bar()

    def _build_ui(self):
        # Frame principal con padding
        main_frame = tk.Frame(self.root, bg=BG_COLOR)
        main_frame.pack(fill="both", expand=True, padx=30, pady=30)

        # Logo / Icono (Unicode circle o similar)
        # Usamos Segoe UI que suele estar en Windows y es limpia
        tk.Label(main_frame, text="✨", bg=BG_COLOR, fg=ACCENT_LIGHT,
                 font=("Segoe UI Emoji", 24)).pack(pady=(0, 10))

        # Título
        tk.Label(main_frame, text="Propel ERP", bg=BG_COLOR, fg=TEXT_WHITE,
                 font=("Segoe UI", 24, "bold")).pack()
        
        # Subtítulo
        tk.Label(main_frame, text="Gestión Inteligente", bg=BG_COLOR, fg=ACCENT_LIGHT,
                 font=("Segoe UI", 10, "bold")).pack(pady=(2, 20))

        # Estado
        self._status_var = tk.StringVar(value="Iniciando...")
        tk.Label(main_frame, textvariable=self._status_var,
                 bg=BG_COLOR, fg=TEXT_MUTED,
                 font=("Segoe UI", 9)).pack(side="bottom", pady=(5, 0))

        # Barra de progreso (delgada, bottom)
        # Creamos un frame pegado al fondo de la ventana para la barra
        self.bar_frame = tk.Frame(self.root, bg=SURFACE, height=6)
        self.bar_frame.place(x=0, y=H-6, width=W, height=6)

        self._fill = tk.Frame(self.bar_frame, bg=ACCENT, height=6, width=0)
        self._fill.place(x=0, y=0, relheight=1.0, width=0)

    def _animate_bar(self):
        delta = self._target - self._pct
        if abs(delta) > 0.5:
            self._pct += delta * 0.15
        else:
            self._pct = self._target

        # Ancho barra
        fill_w = int(self._pct / 100 * self._bar_total)
        self._fill.place(x=0, y=0, relheight=1.0, width=fill_w)
        
        self.root.after(20, self._animate_bar)

    def _poll_queue(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                if msg["kind"] == "step":
                    idx = msg["index"]
                    self._target = STEPS[idx][0]
                    self._status_var.set(STEPS[idx][1])
                elif msg["kind"] == "close":
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(50, self._poll_queue)

    def set_step(self, index: int):
        self._queue.put({"kind": "step", "index": index})

    def close(self):
        self._queue.put({"kind": "close"})

    def start(self):
        self.root.mainloop()


# ─── LOGICA DE ARRANQUE ────────────────────────────────────────────────────────

def launch_sequence(splash: SplashScreen):
    base_dir   = get_base_dir()
    python_exe = get_venv_python(base_dir)
    manage_py  = os.path.join(base_dir, "manage.py")

    splash.set_step(0)
    time.sleep(0.5)

    splash.set_step(1)
    time.sleep(0.5)

    splash.set_step(2)
    time.sleep(0.4)

    splash.set_step(3)
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    
    # Lanzar Django
    subprocess.Popen(
        [python_exe, manage_py, "runserver", f"{HOST}:{PORT}", "--noreload"],
        cwd=base_dir,
        creationflags=flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)

    splash.set_step(4)
    if wait_for_server(HOST, PORT, timeout=90):
        splash.set_step(5)
        time.sleep(0.8)
        webbrowser.open(f"http://{HOST}:{PORT}")
        time.sleep(0.5)
        splash.close()
    else:
        # Si falla, cerramos splash igual para no colgar (o podríamos mostrar error)
        splash.close()


if __name__ == "__main__":
    splash = SplashScreen()
    t = threading.Thread(target=launch_sequence, args=(splash,), daemon=True)
    t.start()
    splash.start()
