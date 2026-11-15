"""Pet Planta - dynamic pixel-art backgrounds (256x144 scene), one per mood.

Layers per mood (sprites/bg/<mood>-*.png), drawn back to front by sprites/pet-planta.js:
  sky     sky gradient (ordered-dither bands) + sun / moon        (seen through the window)
  clouds  horizontally tileable cloud strip, scrolled by the player
  view    outside scenery: hills, trees, ground                    (transparent sky)
  room    greenhouse room: walls, floor, shelves, potted plants, hanging plants, window frame, pedestal
          (window panes are transparent) + mood decor (bunting, frost, moonlight...)
  light   translucent light beams, pulsed by the player
Animated particles (snow, rain, stars, confetti, motes, butterflies, fireflies, party lights) are described in
sprites/bg/backgrounds.json and drawn by the player, so they never visibly loop.
Run: python3 tools/gen_backgrounds.py
"""
import json, math, os, random
from PIL import Image, ImageDraw

W, H = 256, 144
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'sprites', 'bg')
BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]
CLEAR = (0, 0, 0, 0)

FRAME = (90, 16, 166, 114)                      # window outer frame
PANES = [(94, 20, 162, 43), (94, 47, 115, 109), (118, 47, 138, 109), (141, 47, 162, 109)]
GLASS = (94, 20, 162, 109)
PLANT_AT = (96, 55)                              # top-left of the 64x64 plant sprite (pot sits on the pedestal)


def C(h, a=255):
    h = h.lstrip('#'); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)


def outline(img, k=0.5):
    src = img.load(); out = img.copy(); o = out.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            if src[x, y][3]: continue
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < w and 0 <= ny < h and src[nx, ny][3] > 200:
                    r, g, b, _ = src[nx, ny]; o[x, y] = (int(r * k), int(g * k), int(b * k), 255); break
    return out


def layer():
    im = Image.new('RGBA', (W, H)); return im, ImageDraw.Draw(im)


# ------------------------------------------------------------------ moods
MOODS = {
    'happy': dict(sky=('6fc0f0', 'bfe7fb'), sun=('sun', 150, 30, 7), clouds=('ffffff', 'd6ebf7', 3, 4),
                  view=dict(hill='9ccf7a', grass='7cc35b', tree='5fae4a', dark='3f8a3a', trunk='8a5a3a'),
                  grade=((1.0, 1.0, 1.0), (0, 0, 0)), light=(255, 244, 205, 70), patch='fff2cc',
                  particles=[dict(type='butterflies', n=2)]),
    'sunny': dict(sky=('4fb2f2', 'cdeeff'), sun=('bigsun', 147, 31, 9), clouds=('ffffff', 'dceefa', 2, 3),
                  view=dict(hill='a9db7c', grass='88d05c', tree='66ba4c', dark='45953c', trunk='8a5a3a'),
                  grade=((1.06, 1.02, 0.92), (14, 10, 0)), light=(255, 236, 170, 95), patch='fff0b8',
                  particles=[dict(type='birds', n=3), dict(type='motes', n=16, color='fff4b0')]),
    'party': dict(sky=('6a5acd', 'ff9e8a'), sun=('sunset', 128, 104, 10), clouds=('ffc6d9', 'e79ac0', 3, 3),
                  view=dict(hill='6f7f86', grass='5b6b70', tree='4d6155', dark='344a3f', trunk='4a3a3a'),
                  grade=((0.86, 0.78, 0.95), (22, 4, 30)), light=None, patch=None,
                  particles=[dict(type='lights'), dict(type='confetti', n=28)]),
    'cold': dict(sky=('a9bccf', 'dfe8f1'), sun=None, clouds=('eef2f6', 'c9d3de', 4, 2),
                 view=dict(hill='e6eef6', grass='f5f9fc', tree='6f988f', dark='4d7a72', trunk='5a4a46', snow=True),
                 grade=((0.70, 0.84, 1.0), (12, 26, 46)), light=None, patch=None,
                 particles=[dict(type='snow', n=46)]),
    'sleep': dict(sky=('121a3f', '2e3a72'), sun=('moon', 148, 30, 7), clouds=('3a4680', '2b3567', 2, 2),
                  view=dict(hill='2b4446', grass='243b36', tree='20372d', dark='14261f', trunk='261e1e'),
                  grade=((0.36, 0.40, 0.60), (6, 8, 26)), light=(170, 190, 255, 45), patch='8ea0d8',
                  particles=[dict(type='stars', n=22), dict(type='fireflies', n=5)]),
    'dry': dict(sky=('f2a64e', 'fbe0a0'), sun=('hotsun', 150, 30, 9), clouds=('fff0cc', 'f5d79a', 2, 1.5),
                view=dict(hill='d8b15a', grass='cf9f48', tree='a88a3a', dark='7d6528', trunk='6b4a2a'),
                grade=((1.05, 0.90, 0.66), (26, 10, 0)), light=(255, 200, 120, 70), patch='ffd9a0',
                particles=[dict(type='motes', n=14, color='e2c08a'), dict(type='leaves', n=3)]),
    'sick': dict(sky=('6f7985', 'aab2bb'), sun=None, clouds=('6a727d', '565d67', 5, 6),
                 view=dict(hill='7e937a', grass='6a8264', tree='5a7558', dark='405a40', trunk='4e4038'),
                 grade=((0.74, 0.80, 0.78), (10, 14, 14)), light=None, patch=None,
                 particles=[dict(type='rain', n=44), dict(type='glassdrops', n=7)]),
}


# ------------------------------------------------------------------ sky
def make_sky(m):
    top, bot = C(m['sky'][0]), C(m['sky'][1])
    im = Image.new('RGBA', (W, H)); p = im.load()
    y0, y1 = GLASS[1], GLASS[3]
    for y in range(H):
        t = min(1, max(0, (y - y0) / (y1 - y0)))
        for x in range(W):
            v = t * 4 + (BAYER[(x & 3) + ((y & 3) << 2)] / 16 - 0.5)
            p[x, y] = lerp(top, bot, min(4, max(0, round(v))) / 4)
    d = ImageDraw.Draw(im)
    if m['sun']:
        kind, cx, cy, r = m['sun']
        if kind in ('sun', 'bigsun', 'hotsun'):
            core = C('ffe14d') if kind != 'hotsun' else C('fff3b8')
            halo = C('fff0a0') if kind != 'hotsun' else C('ffd88a')
            if kind != 'sun':  # dithered glow halo
                for y in range(cy - r - 6, cy + r + 7):
                    for x in range(cx - r - 6, cx + r + 7):
                        dd = math.hypot(x - cx, y - cy)
                        if r < dd <= r + 6 and BAYER[(x & 3) + ((y & 3) << 2)] < 16 * (1 - (dd - r) / 6) * 0.7:
                            p[x, y] = halo
            for a in range(0, 360, 45):
                ra = math.radians(a)
                d.line([cx + (r + 2) * math.cos(ra), cy + (r + 2) * math.sin(ra), cx + (r + 4) * math.cos(ra), cy + (r + 4) * math.sin(ra)], fill=C('ffd23f'))
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=core)
            d.ellipse([cx - r + 2, cy - r + 2, cx - 1, cy - 1], fill=C('fff7c2'))
        elif kind == 'moon':
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C('fff2b0'))
            d.ellipse([cx - r + 3, cy - r - 2, cx + r + 3, cy + r - 2], fill=lerp(top, bot, 0.1))
        elif kind == 'sunset':
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C('ffcf6b'))
            d.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], fill=C('ffe08f'))
    return im


# ------------------------------------------------------------------ clouds (tileable 128 wide)
def make_clouds(m, seed):
    col, shade, n, _ = m['clouds']
    TW, TH = 128, 36
    im = Image.new('RGBA', (TW, TH)); d = ImageDraw.Draw(im)
    rnd = random.Random(seed)
    for i in range(n):
        x = int(i * TW / n + rnd.randint(-6, 6)); y = rnd.randint(4, 20); w = rnd.randint(14, 24 if n > 3 else 20)
        for ox in (-TW, 0, TW):
            cx = x + ox
            d.rectangle([cx, y + 4, cx + w, y + 8], fill=C(col))
            d.ellipse([cx + 2, y, cx + w // 2 + 2, y + 8], fill=C(col))
            d.ellipse([cx + w // 3, y - 3, cx + w - 2, y + 8], fill=C(col))
            d.line([cx + 1, y + 8, cx + w - 1, y + 8], fill=C(shade))
    return im


# ------------------------------------------------------------------ outside view
def tree(d, cx, base, r, v, snow=False):
    d.rectangle([cx - 1, base - r - 2, cx + 1, base], fill=C(v['trunk']))
    cy = base - r - 4
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C(v['dark']))
    d.ellipse([cx - r, cy - r, cx + r - 2, cy + r - 2], fill=C(v['tree']))
    d.ellipse([cx - r // 2 - 2, cy - r + 2, cx, cy - 1], fill=lerp(C(v['tree']), (255, 255, 255), 0.18))
    if snow:
        d.chord([cx - r, cy - r, cx + r, cy + r // 2], 190, 350, fill=C('f7fbff'))


def make_view(m):
    v = m['view']; im, d = layer()
    d.ellipse([60, 84, 200, 150], fill=C(v['hill']))
    d.ellipse([130, 90, 230, 140], fill=lerp(C(v['hill']), C(v['grass']), 0.5))
    d.rectangle([0, 100, W, H], fill=C(v['grass']))
    tree(d, 101, 100, 8, v, v.get('snow')); tree(d, 157, 98, 10, v, v.get('snow'))
    out = outline(im, 0.7)
    # aerial perspective: push the outside view toward the horizon colour so the plant pops in front of it
    haze = C(m['sky'][1]); p = out.load()
    for y in range(H):
        for x in range(W):
            r, g, b, a = p[x, y]
            if a: p[x, y] = (round(r + (haze[0] - r) * 0.32), round(g + (haze[1] - g) * 0.32), round(b + (haze[2] - b) * 0.32), a)
    return out


# ------------------------------------------------------------------ room
TERRA, TERRA_D, RIM = C('c8744a'), C('9e5636'), C('dc8b5c')
LEAF, LEAF_L, LEAF_D, CACT = C('5aa64a'), C('7cc35b'), C('3e8038'), C('6fb35a')
WOOD, WOOD_D, WOOD_L = C('b8794a'), C('8a5634'), C('cf9461')


def pot(d, cx, yb, w=10, h=7):
    d.polygon([(cx - w // 2, yb - h), (cx + w // 2, yb - h), (cx + w // 2 - 2, yb), (cx - w // 2 + 2, yb)], fill=TERRA)
    d.polygon([(cx + w // 2 - 3, yb - h), (cx + w // 2, yb - h), (cx + w // 2 - 2, yb), (cx + w // 2 - 4, yb)], fill=TERRA_D)
    d.rectangle([cx - w // 2 - 1, yb - h - 2, cx + w // 2 + 1, yb - h], fill=RIM)
    return yb - h - 2


def leaf(d, x, y, a, L, w, col, rib=None):
    ra = math.radians(a); px, py = -math.sin(ra), math.cos(ra)
    tip = (x + L * math.cos(ra), y + L * math.sin(ra))
    mid = (x + L * 0.45 * math.cos(ra), y + L * 0.45 * math.sin(ra))
    pts = [(x, y), (mid[0] + px * w, mid[1] + py * w), tip, (mid[0] - px * w, mid[1] - py * w)]
    d.polygon([tuple(map(round, p)) for p in pts], fill=col)
    if rib: d.line([x, y, round(tip[0] - 1.5 * math.cos(ra)), round(tip[1] - 1.5 * math.sin(ra))], fill=rib)


def cactus(d, cx, y, h=12):
    d.rounded_rectangle([cx - 3, y - h, cx + 3, y], 3, fill=CACT)
    d.rounded_rectangle([cx - 7, y - h + 4, cx - 5, y - h + 9], 1, fill=CACT); d.line([cx - 5, y - h + 8, cx - 3, y - h + 8], fill=CACT)
    d.rounded_rectangle([cx + 5, y - h + 2, cx + 7, y - h + 7], 1, fill=CACT); d.line([cx + 3, y - h + 6, cx + 5, y - h + 6], fill=CACT)
    d.line([cx, y - h + 2, cx, y - 1], fill=LEAF_D)
    d.point((cx, y - h - 1), fill=C('ff7aa8')); d.point((cx - 1, y - h), fill=C('ff7aa8')); d.point((cx + 1, y - h), fill=C('ff7aa8'))


def succulent(d, cx, y):
    for i, a in enumerate(range(-160, -10, 25)):
        leaf(d, cx, y, a, 8 if i % 2 else 6, 2, LEAF_L if i % 2 else LEAF)
    for a in (-120, -60): leaf(d, cx, y, a, 5, 2, C('8fd46a'))


def fern(d, cx, y, n=5, L=13):
    for i in range(n):
        a = -160 + i * (140 / (n - 1))
        x0, y0 = cx, y
        for s in range(L):
            t = s / L
            ang = math.radians(a + (90 - abs(a + 90)) * 0)  # base direction
            x = cx + math.cos(math.radians(a)) * s * 1.0
            yy = y + math.sin(math.radians(a)) * s * 0.9 + (t * t) * 9  # droop
            d.point((round(x), round(yy)), fill=LEAF_D)
            if s % 2 == 0 and s > 1:
                d.point((round(x), round(yy) - 1), fill=LEAF_L); d.point((round(x), round(yy) + 1), fill=LEAF)


def bush(d, cx, y, r=6):
    d.ellipse([cx - r, y - 2 * r + 2, cx + r, y + 1], fill=LEAF_D)
    d.ellipse([cx - r + 1, y - 2 * r + 2, cx + r - 2, y - 1], fill=LEAF)
    d.ellipse([cx - r + 2, y - 2 * r + 3, cx, y - r], fill=LEAF_L)


def snake(d, cx, y, h=16):
    for i, (dx, hh) in enumerate([(-4, h - 4), (-1, h), (2, h - 2), (5, h - 6)]):
        x = cx + dx
        d.polygon([(x - 2, y), (x + 2, y), (x + (1 if i % 2 else -1), y - hh)], fill=LEAF if i % 2 else LEAF_D)
        d.line([x, y - 2, x, y - hh // 2], fill=C('b9d97a'))


def vine(d, x, y, L):
    for s in range(L):
        xx = x + (1 if (s // 3) % 2 else -1)
        d.point((xx, y + s), fill=LEAF_D)
        if s % 3 == 0: d.point((xx - 1, y + s), fill=LEAF_L); d.point((xx + 1, y + s + 1), fill=LEAF)


def big_plant(d, cx, yb, kind):
    top = pot(d, cx, yb, 18, 13)
    if kind == 'monstera':
        for a, L in ((-150, 22), (-120, 26), (-95, 28), (-70, 25), (-40, 21), (-165, 16), (-20, 16)):
            leaf(d, cx, top, a, L, 5, LEAF if a % 20 else LEAF_L, LEAF_D)
    else:
        for i, (dx, hh) in enumerate([(-5, 26), (-2, 32), (1, 29), (4, 34), (7, 24)]):
            x = cx + dx
            d.polygon([(x - 2, top), (x + 2, top), (x + (1 if i % 2 else -1), top - hh)], fill=LEAF if i % 2 else LEAF_D)
            d.line([x, top - 3, x, top - hh // 2], fill=C('b9d97a'))


def make_room(m, mood):
    base, d = layer()
    wall, wall2 = C('f3e3c3'), C('e4cfa6')
    d.rectangle([0, 0, W, H], fill=wall)
    d.polygon([(0, 8), (22, 14), (22, 112), (0, 122)], fill=wall2)
    d.polygon([(W, 8), (233, 14), (233, 112), (W, 122)], fill=wall2)
    d.line([(22, 14), (22, 112)], fill=C('d4bb8f')); d.line([(233, 14), (233, 112)], fill=C('d4bb8f'))
    d.rectangle([0, 0, W, 7], fill=C('d9b48a')); d.line([(0, 8), (W, 8)], fill=WOOD_D)
    d.polygon([(0, 8), (22, 14), (233, 14), (W, 8)], fill=C('ead6b3'))
    # floor
    d.polygon([(0, 122), (22, 112), (233, 112), (W, 122), (W, H), (0, H)], fill=C('c98f5e'))
    for i, y in enumerate(range(118, H, 6)):
        d.line([(0, y), (W, y)], fill=C('a96f45'))
        for x in range((i * 23) % 40, W, 40): d.line([(x, y + 1), (x, y + 5)], fill=C('b07a4f'))
    d.rectangle([22, 110, 233, 112], fill=WOOD)
    # light patch on the floor under the window
    if m['patch']:
        pc = C(m['patch']); bp = base.load()
        for y in range(113, H):
            t = (y - 113) / (H - 113)
            x0, x1 = 86 - t * 34, 170 - t * 4
            for x in range(int(x0), int(x1)):
                if BAYER[(x & 3) + ((y & 3) << 2)] < 4: bp[x, y] = pc
    # window frame with transparent panes
    win, wd = layer()
    wd.rectangle(FRAME, fill=WOOD)
    wd.rectangle([FRAME[0] + 2, FRAME[1] + 2, FRAME[2] - 2, FRAME[3] - 2], fill=WOOD_L)
    for (x0, y0, x1, y1) in PANES: wd.rectangle([x0, y0, x1, y1], fill=CLEAR)
    wd.rectangle([86, 109, 170, 113], fill=WOOD_L); wd.line([(86, 113), (170, 113)], fill=WOOD_D)
    win = outline(win, 0.55)
    # shelves + small plants
    sh, sd = layer()
    for y in (42, 76):
        sd.rectangle([26, y, 82, y + 3], fill=WOOD); sd.line([(26, y + 3), (82, y + 3)], fill=WOOD_D)
        sd.polygon([(32, y + 4), (36, y + 4), (32, y + 9)], fill=WOOD_D); sd.polygon([(76, y + 4), (80, y + 4), (80, y + 9)], fill=WOOD_D)
    sd.rectangle([182, 70, 232, 73], fill=WOOD); sd.line([(182, 73), (232, 73)], fill=WOOD_D)
    sd.polygon([(188, 74), (192, 74), (188, 79)], fill=WOOD_D); sd.polygon([(224, 74), (228, 74), (228, 79)], fill=WOOD_D)
    cactus(sd, 34, pot(sd, 34, 42)); succulent(sd, 52, pot(sd, 52, 42, 12)); fern(sd, 70, pot(sd, 70, 42))
    bush(sd, 34, pot(sd, 34, 76, 12)); snake(sd, 53, pot(sd, 53, 76)); cactus(sd, 71, pot(sd, 71, 76), 9)
    succulent(sd, 192, pot(sd, 192, 70)); bush(sd, 208, pot(sd, 208, 70, 12), 5); cactus(sd, 224, pot(sd, 224, 70), 10)
    # hanging plants
    for hx, hy, vl in ((188, 30, 22), (216, 24, 30)):
        t = pot(sd, hx, hy, 12, 7); bush(sd, hx, t + 1, 6)
        vine(sd, hx - 5, hy - 3, vl); vine(sd, hx + 5, hy - 2, vl - 8)
        for ex in (-7, 0, 7):  # macrame strings from one hook to the rim
            sd.line([(hx, 9), (hx + ex, t)], fill=C('a89480'))
        sd.point((hx, 8), fill=C('6b5a4a'))
    sh = outline(sh, 0.5)
    # floor plants
    fl, fd = layer()
    big_plant(fd, 40, 134, 'monstera'); big_plant(fd, 214, 132, 'snake')
    bush(fd, 72, pot(fd, 72, 126, 12, 8), 7); bush(fd, 184, pot(fd, 184, 124, 12, 8), 7)
    fl = outline(fl, 0.5)
    # pedestal
    pe, pd = layer()
    pd.rectangle([100, 116, 156, 121], fill=C('efe3cf')); pd.line([(100, 121), (156, 121)], fill=C('cdbd9f'))
    pd.rectangle([104, 122, 152, H], fill=C('e3d4b9'))
    pd.rectangle([108, 125, 148, 139], outline=C('c4b293'))
    for x in range(112, 146, 8):
        pd.arc([x, 129, x + 6, 135], 180, 360, fill=C('b9a684')); pd.arc([x + 3, 129, x + 9, 135], 0, 180, fill=C('b9a684'))
    pe = outline(pe, 0.6)
    # foreground leaves
    fg, gd = layer()
    for a, L in ((-60, 30), (-35, 34), (-80, 24)): leaf(gd, -2, 146, a, L, 7, C('3f7f3a'), C('2c5c2a'))
    for a, L in ((-120, 30), (-145, 34), (-100, 24)): leaf(gd, W + 2, 146, a, L, 7, C('3f7f3a'), C('2c5c2a'))
    fg = outline(fg, 0.5)
    for l in (win, sh, fl, pe, fg): base.alpha_composite(l)
    bp = base.load()
    for (x0, y0, x1, y1) in PANES:   # see-through glass + small reflections
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1): bp[x, y] = CLEAR
        for k in range(5):
            if y1 - 6 - k >= y0: bp[x0 + 3 + k, y1 - 6 - k] = (255, 255, 255, 110)
            if y1 - 9 - k >= y0 and x0 + 3 + k + 3 <= x1: bp[x0 + 6 + k, y1 - 6 - k] = (255, 255, 255, 70)
    # mood colour grade (keep panes transparent)
    mul, add = m['grade']; p = base.load()
    for y in range(H):
        for x in range(W):
            r, g, b, a = p[x, y]
            if a: p[x, y] = (min(255, int(r * mul[0] + add[0])), min(255, int(g * mul[1] + add[1])), min(255, int(b * mul[2] + add[2])), a)
    decor(base, mood)
    return base


def decor(im, mood):
    d = ImageDraw.Draw(im); p = im.load()
    if mood == 'party':
        cols = [C('f06b9a'), C('f7c531'), C('4aa8e8'), C('7ed957'), C('b57cf2')]
        pts = [(x, 12 + round(10 * math.sin(math.pi * (x - 24) / 208))) for x in range(24, 233)]
        for x, y in pts: p[x, y] = C('7a5a4a')
        for i, x in enumerate(range(28, 230, 9)):
            y = 12 + round(10 * math.sin(math.pi * (x - 24) / 208))
            d.polygon([(x - 3, y), (x + 3, y), (x, y + 6)], fill=cols[i % len(cols)])
        for bx, by, col in ((44, 22, 'f06b9a'), (54, 18, '4aa8e8'), (226, 40, 'f7c531')):
            d.line([(bx, by + 7), (bx + (2 if bx < 100 else -2), by + 24)], fill=C('e8e0d0'))
            d.ellipse([bx - 4, by - 5, bx + 4, by + 6], fill=C(col)); d.point((bx - 2, by - 2), fill=C('ffffff'))
            d.point((bx, by + 7), fill=C(col))
    if mood == 'cold':
        for (x0, y0, x1, y1) in PANES:
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    dc = min(x - x0, x1 - x) + min(y - y0, y1 - y)
                    if dc < 7 and BAYER[(x & 3) + ((y & 3) << 2)] < 16 - dc * 2.4: p[x, y] = (238, 246, 255, 235)
        d.rounded_rectangle([88, 106, 168, 110], 2, fill=C('f7fbff')); d.line([(89, 110), (167, 110)], fill=C('c9d8e8'))
    if mood == 'sleep':  # small warm night lamp on the right shelf
        lx, ly = 200, 62
        for y in range(ly - 14, ly + 10):
            for x in range(lx - 14, lx + 15):
                dd = math.hypot(x - lx, y - ly)
                if dd < 13 and BAYER[(x & 3) + ((y & 3) << 2)] < 9 * (1 - dd / 13) and p[x, y][3]:
                    r, g, b, a = p[x, y]; p[x, y] = (min(255, r + 70), min(255, g + 50), min(255, b + 10), a)
        d.rectangle([lx - 1, ly + 1, lx + 1, ly + 7], fill=C('5a4a3a')); d.polygon([(lx - 5, ly + 1), (lx + 5, ly + 1), (lx + 3, ly - 5), (lx - 3, ly - 5)], fill=C('ffd27a'))
        d.line([(lx - 5, ly + 1), (lx + 5, ly + 1)], fill=C('c9953f'))


def make_light(m):
    im = Image.new('RGBA', (W, H))
    if not m['light']: return im
    col = m['light']; p = im.load()
    for (x0, y0, x1, y1) in PANES[1:]:
        for y in range(y0, H):
            sh = (y - y0) * 0.55
            for x in range(int(x0 - sh), int(x1 - sh) + 1):
                if 0 <= x < W and (y < y1 or y >= 113) and BAYER[(x & 3) + ((y & 3) << 2)] < 8:
                    if y < y1 and x0 <= x <= x1: continue
                    p[x, y] = col
    return im


def party_lights():
    return [[x, 15 + round(10 * math.sin(math.pi * (x - 24) / 208)) + 1] for x in range(32, 230, 11)]


def main():
    os.makedirs(OUT, exist_ok=True)
    cfg = {'size': [W, H], 'plant': {'x': PLANT_AT[0], 'y': PLANT_AT[1]}, 'glass': GLASS, 'panes': PANES,
           'cloudY': GLASS[1] + 1, 'moods': {}}
    for i, (mood, m) in enumerate(MOODS.items()):
        files = {}
        for name, img in (('sky', make_sky(m)), ('clouds', make_clouds(m, i * 7 + 3)), ('view', make_view(m)),
                          ('room', make_room(m, mood)), ('light', make_light(m))):
            fn = f'{mood}-{name}.png'
            img.save(os.path.join(OUT, fn), optimize=True); files[name] = fn
        parts = [dict(p) for p in m['particles']]
        for p in parts:
            if p['type'] == 'lights': p['points'] = party_lights()
        cfg['moods'][mood] = {**files, 'cloudSpeed': m['clouds'][3], 'lightPulse': bool(m['light']), 'particles': parts}
        # static preview (plant frame 0 on the pedestal)
        sc = Image.new('RGBA', (W, H))
        for name in ('sky', 'clouds', 'view', 'room', 'light'):
            img = Image.open(os.path.join(OUT, files[name])).convert('RGBA')
            if name == 'clouds':
                sc.alpha_composite(img, (0, cfg['cloudY'])); sc.alpha_composite(img, (128, cfg['cloudY']))
            else:
                sc.alpha_composite(img)
        pl = Image.open(os.path.join(ROOT, 'sprites', mood, 'frames', f'{mood}_0.png')).convert('RGBA')
        sc.alpha_composite(pl, PLANT_AT)
        os.makedirs(os.path.join(ROOT, 'run', 'bg'), exist_ok=True)
        sc.resize((W * 3, H * 3), Image.NEAREST).save(os.path.join(ROOT, 'run', 'bg', f'{mood}-still-x3.png'))
    json.dump(cfg, open(os.path.join(OUT, 'backgrounds.json'), 'w'), indent=1)
    print('ok', list(cfg['moods']))


if __name__ == '__main__':
    main()
