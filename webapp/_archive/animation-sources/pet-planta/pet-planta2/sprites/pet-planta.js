/* Pet Planta player.
 *
 *   const pet = await new PetPlanta(canvas, { base: 'sprites/', scene: true }).load();
 *   pet.start();               // starts on sprites.json "default" (happy)
 *   pet.setMood('sunny');      // plays transitions["happy>sunny"] once, then loops "sunny"
 *
 * Plant
 * - Every ordered pair of moods has its own transition sheet (sprites/transitions/<from>-to-<to>.png).
 *   Its last frame is frame 7 of the target loop, so the loop continues seamlessly from frame 0.
 * - Transition sheets load on demand (the ones leaving the current mood are preloaded); if one is not
 *   ready yet, a pixel dither dissolve (Bayer 4x4) is used instead.
 * - setMood() during a transition is queued (only the latest request is kept).
 * Scene (scene: true, canvas 256x144)
 * - A greenhouse room per mood (sprites/bg/): sky, scrolling clouds, outside view, room, pulsing light,
 *   plus live particles (snow, rain, stars, fireflies, butterflies, birds, confetti, party lights, motes...).
 * - The background switches together with the plant, with the same dither dissolve.
 * Music sync
 * - pet.syncAudio(audioElement) locks every mood that has a "beat" entry in sprites.json (the party loop:
 *   16 frames = 1 bar, frame 0 = the strong beat) to audio.currentTime, so the dance stays on the beat even
 *   after seeking or frame drops. Party lights in the scene blink on the beat too. Without music it simply
 *   plays at the song tempo. states.party.timeline switches to choreography moves (sprites/party/moves/) during the
 *   parts of the song where the singer dances in the music video; pet.move tells which move is playing.
 * Users with "reduce motion" enabled get instant swaps and a still background.
 */
(function () {
  const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
  const PHASE = { stars: 'sky', snow: 'out', rain: 'out', glassdrops: 'out', butterflies: 'out', birds: 'out', fireflies: 'out',
                  confetti: 'in', motes: 'in', leaves: 'in', lights: 'in' };

  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

  class PetPlanta {
    constructor(canvas, opts = {}) {
      this.c = canvas;
      this.ctx = canvas.getContext('2d');
      this.base = opts.base ?? 'sprites/';
      this.dMs = opts.ditherMs ?? 360;
      this.steps = opts.steps ?? 8;
      this.scene = opts.scene ?? false;
      this.reduce = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
      this.cur = null; this.prev = null; this.tr = null; this.pending = null; this.onchange = null;
      this.tImgs = {}; this.bg = null; this.bgPrev = null;
    }

    _img(src) { return new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = src; }); }
    _url(p) { return this.base + p.replace(/^sprites\//, ''); }
    _ctx(w, h) { const k = document.createElement('canvas'); k.width = w; k.height = h; return k.getContext('2d', { willReadFrequently: true }); }

    async load() {
      const idx = await (await fetch(this.base + 'sprites.json')).json();
      this.index = idx; this.cell = idx.cell;
      this.a = this._ctx(idx.cell, idx.cell); this.b = this._ctx(idx.cell, idx.cell); this.o = this._ctx(idx.cell, idx.cell);
      this.shown = this._ctx(idx.cell, idx.cell); this.edge = this._ctx(idx.cell, idx.cell); this.e2 = this._ctx(idx.cell, idx.cell);
      this.blend = null;   // short dither between the frame on screen and the next one at both ends of a transition
      this.sheets = {};
      const jobs = Object.entries(idx.states).map(async ([m, s]) => {
        this.sheets[m] = { img: await this._img(this._url(s.sheet)), n: s.frames, ms: s.frameDurationMs, label: s.label };
        if (s.moves) {   // choreography moves used by the music timeline
          this.sheets[m].moves = {};
          await Promise.all(Object.entries(s.moves).map(async ([k, mv]) => {
            this.sheets[m].moves[k] = { img: await this._img(this._url(mv.sheet)), n: mv.frames, loop: mv.loop };
          }));
        }
      });
      if (this.scene) jobs.push(this._loadScene());
      await Promise.all(jobs);
      return this;
    }

    async _loadScene() {
      const cfg = await (await fetch(this.base + 'bg/backgrounds.json')).json();
      this.sc = cfg; const [W, H] = cfg.size;
      this.sA = this._ctx(W, H); this.sB = this._ctx(W, H); this.sO = this._ctx(W, H);
      this.layers = {};
      await Promise.all(Object.entries(cfg.moods).map(async ([m, d]) => {
        const L = {};
        for (const k of ['sky', 'clouds', 'view', 'room', 'light']) L[k] = await this._img(this.base + 'bg/' + d[k]);
        L.parts = d.particles.map((p, i) => this._makeParticles(p, m.length * 31 + i * 7));
        this.layers[m] = L;
      }));
    }

    _makeParticles(def, seed) {
      const r = rng(seed), G = this.sc.glass, list = [];
      const n = def.n || 0;
      for (let i = 0; i < n; i++) list.push({ x: r(), y: r(), v: r(), ph: r() * 6.283, k: i });
      return { ...def, list, phase: PHASE[def.type], G };
    }

    syncAudio(audio, beat) {
      this.audio = audio || null;
      this.beatOverride = beat || null;
      return this;
    }

    _beatOf(m) {   // beat position (in beats) of the playing music for a beat-synced mood, or null
      const st = this.index.states[m], b = this.beatOverride || (st && st.beat);
      if (!b || !this.audio || this.audio.paused) return null;
      return (this.audio.currentTime - (b.firstDownbeatS || 0)) * b.bpm / 60;
    }

    get moods() { return Object.keys(this.sheets); }
    get mood() { return this.cur && this.cur.m; }
    get target() { return this.tr ? this.tr.to : this.mood; }

    _trans(from, to) {
      const key = from + '>' + to, t = (this.index.transitions || {})[key];
      if (!t) return null;
      if (!this.tImgs[key]) {
        this.tImgs[key] = { ready: false, n: t.frames, ms: t.frameDurationMs };
        this._img(this._url(t.sheet)).then(img => { this.tImgs[key].img = img; this.tImgs[key].ready = true; }).catch(() => {});
      }
      return this.tImgs[key].ready ? this.tImgs[key] : null;
    }

    _preloadFrom(m) { for (const to of this.moods) if (to !== m) this._trans(m, to); }

    start(m) {
      this.cur = { m: m || this.index.default, t0: performance.now() };
      this.bg = this.cur.m;
      this._preloadFrom(this.cur.m);
      const tick = (now) => { this._draw(now); this.raf = requestAnimationFrame(tick); };
      this.raf = requestAnimationFrame(tick);
      return this;
    }

    stop() { cancelAnimationFrame(this.raf); }

    _bgSwitch(m, now, dur) {
      if (!this.scene || this.bg === m) return;
      if (this.reduce) { this.bg = m; this.bgPrev = null; return; }
      this.bgPrev = { m: this.bg, t0: now, dur }; this.bg = m;
    }

    setMood(m) {
      if (!this.sheets[m]) return;
      if (this.tr || this.prev) { this.pending = (m === this.target ? null : m); if (this.onchange) this.onchange(m); return; }
      if (this.cur && this.cur.m === m) return;
      const now = performance.now(), from = this.cur && this.cur.m;
      if (this.onchange) this.onchange(m);
      if (this.reduce || !from) { this.cur = { m, t0: now }; this.bg = m; this._preloadFrom(m); return; }
      const t = this._trans(from, m);
      if (t) { this.tr = { ...t, to: m, t0: now }; this._edgeBlend(now, 2 * t.ms); this._bgSwitch(m, now, t.n * t.ms); }
      else { this.prev = this.cur; this.cur = { m, t0: now }; this.tStart = now; this._bgSwitch(m, now, this.dMs); this._preloadFrom(m); }
    }

    _frame(ctx, img, k) {
      const C = this.cell;
      ctx.clearRect(0, 0, C, C);
      ctx.drawImage(img, k * C, 0, C, C, 0, 0, C, C);
    }

    _loopFrame(ctx, st, now) {
      const s = this.sheets[st.m], beats = this._beatOf(st.m);
      if (beats !== null) {
        const info = this.index.states[st.m], b = this.beatOverride || info.beat, fpb = b.framesPerBeat || 4;
        const seg = (info.timeline || []).find(e => beats >= e.fromBeat && beats < e.toBeat);
        const mv = seg && s.moves && s.moves[seg.move];
        if (mv) {   // choreography move for this part of the song
          let k = Math.floor((beats - seg.fromBeat) * fpb);
          k = mv.loop ? ((k % mv.n) + mv.n) % mv.n : Math.min(Math.max(k, 0), mv.n - 1);
          this.move = seg.move; this._frame(ctx, mv.img, k);
        } else {
          const k = Math.floor(beats * fpb);
          this.move = null; this._frame(ctx, s.img, ((k % s.n) + s.n) % s.n);
        }
      } else this._frame(ctx, s.img, Math.floor((now - st.t0) / s.ms) % s.n);
    }

    _finish() {
      const p = this.pending; this.pending = null;
      if (p && p !== this.cur.m) this.setMood(p);
    }

    _dither(A, B, w, h, p) {   // writes B into A where the Bayer threshold is below the progress
      const lim = (Math.floor(p * this.steps) + 1) * 16 / this.steps, d = A.data, s = B.data;
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        if (BAYER[(x & 3) + ((y & 3) << 2)] < lim) { const i = (y * w + x) * 4; d[i] = s[i]; d[i + 1] = s[i + 1]; d[i + 2] = s[i + 2]; d[i + 3] = s[i + 3]; }
      }
      return A;
    }

    _edgeBlend(now, dur) {   // freeze what is on screen now and dissolve it into whatever comes next
      if (this.reduce) return;
      this.edge.clearRect(0, 0, this.cell, this.cell); this.edge.drawImage(this.shown.canvas, 0, 0);
      this.blend = { t0: now, dur };
    }

    _plant(now) {
      let out = this._plantRaw(now);
      if (this.blend) {
        const p = (now - this.blend.t0) / this.blend.dur, C = this.cell;
        if (p >= 1) this.blend = null;
        else {
          this.e2.putImageData(this._dither(this.edge.getImageData(0, 0, C, C), out.getImageData(0, 0, C, C), C, C, p), 0, 0);
          out = this.e2;
        }
      }
      this.shown.clearRect(0, 0, this.cell, this.cell); this.shown.drawImage(out.canvas, 0, 0);
      return out;
    }

    _plantRaw(now) {
      const C = this.cell;
      if (this.tr) {
        const k = Math.floor((now - this.tr.t0) / this.tr.ms);
        if (k >= this.tr.n) {
          const ms = this.tr.ms;
          this.cur = { m: this.tr.to, t0: now }; this.tr = null; this._edgeBlend(now, 2 * ms);
          this._preloadFrom(this.cur.m); this._loopFrame(this.b, this.cur, now); this._finish();
        } else this._frame(this.b, this.tr.img, k);
        return this.b;
      }
      this._loopFrame(this.b, this.cur, now);
      if (!this.prev) return this.b;
      const p = (now - this.tStart) / this.dMs;
      if (p >= 1) { this.prev = null; this._finish(); return this.b; }
      this._loopFrame(this.a, this.prev, now);
      this.o.putImageData(this._dither(this.a.getImageData(0, 0, C, C), this.b.getImageData(0, 0, C, C), C, C, p), 0, 0);
      return this.o;
    }

    // ---------------- scene ----------------
    _particles(ctx, L, phase, t) {
      const px = (x, y, c) => { ctx.fillStyle = c; ctx.fillRect(Math.round(x), Math.round(y), 1, 1); };
      for (const P of L.parts) {
        if (P.phase !== phase) continue;
        const [gx0, gy0, gx1, gy1] = P.G, gw = gx1 - gx0 + 1, gh = gy1 - gy0 + 1;
        for (const q of P.list) {
          if (P.type === 'stars') {
            const x = gx0 + q.x * gw, y = gy0 + q.y * 46, s = Math.sin(t * (1 + q.v * 2) + q.ph);
            if (s > 0.1) px(x, y, '#fff8d0');
            if (s > 0.85) { px(x - 1, y, '#c8c4a0'); px(x + 1, y, '#c8c4a0'); px(x, y - 1, '#c8c4a0'); px(x, y + 1, '#c8c4a0'); }
          } else if (P.type === 'snow') {
            const y = gy0 + ((q.y * gh + t * (5 + q.v * 8)) % gh), x = gx0 - 2 + q.x * (gw + 4) + Math.sin(t * 1.3 + q.ph) * 1.5;
            px(x, y, '#ffffff');
            if (q.k % 5 === 0) { px(x - 1, y, '#e8f2ff'); px(x + 1, y, '#e8f2ff'); px(x, y - 1, '#e8f2ff'); px(x, y + 1, '#e8f2ff'); }
          } else if (P.type === 'rain') {
            const y = gy0 - 4 + ((q.y * (gh + 8) + t * (80 + q.v * 40)) % (gh + 8)), x = gx0 + ((q.x * gw + (y - gy0) * 0.3) % gw);
            px(x, y, '#d4dce6'); px(x - 0.3, y - 1, '#b9c4d2'); px(x - 0.6, y - 2, '#9eabbb');
          } else if (P.type === 'glassdrops') {
            const pane = this.sc.panes[1 + (q.k % 3)], h = pane[3] - pane[1];
            const x = pane[0] + 2 + q.x * (pane[2] - pane[0] - 4), y = pane[1] + ((q.y * h + t * (2 + q.v * 5)) % h);
            px(x, y, '#e6edf4'); px(x, y + 1, '#c3cfdb'); px(x, y - 1, '#8e9aa8'); px(x, y - 2, '#8e9aa8');
          } else if (P.type === 'butterflies') {
            const x = gx0 + gw / 2 + Math.sin(t * 0.55 + q.ph) * (gw / 2 - 6), y = 62 + Math.sin(t * 1.1 + q.ph * 2) * 14;
            const open = Math.floor(t * 7 + q.ph) % 2, wc = q.k % 2 ? '#ff8fc0' : '#ffb347';
            px(x, y, '#3a2a2a'); px(x, y + 1, '#3a2a2a');
            if (open) { px(x - 1, y, wc); px(x - 2, y - 1, wc); px(x + 1, y, wc); px(x + 2, y - 1, wc); px(x - 1, y + 1, wc); px(x + 1, y + 1, wc); }
            else { px(x - 1, y - 1, wc); px(x + 1, y - 1, wc); px(x - 1, y, wc); px(x + 1, y, wc); }
          } else if (P.type === 'birds') {
            const x = gx0 - 6 + ((q.x * (gw + 12) + t * (6 + q.v * 6)) % (gw + 12)), y = 26 + q.y * 14 + Math.sin(t * 2 + q.ph);
            const up = Math.floor(t * 5 + q.ph) % 2;
            px(x, y, '#3a4a5a'); px(x - 1, y - up, '#3a4a5a'); px(x + 1, y - up, '#3a4a5a'); px(x - 2, y - up, '#3a4a5a'); px(x + 2, y - up, '#3a4a5a');
          } else if (P.type === 'fireflies') {
            const x = gx0 + 6 + q.x * (gw - 12) + Math.sin(t * 0.7 + q.ph) * 5, y = 72 + q.y * 30 + Math.cos(t * 0.9 + q.ph) * 4;
            if (Math.sin(t * 2.2 + q.ph) > -0.2) { px(x, y, '#f4ff8a'); px(x - 1, y, '#7f9a3a'); px(x + 1, y, '#7f9a3a'); px(x, y - 1, '#7f9a3a'); px(x, y + 1, '#7f9a3a'); }
          } else if (P.type === 'confetti') {
            const cols = ['#f06b9a', '#f7c531', '#4aa8e8', '#7ed957', '#b57cf2', '#ffffff'];
            const y = ((q.y * 160 + t * (16 + q.v * 18)) % 160) - 10, x = q.x * 256 + Math.sin(t * 2 + q.ph) * 3;
            ctx.fillStyle = cols[q.k % cols.length];
            if (Math.floor(t * 6 + q.ph) % 2) ctx.fillRect(Math.round(x), Math.round(y), 2, 1); else ctx.fillRect(Math.round(x), Math.round(y), 1, 2);
          } else if (P.type === 'motes') {
            const x = 64 + q.x * 100 + Math.sin(t * 0.5 + q.ph) * 4, y = 52 + q.y * 76 + Math.sin(t * 0.4 + q.ph * 1.7) * 8;
            if (Math.sin(t * 3 + q.ph) > -0.3) px(x, y, '#' + (P.color || 'fff4b0'));
          } else if (P.type === 'leaves') {
            const y = 40 + ((q.y * 100 + t * (8 + q.v * 6)) % 100), x = 30 + q.x * 196 + Math.sin(t * 1.5 + q.ph) * 6;
            const flip = Math.sin(t * 1.5 + q.ph) > 0;
            px(x, y, '#a07a3a'); px(x + (flip ? 1 : -1), y, '#c9a05a'); px(x, y - 1, '#7d5a2a');
          }
        }
        if (P.type === 'lights') {
          const beats = this._beatOf('party');
          const cols = ['#ff5c8a', '#ffd23f', '#4aa8e8', '#7ed957', '#c07cf2'], step = beats !== null ? Math.floor(beats) : Math.floor(t * 2.5);
          P.points.forEach(([x, y], i) => {
            const on = (i + step) % 2 === 0;
            ctx.fillStyle = cols[(i + step) % cols.length]; ctx.fillRect(x - 1, y, 2, 2);
            if (on) { ctx.fillStyle = '#ffffff'; ctx.fillRect(x - 1, y, 1, 1); }
          });
        }
        if (P.type === 'stars') {   // an occasional shooting star
          const u = (t % 9) / 0.7;
          if (u < 1) { const x = gx0 + 8 + u * 40, y = gy0 + 4 + u * 12; px(x, y, '#ffffff'); px(x - 1, y - 0.3, '#c9d6ff'); px(x - 2, y - 0.6, '#8fa2e0'); }
        }
      }
    }

    _scene(ctx, m, now) {
      const L = this.layers[m], d = this.sc.moods[m], [W, H] = this.sc.size;
      const t = this.reduce ? 0 : now / 1000;
      ctx.clearRect(0, 0, W, H);
      ctx.drawImage(L.sky, 0, 0);
      this._particles(ctx, L, 'sky', t);
      const off = Math.floor((t * d.cloudSpeed) % L.clouds.width);
      for (let x = -off; x < W; x += L.clouds.width) ctx.drawImage(L.clouds, x, this.sc.cloudY);
      ctx.drawImage(L.view, 0, 0);
      this._particles(ctx, L, 'out', t);
      ctx.drawImage(L.room, 0, 0);
      this._particles(ctx, L, 'in', t);
      if (d.lightPulse) { ctx.globalAlpha = 0.7 + 0.3 * Math.sin(t * 1.2); ctx.drawImage(L.light, 0, 0); ctx.globalAlpha = 1; }
    }

    _draw(now) {
      const ctx = this.ctx, W = this.c.width, H = this.c.height;
      const plant = this._plant(now);
      ctx.imageSmoothingEnabled = false;
      if (!this.scene) { ctx.clearRect(0, 0, W, H); ctx.drawImage(plant.canvas, 0, 0, W, H); return; }
      const [SW, SH] = this.sc.size;
      let out = this.sB;
      this._scene(this.sB, this.bg, now);
      if (this.bgPrev) {
        const p = (now - this.bgPrev.t0) / this.bgPrev.dur;
        if (p >= 1) this.bgPrev = null;
        else {
          this._scene(this.sA, this.bgPrev.m, now);
          this.sO.putImageData(this._dither(this.sA.getImageData(0, 0, SW, SH), this.sB.getImageData(0, 0, SW, SH), SW, SH, p), 0, 0);
          out = this.sO;
        }
      }
      out.drawImage(plant.canvas, this.sc.plant.x, this.sc.plant.y);
      ctx.clearRect(0, 0, W, H);
      ctx.drawImage(out.canvas, 0, 0, W, H);
    }
  }

  window.PetPlanta = PetPlanta;
})();
