# JARVIS Offline Assistant (Windows)

This project runs **offline** for:
- LLM (via local Ollama)
- Speech-to-text (via faster-whisper)
- Text-to-speech (Windows SAPI5 via pyttsx3)

> Note: Opening YouTube/Google/LinkedIn requires internet (websites), but the AI itself is local/offline.

## 1) Setup

### A) Create venv + install deps
```powershell
cd C:\jarvis_offline_assistant
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### B) Ollama
Make sure Ollama is running:
```powershell
ollama serve
ollama pull llama3.2:3b
```

### C) Whisper model (local)
Download **Systran/faster-whisper-base** (CTranslate2) and place it here:
`models/faster-whisper-base/`

In `config.json` set:
```json
"whisper_model": "C:\\jarvis_offline_assistant\\models\\faster-whisper-base"
```

## 2) Run
```powershell
.\.venv\Scripts\Activate.ps1
python -u app\main.py
```

## 3) Voice troubleshooting

If you see errors like:
- Invalid sample rate (-9997)
- WDM-KS host error (-9999)

Run this to list devices and choose a better input device (prefer WASAPI/MME):
```powershell
python -c "import sounddevice as sd; print('DEFAULT', sd.default.device); print('--- INPUT DEVICES ---'); [print(i, d['name'], 'hostapi', sd.query_hostapis(d['hostapi'])['name'], 'sr', d['default_samplerate']) for i,d in enumerate(sd.query_devices()) if d['max_input_channels']>0]"
```

Then update `config.json`:
```json
"audio_input_device": <index>,
"audio_sample_rate": 48000
```

## 4) Commands
- `open youtube`
- `youtube search lo fi beats`
- `search on google python venv activate`
- `open linkedin`
- `open file C:\Users\...\Desktop\test.pdf`
