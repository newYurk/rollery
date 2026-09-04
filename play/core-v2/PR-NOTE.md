# Core V2 — F01–F04 millimetre kernel

Branch: `core-v2/f01-f02`. Independent millimetre kernel in `play/core-v2/`. No legacy imports, no UI.

## Model

Ring winding (hosomaki): rice is one closed ring around a box core, nori sits on that ring plus a bare-strip overlap tail. `fromUZero`. Neutral hand only.

Empty core (F01): `Wc × Hc = 5 × 7.2 mm`. `r0(φ) = min((Wc/2)/|cos φ|, (Hc/2)/|sin φ|)`.

F02 cucumber sits in the core (`uMm = 36.25`). Section area is the rest-state sector ≈ 76.97 mm². Hard fillings keep catalog cross-section and slip; nori carries the arc (erratum-022, Tokiwa ずれる).

F03: five uMm through the footprint boundary of `placementWindowMm`. Valid through 45.5 inclusive; 46.5+ is `outsideModelScope: closure_window`. Inside the window the slice does not move with u (#139).

F04a `uMm=100` → `invalid: patch_out_of_sheet`. F04b `uMm=70` → `outsideModelScope: closure_window`. No silent recentre.

## Discretization

`NB = 1440` rays. Independent arc oracle uses `4 × NB`.

## Named EPS

| Constant | Value | Why |
|---|---|---|
| `EPS_LENGTH_MM` | 0.15 | ~2× bin step of the nori arc; ×5 unit error is ~18 mm |
| `EPS_INVERT_MM` | = `EPS_LENGTH_MM` | erratum-010 default |
| `EPS_CORE_ASYMMETRY_MM` | 0.50 | in (0.377; 1.88): catches scalar r0 and forgotten ×U_MM |
| `EPS_RAY_FRACTION` | 4/1440 ≈ 0.0028 | overlap fraction is ~0.19 |
| `EPS_AREA_RATIO` | 1.05 | rest-state grid noise; fillings do not stretch with the sheet |
| `PLACEMENT_EDGE_MARGIN_MM` | 20 | absolute 2 cm (marron), does **not** scale with sheet length |
| `MAX_CENTER_DELTA_MM` | 0.15 | F03 neighbours inside the window |
| `MAX_AREA_RATIO_DELTA` | 0.02 | F03 neighbour area ratio − 1 |

## How to run

```sh
git fetch origin && git checkout core-v2/f01-f02
node play/core-v2/run-fixtures.mjs
node --test play/core-v2/core-v2.test.mjs
```

JSON reports: `play/core-v2/reports/F01.json` … `F04b.json`.

This kernel is **not** wired to `play/index.html`. The live game is still legacy.

## Known limits

- `baseId: 'hosomaki'` vs catalog key `hoso` — snapshot, not a live catalog adapter.
- F02 `vMm` / `placement` taken from F07’s “as in F02” (`embedded`, mid-width).
- F05–F08, UI adapter, recorded hand, production `geometry.js` — out of scope.
- #109 (catalog label honesty) is internal, not a chef-source question.
