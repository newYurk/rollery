# Rollery — sheet → spiral → cut

A prototype of a roll-making game: lay fillings on a flat sheet, roll it up,
cut it — and the cross-section you see is a deterministic unrolling of what you
actually placed.

**Play it:** https://newyurk.github.io/rollery/play/ — phone (portrait), tablet or desktop.
**Puzzle mode:** https://newyurk.github.io/rollery/play/?puzzle — reproduce the shown cross-section.
**Everything else:** https://newyurk.github.io/rollery/ — the front page with three doors (game, local lab, docs).

## Model, in one paragraph

No soft-body physics. The sheet is a `(u, v, z)` canvas of patches; rolling is
a variable-thickness winding where thick fillings displace rice and the near
edge is tucked into a solid core, like a real maki. It is a phenomenological
model — every parameter answers for one observable effect — verified against
real-roll numbers with sources. The details live where they are maintained:
the design digest in `docs/design-core.md`, the numeric audit in
`docs/geometry-audit.md`, the real-world comparison in `docs/reality-check.md`,
and the canonical reference numbers in the executable check
(`play/index.html?check`, constants in `play/checks.js`).

## Where things are

- `play/` — the stand itself (Canvas 2D, classic scripts, no build step):
  - `model/` — the core, free of any browser API: `util.js`, `catalog.js`
    (bases, wrappers, ingredients), `geometry.js` (spread profile, stacking,
    height map, winding, tuck core, material sampling).
  - `render/` — `slice.js` (cut face), `sheet.js` (top view), `screens.js`.
  - `ui/` — `layout.js` (canvas, breakpoints), `controls.js`, `album.js`.
  - `modes/puzzle.js` — the only game mode; `state.js`, `audio.js`,
    `checks.js` (regression, run via `?check`), `index.html` (153-line shell).
  - Load order is mandatory and documented in each file's header.
- `sim/` — the offline MLS-MPM reference used to calibrate the stand
  (run it via `sim/lab/lab.sh`); run outputs stay local and out of git.
- `docs/` — knowledge base; start at `docs/index.html` (published) or `STATE.md`
  (working entry point, Russian). The target architecture is
  `docs/domain-contract.md`; finished work is archived in `docs/archive/`.
- Work is tracked in GitHub issues; ideas live in `docs/ideas.md`.

This is a measurement rig, not a game and not a stack decision.
