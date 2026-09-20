'use strict';
/* Puzzle board — arrange sticks, check the cut, roll. */

(function () {
  if (typeof window.__boardStop === 'function') window.__boardStop();
  const TAU = Math.PI * 2;
  const Lmm = 180;
  const INK = {
    salmon: { name: 'Salmon', fill: ['#e07a4a', '#c45c38', '#f0a06a'], mark: '#e07a4a' },
    cucumber: { name: 'Cucumber', fill: ['#6f9440', '#4e6e2c', '#c5d97a'], mark: '#6f9440' },
    tuna: { name: 'Tuna', fill: ['#b03a48', '#7a2432', '#e07a82'], mark: '#b03a48' },
  };
  const PUZZLES = [
    {
      id: 1, title: 'PUZZLE 01', photo: true, guides: true, tol: 0.045,
      target: [
        { kind: 'cucumber', u: 0.22 },
        { kind: 'salmon', u: 0.50 },
        { kind: 'tuna', u: 0.78 },
      ],
      start: [
        { kind: 'salmon', u: 0.28, id: 'salmon' },
        { kind: 'tuna', u: 0.48, id: 'tuna' },
        { kind: 'cucumber', u: 0.74, id: 'cucumber' },
      ],
    },
    {
      id: 2, title: 'PUZZLE 02', photo: false, guides: false, tol: 0.04,
      target: [
        { kind: 'salmon', u: 0.24 },
        { kind: 'tuna', u: 0.50 },
        { kind: 'cucumber', u: 0.76 },
      ],
      start: [
        { kind: 'cucumber', u: 0.26, id: 'cucumber' },
        { kind: 'salmon', u: 0.54, id: 'salmon' },
        { kind: 'tuna', u: 0.78, id: 'tuna' },
      ],
    },
  ];
  const DU = 0.11;

  const canvasEl = document.getElementById('c');
  if (!(canvasEl instanceof HTMLCanvasElement)) return;
  const canvas = canvasEl.cloneNode(false);
  canvasEl.parentNode.replaceChild(canvas, canvasEl);
  const ctx = canvas.getContext('2d');
  const G = {
    level: 0,
    pieces: PUZZLES[0].start.map((p) => ({ ...p })),
    drag: null, pass: false, checked: false, score: 0, guides: true,
    phase: 'arrange', rollT: 0, winPulse: 0, lesson: true,
    W: 0, H: 0, dpr: 1, layout: null, hits: [],
  };

  const WEDGE_ANG = { salmon: -1.5436, cucumber: 2.4842, tuna: 0.5288 };
  const ASSET = (function () {
    const s = document.currentScript && document.currentScript.src;
    return s ? s.replace(/board\.js(\?.*)?$/, '') : '/play/';
  })();
  const imgs = {};
  function loadImg(name, src) {
    const im = new Image();
    im.onload = () => { imgs[name] = im; };
    im.src = src;
  }
  loadImg('maki', ASSET + 'assets/board/maki-target.png');
  loadImg('base', ASSET + 'assets/board/maki-base.png');
  ['salmon', 'cucumber', 'tuna'].forEach((k) => {
    loadImg(k, ASSET + 'assets/board/' + k + '.png?v=7');
    loadImg('wedge-' + k, ASSET + 'assets/board/wedge-' + k + '.png');
  });

  function puzzle() { return PUZZLES[G.level]; }
  function TARGET() { return puzzle().target; }

  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function ease(t) { return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }
  function rr(x, y, w, h, r) {
    const R = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + R, y);
    ctx.arcTo(x + w, y, x + w, y + h, R);
    ctx.arcTo(x + w, y + h, x, y + h, R);
    ctx.arcTo(x, y + h, x, y, R);
    ctx.arcTo(x, y, x + w, y, R);
    ctx.closePath();
  }
  function displayFont(px, w) {
    return (w || 600) + ' ' + px + 'px "Palatino Linotype", Palatino, "Iowan Old Style", Georgia, serif';
  }
  function ui(px, w) {
    return (w || 600) + ' ' + px + 'px "Avenir Next", "Segoe UI", system-ui, sans-serif';
  }

  function deltas() {
    return TARGET().map((t) => {
      const p = G.pieces.find((x) => x.kind === t.kind);
      const du = (p ? p.u : 0) - t.u;
      return { kind: t.kind, du, mm: Math.round(Math.abs(du) * Lmm), dir: (p && p.u < t.u) ? 'UP' : 'DOWN' };
    });
  }
  function matchScore() {
    const ds = deltas();
    const worst = Math.max(...ds.map((d) => Math.abs(d.du)));
    return { pass: worst <= puzzle().tol, score: Math.round(clamp(1 - worst / 0.35, 0, 1) * 100), ds };
  }

  function relayout() {
    const dpr = Math.min(3, window.devicePixelRatio || 1);
    const VW = window.innerWidth, VH = window.innerHeight;
    if (canvas.width !== Math.round(VW * dpr) || canvas.height !== Math.round(VH * dpr)) {
      canvas.width = Math.round(VW * dpr);
      canvas.height = Math.round(VH * dpr);
      canvas.style.width = VW + 'px';
      canvas.style.height = VH + 'px';
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    G.W = VW; G.H = VH; G.dpr = dpr;
    const colW = Math.min(420, VW);
    const ox = Math.round((VW - colW) / 2);
    const headerH = 48, stepsH = 28, cutH = 158, dockH = 86, pad = 14;
    const sheetY = headerH + stepsH + cutH + 8;
    const sheetH = Math.max(170, VH - sheetY - dockH - 6);
    const sheet = { x: ox + pad, y: sheetY, w: colW - pad * 2, h: sheetH };
    const rice = { x: sheet.x + 22, y: sheet.y + 18, w: sheet.w - 44, h: sheet.h - 40 };
    const cardW = (colW - pad * 2 - 10) / 2;
    const cutY = headerH + stepsH + 8;
    const cutR = Math.min(46, cardW / 2 - 20, (cutH - 52) / 2);
    const cuts = [
      { lab: 'TARGET CUT', x: ox + pad + cardW / 2, y: cutY + 10 + cutR, r: cutR, target: true, card: { x: ox + pad, y: cutY, w: cardW, h: cutH - 10 } },
      { lab: 'YOUR CUT', x: ox + pad + 10 + cardW + cardW / 2, y: cutY + 10 + cutR, r: cutR, target: false, card: { x: ox + pad + cardW + 10, y: cutY, w: cardW, h: cutH - 10 } },
    ];
    G.layout = { ox, colW, headerH, stepsH, cutH, sheet, rice, cuts, dockY: VH - dockH, dockH, pad };
  }

  function uToY(u, rice) { return rice.y + (1 - u) * rice.h; }
  function yToU(y, rice) { return clamp(1 - (y - rice.y) / rice.h, 0.08, 0.92); }
  function stripRect(p, rice) {
    const h = DU * rice.h;
    return { x: rice.x + 10, y: uToY(p.u, rice) - h / 2, w: rice.w - 20, h };
  }

  function drawPetal(kind, ang, R) {
    const c = INK[kind].fill;
    ctx.save();
    ctx.rotate(ang);
    ctx.beginPath();
    if (kind === 'cucumber') {
      ctx.moveTo(R * 0.06, 0);
      ctx.bezierCurveTo(R * 0.22, R * 0.30, R * 0.48, R * 0.28, R * 0.66, 0);
      ctx.bezierCurveTo(R * 0.48, -R * 0.28, R * 0.22, -R * 0.30, R * 0.06, 0);
    } else if (kind === 'salmon') {
      ctx.moveTo(R * 0.04, 0);
      ctx.lineTo(R * 0.18, R * 0.34);
      ctx.lineTo(R * 0.52, R * 0.30);
      ctx.lineTo(R * 0.66, 0);
      ctx.lineTo(R * 0.52, -R * 0.30);
      ctx.lineTo(R * 0.18, -R * 0.32);
      ctx.closePath();
    } else {
      ctx.moveTo(R * 0.08, 0);
      ctx.lineTo(R * 0.26, R * 0.22);
      ctx.lineTo(R * 0.50, R * 0.20);
      ctx.lineTo(R * 0.64, 0);
      ctx.lineTo(R * 0.50, -R * 0.20);
      ctx.lineTo(R * 0.26, -R * 0.22);
      ctx.closePath();
    }
    const g = ctx.createLinearGradient(R * 0.10, -R * 0.16, R * 0.62, R * 0.14);
    g.addColorStop(0, c[2]);
    g.addColorStop(0.5, c[0]);
    g.addColorStop(1, c[1]);
    ctx.fillStyle = g;
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(R * 0.12, 0);
    ctx.lineTo(R * 0.48, R * 0.12);
    ctx.lineTo(R * 0.48, -R * 0.05);
    ctx.closePath();
    ctx.fillStyle = c[2];
    ctx.globalAlpha = 0.30;
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  function drawRiceRing(rad) {
    const n = 16;
    for (let i = 0; i < n; i++) {
      const a = (i + 0.35) / n * TAU;
      ctx.save();
      ctx.translate(Math.cos(a) * rad * 0.80, Math.sin(a) * rad * 0.80);
      ctx.rotate(a + 0.5);
      ctx.beginPath();
      ctx.ellipse(0, 0, rad * 0.135, rad * 0.088, 0, 0, TAU);
      ctx.fillStyle = i % 2 ? '#f8f3e9' : '#efe5d4';
      ctx.fill();
      ctx.restore();
    }
  }

  function drawSchematicRoll(pieces, rad) {
    ctx.beginPath();
    ctx.arc(0, 0, rad * 1.02, 0, TAU);
    ctx.fillStyle = '#16140f';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(0, 0, rad * 0.93, 0, TAU);
    ctx.fillStyle = '#f3ece0';
    ctx.fill();
    drawRiceRing(rad);
    ctx.beginPath();
    ctx.arc(0, 0, rad * 0.66, 0, TAU);
    ctx.fillStyle = '#f3ece0';
    ctx.fill();
    const seats = TARGET().slice().sort((a, b) => a.u - b.u);
    const placed = pieces.slice().sort((a, b) => a.u - b.u);
    for (let i = 0; i < placed.length; i++) {
      const dest = WEDGE_ANG[seats[i].kind];
      if (dest == null) continue;
      drawPetal(placed[i].kind, dest, rad);
    }
  }

  function drawSpriteMaki(cx, cy, R, pieces, isTarget) {
    const size = R * 2.0;
    const wantPhoto = puzzle().photo && imgs.maki && (isTarget || G.pass);
    if (wantPhoto) {
      ctx.drawImage(imgs.maki, cx - size / 2, cy - size / 2, size, size);
      return true;
    }
    ctx.save();
    ctx.translate(cx, cy);
    drawSchematicRoll(isTarget ? TARGET() : pieces, size / 2);
    ctx.restore();
    return true;
  }

  function drawPaper() {
    ctx.fillStyle = '#efe4cf'; ctx.fillRect(0, 0, G.W, G.H);
    const L = G.layout;
    const shards = [
      [0, 0, 120, 0, 0, 90, '#2a6b62'],
      [G.W, 0, G.W - 140, 0, G.W, 100, '#d45a3c'],
      [0, G.H, 0, G.H - 110, 90, G.H, '#1c2430'],
      [G.W, G.H, G.W - 100, G.H, G.W, G.H - 80, '#e07a4a'],
    ];
    for (const s of shards) {
      ctx.beginPath(); ctx.moveTo(s[0], s[1]); ctx.lineTo(s[2], s[3]); ctx.lineTo(s[4], s[5]);
      ctx.closePath(); ctx.globalAlpha = 0.12; ctx.fillStyle = s[6]; ctx.fill(); ctx.globalAlpha = 1;
    }
    if (L.colW < G.W - 8) {
      ctx.fillStyle = 'rgba(28,36,48,0.04)';
      ctx.fillRect(0, 0, L.ox, G.H);
      ctx.fillRect(L.ox + L.colW, 0, G.W - L.ox - L.colW, G.H);
    }
  }

  function roundBtn(id, x, cy, glyph) {
    ctx.beginPath(); ctx.arc(x, cy, 14, 0, TAU);
    ctx.strokeStyle = 'rgba(244,234,216,0.45)'; ctx.lineWidth = 1.2; ctx.stroke();
    ctx.fillStyle = '#f4ead8'; ctx.font = ui(13, 600); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(glyph, x, cy + 1);
    G.hits.push({ id, x: x - 16, y: cy - 16, w: 32, h: 32 });
  }

  function drawHeader(L) {
    ctx.fillStyle = '#1c2430';
    ctx.fillRect(L.ox, 0, L.colW, L.headerH);
    roundBtn('back', L.ox + 22, L.headerH / 2, '←');
    ctx.fillStyle = '#f4ead8';
    ctx.font = displayFont(16, 700);
    ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    ctx.fillText('ROLLERY', L.ox + 42, L.headerH / 2 - 7);
    ctx.fillStyle = '#e2c48a';
    ctx.font = ui(9, 600);
    ctx.fillText(puzzle().title, L.ox + 42, L.headerH / 2 + 10);
    roundBtn('undo', L.ox + L.colW - 56, L.headerH / 2, '↺');
    if (puzzle().guides) {
      roundBtn('guides', L.ox + L.colW - 22, L.headerH / 2, G.guides ? '▣' : '□');
    }
  }

  function drawSteps(L) {
    const y = L.headerH;
    const nowArrange = G.phase === 'arrange' && !G.pass;
    const nowMatch = G.pass && G.phase === 'arrange';
    const nowCut = G.phase === 'rolling' || G.phase === 'rolled';
    const steps = [
      { t: 'BASE', on: true }, { t: 'RICE', on: true },
      { t: 'ARRANGE', on: true, now: nowArrange },
      { t: 'MATCH', on: G.pass, now: nowMatch },
      { t: 'CUT', on: nowCut, now: nowCut },
    ];
    const x0 = L.ox + 12, w = L.colW - 24, slot = w / steps.length;
    ctx.fillStyle = '#e8dcc6';
    ctx.fillRect(x0, y, w, L.stepsH);
    steps.forEach((s, i) => {
      const x = x0 + i * slot;
      if (s.now) { ctx.fillStyle = '#d45a3c'; ctx.fillRect(x, y, slot, L.stepsH); }
      ctx.fillStyle = s.now ? '#f4ead8' : (s.on ? '#1c2430' : '#8a7f70');
      ctx.font = ui(8, 700); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(s.t, x + slot / 2, y + L.stepsH / 2);
    });
  }

  function drawCuts(L) {
    const pulse = G.winPulse > 0 ? 1 + 0.04 * Math.sin(G.winPulse * 14) * G.winPulse : 1;
    for (const c of L.cuts) {
      ctx.save();
      if (!c.target && pulse !== 1) {
        ctx.translate(c.x, c.y);
        ctx.scale(pulse, pulse);
        ctx.translate(-c.x, -c.y);
      }
      rr(c.card.x, c.card.y, c.card.w, c.card.h, 14);
      ctx.fillStyle = '#243038'; ctx.fill();
      ctx.save();
      rr(c.card.x, c.card.y, c.card.w, c.card.h, 14);
      ctx.clip();
      ctx.fillStyle = 'rgba(12,14,16,0.45)';
      ctx.fillRect(c.card.x, c.card.y + c.card.h - 24, c.card.w, 24);
      ctx.restore();
      drawSpriteMaki(c.x, c.y, c.r, c.target ? TARGET() : G.pieces, c.target);
      ctx.fillStyle = '#d8ccb6';
      ctx.font = ui(7, 700); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(c.lab, c.x, c.card.y + c.card.h - 12);
      ctx.restore();
    }
    if (G.pass) {
      const c = L.cuts[1];
      ctx.fillStyle = '#9dba5a';
      ctx.font = ui(8, 700);
      ctx.textAlign = 'center';
      ctx.fillText('MATCHED', c.x, c.card.y + 14);
    }
  }

  function drawSheet(L) {
    const s = L.sheet, rice = L.rice;
    const rolling = G.phase === 'rolling' || G.phase === 'rolled';
    const t = rolling ? ease(G.rollT) : 0;
    rr(s.x, s.y, s.w, s.h, 16);
    ctx.fillStyle = '#2a322c'; ctx.fill();

    ctx.save();
    ctx.translate(s.x + 11, s.y + s.h / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillStyle = '#d8d0c0'; ctx.font = ui(8, 700);
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('ROLL DIRECTION', 0, 0);
    ctx.restore();

    rr(rice.x, rice.y, rice.w, rice.h, 10);
    ctx.fillStyle = '#f6f0e4'; ctx.fill();
    ctx.save();
    rr(rice.x, rice.y, rice.w, rice.h, 10); ctx.clip();
    for (let i = 0; i < 120; i++) {
      const x = rice.x + 6 + ((i * 53) % (rice.w - 12));
      const y = rice.y + 6 + ((i * 37) % (rice.h - 12));
      ctx.beginPath(); ctx.ellipse(x, y, 3.4, 2.2, (i % 7) * 0.4, 0, TAU);
      ctx.fillStyle = i % 3 ? 'rgba(210,196,170,0.45)' : 'rgba(255,252,246,0.5)';
      ctx.fill();
    }

    const front = rice.y + rice.h * (1 - t);
    const cylH = lerp(0, Math.min(42, rice.h * 0.18), Math.min(1, t * 1.4));

    if (G.guides && G.phase === 'arrange' && !G.pass) {
      const worst = deltas().filter((d) => d.mm >= 6).sort((a, b) => b.mm - a.mm)[0];
      if (worst) {
        const tgt = TARGET().find((x) => x.kind === worst.kind);
        const y = uToY(tgt.u, rice);
        ctx.save();
        ctx.setLineDash([5, 4]);
        ctx.strokeStyle = INK[tgt.kind].mark;
        ctx.lineWidth = 1.6;
        ctx.globalAlpha = 0.55;
        ctx.beginPath();
        ctx.moveTo(rice.x + 12, y);
        ctx.lineTo(rice.x + rice.w - 12, y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
        ctx.beginPath();
        ctx.moveTo(rice.x + 12, y - 5);
        ctx.lineTo(rice.x + 12, y + 5);
        ctx.moveTo(rice.x + rice.w - 12, y - 5);
        ctx.lineTo(rice.x + rice.w - 12, y + 5);
        ctx.stroke();
        ctx.restore();
      }
    }

    for (const p of G.pieces) {
      const r = stripRect(p, rice);
      const cy = r.y + r.h / 2;
      if (rolling && (t > 0.82 || cy > front - 6)) continue;
      const spec = INK[p.kind];
      const hold = G.drag && G.drag.id === p.id;
      const dx = r.x + 10, dw = r.w - 20, dh = r.h * 0.74;
      const dy = r.y + (r.h - dh) / 2;
      ctx.save();
      rr(dx, dy, dw, dh, dh * 0.48);
      ctx.clip();
      if (imgs[p.kind]) {
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(imgs[p.kind], dx, dy, dw, dh);
      } else {
        ctx.fillStyle = spec.fill[0];
        ctx.fillRect(dx, dy, dw, dh);
      }
      ctx.restore();
      if (hold) {
        ctx.strokeStyle = '#1c2430';
        ctx.lineWidth = 2;
        rr(dx - 2, dy - 2, dw + 4, dh + 4, dh * 0.48);
        ctx.stroke();
      }
      if (G.phase === 'arrange') {
        G.hits.push({ id: 'piece:' + p.id, x: r.x, y: r.y, w: r.w, h: r.h });
      }
    }

    if (rolling && cylH > 2) {
      const y = front - cylH * 0.45;
      rr(rice.x + 4, y, rice.w - 8, cylH, cylH * 0.48);
      ctx.fillStyle = '#1a1814';
      ctx.fill();
      rr(rice.x + 10, y + cylH * 0.18, rice.w - 20, cylH * 0.42, cylH * 0.2);
      ctx.fillStyle = '#3a342c';
      ctx.fill();
      ctx.fillStyle = 'rgba(244,234,216,0.16)';
      ctx.fillRect(rice.x + 18, y + cylH * 0.22, rice.w - 36, 2);
    }

    if (t > 0.02) {
      ctx.fillStyle = '#2a322c';
      ctx.fillRect(rice.x, front + cylH * 0.4, rice.w, rice.y + rice.h - front);
    }
    ctx.restore();

    if (G.guides && G.phase === 'arrange' && !G.pass) {
      const ds = deltas().filter((d) => d.mm >= 4).sort((a, b) => b.mm - a.mm);
      if (ds[0]) {
        const tgt = TARGET().find((x) => x.kind === ds[0].kind);
        const p = G.pieces.find((x) => x.kind === ds[0].kind);
        const a = stripRect(p, rice), b = stripRect(tgt, rice);
        const x = rice.x + rice.w - 10;
        ctx.strokeStyle = INK[ds[0].kind].mark;
        ctx.fillStyle = INK[ds[0].kind].mark;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(x, a.y + a.h / 2);
        ctx.lineTo(x, b.y + b.h / 2);
        ctx.stroke();
        const dir = b.y < a.y ? -1 : 1, ty = b.y + b.h / 2;
        ctx.beginPath();
        ctx.moveTo(x, ty);
        ctx.lineTo(x - 4, ty + 7 * dir);
        ctx.lineTo(x + 4, ty + 7 * dir);
        ctx.closePath();
        ctx.fill();
        const label = INK[ds[0].kind].name.toUpperCase() + '  ' + ds[0].dir + '  ' + ds[0].mm + ' mm';
        ctx.font = ui(9, 700);
        const tw = ctx.measureText(label).width;
        const ly = rice.y + 8;
        const lx = rice.x + rice.w - tw - 18;
        rr(lx, ly, tw + 14, 18, 6);
        ctx.fillStyle = '#1c2430';
        ctx.fill();
        ctx.fillStyle = '#f4ead8';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, lx + tw / 2 + 7, ly + 10);
      }
    }

    if (G.lesson && G.phase === 'arrange' && G.level === 0) {
      const ly = s.y + s.h - 36;
      rr(s.x + 28, ly, s.w - 56, 22, 8);
      ctx.fillStyle = '#1c2430';
      ctx.fill();
      ctx.fillStyle = '#f4ead8';
      ctx.font = ui(8, 700);
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('THIS EDGE BECOMES THE CORE', s.x + s.w / 2, ly + 12);
    } else {
      ctx.fillStyle = '#d8d0c0';
      ctx.font = ui(8, 600); ctx.textAlign = 'center';
      ctx.fillText('↑  FROM THIS EDGE  ·  becomes the core', s.x + s.w / 2, s.y + s.h - 12);
    }
  }

  function drawDock(L) {
    const y = L.dockY, x = L.ox + L.pad, w = L.colW - L.pad * 2;
    const by = y + 22, bh = 44;
    const gap = 8;
    const resetW = 72, rollW = 88;
    const checkW = w - resetW - rollW - gap * 2;
    const busy = G.phase === 'rolling';

    rr(x, by, resetW, bh, 12);
    ctx.fillStyle = '#fff'; ctx.fill();
    ctx.strokeStyle = 'rgba(28,36,48,0.18)'; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = '#1c2430'; ctx.font = ui(11, 700); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('RESET', x + resetW / 2, by + bh / 2);
    if (!busy) G.hits.push({ id: 'reset', x, y: by, w: resetW, h: bh });

    const cx = x + resetW + gap;
    rr(cx, by, checkW, bh, 12);
    ctx.fillStyle = G.pass ? '#2a6b62' : '#d45a3c'; ctx.fill();
    ctx.fillStyle = '#f4ead8'; ctx.font = ui(13, 700);
    let mid = 'CHECK CUT';
    if (G.phase === 'rolling') mid = 'ROLLING';
    else if (G.phase === 'rolled') mid = 'ROLLED';
    else if (G.pass) mid = 'MATCHED  ' + G.score + '%';
    else if (G.checked) mid = 'AGAIN  ·  ' + G.score + '%';
    ctx.fillText(mid, cx + checkW / 2, by + bh / 2);
    if (G.phase === 'arrange') G.hits.push({ id: 'check', x: cx, y: by, w: checkW, h: bh });

    const rx = x + w - rollW;
    const canRoll = G.pass && G.phase === 'arrange';
    const canNext = G.phase === 'rolled';
    const glow = canRoll && (Math.sin(performance.now() / 280) > 0);
    rr(rx, by, rollW, bh, 12);
    ctx.fillStyle = canRoll || canNext ? (glow ? '#2a241c' : '#1c2430') : '#d9d0c2';
    ctx.fill();
    ctx.fillStyle = canRoll || canNext ? '#f4ead8' : '#8a7f70';
    ctx.font = ui(10, 700);
    const rlab = busy ? '…' : (canNext ? (G.level < PUZZLES.length - 1 ? 'NEXT' : 'AGAIN') : (canRoll ? 'ROLL' : 'LOCKED'));
    ctx.fillText(rlab, rx + rollW / 2, by + bh / 2);
    if (canRoll) G.hits.push({ id: 'roll', x: rx, y: by, w: rollW, h: bh });
    if (canNext) G.hits.push({ id: 'next', x: rx, y: by, w: rollW, h: bh });
  }

  function frame() {
    G.hits = [];
    relayout();
    const L = G.layout;
    drawPaper();
    drawHeader(L);
    drawSteps(L);
    drawCuts(L);
    drawSheet(L);
    drawDock(L);
  }

  function hitAt(x, y) {
    for (let i = G.hits.length - 1; i >= 0; i--) {
      const h = G.hits[i];
      if (x >= h.x && x <= h.x + h.w && y >= h.y && y <= h.y + h.h) return h;
    }
    return null;
  }
  function loadLevel(i) {
    G.level = clamp(i, 0, PUZZLES.length - 1);
    const P = puzzle();
    G.pieces = P.start.map((p) => ({ ...p }));
    G.pass = false; G.checked = false; G.score = 0; G.drag = null;
    G.phase = 'arrange'; G.rollT = 0; G.winPulse = 0;
    G.guides = P.guides;
    if (G.level === 0) G.lesson = G.lesson !== false;
  }
  function reset() {
    loadLevel(G.level);
  }
  function check() {
    if (G.phase !== 'arrange') return;
    const m = matchScore();
    G.checked = true; G.pass = m.pass; G.score = m.score;
    if (m.pass) G.winPulse = 1;
  }
  function startRoll() {
    if (!(G.pass && G.phase === 'arrange')) return;
    G.phase = 'rolling';
    G.rollT = 0;
  }
  function goNext() {
    if (G.level < PUZZLES.length - 1) loadLevel(G.level + 1);
    else loadLevel(0);
  }
  function onDown(x, y) {
    const h = hitAt(x, y);
    if (!h) return;
    if (h.id.startsWith('piece:')) {
      const id = h.id.slice(6);
      const p = G.pieces.find((q) => q.id === id);
      const r = stripRect(p, G.layout.rice);
      G.drag = { id, off: y - (r.y + r.h / 2) };
      G.pass = false;
      G.lesson = false;
      return;
    }
    if (h.id === 'reset' || h.id === 'undo') reset();
    if (h.id === 'check') check();
    if (h.id === 'guides') G.guides = !G.guides;
    if (h.id === 'roll') startRoll();
    if (h.id === 'next') goNext();
    if (h.id === 'back') { if (G.level > 0) loadLevel(G.level - 1); else reset(); }
  }
  function onMove(x, y) {
    if (!G.drag || G.phase !== 'arrange') return;
    const p = G.pieces.find((q) => q.id === G.drag.id);
    p.u = yToU(y - G.drag.off, G.layout.rice);
    G.pass = false;
  }
  function onUp() { G.drag = null; }
  function pt(e) {
    const r = canvas.getBoundingClientRect();
    const t = e.touches ? e.touches[0] || e.changedTouches[0] : e;
    return { x: t.clientX - r.left, y: t.clientY - r.top };
  }

  let alive = true;
  let last = 0;
  function loop(now) {
    if (!alive) return;
    const dt = Math.min(0.1, (now - last) / 1000 || 0.016);
    last = now;
    if (G.winPulse > 0) G.winPulse = Math.max(0, G.winPulse - dt * 1.6);
    if (G.phase === 'rolling') {
      G.rollT = Math.min(1, G.rollT + dt / 1.35);
      if (G.rollT >= 1) G.phase = 'rolled';
    }
    frame();
    requestAnimationFrame(loop);
  }

  canvas.addEventListener('pointerdown', onPointerDown);
  canvas.addEventListener('pointermove', onPointerMove);
  canvas.addEventListener('pointerup', onUp);
  canvas.addEventListener('pointercancel', onUp);
  window.addEventListener('resize', frame);
  window.__boardStop = function () {
    alive = false;
    canvas.removeEventListener('pointerdown', onPointerDown);
    canvas.removeEventListener('pointermove', onPointerMove);
    canvas.removeEventListener('pointerup', onUp);
    canvas.removeEventListener('pointercancel', onUp);
    window.removeEventListener('resize', frame);
    window.__board = null;
  };
  function onPointerDown(e) { canvas.setPointerCapture(e.pointerId); const p = pt(e); onDown(p.x, p.y); }
  function onPointerMove(e) { const p = pt(e); onMove(p.x, p.y); }
  loadLevel(0);
  window.__board = G;
  requestAnimationFrame(loop);
})();
