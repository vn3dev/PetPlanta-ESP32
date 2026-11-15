"""Party choreography moves, based on the singer's dance in the music video, beat-synced to the song.

Each move is a sheet of 64x64 frames at 4 frames per beat. A timeline (in beats from the song's first strong
downbeat) says which move plays when; outside the timeline the regular party groove loop plays.
Writes sprites/party/moves/<move>.png and adds `moves` + `timeline` to states.party in sprites/sprites.json.
Run after gen_plant.py and before gen_transitions.py.
"""
import importlib.util, json, os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('gp', os.path.join(HERE, 'gen_plant.py'))
gp = importlib.util.module_from_spec(spec); spec.loader.exec_module(gp)
gp.POT_IMG = gp.draw_pot()
C, INK, WHITE, CELL = gp.C, gp.INK, gp.WHITE, gp.CELL
PAL = gp.PAL['party']
LEAF = C(PAL['head'])   # arms use the lighter head green + their own outline so they read in front of the crown
CROWN = gp.render_crown(PAL, 0)

# left "free" arm poses: (elbow, hand) relative to the head centre
LARM = {
    'down':  ((-6, 15), (-9, 17)),
    'out':   ((-9, 14), (-17, 11)),
    'up':    ((-14, 9), (-17, -3)),
    'high':  ((-15, 6), (-12, -15)),
    'over':  ((-15, 6), (-6, -12)),
    'point': ((-10, 13), (-19, 7)),
    'tuck':  ((-5, 15), (2, 10)),
}
# microphone positions: (elbow, mic head) relative to the head centre
MIC = {
    'cheek': ((5, 13), (10, 4)),
    'out':   ((10, 14), (16, 3)),
    'high':  ((15, 6), (13, -12)),
    'front': ((5, 15), (3, 6)),
}


def arm(d, pts, hand_r=2):
    d.line(pts, fill=LEAF, width=3)
    hx, hy = pts[-1]
    d.ellipse([hx - hand_r, hy - hand_r, hx + hand_r, hy + hand_r], fill=LEAF)


FRONT = {'tuck', 'front'}   # poses where the hands are in front of the chest (drawn over the chain)


def draw_left(d, cx, cy, pose, part='all'):
    """part: 'upper' = stem->elbow, 'lower' = elbow->hand + hand, 'all' = both"""
    (ex, ey), (hx, hy) = LARM[pose]
    if part in ('all', 'upper'): d.line([(cx - 1, cy + 14), (cx + ex, cy + ey)], fill=LEAF, width=3)
    if part in ('all', 'lower'):
        arm(d, [(cx + ex, cy + ey), (cx + hx, cy + hy)])
        if pose == 'point':  # pointing leaf tip
            d.polygon([(cx + hx - 1, cy + hy - 1), (cx + hx - 5, cy + hy - 2), (cx + hx - 1, cy + hy + 1)], fill=LEAF)


def draw_mic(d, cx, cy, pos, up=0, part='all'):
    (ex, ey), (mx, my) = MIC[pos]
    hx, hy = cx + mx, cy + my - up
    if part in ('all', 'upper'): d.line([(cx + 1, cy + 14), (cx + ex, cy + ey)], fill=LEAF, width=3)
    if part == 'upper': return
    d.line([(cx + ex, cy + ey), (hx + 3, hy + 6)], fill=LEAF, width=3)
    d.line([(hx + 1, hy + 2), (hx + 3, hy + 7)], fill=C('2a2a33'), width=2)
    d.ellipse([hx + 1, hy + 4, hx + 5, hy + 8], fill=LEAF)
    d.ellipse([hx - 2, hy - 2, hx + 2, hy + 2], fill=C('c8ccd6'))
    d.point((hx - 1, hy - 1), fill=WHITE); d.point((hx, hy), fill=C('7a7f8c')); d.point((hx + 1, hy + 1), fill=C('7a7f8c'))
    d.point((hx + 1, hy - 1), fill=C('7a7f8c')); d.point((hx - 1, hy + 1), fill=C('7a7f8c'))


def render(f, prev):
    cx, cy = gp.HCX + f['dx'], gp.HCY + f['dy']
    sq = f.get('sq', 0); rx, ry = gp.RX + sq, gp.RY - sq
    plant = Image.new('RGBA', (CELL, CELL)); d = ImageDraw.Draw(plant)
    gp.draw_stem(d, cx, cy + ry - 1, PAL)
    sp = f.get('spread', 0)
    for depth in ('back', 'front'):
        for g in 'LTR':
            ox = prev['dx'] + f.get('sw', 0) + (-sp if g == 'L' else sp if g == 'R' else 0)
            oy = prev['dy'] - (sp if g == 'T' else 0)
            gp.paste(plant, CROWN[depth][g], ox, oy)
    d = ImageDraw.Draw(plant)
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=C(PAL['shade']))
    d.ellipse([cx - rx, cy - ry, cx + rx - 2, cy + ry - 2], fill=C(PAL['head']))
    d.ellipse([cx - 8, cy - 8, cx - 2, cy - 4], fill=C(PAL['hi']))
    if f.get('face', True):   # face=False: back of the head (spin)
        fx = cx + f.get('fx', 0)
        gp.draw_mouth(d, fx, cy, SERIOUS.get(f['mouth'], f['mouth']))
        gp.draw_glasses(d, fx, cy, f.get('glint'))   # serious party look: shades + frowning brows
        gp.draw_brows(d, fx, cy)
    gp.draw_beanie(d, cx, cy, max(-1, min(1, f['dy'] - prev['dy'])))
    out = gp.outline(plant)
    mic, larm, up = f.get('mic', 'cheek'), f.get('larm'), f.get('up', 0)
    # behind the chain: whole arms, or only the upper arms when the hands are in front of the chest
    back = Image.new('RGBA', (CELL, CELL)); bd = ImageDraw.Draw(back)
    draw_mic(bd, cx, cy, mic, up, 'upper' if mic in FRONT else 'all')
    if larm: draw_left(bd, cx, cy, larm, 'upper' if larm in FRONT else 'all')
    out.alpha_composite(gp.outline(back, 0.4))
    gp.chain_layer(out, cx, cy, max(-1, min(1, prev['dx'] - f['dx'])))   # chain over the upper arms
    # in front of the chain: forearms, hands and mic for the chest-level poses
    if mic in FRONT or larm in FRONT:
        fr = Image.new('RGBA', (CELL, CELL)); fd = ImageDraw.Draw(fr)
        if larm in FRONT: draw_left(fd, cx, cy, larm, 'lower')
        if mic in FRONT: draw_mic(fd, cx, cy, mic, up, 'lower')
        out.alpha_composite(gp.outline(fr, 0.4))
    out.alpha_composite(gp.POT_IMG)
    return out


SERIOUS = {'big': 'rap', 'smile': 'smirk'}   # rapper face: open serious mouth / half smile instead of grins


def S(**kw):
    n = max(len(v) for v in kw.values() if isinstance(v, list))
    return [{k: (v[i] if isinstance(v, list) else v) for k, v in kw.items()} for i in range(n)]


R4 = lambda *a: list(a) * 4
MOVES = {
    # 0:00-0:03  sings into the mic, free arm sweeps out and over the head
    'sweep': dict(loop=True, frames=S(
        dy=[1, -1, -2, -1, 1, -1, -2, -1], sq=[1, 0, 0, 0, 1, 0, 0, 0], dx=[0, -1, -1, 0, 0, 1, 1, 0], sw=[0, 1, 1, 0, 0, -1, -1, 0],
        larm=['out', 'out', 'up', 'high', 'high', 'up', 'out', 'out'], mic='cheek', up=[0, 1, 1, 0, 0, 1, 1, 0],
        mouth=['big', 'o', 'big', 'smile', 'big', 'o', 'big', 'smile'], eyes=['happy', 'happy', 'open', 'open', 'happy', 'happy', 'open', 'open'])),
    # 0:03-0:06  head thrown back, arm on the forehead (swoon)
    'swoon': dict(loop=True, frames=S(
        dy=[0, -1, -2, -1, 0, -1, -2, -1], dx=[1, 1, 2, 2, 1, 1, 2, 2], sw=[-1, -1, -1, -1, -1, -1, -1, -1],
        larm=['over', 'over', 'high', 'over', 'over', 'over', 'high', 'over'], mic='cheek', up=1,
        mouth=['big', 'big', 'o', 'big', 'big', 'o', 'big', 'o'], eyes='happy')),
    # 0:06-0:07  spins on the floor and pops up (one beat, plays once)
    'spin': dict(loop=False, frames=S(
        dy=[3, 2, 1, -3], sq=[1, 1, 0, 0], dx=[0, 0, 0, 0], sw=[-2, 3, -2, 0], spread=[0, 0, 0, 2],
        face=[True, False, True, True], fx=[-4, 0, 4, 0],
        larm=['down', 'down', 'down', 'up'], mic=['cheek', 'cheek', 'cheek', 'high'],
        eyes=['open', 'open', 'open', 'open'], mouth=['o', 'o', 'o', 'big'])),
    # 0:07-0:11 and 3:06-3:10  wide stance, arms out, stomping side to side
    'stomp': dict(loop=True, frames=S(
        dx=[-1, -2, -2, -2, -2, -2, -2, -1, 1, 2, 2, 2, 2, 2, 2, 1], dy=R4(2, 0, -1, 0), sq=R4(1, 0, 0, 0),
        sw=[1, 1, 1, 1, 1, 1, 1, 1, -1, -1, -1, -1, -1, -1, -1, -1], spread=R4(1, 0, 0, 0),
        larm=['out', 'out', 'up', 'out', 'out', 'down', 'out', 'out', 'out', 'out', 'up', 'out', 'out', 'down', 'out', 'out'],
        mic='out', up=R4(0, 1, 2, 1), mouth=R4('big', 'o', 'smile', 'o'), eyes=R4('happy', 'open', 'open', 'open'))),
    # 3:10-3:12  hunched, both hands on the mic, bobbing on the off-beat
    'hunch': dict(loop=True, frames=S(
        dy=[3, 1, 3, 1], dx=1, sq=[1, 0, 1, 0], sw=[1, 0, 1, 0],
        larm='tuck', mic='front', eyes='happy', mouth=['big', 'o', 'big', 'o'])),
    # 3:12-3:14  arm raised high over the head, mic out, singing
    'raise': dict(loop=True, frames=S(
        dy=[0, -1, -2, -1, 0, -1, -2, -1], dx=[0, 0, -1, -1, 0, 0, 1, 1], sq=[1, 0, 0, 0, 1, 0, 0, 0], spread=[0, 1, 1, 0, 0, 1, 1, 0],
        larm=['high', 'high', 'up', 'high', 'high', 'high', 'up', 'high'], mic='out', up=[0, 1, 1, 0, 0, 1, 1, 0],
        mouth='big', eyes=['happy', 'happy', 'open', 'happy', 'happy', 'happy', 'open', 'happy'])),
    # 3:14-3:17  points at the crowd, mic held up high
    'point': dict(loop=True, frames=S(
        dy=[1, 0, -1, 0, 1, 0, -1, 0], dx=[0, 0, -1, -1, 0, 0, -1, -1], sq=[1, 0, 0, 0, 1, 0, 0, 0],
        larm=['point', 'point', 'point', 'out', 'point', 'point', 'point', 'out'], mic='high', up=[0, 1, 1, 0, 0, 1, 1, 0],
        mouth=['big', 'big', 'o', 'smile', 'big', 'big', 'o', 'smile'], eyes=['open', 'open', 'happy', 'open', 'open', 'open', 'happy', 'open'])),
}

# timeline in beats counted from the song's first strong downbeat (beat 0 = 2.1673 s at 79.178 BPM)
TIMELINE = [
    dict(fromBeat=-4, toBeat=2, move='sweep'),
    dict(fromBeat=2, toBeat=6, move='swoon'),
    dict(fromBeat=6, toBeat=7, move='spin'),
    dict(fromBeat=7, toBeat=12, move='stomp'),
    dict(fromBeat=243, toBeat=248, move='stomp'),
    dict(fromBeat=248, toBeat=251, move='hunch'),
    dict(fromBeat=251, toBeat=254, move='raise'),
    dict(fromBeat=254, toBeat=258, move='point'),
]


def main():
    out = os.path.join(gp.ROOT, 'sprites', 'party', 'moves'); os.makedirs(out, exist_ok=True)
    idx_path = os.path.join(gp.ROOT, 'sprites', 'sprites.json'); idx = json.load(open(idx_path))
    beat = idx['states']['party']['beat']
    moves = {}
    review = Image.new('RGBA', (CELL * 16, CELL * len(MOVES)), (232, 244, 220, 255))
    for r, (name, m) in enumerate(MOVES.items()):
        fr = m['frames']; n = len(fr)
        frames = [render(fr[i], fr[i - 1] if (m['loop'] or i) else fr[i]) for i in range(n)]
        sheet = Image.new('RGBA', (CELL * n, CELL))
        for i, f in enumerate(frames): sheet.paste(f, (i * CELL, 0))
        sheet.save(os.path.join(out, f'{name}.png'), optimize=True)
        review.alpha_composite(sheet, (0, r * CELL))
        moves[name] = {'sheet': f'sprites/party/moves/{name}.png', 'frames': n, 'loop': m['loop']}
    idx['states']['party']['moves'] = moves
    idx['states']['party']['timeline'] = TIMELINE
    idx['states']['party']['timelineNote'] = ('beats counted from beat.firstDownbeatS; inside a timeline entry the move plays '
                                              '(4 frames per beat, looping or once); elsewhere the regular party loop plays')
    json.dump(idx, open(idx_path, 'w'), indent=2, ensure_ascii=False)
    os.makedirs(os.path.join(gp.ROOT, 'run', '64', 'qa'), exist_ok=True)
    review.resize((review.width * 2, review.height * 2), Image.NEAREST).save(os.path.join(gp.ROOT, 'run', '64', 'qa', 'party-moves-x2.png'))
    for e in TIMELINE:
        t0 = beat['firstDownbeatS'] + e['fromBeat'] * 60 / beat['bpm']; t1 = beat['firstDownbeatS'] + e['toBeat'] * 60 / beat['bpm']
        print(f"{e['move']:6s} {max(0, t0):7.2f}s -> {t1:7.2f}s")


if __name__ == '__main__':
    main()
