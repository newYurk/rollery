# Rollery — sheet → spiral → cut

A one-file prototype of a roll-making game: lay fillings on a flat sheet, roll it up, cut it —
and the cross-section you see is a deterministic unrolling of what you actually placed.
No soft-body physics: the sheet is a `(u, v, z)` canvas of patches, the roll is an Archimedean
spiral, and the cut face is rendered pixel by pixel by mapping `(r, φ)` back onto the sheet.

**Play it:** https://newyurk.github.io/rollery/ — best on a phone in portrait; works on desktop too.

## What's in the stand

- Sheet view: tap to place the selected filling, drag to move, drag off the sheet to remove,
  tap a filling to select it. **Wrap in nori** adds four real nori patches around a filling
  (under, over, two end caps) — a closed outline on the cut, the kazarimaki trick done with flat layers only.
- Pull the mat upward to roll. Tap the roll where you want to cut.
- Cut ritual: knife → press → cut → the face opens like a door. Then slice into six and see every piece —
  a filling that covers only part of the sheet shows up only in its pieces.
- Two bases: sushi roll (nori + rice) and sweet roll cake (sponge + cream). Same model, different palette.
- Live cross-section preview (👁) is an author's tool; keep it off during playtests.

## Files

- `index.html` — the whole stand (Canvas 2D, Web Audio, no build step, no dependencies).
- `HYPOTHESIS.md` — hypothesis, measurements and pass/fail criteria, written before the code (Russian).
- `docs/design-core.md` — digest of the design thread the stand is built from (Russian).
- `docs/mechanics.md` — candidate core mechanics and a recommendation (Russian).
- `STATE.md` — project entry point: where we are and what's next (Russian).

This is a measurement rig, not a game and not a stack decision.
