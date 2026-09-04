# Core V2 — F01–F07 millimetre kernel

Branch: `core-v2/f01-f02`. Independent millimetre kernel in `play/core-v2/`. No legacy imports, no UI.

## Model

Ring winding: rice is one closed ring around a box core, nori sits on that ring plus a bare-strip overlap tail. `fromUZero`. Neutral hand only.

One filling sits at the core origin (F01–F04). Several fillings: `centerX = uMm − windowCenter` — a pure function of that patch’s own `uMm`, no shelf packing, no array-order effect (erratum-007). Hard fillings keep catalog area and slip; nori carries the arc (erratum-022).

## Fixtures

| id | status |
|---|---|
| F01 empty hosomaki | `valid` |
| F02 cucumber at 36.25 mm | `valid` |
| F03 43.5–45.5 | `valid`; 46.5+ `outsideModelScope` |
| F04a u=100 | `invalid: patch_out_of_sheet` |
| F04b u=70 | `outsideModelScope: closure_window` |
| F05 futomaki [A,B,C] vs [C,A,B] | same hashes |
| F06 | JSON round-trip + new instance |
| F07 probe 56…64 mm through cucumber | coordinate, not ordinal; same-material overlap invalid |

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

Not wired to `play/index.html`. F08, UI, recorded hand, production `geometry.js` — out of scope.
