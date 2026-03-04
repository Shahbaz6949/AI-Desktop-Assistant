import sounddevice as sd

print("--- INPUT DEVICES ---")
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        api = sd.query_hostapis(d["hostapi"])["name"]
        sr = int(d["default_samplerate"])
        name = d["name"]
        print("{:>2} | {:<18} | {:>5} Hz | {}".format(i, api, sr, name))

print("\nTip: Prefer WASAPI/MME. Avoid WDM-KS.")

