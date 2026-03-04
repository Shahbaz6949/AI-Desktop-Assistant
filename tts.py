from __future__ import annotations

import base64
import queue
import subprocess
import threading
from dataclasses import dataclass
from typing import Optional


@dataclass
class TTSConfig:
    # engines: "powershell_sapi" (recommended), "sapi5", "piper"
    engine: str = "powershell_sapi"

    # piper (optional)
    piper_exe: str = "piper/piper.exe"
    piper_voice: str = "piper/voices/en_US-lessac-medium.onnx"


class Speaker:
    """
    ✅ Fix: Speech output must run in ONE dedicated thread.
    This prevents "1-2 words then stop" issues caused by pyttsx3/sapi5 + multi-threads.
    """

    def __init__(self, cfg: TTSConfig):
        self.cfg = cfg
        self._q: "queue.Queue[str]" = queue.Queue()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._current_proc: Optional[subprocess.Popen] = None

        # optional pyttsx3 init (only if user selects sapi5)
        self._pyttsx3 = None
        self._engine = None
        if (cfg.engine or "").lower() == "sapi5":
            try:
                import pyttsx3
                self._pyttsx3 = pyttsx3
                self._engine = pyttsx3.init("sapi5")
                # you can tune voice rate here if you want:
                # self._engine.setProperty("rate", 170)
            except Exception:
                # fallback to powershell
                self.cfg.engine = "powershell_sapi"

        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def speak(self, text: str):
        t = (text or "").strip()
        if not t:
            return

        # prevent extremely long speeches that can feel stuck
        if len(t) > 1200:
            t = t[:1200].rsplit(" ", 1)[0] + "..."

        self._q.put(t)

    def stop(self):
        # stop current speech + clear queue
        with self._lock:
            self._stop_event.set()

            # clear queued items
            try:
                while True:
                    self._q.get_nowait()
            except queue.Empty:
                pass

            # stop current process (powershell) if running
            try:
                if self._current_proc and self._current_proc.poll() is None:
                    self._current_proc.terminate()
            except Exception:
                pass
            self._current_proc = None

            # stop pyttsx3 if used
            try:
                if self._engine is not None:
                    self._engine.stop()
            except Exception:
                pass

            self._stop_event.clear()

    # ---------------- internals ----------------
    def _run(self):
        while True:
            text = self._q.get()
            if not text:
                continue
            if self._stop_event.is_set():
                continue

            eng = (self.cfg.engine or "powershell_sapi").lower()

            try:
                if eng == "sapi5" and self._engine is not None:
                    # ✅ blocking speak in single thread
                    self._engine.say(text)
                    self._engine.runAndWait()
                elif eng == "piper":
                    self._speak_piper(text)
                else:
                    # ✅ default: windows offline SAPI (very stable)
                    self._speak_powershell_sapi(text)
            except Exception:
                # ignore speech errors to avoid crashing app
                pass

    def _speak_powershell_sapi(self, text: str):
        # Pass text safely as base64 to avoid quote issues
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")

        ps = (
            "$b=[Convert]::FromBase64String('" + b64 + "');"
            "$t=[Text.Encoding]::UTF8.GetString($b);"
            "Add-Type -AssemblyName System.Speech;"
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            "$s.Volume=100;"
            "$s.Rate=0;"
            "$s.Speak($t);"
        )

        with self._lock:
            self._current_proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )

        self._current_proc.wait()

        with self._lock:
            self._current_proc = None

    def _speak_piper(self, text: str):
        # Optional: if you really want piper.
        # Needs piper exe + voice model + audio playback setup.
        # Keeping simple: fallback to PowerShell if piper not present.
        self._speak_powershell_sapi(text)
