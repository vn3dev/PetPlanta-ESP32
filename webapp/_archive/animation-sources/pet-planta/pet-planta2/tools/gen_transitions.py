"""Pet Planta - one hand-tuned transition animation for every ordered pair of moods (7x6 = 42).

Each transition is 8 frames (64x64) that really morph the plant instead of cross-fading:
  - palette and leaf droop interpolate from the old mood to the new one (eased, stepped),
  - the head moves to the new pose with a mood-specific reaction (joy hop, slump, shiver...),
  - the face goes: surprise -> blink -> reaction of the new mood -> new mood face,
  - accessories have entrances/exits (sunglasses drop on / slide off, party hat falls and bounces / flies off),
  - a themed particle FX of the TARGET mood (hearts, confetti, sun, snow, moon+bubbles, dust+sweat, germs).
The last frame is exactly the last frame of the target loop, so the loop continues seamlessly from frame 0.
Run after gen_plant.py: python3 tools/gen_transitions.py
"""
import importlib.util, json, math, os, random
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('gp', os.path.join(HERE, 'gen_plant.py'))
gp = importlib.util.module_from_spec(spec); spec.loader.exec_module(gp)
gp.POT_IMG = gp.draw_pot()

CELL, NF, MS = 64, 8, 70
ROOT = gp.ROOT
C, INK, WHITE = gp.C, gp.INK, gp.WHITE
MOODS = list(gp.MOODS)
UP = {'happy', 'party', 'sunny'}


# ---------- palette / crown interpolation ----------
def lerp_hex(a, b, t):
    ca, cb = C(a), C(b)
    return '%02x%02x%02x' % tuple(round(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))


def mix_pal(A, B, t):
    pa, pb = gp.PAL[A], gp.PAL[B]
    out = {}
    for k in ('head', 'shade', 'hi', 'leaf1', 'leaf2', 'stem', 'stemd'):
        out[k] = lerp_hex(pa[k], pb[k], t)
    out['tip'] = lerp_hex(pa['tip'] or pa['leaf1'], pb['tip'] or pb['leaf1'], t)
    out['blush'] = (pa['blush'] if t < 0.5 else pb['blush'])
    return out


_crowns = {}


def crown(pal, droop):
    key = (tuple(sorted((k, v or '') for k, v in pal.items())), round(droop, 3))
    if key not in _crowns: _crowns[key] = gp.render_crown(pal, droop)
    return _crowns[key]


def ease(t):
    return t * t * (3 - 2 * t)


# ---------- extra faces used only in transitions ----------
def mouth(d, cx, cy, kind):
    my = cy + 5
    if kind == 'o':
        d.rectangle([cx - 1, my, cx + 1, my + 2], fill=INK); d.point((cx, my + 1), fill=C('8a2b3d'))
    elif kind == 'yawn':
        d.rectangle([cx - 2, my - 1, cx + 2, my + 3], fill=INK); d.rectangle([cx - 1, my, cx + 1, my + 2], fill=C('8a2b3d'))
        d.point((cx, my + 2), fill=C('f2788f'))
    else:
        gp.draw_mouth(d, cx, cy, kind)


# ---------- particles (target mood FX) ----------
def heart(d, x, y, col):
    for yy, row in enumerate(['.X.X.', 'XXXXX', '.XXX.', '..X..']):
        for xx, ch in enumerate(row):
            if ch == 'X': d.point((x + xx, y + yy), fill=col)


def fx_layer(B, k):
    im = Image.new('RGBA', (CELL, CELL)); d = ImageDraw.Draw(im)
    rnd = random.Random(B)
    if k < 2: return im
    s = k - 2  # 0..5
    if B == 'happy':
        for j, (x0, y0) in enumerate([(9, 26), (49, 22), (15, 12), (45, 9)]):
            if s >= j * 0.7:
                heart(d, x0 + (1 if (s + j) % 2 else 0), y0 - 3 * (s - j // 2), C('ff6f91') if j % 2 else C('ff8fab'))
    elif B == 'party':
        cols = ['f06b9a', 'f7c531', '4aa8e8', '7ed957', 'b57cf2', 'ffffff']
        for j in range(16):
            x0, y0, vy, vx = rnd.randint(4, 59), rnd.randint(-14, 6), rnd.randint(3, 6), rnd.choice((-1, 0, 1))
            x, y = x0 + vx * s, y0 + vy * s
            col = C(cols[j % len(cols)])
            if (s + j) % 2: d.line([x, y, x + 1, y], fill=col)
            else: d.line([x, y, x, y + 1], fill=col)
    elif B == 'sunny':
        r = [2, 3, 4, 4, 3, 0][s]
        if r:
            cx, cy = 53, 9
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C('ffd23f'))
            for a in range(0, 360, 45):
                a2 = math.radians(a + (22 if s % 2 else 0))
                d.point((round(cx + (r + 2) * math.cos(a2)), round(cy + (r + 2) * math.sin(a2))), fill=C('ffb627'))
        for j, (x0, y0) in enumerate([(10, 18), (50, 30), (14, 36)]):
            if 1 <= s <= 4 and (s + j) % 2 == 0:
                d.line([x0 - 1, y0, x0 + 1, y0], fill=C('ffe066')); d.line([x0, y0 - 1, x0, y0 + 1], fill=C('ffe066'))
    elif B == 'cold':
        for j in range(9):
            x0, y0, vy = rnd.randint(5, 58), rnd.randint(-16, 4), rnd.randint(2, 4)
            x, y = x0 + (1 if (s + j) % 3 == 0 else 0), y0 + vy * s
            d.line([x - 1, y, x + 1, y], fill=WHITE); d.line([x, y - 1, x, y + 1], fill=WHITE)
            d.point((x, y), fill=C('bfe6ff'))
    elif B == 'sleep':
        r = [2, 3, 4, 4, 3, 0][s]
        if r:
            cx, cy = 52, 10
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C('fff2a8'))
            d.ellipse([cx - r + 2, cy - r - 1, cx + r + 2, cy + r - 1], fill=(0, 0, 0, 0))
        for j, (x0, y0) in enumerate([(44, 24), (47, 20), (41, 16)]):
            y = y0 - 2 * (s - j)
            if s >= j and y > 2:
                rr = 1 + (j % 2)
                d.ellipse([x0 - rr, y - rr, x0 + rr, y + rr], outline=C('cfe8ff'))
        if s in (1, 3): d.point((10, 8), fill=WHITE); d.point((16, 14), fill=C('fff2a8'))
    elif B == 'dry':
        if s <= 4:  # sweat drop sliding down the head
            x, y = 45, 12 + 3 * s
            d.point((x, y), fill=C('bfe6ff')); d.line([x - 1, y + 1, x + 1, y + 1], fill=C('8fd0ff'))
            d.line([x - 1, y + 2, x + 1, y + 2], fill=C('8fd0ff')); d.point((x, y + 3), fill=C('8fd0ff'))
        for j in range(6):
            x0, y0 = rnd.randint(8, 56), rnd.randint(4, 30)
            if (s + j) % 2: d.point((x0 + s, y0 + 2 * s), fill=C('c9a96e'))
        lx, ly = 12 + (1 if s % 2 else -1), 14 + 4 * s  # a dry leaf falling
        d.line([lx, ly, lx + 2, ly], fill=C('a07a3a')); d.point((lx + 1, ly - 1), fill=C('a07a3a'))
    elif B == 'sick':
        cols = [C('a07bd8'), C('86b05a')]
        for j, (x0, y0) in enumerate([(14, 28), (50, 26), (20, 18), (46, 14), (32, 6)]):
            y = y0 - 3 * (s - j // 2)
            if s >= j // 2 and y > 1:
                rr = 1 + (j % 2)
                x = x0 + (1 if (s + j) % 2 else -1)
                d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=cols[j % 2])
    return gp.outline(im)


# ---------- choreography ----------
EXIT_EYES = {'happy': 'open', 'party': 'happy', 'sunny': 'open', 'cold': 'squeeze', 'sleep': 'blink', 'dry': 'tired', 'sick': 'x'}
REACT = {  # (k3, k4) faces for the target mood
    'happy': [('happy', 'big'), ('happy', 'smile')],
    'party': [('open', 'o'), ('happy', 'big')],
    'sunny': [('happy', 'grin'), ('happy', 'grin')],
    'cold':  [('squeeze', 'o'), ('squeeze', 'teeth')],
    'sleep': [('tired', 'yawn'), ('blink', 'yawn')],
    'dry':   [('tired', 'flat'), ('tired', 'frown')],
    'sick':  [('tired', 'wavy'), ('x', 'wavy')],
}
REACT_DY = {
    'happy': [0, -1, -2, -2, -1, 0, 0, 0], 'party': [0, -1, -3, -4, -3, -1, 1, 0], 'sunny': [0, -1, -2, -1, 0, 0, 0, 0],
    'cold': [0, 0, 0, 0, 0, 0, 0, 0], 'sleep': [0, -1, 0, 1, 1, 0, 0, 0], 'dry': [0, -1, 0, 1, 2, 1, 0, 0], 'sick': [0, -1, 0, 1, 2, 1, 0, 0],
}
GLASS_IN = {3: -14, 4: -6, 5: 1, 6: 0}
GLASS_OUT = {1: 0, 2: -6, 3: -14, 4: -24}
HAT_IN = {2: -24, 3: -14, 4: -6, 5: 1, 6: 0}
HAT_OUT = {1: 0, 2: -5, 3: -12, 4: -22, 5: -34}


def render(pal, droop, p):
    cr = crown(pal, droop)
    cx, cy = gp.HCX + p['dx'], gp.HCY + p['dy']
    sq = p.get('sq', 0); rx, ry = gp.RX + sq, gp.RY - sq
    plant = Image.new('RGBA', (CELL, CELL)); d = ImageDraw.Draw(plant)
    gp.draw_stem(d, cx, cy + ry - 1, pal)
    sp = p.get('spread', 0)
    for depth in ('back', 'front'):
        for g in 'LTR':
            ox = p['cdx'] + p.get('sw', 0) + (-sp if g == 'L' else sp if g == 'R' else 0)
            oy = p['cdy'] - (sp if g == 'T' else 0)
            gp.paste(plant, cr[depth][g], ox, oy)
    d = ImageDraw.Draw(plant)
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=C(pal['shade']))
    d.ellipse([cx - rx, cy - ry, cx + rx - 2, cy + ry - 2], fill=C(pal['head']))
    d.ellipse([cx - 8, cy - 8, cx - 2, cy - 4], fill=C(pal['hi']))
    if pal['blush']:
        d.rectangle([cx - 11, cy + 3, cx - 9, cy + 4], fill=C(pal['blush']))
        d.rectangle([cx + 8, cy + 3, cx + 10, cy + 4], fill=C(pal['blush']))
    gp.draw_eyes(d, cx, cy, p['eyes'])
    mouth(d, cx, cy, p['mouth'])
    if p.get('glasses') is not None: gp.draw_glasses(d, cx, cy + p['glasses'], None)
    if p.get('hat') is not None: gp.draw_beanie(d, cx, cy + p['hat'], 0)
    if p.get('chain'): gp.draw_chain(d, cx, cy, 0)
    out = gp.outline(plant)
    if p.get('mic') is not None:
        arms = Image.new('RGBA', (CELL, CELL)); gp.draw_mic(ImageDraw.Draw(arms), cx, cy, p['mic'], C(pal['head']))
        out.alpha_composite(gp.outline(arms, 0.4))
    out.alpha_composite(gp.POT_IMG)
    return out


def transition(A, B):
    nb = len(gp.MOODS[B]['frames']); fa, fb = gp.MOODS[A]['frames'][0], gp.MOODS[B]['frames'][nb - 1]
    da, db = gp.MOODS[A]['droop'], gp.MOODS[B]['droop']
    frames, prev = [], None
    first = gp.render_frame(A, gp.MOODS[A], 0, gp.render_crown(gp.PAL[A], da))
    last = gp.render_frame(B, gp.MOODS[B], nb - 1, gp.render_crown(gp.PAL[B], db))
    for k in range(NF):
        if k == 0: frames.append(first); prev = (fa['dx'], fa['dy']); continue
        if k == NF - 1:
            f = last.copy(); f.alpha_composite(fx_layer(B, k)); frames.append(f); continue
        t = ease(k / (NF - 1))
        tq = round(t * 6) / 6
        pal = mix_pal(A, B, tq)
        droop = da + (db - da) * tq
        dx = round(fa['dx'] + (fb['dx'] - fa['dx']) * t)
        dy = round(fa['dy'] + (fb['dy'] - fa['dy']) * t) + REACT_DY[B][k]
        if B == 'cold' and k >= 3: dx += (-1, 1)[k % 2]
        if k == 1: eyes, mo = EXIT_EYES[A], 'o'
        elif k == 2: eyes, mo = 'blink', 'o'
        elif k in (3, 4): eyes, mo = REACT[B][k - 3]
        else:
            eyes, mo = fb['eyes'], fb['mouth']
            if eyes == 'none': eyes = 'happy'
        p = dict(dx=dx, dy=dy, cdx=prev[0], cdy=prev[1], eyes=eyes, mouth=mo,
                 spread=(1 if (B in UP and 2 <= k <= 4) else 0),
                 sw=((-1, 1)[k % 2] if B in UP and k in (1, 2) else 0),
                 sq=(1 if B in ('party', 'happy') and k == 5 else 0))
        if B == 'sunny' and A != 'sunny' and k in GLASS_IN: p['glasses'] = GLASS_IN[k]
        if A == 'sunny' and B != 'sunny' and k in GLASS_OUT: p['glasses'] = GLASS_OUT[k]
        if B == 'party' and A != 'party' and k in HAT_IN: p['hat'] = HAT_IN[k]
        if A == 'party' and B != 'party' and k in HAT_OUT: p['hat'] = HAT_OUT[k]
        # chain + microphone: pop in near the end when entering the party, drop right away when leaving it
        if (B == 'party' and k >= 5) or (A == 'party' and k <= 1):
            p['chain'] = True; p['mic'] = 1 if k % 2 else 0
        f = render(pal, droop, p)
        f.alpha_composite(fx_layer(B, k))
        frames.append(f)
        prev = (dx, dy)
    return frames


def main():
    tdir = os.path.join(ROOT, 'sprites', 'transitions'); os.makedirs(tdir, exist_ok=True)
    qa = os.path.join(ROOT, 'run', '64', 'qa', 'transitions'); os.makedirs(qa, exist_ok=True)
    idx_path = os.path.join(ROOT, 'sprites', 'sprites.json')
    idx = json.load(open(idx_path)); idx['transitions'] = {}
    bg = (232, 244, 220, 255)
    for A in MOODS:
        review = Image.new('RGBA', (CELL * NF, CELL * (len(MOODS) - 1)), bg)
        r = 0
        for B in MOODS:
            if A == B: continue
            frames = transition(A, B)
            sheet = Image.new('RGBA', (CELL * NF, CELL))
            for i, f in enumerate(frames): sheet.paste(f, (i * CELL, 0))
            name = f'{A}-to-{B}.png'
            sheet.save(os.path.join(tdir, name), optimize=True)
            idx['transitions'][f'{A}>{B}'] = {'sheet': f'sprites/transitions/{name}', 'frames': NF, 'frameDurationMs': MS}
            review.alpha_composite(sheet, (0, r * CELL)); r += 1
        review.resize((review.width * 3, review.height * 3), Image.NEAREST).save(os.path.join(qa, f'from-{A}-x3.png'))
    idx['transitionNote'] = 'play transitions[from>to] once, then loop states[to] from frame 0 (last transition frame == frame 7 of the target loop)'
    json.dump(idx, open(idx_path, 'w'), indent=2, ensure_ascii=False)
    print('transitions:', len(idx['transitions']))


if __name__ == '__main__':
    main()
