import sounddevice as sd

print("=== HOST APIS ===")
for i, h in enumerate(sd.query_hostapis()):
    print(f"{i:>2} | {h['name']}")

print("\n=== ALL DEVICES ===")
for i, d in enumerate(sd.query_devices()):
    api = sd.query_hostapis(d["hostapi"])["name"]
    ins = d["max_input_channels"]
    outs = d["max_output_channels"]
    sr = int(d["default_samplerate"])
    print(f"{i:>2} | {api:<16} | in:{ins} out:{outs} | {sr:>5} Hz | {d['name']}")
