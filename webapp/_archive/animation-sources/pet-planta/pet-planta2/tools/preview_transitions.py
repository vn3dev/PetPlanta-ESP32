"""Builds previews/transitions-tour-x4.gif (a tour through moods using the real transition sheets)
and one GIF per transition in previews/transitions/<from>-to-<to>-x4.gif. Run after gen_transitions.py."""
import json, os
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
idx = json.load(open(os.path.join(ROOT, 'sprites', 'sprites.json')))
CELL, BG = idx['cell'], (232, 244, 220)
load = lambda p: Image.open(os.path.join(ROOT, p)).convert('RGBA')
def cells(img, n): return [img.crop((k * CELL, 0, (k + 1) * CELL, CELL)) for k in range(n)]
def flat(f):
    c = Image.new('RGBA', (CELL, CELL), BG + (255,)); c.alpha_composite(f); return c.resize((256, 256), Image.NEAREST).convert('RGB')
def save(path, frames, durs):
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=durs, loop=0, disposal=2)
loops = {m: (cells(load(s['sheet']), s['frames']), s['frameDurationMs']) for m, s in idx['states'].items()}
os.makedirs(os.path.join(ROOT, 'previews', 'transitions'), exist_ok=True)
for key, t in idx['transitions'].items():
    a, b = key.split('>')
    tf = cells(load(t['sheet']), t['frames'])
    fr = [flat(f) for f in loops[a][0]] + [flat(f) for f in tf] + [flat(f) for f in loops[b][0]]
    du = [loops[a][1]] * len(loops[a][0]) + [t['frameDurationMs']] * len(tf) + [loops[b][1]] * len(loops[b][0])
    save(os.path.join(ROOT, 'previews', 'transitions', f'{a}-to-{b}-x4.gif'), fr, du)
tour = ['happy', 'sunny', 'party', 'cold', 'sleep', 'dry', 'sick', 'happy']
fr, du = [], []
for a, b in zip(tour, tour[1:]):
    for _ in range(2): fr += [flat(f) for f in loops[a][0]]; du += [loops[a][1]] * len(loops[a][0])
    t = idx['transitions'][f'{a}>{b}']
    fr += [flat(f) for f in cells(load(t['sheet']), t['frames'])]; du += [t['frameDurationMs']] * t['frames']
save(os.path.join(ROOT, 'previews', 'transitions-tour-x4.gif'), fr, du)
print('ok', len(idx['transitions']))
