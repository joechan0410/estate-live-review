"""Generate a small, non-speech playback fixture using only Python's standard library."""
from pathlib import Path
import math
import struct
import wave

output = Path(__file__).resolve().parents[1] / 'public/audio/demo-tones.wav'
output.parent.mkdir(parents=True, exist_ok=True)
rate, duration = 8000, 24
with wave.open(str(output), 'wb') as audio:
    audio.setnchannels(1)
    audio.setsampwidth(2)
    audio.setframerate(rate)
    samples = bytearray()
    notes = [261.63, 329.63, 392.0, 523.25]
    for i in range(rate * duration):
        t = i / rate
        phase = t % 3
        envelope = max(0, min(1, phase / .08, (2.3 - phase) / .3))
        note = notes[int(t // 3) % len(notes)]
        value = .12 * envelope * (math.sin(2 * math.pi * note * t) + .3 * math.sin(2 * math.pi * note * 2 * t))
        samples.extend(struct.pack('<h', int(value * 32767)))
    audio.writeframes(samples)
print(output.name, output.stat().st_size)
