# Rollery — sheet → spiral → cut

A one-file prototype of a roll-making game: lay fillings on a flat sheet, roll it up, cut it —
and the cross-section you see is a deterministic unrolling of what you actually placed.

**Play it:** https://newyurk.github.io/rollery/ — phone (portrait), tablet or desktop.
**Puzzle mode:** https://newyurk.github.io/rollery/?puzzle — reproduce the shown cross-section.

## Model

No soft-body physics. The sheet is a `(u, v, z)` canvas of patches (`u` along the rolling direction,
`v` along the roll, `z` through the spread). Rolling is a **variable-thickness winding**: the sheet is
sliced into 1440 angular bins and wound turn by turn; where a filling is thicker than the spread it
displaces it (rice compressibility κ), the excess is squeezed by the mat (β), the thickness profile is
smoothed, the last 8 % of the sheet is bare wrapper for the seam. The cut face is rendered pixel by pixel by
mapping `(r, φ)` back onto the sheet; the cross-section can be pressed round, square or triangular.
Ingredient sizes are in real units (rice layer ≈ 5 mm). See `docs/design-core.md` and `docs/geometry-audit.md`.

## What's in the stand

- Sheet view: tap to place, drag to move, drag off the sheet to remove, tap to select.
  **Wrap in nori** adds four real nori patches around a filling (under, over, two end caps) — a closed
  outline on the cut. Coloured rice acts as pattern paint (the kazarimaki technique).
- Pull the mat upward to roll. Tap the roll where you want to cut.
- Cut ritual: knife → press → cut → the face opens like a door. Then slice into six and see every piece.
- Two bases: sushi roll (nori + rice) and sweet roll cake (sponge + cream). Shapes: ⭕ ◻ △.
- **Puzzle**: 15 levels — reproduce a target cross-section (or a row of pieces). Difficulty knobs: number of
  fillings, turns (sheet length), pieces shown, nori wrapping, short fillings, coloured rice, shape.
  Similarity is computed on material maps of the cut with a one-pixel tolerance; misses get a hint.
  🔗 copies a link to the puzzle (the layout travels in the URL hash; a friend sees only the cut) —
  from the plain stand it shares *your* layout as a puzzle.
- Live cross-section preview (👁) is an author's tool; keep it off during playtests.

## Files

- `index.html` — the whole stand (Canvas 2D, Web Audio, no build step, no dependencies).
- `HYPOTHESIS.md` — hypothesis, measurements and pass/fail criteria, written before the code (Russian).
- `docs/design-core.md` — digest of the design thread + the winding model (Russian).
- `docs/geometry-audit.md` — independent numeric audit of the spiral/winding math (Russian).
- `docs/mechanics.md`, `docs/core-v0.md` — core-mechanic candidates and the puzzle-reproduce spec (Russian).
- `docs/ideas.md` — idea bank (coloured rice as paint, mini-rolls as elements).
- `docs/ui-review.md` — UI/UX and responsive-layout review across viewports (Russian).
- `STATE.md` — project entry point: where we are and what's next (Russian).

This is a measurement rig, not a game and not a stack decision.
