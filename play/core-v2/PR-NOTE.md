# Core V2 — F01–F07 millimetre kernel

Branch: `core-v2/f01-f02` → [PR #172](https://github.com/newYurk/rollery/pull/172).
Independent millimetre kernel in `play/core-v2/`. No legacy imports.

## Model

Ring winding: rice is a closed ring around a still core, nori outside plus overlap tail. `fromUZero`. Neutral hand. `winding: 'ring'` is a recipe field; `spiral` / `inverted` throw `unsupported`.

One filling sits at the origin. Several fillings pack **rigid, side by side** (lower `u` left, 1 mm gap, wrap to a second row if needed). They do not ghost through each other. Sheet footprints of different materials may still overlap (F07 recipe); the **slice** packs. Same-material sheet overlap stays `invalid: patch_material_overlap`.

This is a kitchen override of erratum-007’s “position = f(own u) only, no auto-pack”. F07 still checks: array order does not matter; lower `u` sits left; probe swaps side at `u = 60`; same-material overlap is invalid.

## Play

`play/core-v2/index.html` (also `?v2` on live play). Chips: empty, kappa, 細切り, layout, futomaki. Drag a filling on the sheet to set `u` (clamped to the window). Knife drag is the roll above the sheet. Probe and refuse chips are tests-only.

## Fixtures

| id | status |
|---|---|
| F01 empty hosomaki | `valid` |
| F02 cucumber at 36.25 mm | `valid` |
| F03 lastValid ± 2 мм | `valid` until footprint edge; then `outsideModelScope` |
| F04a u=100 | `invalid: patch_out_of_sheet` |
| F04b u=70 | `outsideModelScope: closure_window` |
| F05 futomaki [A,B,C] vs [C,A,B] | same hashes; no AABB overlap |
| F06 | JSON round-trip + new instance |
| F07 probe 56…64 mm | packs beside cucumber; swaps side at 60; same-material overlap invalid |

## Named EPS

| Constant | Value |
|---|---|
| `EPS_LENGTH_MM` | 0.15 |
| `EPS_CORE_ASYMMETRY_MM` | 0.50 |
| `EPS_AREA_RATIO` | 1.05 |
| `PLACEMENT_EDGE_MARGIN_MM` | 20 (absolute, marron) |
| `MAX_CENTER_DELTA_MM` | 0.15 |
| `MAX_AREA_RATIO_DELTA` | 0.02 |

## How to run

```sh
git fetch origin && git checkout core-v2/f01-f02
node play/core-v2/run-fixtures.mjs
node --test play/core-v2/core-v2.test.mjs
```

## Open, not this PR

- `EPS_AREA_RATIO` / stretch-vs-slip (#134)
- #109 catalog revalidation
- F08, recorded hand, production `geometry.js`
- uramaki / uzumaki (`winding` enum reserved)
