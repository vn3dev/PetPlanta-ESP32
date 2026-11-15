"""Pet Planta - procedural pixel-art generator (v2), 64x64 cells, 8 frames per mood.

Polish rules used here:
- leaf crown shapes are rasterized ONCE per mood (no per-frame re-rasterizing = no "boiling" pixels);
  animation only moves parts by whole pixels.
- the crown follows the head with a 1-frame lag (secondary motion).
- stem is a continuous 2px curve, every part gets a 1px dark selective outline.
- the pot never moves (anchor: bottom-center).
Run: python3 tools/gen_plant.py
"""
import json, math, os, shutil
from PIL import Image, ImageDraw

CELL, N = 64, 8
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HCX, HCY, RX, RY = 32, 23, 12, 11


def C(h, a=255):
    h = h.lstrip('#'); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


INK, WHITE, PINK = C('1f1a1c'), C('ffffff'), C('f2788f')
POT = dict(pot=C('955f3b'), dark=C('6e4228'), hi=C('b27548'), rim=C('a2683f'), rimhi=C('c08257'), soil=C('4a2e1c'))

BASE = dict(head='72c862', shade='58ad4c', hi='a3e08c', leaf1='4cb54f', leaf2='2f8a3c', stem='4f9a3e', stemd='3b7a2f', blush='fc919b', tip=None)
PAL = {
    'happy': BASE,
    'party': dict(BASE, head='7fd66a', shade='62bb55', hi='b0ef93', leaf1='52c257', leaf2='36994a', blush=None),
    'sunny': dict(BASE, head='7acf63', hi='b3ea95'),
    'cold':  dict(head='8cc6c2', shade='6aa9a8', hi='c4e7e3', leaf1='5fa7a6', leaf2='3f8486', stem='5a9a95', stemd='447c79', blush=None, tip='e6f6ff'),
    'sleep': dict(head='5f9c78', shade='4a8463', hi='84ba98', leaf1='3f8058', leaf2='2d6645', stem='427a4c', stemd='30603a', blush='c98a95', tip=None),
    'dry':   dict(head='c9c47a', shade='aea95f', hi='e2dd9e', leaf1='a5a452', leaf2='868640', stem='99984c', stemd='7a7a3a', blush=None, tip='8a6a35'),
    'sick':  dict(head='a6a463', shade='8a884e', hi='c2bf85', leaf1='8f8a4a', leaf2='6e6a36', stem='7a7440', stemd='5f5a30', blush=None, tip='6b4f2a'),
}

# big clean sawtooth crown like the reference: dark back spikes + lighter, shorter front spikes in between
BACK = [(166, 'L'), (-178, 'L'), (-156, 'L'), (-134, 'L'), (-112, 'T'), (-90, 'T'), (-68, 'T'), (-46, 'R'), (-24, 'R'), (-2, 'R'), (14, 'R')]
FRONT = [(-167, 'L'), (-145, 'L'), (-123, 'T'), (-101, 'T'), (-79, 'T'), (-57, 'T'), (-35, 'R'), (-13, 'R')]


def droop_angle(a, droop):
    if droop <= 0: return a
    left = a > 90 or a < -90 or (a == -90 and False)
    k = 42 * droop
    return max(a - k, -218) if left or a in (170,) else min(a + k, 38)


def P(cx, cy, r, ang):
    return (cx + r * math.cos(math.radians(ang)), cy + r * math.sin(math.radians(ang)))


def leaf_poly(a, L, w=15, br=12):
    pts = [P(HCX, HCY, br, a - w), P(HCX, HCY, L, a), P(HCX, HCY, br, a + w), (HCX, HCY)]
    return [tuple(map(round, p)) for p in pts]


def render_crown(pal, droop):
    layers = {d: {g: Image.new('RGBA', (CELL, CELL)) for g in 'LTR'} for d in ('back', 'front')}
    for depth, lst, col, L in (('back', BACK, 'leaf2', 20), ('front', FRONT, 'leaf1', 17)):
        for i, (a, g) in enumerate(lst):
            aa = droop_angle(a, droop)
            side = abs(abs(a) - 90) / 90  # side spikes a bit shorter
            length = L - round(2 * side) - 3 * droop
            d = ImageDraw.Draw(layers[depth][g])
            d.polygon(leaf_poly(aa, length), fill=C(pal[col]))
            if pal['tip']:
                t = [P(HCX, HCY, length * 0.74, aa - 7), P(HCX, HCY, length, aa), P(HCX, HCY, length * 0.74, aa + 7)]
                d.polygon([tuple(map(round, p)) for p in t], fill=C(pal['tip']))
    return layers


def paste(dst, layer, ox, oy):
    tmp = Image.new('RGBA', dst.size); tmp.paste(layer, (ox, oy), layer); dst.alpha_composite(tmp)


def outline(img, k=0.45):
    src = img.load(); out = img.copy(); o = out.load()
    for y in range(CELL):
        for x in range(CELL):
            if src[x, y][3]: continue
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < CELL and 0 <= ny < CELL and src[nx, ny][3]:
                    r, g, b, _ = src[nx, ny]; o[x, y] = (int(r * k), int(g * k), int(b * k), 255); break
    return out


def draw_pot():
    im = Image.new('RGBA', (CELL, CELL)); d = ImageDraw.Draw(im); p = POT
    d.polygon([(20, 48), (43, 48), (40, 59), (23, 59)], fill=p['pot'])
    d.polygon([(38, 48), (43, 48), (40, 59), (37, 59)], fill=p['dark'])
    d.line([(22, 49), (24, 57)], fill=p['hi'])
    d.rectangle([18, 44, 45, 47], fill=p['rim'])
    d.line([(18, 47), (45, 47)], fill=p['dark'])
    d.line([(18, 44), (20, 44)], fill=p['rimhi']); d.line([(43, 44), (45, 44)], fill=p['rimhi'])
    d.rectangle([21, 44, 42, 45], fill=p['soil'])
    return outline(im)


POT_IMG = None


def draw_stem(d, cx, yb, pal):
    dx = cx - HCX
    for y in range(yb, 46):
        t = (45 - y) / max(1, 45 - yb)
        x = 31 + round(dx * t * t)
        d.point((x, y), fill=C(pal['stem'])); d.point((x + 1, y), fill=C(pal['stemd']))


def pts(d, lst, col):
    for p in lst: d.point(p, fill=col)


def draw_eyes(d, cx, cy, kind):
    ey = cy - 1
    for side, ex in ((0, cx - 7), (1, cx + 4)):
        if kind == 'open':
            d.rectangle([ex, ey + 1, ex + 3, ey + 3], fill=INK); d.line([ex + 1, ey, ex + 2, ey], fill=INK)
            d.line([ex + 1, ey + 4, ex + 2, ey + 4], fill=INK); d.point((ex + 1, ey + 1), fill=WHITE)
        elif kind == 'blink':
            d.line([ex, ey + 3, ex + 3, ey + 3], fill=INK)
        elif kind == 'happy':
            pts(d, [(ex, ey + 3), (ex + 1, ey + 2), (ex + 2, ey + 2), (ex + 3, ey + 3)], INK)
        elif kind == 'sleep':
            pts(d, [(ex, ey + 2), (ex + 1, ey + 3), (ex + 2, ey + 3), (ex + 3, ey + 2)], INK)
        elif kind == 'tired':
            d.line([ex, ey + 2, ex + 3, ey + 2], fill=INK); d.line([ex + 1, ey + 3, ex + 2, ey + 3], fill=INK)
        elif kind == 'x':
            for t in range(4): d.point((ex + t, ey + t), fill=INK); d.point((ex + 3 - t, ey + t), fill=INK)
        elif kind == 'squeeze':
            seq = [(0, 0), (1, 1), (2, 2), (1, 3), (0, 4)]
            pts(d, [((ex + x) if side == 0 else (ex + 3 - x), ey + y) for x, y in seq], INK)


def draw_mouth(d, cx, cy, kind):
    my = cy + 5
    if kind == 'smile':
        pts(d, [(cx - 2, my), (cx - 1, my + 1), (cx, my + 1), (cx + 1, my + 1), (cx + 2, my)], INK)
    elif kind == 'grin':
        pts(d, [(cx - 3, my), (cx - 2, my + 1), (cx - 1, my + 1), (cx, my + 1), (cx + 1, my + 1), (cx + 2, my + 1), (cx + 3, my)], INK)
    elif kind == 'big':
        d.line([cx - 3, my, cx + 3, my], fill=INK); d.line([cx - 2, my + 1, cx + 2, my + 1], fill=INK)
        d.line([cx - 1, my + 2, cx + 1, my + 2], fill=INK); d.line([cx - 1, my + 1, cx + 1, my + 1], fill=PINK)
    elif kind == 'frown':
        pts(d, [(cx - 2, my + 1), (cx - 1, my), (cx, my), (cx + 1, my), (cx + 2, my + 1)], INK)
    elif kind == 'flat':
        d.line([cx - 1, my + 1, cx, my + 1], fill=INK)
    elif kind == 'wavy':
        for i, x in enumerate(range(cx - 3, cx + 4)): d.point((x, my + (i % 2)), fill=INK)
    elif kind == 'smirk':   # cool half smile, one corner up
        pts(d, [(cx - 3, my + 1), (cx - 2, my + 1), (cx - 1, my + 1), (cx, my + 1), (cx + 1, my), (cx + 2, my - 1)], INK)
    elif kind == 'rap':     # serious open mouth with the upper teeth showing
        d.rectangle([cx - 3, my, cx + 2, my + 2], fill=INK)
        d.line([cx - 2, my, cx + 1, my], fill=WHITE)
    elif kind == 'teeth':
        d.rectangle([cx - 3, my, cx + 3, my + 2], fill=INK)
        for x in range(cx - 2, cx + 3): d.point((x, my + 1), fill=WHITE if (x - cx) % 2 == 0 else INK)
        d.point((cx - 1, my + 1), fill=WHITE); d.point((cx + 1, my + 1), fill=WHITE)
        d.point((cx - 1, my + 1), fill=INK)


def draw_brows(d, cx, cy):
    """frowning brows just above the sunglasses: the serious 'boss' look"""
    pts(d, [(cx - 10, cy - 5), (cx - 9, cy - 5), (cx - 8, cy - 4), (cx - 7, cy - 4), (cx - 6, cy - 3), (cx - 5, cy - 3)], INK)
    pts(d, [(cx + 10, cy - 5), (cx + 9, cy - 5), (cx + 8, cy - 4), (cx + 7, cy - 4), (cx + 6, cy - 3), (cx + 5, cy - 3)], INK)


def draw_glasses(d, cx, cy, glint):
    lens = C('1c1c2a'); rim = C('0e0e16')
    for x0 in (cx - 9, cx + 3):
        d.rectangle([x0, cy - 2, x0 + 6, cy + 2], fill=lens)
        d.point((x0, cy + 2), fill=(0, 0, 0, 0)); d.point((x0 + 6, cy + 2), fill=(0, 0, 0, 0))
        d.point((x0 + 1, cy - 1), fill=C('4a4a6a'))
    d.line([cx - 3, cy - 1, cx + 3, cy - 1], fill=rim)
    d.line([cx - 11, cy - 1, cx - 10, cy - 1], fill=rim); d.line([cx + 10, cy - 1, cx + 11, cy - 1], fill=rim)
    if glint is not None:
        gx = cx - 8 + glint
        for i in range(3):
            if cx - 9 <= gx + i <= cx - 3: d.point((gx + i, cy + 1 - i), fill=WHITE)


def draw_hat(img, cx, cy):
    base1, base2, apex = (cx - 11, cy - 6), (cx + 2, cy - 11), (cx - 7, cy - 17)
    m = Image.new('L', (CELL, CELL)); ImageDraw.Draw(m).polygon([base1, base2, apex], fill=255)
    mx, my = (base1[0] + base2[0]) / 2, (base1[1] + base2[1]) / 2
    ax, ay = apex[0] - mx, apex[1] - my; L2 = ax * ax + ay * ay
    mp, ip = m.load(), img.load()
    for y in range(CELL):
        for x in range(CELL):
            if mp[x, y]:
                t = ((x - mx) * ax + (y - my) * ay) / L2
                ip[x, y] = C('4aa8e8') if t < 0.3 else C('f7c531') if t < 0.62 else C('f06b9a')
    d = ImageDraw.Draw(img)
    d.rectangle([apex[0] - 1, apex[1] - 2, apex[0] + 1, apex[1]], fill=WHITE); d.point((apex[0] + 1, apex[1]), fill=C('d6d6e0'))


RED, RED_D, RED_H = C('d93a3a'), C('a82424'), C('f0645c')
GOLD, GOLD_D, GOLD_H = C('ffd23f'), C('c9971f'), C('fff1a0')


def draw_beanie(d, cx, cy, flop=0):
    """red beanie with folded brim and a floppy tip (inspired by the party singer)"""
    d.chord([cx - 10, cy - 17, cx + 10, cy + 3], 180, 360, fill=RED)
    d.ellipse([cx - 7, cy - 15, cx - 3, cy - 12], fill=RED_H)
    d.polygon([(cx + 1, cy - 16), (cx + 8, cy - 18 + flop), (cx + 11, cy - 14 + flop), (cx + 7, cy - 11)], fill=RED)
    d.line([(cx + 7, cy - 11), (cx + 11, cy - 14 + flop)], fill=RED_D)
    d.rectangle([cx - 11, cy - 8, cx + 11, cy - 5], fill=RED_D)
    for x in range(cx - 10, cx + 11, 2): d.line([(x, cy - 8), (x, cy - 6)], fill=C('8f1c1c'))
    d.line([(cx - 11, cy - 8), (cx + 11, cy - 8)], fill=RED)


def draw_chain(d, cx, cy, swing=0):
    """chunky gold chain with a square 'cheese' pendant"""
    for i in range(23):
        t = i / 22
        x = round(cx - 10 + 20 * t + swing * 4 * t * (1 - t)); y = round(cy + 8 + 24 * t * (1 - t))
        d.point((x, y), fill=GOLD if i % 2 == 0 else GOLD_D)
        d.point((x, y + 1), fill=GOLD_D if i % 2 == 0 else GOLD)
    px, py = cx + swing, cy + 14
    d.point((px, py - 1), fill=GOLD_D)
    d.rectangle([px - 3, py, px + 3, py + 4], fill=GOLD)
    d.line([(px - 3, py), (px + 2, py)], fill=GOLD_H)
    d.point((px - 1, py + 2), fill=GOLD_D); d.point((px + 1, py + 1), fill=GOLD_D); d.point((px + 2, py + 3), fill=GOLD_D)


def chain_layer(img, cx, cy, swing=0):
    """composite the gold chain on top of everything (arms pass behind it), with its own dark outline"""
    ch = Image.new('RGBA', (CELL, CELL)); draw_chain(ImageDraw.Draw(ch), cx, cy, swing)
    img.alpha_composite(outline(ch, 0.45))


def draw_mic(d, cx, cy, up, leaf):
    """microphone held by a thin leaf 'arm' growing from the stem, next to the cheek"""
    hx, hy = cx + 10, cy + 4 - up
    # thin arm from the stem to the hand
    d.line([(cx + 1, cy + 14), (cx + 5, cy + 13), (hx + 2, hy + 7)], fill=leaf, width=3)
    d.line([(hx + 1, hy + 2), (hx + 3, hy + 7)], fill=C('2a2a33'), width=2)
    d.ellipse([hx + 1, hy + 4, hx + 5, hy + 8], fill=leaf)             # leafy hand around the handle
    d.ellipse([hx - 2, hy - 2, hx + 2, hy + 2], fill=C('c8ccd6'))
    d.point((hx - 1, hy - 1), fill=WHITE); d.point((hx, hy), fill=C('7a7f8c')); d.point((hx + 1, hy + 1), fill=C('7a7f8c'))
    d.point((hx + 1, hy - 1), fill=C('7a7f8c')); d.point((hx - 1, hy + 1), fill=C('7a7f8c'))


def S(**kw):
    n = max([len(v) for v in kw.values() if isinstance(v, list)] or [N])
    return [{k: (v[i] if isinstance(v, list) else v) for k, v in kw.items()} for i in range(n)]


MOODS = {
    'happy': dict(ms=150, droop=0, label='feliz (padrao)', frames=S(
        dy=[0, -1, -1, -2, -2, -1, -1, 0], dx=[0, 0, 1, 1, 0, 0, -1, -1], sw=[0, -1, -1, 0, 1, 1, 0, -1],
        eyes=['open', 'open', 'open', 'open', 'open', 'blink', 'open', 'open'], mouth='smile')),
    # synced to the party song: 79.178 BPM, 4 frames per beat, frame 0 = strongest beat of the bar
    'party': dict(ms=189.446, droop=0, label='modo festa', beat=dict(bpm=79.178, firstDownbeatS=2.1673, framesPerBeat=4),
                  frames=S(
        dy=[2, -2, -3, -1,   1, -1, -2, -1,   1, -2, -3, -1,   1, -1, -2, 0],
        sq=[1, 0, 0, 0,      1, 0, 0, 0,      1, 0, 0, 0,      1, 0, 0, 0],
        dx=[0, -1, -1, -1,  -1, -2, -2, -1,   0, 1, 1, 1,      1, 2, 2, 1],
        sw=[0, 1, 1, 1,      1, 1, 1, 0,      0, -1, -1, -1,  -1, -1, -1, 0],
        spread=[0, 2, 1, 0,  0, 1, 0, 0,      0, 2, 1, 0,      0, 1, 0, 0],
        mouth=['rap', 'o', 'smirk', 'smirk', 'rap', 'smirk', 'o', 'smirk', 'rap', 'o', 'smirk', 'smirk', 'rap', 'smirk', 'rap', 'smirk'],
        eyes='open', glasses=True, brows=True, blush=False,
        glint=[0, 2, 4, None, None, None, None, None, None, None, None, None, None, None, None, None],
        mic=[1, 2, 2, 1,     0, 1, 1, 0,      1, 2, 2, 1,      0, 1, 1, 0],
        beanie=True, chain=True)),
    'sunny': dict(ms=170, droop=0, label='curtindo o sol', frames=S(
        dy=[0, 0, -1, -1, -1, 0, 0, 0], dx=[0, 1, 1, 1, 0, -1, -1, 0], sw=[0, 0, 1, 1, 0, 0, -1, -1],
        eyes='none', mouth='grin', glasses=True, glint=[None, 0, 2, 4, None, None, None, None])),
    'cold': dict(ms=80, droop=0.1, label='com frio', frames=S(
        dy=1, dx=[-1, 1, -1, 1, -1, 1, 0, 0], dy2=[1, 1, 1, 1, 1, 1, 0, 1], sw=[1, -1, 1, -1, 1, -1, 0, 0],
        eyes='squeeze', mouth='teeth', blush=False)),
    'sleep': dict(ms=240, droop=0.25, label='dormindo', frames=S(
        dy=[1, 0, 0, -1, -1, 0, 0, 1], dx=[1, 1, 2, 2, 1, 1, 0, 0], sw=[0, 0, 1, 1, 0, -1, -1, 0],
        eyes='sleep', mouth='flat')),
    'dry': dict(ms=220, droop=0.6, label='seca', frames=S(
        dy=[2, 2, 3, 3, 4, 4, 3, 3], dx=[1, 2, 2, 1, 1, 2, 2, 1], sw=[0, -1, -1, 0, 0, 1, 1, 0],
        eyes=['tired', 'tired', 'tired', 'tired', 'blink', 'tired', 'tired', 'tired'], mouth='frown')),
    'sick': dict(ms=180, droop=1.0, label='doente', frames=S(
        dy=[4, 5, 5, 4, 4, 5, 5, 4], dx=[2, 3, 2, 1, 2, 3, 2, 1], sw=[0, 1, 1, -1, -1, 1, 1, -1],
        eyes='x', mouth='wavy')),
}


def render_frame(mood, spec, i, crown):
    pal = PAL[mood]; f = spec['frames'][i]; prev = spec['frames'][i - 1]
    dy = f['dy'] + (f.get('dy2', 0) - 1 if 'dy2' in f else 0)
    pdy = prev['dy'] + (prev.get('dy2', 0) - 1 if 'dy2' in prev else 0)
    cx, cy = HCX + f['dx'], HCY + dy
    sq = f.get('sq', 0); rx, ry = RX + sq, RY - sq
    plant = Image.new('RGBA', (CELL, CELL)); d = ImageDraw.Draw(plant)
    draw_stem(d, cx, cy + ry - 1, pal)
    cdx, cdy = prev['dx'], pdy  # crown lags one frame
    sp = f.get('spread', 0)
    for depth in ('back', 'front'):
        for g in 'LTR':
            ox = cdx + f['sw'] + (-sp if g == 'L' else sp if g == 'R' else 0)
            oy = cdy - (sp if g == 'T' else 0)
            if g == 'T': ox = cdx + prev['sw']
            paste(plant, crown[depth][g], ox, oy)
    d = ImageDraw.Draw(plant)
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=C(pal['shade']))
    d.ellipse([cx - rx, cy - ry, cx + rx - 2, cy + ry - 2], fill=C(pal['head']))
    d.ellipse([cx - 8, cy - 8, cx - 2, cy - 4], fill=C(pal['hi']))
    if pal['blush'] and f.get('blush', True):
        d.rectangle([cx - 11, cy + 3, cx - 9, cy + 4], fill=C(pal['blush']))
        d.rectangle([cx + 8, cy + 3, cx + 10, cy + 4], fill=C(pal['blush']))
    if f['eyes'] != 'none': draw_eyes(d, cx, cy, f['eyes'])
    draw_mouth(d, cx, cy, f['mouth'])
    if f.get('glasses'): draw_glasses(d, cx, cy, f.get('glint'))
    if f.get('brows'): draw_brows(d, cx, cy)
    if f.get('hat'): draw_hat(plant, cx, cy)
    if f.get('beanie'): draw_beanie(d, cx, cy, max(-1, min(1, dy - pdy)))
    out = outline(plant)
    if f.get('mic') is not None:   # arm on its own outlined layer so it reads in front of the crown
        arms = Image.new('RGBA', (CELL, CELL)); draw_mic(ImageDraw.Draw(arms), cx, cy, f['mic'], C(pal['head']))
        out.alpha_composite(outline(arms, 0.4))
    if f.get('chain'): chain_layer(out, cx, cy, max(-1, min(1, prev['dx'] - f['dx'])))
    out.alpha_composite(POT_IMG)
    return out


def main():
    global POT_IMG
    POT_IMG = draw_pot()
    sp = os.path.join(ROOT, 'sprites')
    for old in ('idle', 'thirsty', 'critical'):
        shutil.rmtree(os.path.join(sp, old), ignore_errors=True)
    index = {'cell': CELL, 'frames': N, 'rows': 1, 'direction': 'south', 'default': 'happy', 'states': {}}
    for mood, spec in MOODS.items():
        crown = render_crown(PAL[mood], spec['droop'])
        n = len(spec['frames'])
        frames = [render_frame(mood, spec, i, crown) for i in range(n)]
        sheet = Image.new('RGBA', (CELL * n, CELL))
        fdir = os.path.join(sp, mood, 'frames'); shutil.rmtree(fdir, ignore_errors=True); os.makedirs(fdir)
        for i, fr in enumerate(frames):
            sheet.paste(fr, (i * CELL, 0)); fr.save(os.path.join(fdir, f'{mood}_{i}.png'), optimize=True)
        sheet.save(os.path.join(sp, mood, f'{mood}-sheet.png'), optimize=True)
        meta = {'state': mood, 'label': spec['label'], 'image': f'{mood}-sheet.png', 'frameWidth': CELL, 'frameHeight': CELL,
                'frames': n, 'columns': n, 'rows': 1, 'frameDurationMs': spec['ms'], 'loop': True,
                'anchor': {'x': 32, 'y': 60, 'note': 'bottom-center of the pot, fixed in all frames'},
                'method': 'code_drawn', 'generator': 'tools/gen_plant.py'}
        json.dump(meta, open(os.path.join(sp, mood, f'{mood}-sheet.json'), 'w'), indent=2, ensure_ascii=False)
        index['states'][mood] = {'label': spec['label'], 'sheet': f'sprites/{mood}/{mood}-sheet.png', 'frames': n, 'frameDurationMs': spec['ms']}
        if spec.get('beat'): index['states'][mood]['beat'] = spec['beat']; meta['beat'] = spec['beat']
        json.dump(meta, open(os.path.join(sp, mood, f'{mood}-sheet.json'), 'w'), indent=2, ensure_ascii=False)
        # adjacent-frame difference report (incl. loop wrap)
        diffs = []
        for a in range(n):
            A, B = frames[a].load(), frames[(a + 1) % n].load()
            diffs.append(sum(A[x, y] != B[x, y] for x in range(CELL) for y in range(CELL)))
        print(f'{mood:6s} changed px per step: {diffs}')
        if mood == 'happy': frames[0].save(os.path.join(sp, 'base', 'plant-base.png'), optimize=True)
    json.dump(index, open(os.path.join(sp, 'sprites.json'), 'w'), indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
