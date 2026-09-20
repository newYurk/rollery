'use strict';
/* Puzzle 01 board — paper chrome + faceted cuts. Independent of the lab renderer. */

(function () {
  const TAU = Math.PI * 2;
  const Lmm = 180;
  const INK = {
    salmon: { name: 'Salmon', fill: ['#e07a4a', '#c45c38', '#f0a06a'], mark: '#e07a4a' },
    cucumber: { name: 'Cucumber', fill: ['#6f9440', '#4e6e2c', '#c5d97a'], mark: '#6f9440' },
    tuna: { name: 'Tuna', fill: ['#b03a48', '#7a2432', '#e07a82'], mark: '#b03a48' },
  };
  const TARGET = [
    { kind: 'cucumber', u: 0.22 },
    { kind: 'salmon', u: 0.50 },
    { kind: 'tuna', u: 0.78 },
  ];
  const START = [
    { kind: 'salmon', u: 0.28, id: 'salmon' },
    { kind: 'tuna', u: 0.48, id: 'tuna' },
    { kind: 'cucumber', u: 0.74, id: 'cucumber' },
  ];
  const DU = 0.13;

  const canvas = document.getElementById('c');
  if (!(canvas instanceof HTMLCanvasElement)) return;
  const ctx = canvas.getContext('2d');
  const G = {
    pieces: START.map((p) => ({ ...p })),
    drag: null, pass: false, checked: false, score: 0, guides: true,
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
    im.onload = () => { imgs[name] = im; if (G.layout) frame(); };
    im.src = src;
  }
  loadImg('maki', ASSET + 'assets/board/maki-target.png');
  loadImg('base', ASSET + 'assets/board/maki-base.png');
  ['salmon','cucumber','tuna'].forEach((k) => {
    loadImg(k, ASSET + 'assets/board/' + k + '.png?v=3');
    loadImg('wedge-' + k, ASSET + 'assets/board/wedge-' + k + '.png');
  });


  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function lerp(a, b, t) { return a + (b - a) * t; }
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
    return TARGET.map((t) => {
      const p = G.pieces.find((x) => x.kind === t.kind);
      const du = (p ? p.u : 0) - t.u;
      return { kind: t.kind, du, mm: Math.round(Math.abs(du) * Lmm), dir: (p && p.u < t.u) ? 'UP' : 'DOWN' };
    });
  }
  function matchScore() {
    const ds = deltas();
    const worst = Math.max(...ds.map((d) => Math.abs(d.du)));
    return { pass: worst <= 0.045, score: Math.round(clamp(1 - worst / 0.35, 0, 1) * 100), ds };
  }
  function orderMatch() {
    const a = G.pieces.slice().sort((x, y) => x.u - y.u).map((p) => p.kind).join();
    const b = TARGET.slice().sort((x, y) => x.u - y.u).map((p) => p.kind).join();
    return a === b;
  }

  function relayout() {
    const dpr = Math.min(2.5, window.devicePixelRatio || 1);
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
    const headerH = 48, stepsH = 28, cutH = 142, dockH = 86, pad = 14;
    const sheetY = headerH + stepsH + cutH + 8;
    const sheetH = Math.max(170, VH - sheetY - dockH - 6);
    const sheet = { x: ox + pad, y: sheetY, w: colW - pad * 2, h: sheetH };
    const rice = { x: sheet.x + 22, y: sheet.y + 18, w: sheet.w - 44, h: sheet.h - 40 };
    const cardW = (colW - pad * 2 - 10) / 2;
    const cutY = headerH + stepsH + 8;
    const cutR = Math.min(50, cardW / 2 - 18, (cutH - 44) / 2);
    const cuts = [
      { lab: 'TARGET CUT', x: ox + pad + cardW / 2, y: cutY + 18 + cutR, r: cutR, target: true, card: { x: ox + pad, y: cutY, w: cardW, h: cutH - 12 } },
      { lab: 'YOUR CUT', x: ox + pad + 10 + cardW + cardW / 2, y: cutY + 18 + cutR, r: cutR, target: false, card: { x: ox + pad + cardW + 10, y: cutY, w: cardW, h: cutH - 12 } },
    ];
    G.layout = { ox, colW, headerH, stepsH, cutH, sheet, rice, cuts, dockY: VH - dockH, dockH, pad };
  }

  function uToY(u, rice) { return rice.y + (1 - u) * rice.h; }
  function yToU(y, rice) { return clamp(1 - (y - rice.y) / rice.h, 0.08, 0.92); }
  function stripRect(p, rice) {
    const h = DU * rice.h;
    return { x: rice.x + 10, y: uToY(p.u, rice) - h / 2, w: rice.w - 20, h };
  }

  function wedge(R, u, du, r0, r1) {
    const a = -Math.PI / 2 + u * TAU * 0.9;
    const half = Math.max(0.38, du * TAU * 0.45);
    const steps = 6, outer = [], inner = [];
    for (let i = 0; i <= steps; i++) {
      const t = lerp(a - half, a + half, i / steps);
      const j = 1 + ((i % 2) ? 0.025 : -0.02);
      outer.push([Math.cos(t) * r1 * j, Math.sin(t) * r1 * j]);
    }
    for (let i = steps; i >= 0; i--) {
      const t = lerp(a - half, a + half, i / steps);
      inner.push([Math.cos(t) * r0, Math.sin(t) * r0]);
    }
    return outer.concat(inner);
  }

  function wrapAng(a) {
    a = a % TAU;
    return a < 0 ? a + TAU : a;
  }
  function arcMid(a, b) {
    let d = wrapAng(b) - wrapAng(a);
    if (d < 0) d += TAU;
    return wrapAng(a + d / 2);
  }
  function drawWell(pieces, rad) {
    const items = pieces.map((p) => ({ kind: p.kind, a: wrapAng(angleOf(p)) }));
    items.sort((x, y) => x.a - y.a);
    const n = items.length;
    const gap = 0.05;
    for (let i = 0; i < n; i++) {
      const prev = items[(i + n - 1) % n];
      const next = items[(i + 1) % n];
      const a0 = wrapAng(arcMid(prev.a, items[i].a) + gap);
      let span = wrapAng(arcMid(items[i].a, next.a) - gap) - a0;
      if (span < 0) span += TAU;
      const c = INK[items[i].kind].fill;
      const mid = a0 + span / 2;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.arc(0, 0, rad * 0.58, a0, a0 + span);
      ctx.closePath();
      const g = ctx.createLinearGradient(
        Math.cos(mid) * rad * 0.08, Math.sin(mid) * rad * 0.08,
        Math.cos(mid) * rad * 0.5, Math.sin(mid) * rad * 0.5
      );
      g.addColorStop(0, c[2]);
      g.addColorStop(0.5, c[0]);
      g.addColorStop(1, c[1]);
      ctx.fillStyle = g;
      ctx.fill();
    }
  }

  function angleOf(p) {
    return 0.78 + p.u * 7.73;
  }
  function angDelta(from, to) {
    let d = (to - from) % TAU;
    if (d > Math.PI) d -= TAU;
    if (d < -Math.PI) d += TAU;
    return d;
  }

  function drawSpriteMaki(cx, cy, R, pieces, isTarget) {
    if (!imgs.maki) return false;
    const size = R * 2.2;
    if (isTarget || matchScore().pass || orderMatch()) {
      ctx.drawImage(imgs.maki, cx - size / 2, cy - size / 2, size, size);
      return true;
    }
    ctx.save();
    ctx.translate(cx, cy);
    const rad = size / 2;
    ctx.drawImage(imgs.maki, -size / 2, -size / 2, size, size);
    ctx.beginPath();
    ctx.arc(0, 0, rad * 0.62, 0, TAU);
    ctx.fillStyle = '#f4eee4';
    ctx.fill();
    const items = pieces.map((p) => ({ kind: p.kind, a: wrapAng(angleOf(p)) }));
    items.sort((x, y) => x.a - y.a);
    const n = items.length;
    const gap = 0.03;
    for (let i = 0; i < n; i++) {
      const prev = items[(i + n - 1) % n];
      const next = items[(i + 1) % n];
      const a0 = wrapAng(arcMid(prev.a, items[i].a) + gap);
      let span = wrapAng(arcMid(items[i].a, next.a) - gap) - a0;
      if (span < 0) span += TAU;
      const mid = a0 + span / 2;
      const w = imgs['wedge-' + items[i].kind];
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.arc(0, 0, rad * 0.60, a0, a0 + span);
      ctx.closePath();
      ctx.clip();
      if (w) {
        ctx.rotate(angDelta(WEDGE_ANG[items[i].kind] || 0, mid));
        ctx.drawImage(w, -size / 2, -size / 2, size, size);
      }
      ctx.restore();
    }
    ctx.restore();
    return true;
  }

  function drawMaki(cx, cy, R, pieces, ghosts) {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.beginPath();
    for (let i = 0; i < 8; i++) {
      const a = (i + 0.5) / 8 * TAU;
      const x = Math.cos(a) * (R + 5), y = Math.sin(a) * (R + 5);
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.closePath();
    ctx.fillStyle = '#1c2430'; ctx.fill();

    ctx.beginPath(); ctx.arc(0, 0, R, 0, TAU);
    ctx.fillStyle = '#1a241c'; ctx.fill();

    const riceN = 8;
    for (let i = 0; i < riceN; i++) {
      const a0 = i / riceN * TAU, a1 = (i + 1) / riceN * TAU;
      ctx.beginPath();
      ctx.moveTo(Math.cos(a0) * R * 0.22, Math.sin(a0) * R * 0.22);
      ctx.lineTo(Math.cos(a0) * R * 0.9, Math.sin(a0) * R * 0.9);
      ctx.lineTo(Math.cos(a1) * R * 0.9, Math.sin(a1) * R * 0.9);
      ctx.lineTo(Math.cos(a1) * R * 0.22, Math.sin(a1) * R * 0.22);
      ctx.closePath();
      ctx.fillStyle = i % 2 ? '#f6f0e4' : '#eadfcf';
      ctx.fill();
    }

    for (const p of pieces.slice().sort((a, b) => a.u - b.u)) {
      const spec = INK[p.kind];
      const pts = wedge(R, p.u, DU, R * 0.26, R * 0.84);
      ctx.beginPath();
      pts.forEach((q, i) => i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]));
      ctx.closePath();
      const g = ctx.createLinearGradient(pts[0][0], pts[0][1], pts[3][0], pts[3][1]);
      g.addColorStop(0, spec.fill[0]); g.addColorStop(0.55, spec.fill[2]); g.addColorStop(1, spec.fill[1]);
      ctx.fillStyle = g; ctx.fill();
      ctx.strokeStyle = 'rgba(28,36,48,0.35)'; ctx.lineWidth = 1; ctx.stroke();
    }

    if (ghosts) {
      ctx.setLineDash([4, 3]); ctx.lineWidth = 1.6; ctx.globalAlpha = 0.85;
      for (const t of ghosts) {
        const pts = wedge(R, t.u, DU, R * 0.26, R * 0.84);
        ctx.beginPath();
        pts.forEach((q, i) => i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]));
        ctx.closePath();
        ctx.strokeStyle = INK[t.kind].mark; ctx.stroke();
      }
      ctx.setLineDash([]); ctx.globalAlpha = 1;
    }

    ctx.beginPath(); ctx.arc(0, 0, R * 0.2, 0, TAU);
    ctx.fillStyle = '#f3eadc'; ctx.fill();
    ctx.beginPath(); ctx.arc(0, 0, R * 0.9, 0, TAU);
    ctx.strokeStyle = '#1a241c'; ctx.lineWidth = 3; ctx.stroke();
    ctx.restore();
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
    ctx.fillText('PUZZLE 01', L.ox + 42, L.headerH / 2 + 10);
    roundBtn('undo', L.ox + L.colW - 56, L.headerH / 2, '↺');
    roundBtn('guides', L.ox + L.colW - 22, L.headerH / 2, G.guides ? '▣' : '□');
  }

  function drawSteps(L) {
    const y = L.headerH;
    const steps = [
      { t: 'BASE', on: true }, { t: 'RICE', on: true },
      { t: 'ARRANGE', on: true, now: true }, { t: 'MATCH', on: G.pass }, { t: 'CUT', on: false },
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
    for (const c of L.cuts) {
      rr(c.card.x, c.card.y, c.card.w, c.card.h, 14);
      ctx.fillStyle = '#243038'; ctx.fill();
      if (!drawSpriteMaki(c.x, c.y, c.r, c.target ? TARGET : G.pieces, c.target)) {
        drawMaki(c.x, c.y, c.r, c.target ? TARGET : G.pieces, c.target ? null : TARGET);
      }
      ctx.fillStyle = '#f4ead8';
      ctx.font = ui(8, 700); ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
      ctx.fillText(c.lab, c.x, c.card.y + c.card.h - 8);
    }
    if (G.pass) {
      const c = L.cuts[1];
      ctx.fillStyle = '#9dba5a';
      ctx.font = ui(8, 700);
      ctx.fillText('MATCHED', c.x, c.card.y + 14);
    }
  }

  function drawSheet(L) {
    const s = L.sheet, rice = L.rice;
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
    ctx.restore();

    if (G.guides) {
      const worst = deltas().filter((d) => d.mm >= 6).sort((a, b) => b.mm - a.mm)[0];
      if (worst) {
        const t = TARGET.find((x) => x.kind === worst.kind);
        const y = uToY(t.u, rice);
        ctx.save();
        ctx.setLineDash([5, 4]);
        ctx.strokeStyle = INK[t.kind].mark;
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
      const spec = INK[p.kind];
      const hold = G.drag && G.drag.id === p.id;
      const dx = r.x, dy = r.y + r.h * 0.06, dw = r.w, dh = r.h * 0.88;
      ctx.save();
      rr(dx, dy, dw, dh, dh * 0.48);
      ctx.clip();
      if (p.kind === 'tuna' || !imgs[p.kind]) {
        const g = ctx.createLinearGradient(dx, dy, dx + dw, dy + dh);
        g.addColorStop(0, spec.fill[1]);
        g.addColorStop(0.5, spec.fill[0]);
        g.addColorStop(1, spec.fill[2]);
        ctx.fillStyle = g;
        ctx.fillRect(dx, dy, dw, dh);
        ctx.strokeStyle = 'rgba(255,230,230,0.22)';
        ctx.lineWidth = Math.max(3, dh * 0.14);
        for (let i = -2; i < 12; i++) {
          ctx.beginPath();
          ctx.moveTo(dx + i * dw * 0.12, dy);
          ctx.lineTo(dx + i * dw * 0.12 + dh * 0.9, dy + dh);
          ctx.stroke();
        }
      } else {
        ctx.fillStyle = spec.fill[0];
        ctx.fillRect(dx, dy, dw, dh);
        ctx.drawImage(imgs[p.kind], dx, dy, dw, dh);
      }
      ctx.restore();
      if (hold) {
        ctx.strokeStyle = '#1c2430';
        ctx.lineWidth = 2;
        rr(dx - 2, dy - 2, dw + 4, dh + 4, dh * 0.48);
        ctx.stroke();
      }
      G.hits.push({ id: 'piece:' + p.id, x: r.x, y: r.y, w: r.w, h: r.h });
    }

    if (G.guides) {
      const ds = deltas().filter((d) => d.mm >= 4).sort((a, b) => b.mm - a.mm);
      if (ds[0]) {
        const t = TARGET.find((x) => x.kind === ds[0].kind);
        const p = G.pieces.find((x) => x.kind === ds[0].kind);
        const a = stripRect(p, rice), b = stripRect(t, rice);
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

    ctx.fillStyle = '#d8d0c0';
    ctx.font = ui(8, 600); ctx.textAlign = 'center';
    ctx.fillText('↑  FROM THIS EDGE  ·  becomes the core', s.x + s.w / 2, s.y + s.h - 12);
  }

  function drawDock(L) {
    const y = L.dockY, x = L.ox + L.pad, w = L.colW - L.pad * 2;
    const by = y + 22, bh = 44;
    const gap = 8;
    const resetW = 72, rollW = 88;
    const checkW = w - resetW - rollW - gap * 2;

    rr(x, by, resetW, bh, 12);
    ctx.fillStyle = '#fff'; ctx.fill();
    ctx.strokeStyle = 'rgba(28,36,48,0.18)'; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = '#1c2430'; ctx.font = ui(11, 700); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('RESET', x + resetW / 2, by + bh / 2);
    G.hits.push({ id: 'reset', x, y: by, w: resetW, h: bh });

    const cx = x + resetW + gap;
    rr(cx, by, checkW, bh, 12);
    ctx.fillStyle = G.pass ? '#2a6b62' : '#d45a3c'; ctx.fill();
    ctx.fillStyle = '#f4ead8'; ctx.font = ui(13, 700);
    ctx.fillText(G.pass ? 'MATCHED  ' + G.score + '%' : (G.checked ? 'AGAIN  ·  ' + G.score + '%' : 'CHECK CUT'), cx + checkW / 2, by + bh / 2);
    G.hits.push({ id: 'check', x: cx, y: by, w: checkW, h: bh });

    const rx = x + w - rollW;
    rr(rx, by, rollW, bh, 12);
    ctx.fillStyle = G.pass ? '#1c2430' : '#d9d0c2'; ctx.fill();
    ctx.fillStyle = G.pass ? '#f4ead8' : '#8a7f70'; ctx.font = ui(10, 700);
    ctx.fillText(G.pass ? 'ROLL' : 'LOCKED', rx + rollW / 2, by + bh / 2);
    G.hits.push({ id: 'roll', x: rx, y: by, w: rollW, h: bh });
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
  function reset() {
    G.pieces = START.map((p) => ({ ...p }));
    G.pass = false; G.checked = false; G.score = 0; G.drag = null;
    frame();
  }
  function check() {
    const m = matchScore();
    G.checked = true; G.pass = m.pass; G.score = m.score;
    frame();
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
      return;
    }
    if (h.id === 'reset' || h.id === 'undo') reset();
    if (h.id === 'check') check();
    if (h.id === 'guides') { G.guides = !G.guides; frame(); }
  }
  function onMove(x, y) {
    if (!G.drag) return;
    const p = G.pieces.find((q) => q.id === G.drag.id);
    p.u = yToU(y - G.drag.off, G.layout.rice);
    G.pass = false;
    frame();
  }
  function onUp() { G.drag = null; frame(); }
  function pt(e) {
    const r = canvas.getBoundingClientRect();
    const t = e.touches ? e.touches[0] || e.changedTouches[0] : e;
    return { x: t.clientX - r.left, y: t.clientY - r.top };
  }

  canvas.addEventListener('pointerdown', (e) => { canvas.setPointerCapture(e.pointerId); const p = pt(e); onDown(p.x, p.y); });
  canvas.addEventListener('pointermove', (e) => { const p = pt(e); onMove(p.x, p.y); });
  canvas.addEventListener('pointerup', onUp);
  canvas.addEventListener('pointercancel', onUp);
  window.addEventListener('resize', frame);
  reset();
  window.__board = G;
})();
