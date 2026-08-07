# Vendored: india-boundary-corrector

Not an npm dependency — these files are vendored directly (not installed via
`npm install`) so production builds need no package-registry access and no
new-package approval, since they're not npm dependencies at all.

## Files

- `india-boundary-corrector.js` — the self-contained "global" build of
  [`@india-boundary-corrector/leaflet-layer`](https://github.com/ramSeraph/india_boundary_corrector)
  v0.2.2 (`dist/index.global.js` from the published npm package, byte-for-byte,
  unmodified). No external imports — it bundles its own dependencies
  (`@india-boundary-corrector/data`, `layer-configs`, `tilefixer`) at publish
  time. Loaded exactly like Leaflet itself is (`loadScript` in
  `DynamicRiskMap.jsx`), and exposes `window.IndiaBoundaryCorrector`.

- `india_boundary_corrections.pmtiles` — the boundary-correction data file
  (1.66 MB), also from the same npm package (`dist/india_boundary_corrections.pmtiles`).
  The plain (non-`.gz`) filename is intentional: the package's own source
  notes the `.gz` variant exists only to work around specific *public CDN*
  compression quirks (unpkg/esm.sh) — self-hosting from our own origin
  doesn't hit that issue, so the plain file is correct here.

  `DynamicRiskMap.jsx` passes `pmtilesUrl: '/vendor/india_boundary_corrections.pmtiles'`
  explicitly to `L.tileLayer.indiaBoundaryCorrected(...)` — without that
  option the library defaults to fetching this file from jsDelivr's CDN at
  runtime, which would defeat the point of vendoring it.

## What this does

Replaces the plain Leaflet `L.tileLayer` used for the base map with
`L.tileLayer.indiaBoundaryCorrected`, which masks the tile provider's
(CARTO/OSM) internationally-neutral Kashmir boundary and redraws India's
officially claimed boundary (J&K/Ladakh, including PoK, as Indian territory)
directly on the tiles — required for a government portal. See the
conversation/commit history for `DynamicRiskMap.jsx` for the full context.

Community-maintained correction (OSM boundary relations + Natural Earth data,
built to match India's official position) — not literally Survey of
India-certified geodata. Worth knowing if this ever needs to survive a formal
compliance review; Bhuvan (ISRO/NRSC) is the formal government channel if a
certified source is required instead.

## Updating

1. `npm pack @india-boundary-corrector/leaflet-layer` on a machine with
   registry access, to get the current version's tarball.
2. Extract it; copy `dist/index.global.js` → `india-boundary-corrector.js`
   and `dist/india_boundary_corrections.pmtiles` → `india_boundary_corrections.pmtiles`
   here, replacing these files.
3. Update the version number in this README.
4. `layerConfig: 'cartodb-light-retina'` in `DynamicRiskMap.jsx` is pinned to
   match our exact tile URL (`rastertiles/voyager/.../{r}.png`) — verify
   that config ID still exists in the new version's
   `@india-boundary-corrector/layer-configs` before deploying (check
   `src/configs.json` in that package).

Current version vendored: **0.2.2** (published ~3 months prior to this being
added).
