from __future__ import annotations

import re
import tempfile
import wave
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np


@dataclass
class STTConfig:
    whisper_model: str = "base"
    device: str = "cpu"
    compute_type: str = "int8"

    vad_silence_ms: int = 1600
    max_record_seconds: int = 25
    vad_energy_multiplier: float = 2.0

    input_device: Optional[int] = None
    preferred_sample_rate: int = 48000
    channels: int = 2

    wasapi_exclusive: bool = False


class SpeechToText:
    def __init__(self, cfg: STTConfig):
        self.cfg = cfg
        from faster_whisper import WhisperModel

        model_path = cfg.whisper_model
        if model_path and Path(model_path).exists():
            self.model = WhisperModel(model_path, device=cfg.device, compute_type=cfg.compute_type)
        else:
            self.model = WhisperModel(model_path or "base", device=cfg.device, compute_type=cfg.compute_type)

    # ---- WASAPI helpers ----
    def _hostapi_name(self, device_index: int) -> str:
        import sounddevice as sd
        d = sd.query_devices(device_index)
        api = sd.query_hostapis(d["hostapi"])["name"]
        return str(api)

    def _is_wasapi(self, device_index: int) -> bool:
        try:
            return "WASAPI" in self._hostapi_name(device_index).upper()
        except Exception:
            return False

    def _make_extra_settings(self, device_index: Optional[int]):
        if device_index is None:
            return None
        try:
            import sounddevice as sd
            if self._is_wasapi(int(device_index)):
                return sd.WasapiSettings(exclusive=bool(self.cfg.wasapi_exclusive))
        except Exception:
            pass
        return None

    # ---- sample-rate candidates ----
    def _device_default_sr(self, device_index: Optional[int]) -> int:
        import sounddevice as sd
        try:
            if device_index is None:
                device_index = sd.default.device[0]
            info = sd.query_devices(int(device_index), "input")
            return int(info.get("default_samplerate", 48000))
        except Exception:
            return 48000

    def _candidate_srs(self, device_index: Optional[int]) -> list[int]:
        srs = []
        if self.cfg.preferred_sample_rate:
            srs.append(int(self.cfg.preferred_sample_rate))
        srs.append(self._device_default_sr(device_index))
        srs += [48000, 44100, 32000, 16000]
        out = []
        for x in srs:
            if x not in out:
                out.append(x)
        return out

    def record_until_silence(self, level_cb: Optional[Callable[[float], None]] = None) -> Path:
        import sounddevice as sd

        dev = self.cfg.input_device
        dev = int(dev) if dev is not None else None

        extra = self._make_extra_settings(dev)

        last_err: Optional[Exception] = None
        for sr in self._candidate_srs(dev):
            try:
                return self._record(
                    samplerate=int(sr),
                    level_cb=level_cb,
                    device_index=dev,
                    extra_settings=extra,
                )
            except Exception as e:
                last_err = e
                continue

        raise RuntimeError(f"Error opening InputStream at all sample rates. Last error: {last_err}")

    def _record(
        self,
        samplerate: int,
        level_cb: Optional[Callable[[float], None]],
        device_index: Optional[int],
        extra_settings,
    ) -> Path:
        import sounddevice as sd

        channels = max(1, int(self.cfg.channels or 1))

        # WASAPI pe blocksize=0 stable hota hai
        stream_blocksize = 0 if (device_index is not None and self._is_wasapi(int(device_index))) else 1024
        read_block = 1024

        max_secs = int(self.cfg.max_record_seconds)
        silence_ms = int(self.cfg.vad_silence_ms)

        silence_blocks_needed = max(1, int((silence_ms / 1000.0) * samplerate / read_block))

        # minimum speech duration before we allow stopping (prevents “1–2 lafz” stop)
        min_speech_blocks = max(3, int(1.0 * samplerate / read_block))

        preroll = deque(maxlen=12)
        frames: list[np.ndarray] = []
        started = False
        silent_blocks = 0
        speech_blocks = 0

        noise_rms_vals: list[float] = []
        noise_blocks = max(6, int(0.6 * samplerate / read_block))  # ~0.6 sec

        def rms(x: np.ndarray) -> float:
            return float(np.sqrt(np.mean(np.square(x), dtype=np.float64)) + 1e-9)

        with sd.InputStream(
            device=device_index,
            samplerate=int(samplerate),
            channels=int(channels),
            dtype="float32",
            blocksize=int(stream_blocksize),
            extra_settings=extra_settings,
        ) as stream:
            total_blocks = int((samplerate * max_secs) / read_block)

            for _ in range(total_blocks):
                data, _ = stream.read(read_block)
                x = np.asarray(data, dtype=np.float32)

                # multi-channel -> mono
                if x.ndim == 2 and x.shape[1] > 1:
                    x = np.mean(x, axis=1)
                else:
                    x = np.squeeze(x)

                r = rms(x)

                if level_cb:
                    level_cb(max(0.05, min(1.0, r * 8.0)))

                if len(noise_rms_vals) < noise_blocks:
                    noise_rms_vals.append(r)
                    preroll.append(x.copy())
                    continue

                noise_floor = float(np.median(noise_rms_vals)) + 1e-6

                # ✅ threshold ko zyada high mat rakho (warna beech beech me silence samajh lega)
                thr = max(noise_floor * float(self.cfg.vad_energy_multiplier), noise_floor + 0.002, 0.004)

                preroll.append(x.copy())

                if not started:
                    if r > thr:
                        started = True
                        frames.extend(list(preroll))
                        silent_blocks = 0
                        speech_blocks = 0
                    continue

                frames.append(x.copy())
                speech_blocks += 1

                if r < thr:
                    silent_blocks += 1
                else:
                    silent_blocks = 0

                # ✅ don’t stop too early — at least ~1 sec speech required
                if speech_blocks >= min_speech_blocks:
                    if silent_blocks >= silence_blocks_needed and len(frames) > noise_blocks:
                        break

        if not frames:
            frames = [np.zeros(read_block, dtype=np.float32)]

        audio = np.concatenate(frames)
        pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp_path = Path(tmp.name)
        tmp.close()

        with wave.open(str(tmp_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(int(samplerate))
            wf.writeframes(pcm.tobytes())

        return tmp_path

    def transcribe(self, wav_path: Path) -> str:
        segments, _info = self.model.transcribe(str(wav_path), beam_size=1)
        parts = []
        for seg in segments:
            if seg.text:
                parts.append(seg.text.strip())
        return " ".join(parts).strip()
