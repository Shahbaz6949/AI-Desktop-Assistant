from __future__ import annotations

import sys
import threading
import re
from pathlib import Path

# ✅ FIX: Allow imports like "from core.utils import ..."
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from core.utils import load_config
from core.llm import OllamaLLM
from core.router import route_command
from core.stt import SpeechToText, STTConfig
from core.tts import Speaker, TTSConfig


class Backend(QObject):
    statusChanged = Signal()
    transcriptChanged = Signal()
    responseChanged = Signal()
    ringLevelChanged = Signal()

    def __init__(self):
        super().__init__()
        self._status = "Ready"
        self._transcript = ""
        self._response = ""
        self._ring_level = 0.15

        self.cfg = load_config()

        # ✅ Force WASAPI mic + samplerate (avoid WDM-KS errors)
        # NOTE: config.json me "audio_input_device": 9 (WASAPI mic) rakhein
        try:
            import sounddevice as sd
            mic_index = self.cfg.get("audio_input_device", None)
            sr = int(self.cfg.get("audio_sample_rate", 48000))
            ch = int(self.cfg.get("audio_channels", 1))

            if mic_index is not None:
                mic_index = int(mic_index)
                sd.default.device = (mic_index, None)   # (input, output)
                sd.default.samplerate = sr
                print(f"[AUDIO] default input device={mic_index}, samplerate={sr}, channels={ch}", file=sys.stderr)
        except Exception as e:
            print(f"[AUDIO] Could not set defaults: {e}", file=sys.stderr)

        # Names
        self.assistant_name = self.cfg.get("assistant_name", "JARVIS")
        self.user_name = self.cfg.get("user_name", "User")

        # system prompt formatting
        sys_prompt_tpl = self.cfg.get("system_prompt", "You are a helpful assistant.")
        system_prompt = sys_prompt_tpl.format(assistant_name=self.assistant_name, user_name=self.user_name)

        self.llm = OllamaLLM(
            model=self.cfg.get("ollama_model", "llama3.2:3b"),
            system_prompt=system_prompt,
            host=self.cfg.get("ollama_host", "http://localhost:11434"),
        )

        # ✅ Mic settings from config (used by STT)
        mic_index = self.cfg.get("audio_input_device", None)
        mic_index = int(mic_index) if mic_index is not None else None
        sr_pref = int(self.cfg.get("audio_sample_rate", 48000))

        self.stt = SpeechToText(STTConfig(
            whisper_model=self.cfg.get("whisper_model", "base"),
            device=self.cfg.get("whisper_device", "cpu"),
            compute_type=self.cfg.get("whisper_compute_type", "int8"),
            vad_silence_ms=int(self.cfg.get("vad_silence_ms", 900)),
            max_record_seconds=int(self.cfg.get("max_record_seconds", 20)),
            vad_energy_multiplier=float(self.cfg.get("vad_energy_multiplier", 3.0)),
            input_device=mic_index,
            preferred_sample_rate=sr_pref,
        ))

        self.speaker = Speaker(TTSConfig(
            engine=self.cfg.get("tts_engine", "sapi5"),
            piper_exe=self.cfg.get("piper_exe", "piper/piper.exe"),
            piper_voice=self.cfg.get("piper_voice", "piper/voices/en_US-lessac-medium.onnx"),
        ))

        self.chrome_preferred = bool(self.cfg.get("chrome_preferred", True))
        self.chrome_path = self.cfg.get("chrome_path", "") or None

        self.allow_open_file = bool(self.cfg.get("allow_open_file", True))
        self.allow_open_url = bool(self.cfg.get("allow_open_url", True))
        self.allow_open_app = bool(self.cfg.get("allow_open_app", True))

        self._busy_lock = threading.Lock()

    # ----- Properties exposed to QML -----
    def getStatus(self):
        return self._status

    def setStatus(self, v):
        if v != self._status:
            self._status = v
            self.statusChanged.emit()

    status = Property(str, getStatus, notify=statusChanged)

    def getTranscript(self):
        return self._transcript

    transcript = Property(str, getTranscript, notify=transcriptChanged)

    def getResponse(self):
        return self._response

    response = Property(str, getResponse, notify=responseChanged)

    def getRingLevel(self):
        return self._ring_level

    ringLevel = Property(float, getRingLevel, notify=ringLevelChanged)

    def _set_transcript(self, txt: str):
        self._transcript = txt
        self.transcriptChanged.emit()

    def _set_response(self, txt: str):
        self._response = txt
        self.responseChanged.emit()

    def _set_ring_level(self, x: float):
        x = max(0.05, min(1.0, float(x)))
        self._ring_level = x
        self.ringLevelChanged.emit()

    # ----- Actions -----
    @Slot()
    def startVoice(self):
        # ✅ UI proof: if this doesn't show, QML is not calling backend
        self._set_transcript("[VOICE] StartVoice clicked ✅")
        self.setStatus("Starting mic...")

        if not self._busy_lock.acquire(blocking=False):
            self.setStatus("Busy... (try again)")
            self._set_transcript("[VOICE] Busy lock held ❌")
            return

        t = threading.Thread(target=self._voice_flow, daemon=True)
        t.start()

    @Slot()
    def stopSpeaking(self):
        self.speaker.stop()
        self.setStatus("Stopped speaking")

    @Slot(str)
    def sendText(self, text: str):
        if not text or not text.strip():
            return
        if not self._busy_lock.acquire(blocking=False):
            self.setStatus("Busy... (try again)")
            return
        t = threading.Thread(target=self._text_flow, args=(text.strip(),), daemon=True)
        t.start()

    # ----- Internal flows -----
    def _voice_flow(self):
        wav_path = None
        try:
            self.setStatus("Listening...")
            self._set_response("")
            self._set_transcript("[VOICE] Listening... 🎤")

            wav_path = self.stt.record_until_silence(level_cb=self._set_ring_level)

            self.setStatus("Transcribing...")
            self._set_transcript("[VOICE] Transcribing... ✍️")

            txt = self.stt.transcribe(wav_path)
            self._set_transcript(txt or "[VOICE] Empty transcript ❌")

            if not txt:
                self.setStatus("Ready (no speech detected)")
                return

            self._handle_user_text(txt)

        except Exception as e:
            self.setStatus(f"Error (voice): {e}")
            self._set_transcript(f"[VOICE] ERROR: {e}")

        finally:
            try:
                if wav_path and Path(wav_path).exists():
                    Path(wav_path).unlink(missing_ok=True)
            except Exception:
                pass
            try:
                if self._busy_lock.locked():
                    self._busy_lock.release()
            except Exception:
                pass
            self._set_ring_level(0.15)

    def _text_flow(self, text: str):
        try:
            self._set_transcript(text)
            self._set_response("")
            self._handle_user_text(text)
        except Exception as e:
            self.setStatus(f"Error: {e}")
        finally:
            try:
                if self._busy_lock.locked():
                    self._busy_lock.release()
            except Exception:
                pass

    def _handle_user_text(self, text: str):
        raw = (text or "").strip()

        # normalize for command matching
        t = re.sub(r"\s+", " ", raw).strip().lower()
        t = re.sub(r"[^\w\s:/\.-\u0600-\u06FF]", "", t)

        # wake word
        t = re.sub(r"^(jarvis|jervis|jarviz)\s+", "", t).strip()

        # common STT variants
        t = t.replace("you tube", "youtube").replace("u tube", "youtube").replace("linked in", "linkedin")

        # Urdu -> English keywords
        t = t.replace("یوٹیوب", "youtube").replace("یوتیوب", "youtube")
        t = t.replace("لنکڈان", "linkedin").replace("لنکڈ اِن", "linkedin").replace("لنکڈ", "linkedin")
        t = t.replace("گوگل", "google")

        # Roman-Urdu verbs -> English intent
        t = re.sub(r"\b(kholo|khol do|kholde|kholna|khol|open karo|khul jao)\b", "open", t)
        t = re.sub(r"\b(search karo|dhoondo|dhondo|find karo|talash karo)\b", "search", t)

        if "youtube" in t and "open" not in t and "search" not in t:
            t = "open youtube"
        if "linkedin" in t and "open" not in t:
            t = "open linkedin"

        # greet shortcut
        if t in ("hello", "hi", "assalam o alaikum", "salam"):
            greet = f"Good morning, {self.user_name}! How can I assist you today?"
            self._set_response(greet)
            self.speaker.speak(greet)
            self.setStatus("Ready")
            return

        rr = route_command(
            t,
            chrome_preferred=self.chrome_preferred,
            chrome_path=self.chrome_path,
            allow_open_file=self.allow_open_file,
            allow_open_url=self.allow_open_url,
            allow_open_app=self.allow_open_app,
        )
        if rr.handled:
            self.setStatus(rr.action_text)
            self._set_response(rr.action_text)
            self.speaker.speak(rr.action_text)
            self.setStatus("Ready")
            return

        # ✅ LLM streaming (UI update hoti rahe) + end pe ONE SHOT speak
        self.setStatus("Thinking...")
        full = ""
        for chunk in self.llm.stream_chat(raw):
            full += chunk
            self._set_response(full)

        final = full.strip()
        if final:
            self.speaker.speak(final)

        self.setStatus("Ready")


def main():
    app = QGuiApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    engine = QQmlApplicationEngine()

    backend = Backend()
    engine.rootContext().setContextProperty("backend", backend)

    qml_path = Path(__file__).parent / "ui" / "Main.qml"
    if not qml_path.exists():
        print(f"[ERROR] Main.qml not found at: {qml_path}", file=sys.stderr)
        sys.exit(1)

    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        print("[ERROR] QML failed to load (rootObjects empty).", file=sys.stderr)
        sys.exit(1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
