# Core V2 PR1 — F01/F02 kernel

Branch: `core-v2/f01-f02`. Independent millimetre kernel in `play/core-v2/`. No legacy imports, no UI.

## Model

Ring winding (hosomaki): rice is one closed ring around a box core, nori sits on that ring plus a bare-strip overlap tail. `fromUZero`. Neutral hand only.

Empty core (F01): `Wc × Hc = 5 × 7.2 mm`. `r0(φ) = min((Wc/2)/|cos φ|, (Hc/2)/|sin φ|)`.

F02 cucumber sits in the core (uMm = 36.25 is inside tuck reach). Section area is the rest-state sector `wU × hU × cutFill × U_MM² ≈ 76.97 mm²`. This does not take a side on #134 — a core filling is not on the winding wall.

## Discretization

`NB = 1440` rays. Independent arc oracle uses `4 × NB`.

## Named EPS (preliminary)

| Constant | Value | Why |
|---|---|---|
| `EPS_LENGTH_MM` | 0.15 | ~2× bin step of the nori arc; ×5 unit error is ~18 mm |
| `EPS_INVERT_MM` | = `EPS_LENGTH_MM` | erratum-010 default |
| `EPS_CORE_ASYMMETRY_MM` | 0.50 | in (0.377; 1.88): catches scalar r0 and forgotten ×U_MM |
| `EPS_RAY_FRACTION` | 4/1440 ≈ 0.0028 | overlap fraction is ~0.19 |
| `EPS_AREA_RATIO` | 1.05 | ≪ 1.18; rest-state noise, not #134 |
| `PLACEMENT_EDGE_MARGIN_MM` | 20 | A5 candidate, owner-open for scaling on larger bases |

## How to run

```sh
git fetch origin && git checkout core-v2/f01-f02
node play/core-v2/run-fixtures.mjs
node --test play/core-v2/core-v2.test.mjs
```

JSON reports: `play/core-v2/reports/F01.json`, `F02.json`.

This kernel is **not** wired to `play/index.html`. The live game is still legacy. PR1 definition of done is green F01/F02, not a playable slice.

## Known limits

- `baseId: 'hosomaki'` vs catalog key `hoso` — snapshot, not a live catalog adapter.
- F02 `vMm` / `placement` taken from F07’s “as in F02” (`embedded`, mid-width).
- `EPS_AREA_RATIO` and `PLACEMENT_EDGE_MARGIN_MM` still owner-open.
- F03–F08, UI adapter, recorded hand — out of scope.
