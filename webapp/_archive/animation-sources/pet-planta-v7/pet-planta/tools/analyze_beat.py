"""Beat analysis for the party song: tempo (BPM), beat phase (first beat offset) and stability.
Usage: python3 tools/analyze_beat.py run/audio/song-mono.wav  -> writes run/audio/beat.json
"""
import json, sys, wave
import numpy as np
from scipy.signal import find_peaks

path = sys.argv[1]
with wave.open(path) as w:
    sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768

HOP, NFFT = 256, 1024
frames = 1 + (len(x) - NFFT) // HOP
win = np.hanning(NFFT).astype(np.float32)
idx = np.arange(NFFT)[None, :] + HOP * np.arange(frames)[:, None]
spec = np.abs(np.fft.rfft(x[idx] * win, axis=1))
logs = np.log1p(100 * spec)
flux = np.maximum(0, np.diff(logs, axis=0)).sum(axis=1)
# low band (kick/bass) flux separately
freqs = np.fft.rfftfreq(NFFT, 1 / sr)
low = np.maximum(0, np.diff(logs[:, freqs < 180], axis=0)).sum(axis=1)
fps = sr / HOP
def norm(v):
    v = v - np.convolve(v, np.ones(int(fps)) / int(fps), mode='same'); v = np.maximum(v, 0); return v / (v.std() + 1e-9)
onset, lowo = norm(flux), norm(low)


def tempo(env, lo=70, hi=180):
    ac = np.correlate(env, env, mode='full')[len(env) - 1:]
    lags = np.arange(len(ac)); bpm = 60 * fps / np.maximum(lags, 1)
    m = (bpm >= lo) & (bpm <= hi)
    # weight toward a comfortable 90-130 range to avoid half/double errors
    weight = np.exp(-0.5 * (np.log2(bpm / 110) / 0.9) ** 2)
    score = ac * weight * m
    lag = int(np.argmax(score))
    # parabolic refinement
    a, b, c = ac[lag - 1], ac[lag], ac[lag + 1]
    frac = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0
    return 60 * fps / (lag + frac), score


def best_phase(env, bpm):
    period = 60 * fps / bpm
    best, bo = -1, 0
    for o in np.linspace(0, period, 200, endpoint=False):
        pos = np.arange(o, len(env) - 1, period).astype(int)
        s = env[pos].sum()
        if s > best: best, bo = s, o
    return bo / fps


bpm_all, _ = tempo(onset)
# fine search around the estimate: maximize energy on the beat grid over the whole song
cands = np.linspace(bpm_all - 1.5, bpm_all + 1.5, 301)
def grid_score(b):
    period = 60 * fps / b
    return max(onset[np.arange(o, len(onset) - 1, period).astype(int)].mean() for o in np.linspace(0, period, 48, endpoint=False))
scores = [grid_score(b) for b in cands]
bpm = float(cands[int(np.argmax(scores))])
offset = best_phase(onset + lowo, bpm)

# per-section tempo check (30 s windows)
sections = []
for s0 in range(0, int(len(onset) / fps) - 20, 30):
    seg = onset[int(s0 * fps): int((s0 + 30) * fps)]
    if len(seg) > fps * 10: sections.append(round(tempo(seg)[0], 2))

# downbeat: which beat of 4 has the strongest low-band hits
period = 60 * fps / bpm
beats = np.arange(offset * fps, len(lowo) - 1, period)
bstr = [lowo[beats[i::4].astype(int)].mean() for i in range(4)]
down = int(np.argmax(bstr))
res = dict(bpm=round(bpm, 3), beat_ms=round(60000 / bpm, 3), first_beat_s=round(offset, 4),
           downbeat_index=down, first_downbeat_s=round(offset + down * 60 / bpm, 4),
           section_bpm_estimates=sections, duration_s=round(len(x) / sr, 2), beats_in_song=len(beats),
           beat_strength_by_position=[round(float(v), 3) for v in bstr])
json.dump(res, open(path.rsplit('/', 1)[0] + '/beat.json', 'w'), indent=2)
print(json.dumps(res, indent=2))
