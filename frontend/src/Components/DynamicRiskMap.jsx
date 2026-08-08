// src/Components/DynamicRiskMap.jsx

import { useState, useEffect, useRef, useMemo } from "react";
import { useNavigate } from 'react-router-dom';
import { API_BASE_URL, getAuthHeaders } from '../config/apiConfig';
import { REGIONAL_OFFICES } from '../constants';
import NameCodeTypeahead from './ui/NameCodeTypeahead';
import PageNavigation from './PageNavigation';
import PageWrapper from './ui/PageWrapper';

const RISK_COLORS = {
  h: { fill: "#E24B4A", border: "#A32D2D", label: "High Risk" },
  m: { fill: "#EF9F27", border: "#854F0B", label: "Medium Risk" },
  l: { fill: "#1D9E75", border: "#0F6E56", label: "Low Risk" },
};

// Hardcoded centroids merged with live API state counts at runtime
const STATE_CENTROIDS = {
  "Andhra Pradesh":    [15.9, 79.7],
  "Arunachal Pradesh": [27.1, 93.6],
  "Assam":             [26.2, 92.9],
  "Bihar":             [25.1, 85.3],
  "Chhattisgarh":      [21.3, 81.9],
  "Goa":               [15.3, 74.0],
  "Gujarat":           [22.3, 71.2],
  "Haryana":           [29.1, 76.1],
  "Himachal Pradesh":  [31.1, 77.2],
  "Jharkhand":         [23.6, 85.3],
  "Karnataka":         [15.3, 75.7],
  "Kerala":            [10.9, 76.3],
  "Madhya Pradesh":    [23.5, 77.5],
  "Maharashtra":       [19.7, 75.7],
  "Manipur":           [24.7, 93.9],
  "Meghalaya":         [25.5, 91.4],
  "Mizoram":           [23.2, 92.8],
  "Nagaland":          [26.2, 94.6],
  "Odisha":            [20.9, 84.2],
  "Punjab":            [31.1, 75.3],
  "Rajasthan":         [27.0, 74.2],
  "Sikkim":            [27.5, 88.5],
  "Tamil Nadu":        [11.1, 78.7],
  "Telangana":         [17.4, 79.1],
  "Tripura":           [23.9, 91.9],
  "Uttar Pradesh":     [27.1, 80.9],
  "Uttarakhand":       [30.3, 79.0],
  "West Bengal":       [23.0, 87.9],
  "Delhi":             [28.6, 77.2],
  "Jammu & Kashmir":   [33.7, 76.9],
  "Ladakh":            [34.2, 77.6],
};

function loadCss(href) {
  if (document.querySelector(`link[href="${href}"]`)) return;
  const l = document.createElement("link");
  l.rel = "stylesheet";
  l.href = href;
  document.head.appendChild(l);
}
function loadScript(src, globalName = "L") {
  return new Promise((res, rej) => {
    if (window[globalName]) return res();
    if (document.querySelector(`script[src="${src}"]`)) {
      const check = setInterval(() => {
        if (window[globalName]) { clearInterval(check); res(); }
      }, 50);
      return;
    }
    const s = document.createElement("script");
    s.src = src;
    s.onload = res;
    s.onerror = rej;
    document.head.appendChild(s);
  });
}

const ZOOM_OPERATORS = 8;
const ZOOM_DISTRICTS = 6;

// How many operator pins to ask the backend for at a given zoom level.
// Zoomed-out views cover a wider bounding box (more potential matches, but
// each pin is tiny/unlabeled), so cap those requests tighter; zoomed-in
// views have a naturally small viewport, so allow more.
function operatorLimitForZoom(zoom) {
  if (zoom >= 12) return 3000;
  if (zoom >= 10) return 2000;
  if (zoom >= ZOOM_OPERATORS) return 1500;
  return 800;
}

const DEFAULT_MAP_FILTERS = { ro: '', riskBucket: '', regCode: '', eaCode: '' };

export default function DynamicRiskMap() {
  const navigate = useNavigate();
  const mapContainerRef = useRef(null);
  const leafletMapRef = useRef(null);
  const markersLayerRef = useRef(null);
  const leafletRef = useRef(null);
  const renderTimerRef = useRef(null);

  const [stateData, setStateData] = useState([]);
  const [stateLoading, setStateLoading] = useState(true);
  const [stateError, setStateError] = useState(null);

  const [operators, setOperators] = useState([]);
  const [operatorsError, setOperatorsError] = useState(null);

  const [selectedState, setSelectedState] = useState(null);
  const [zoomLevel, setZoomLevel] = useState(5);
  const [mapReady, setMapReady] = useState(false);
  const [loadError, setLoadError] = useState(null);

  // Filters: `filters` is what's actually applied (drives fetches); `draft`
  // is what the controls show while the user is still picking values —
  // mirrors OperatorsTab.jsx's draft/apply pattern.
  const [filters, setFilters] = useState(DEFAULT_MAP_FILTERS);
  const [draft, setDraft] = useState(DEFAULT_MAP_FILTERS);
  const [filterOptions, setFilterOptions] = useState({ regional_offices: REGIONAL_OFFICES, registrars: [], eas: [], risk_buckets: [] });
  const filtersRef = useRef(filters);
  useEffect(() => { filtersRef.current = filters; }, [filters]);

  const [searchId, setSearchId] = useState('');
  const [locating, setLocating] = useState(false);
  const [locateError, setLocateError] = useState(null);

  // Filter dropdown data (registrar/EA typeahead, risk buckets) — cascades
  // on draft.ro/draft.regCode the same way OperatorsTab's does.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch(`${API_BASE_URL}/api/operator_filters`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({ ro: draft.ro, reg_code: draft.regCode }),
        });
        if (!resp.ok || cancelled) return;
        const data = await resp.json();
        if (cancelled) return;
        setFilterOptions(prev => ({
          regional_offices: data.regional_offices || prev.regional_offices || REGIONAL_OFFICES,
          registrars: data.registrars || [],
          eas: data.eas || [],
          risk_buckets: data.risk_buckets || [],
        }));
      } catch (err) {
        // keep previous options on failure
      }
    })();
    return () => { cancelled = true; };
  }, [draft.ro, draft.regCode]);

  // Fetch live state-wise counts and merge with hardcoded centroids. Reruns
  // whenever the applied filters change, so bubbles/totals stay consistent
  // with whatever's showing in the pin layer.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setStateLoading(true);
      setStateError(null);
      try {
        const params = new URLSearchParams();
        if (filters.ro) params.set('ro', filters.ro);
        if (filters.riskBucket) params.set('risk_bucket', filters.riskBucket);
        if (filters.regCode) params.set('reg_code', filters.regCode);
        if (filters.eaCode) params.set('ea_code', filters.eaCode);
        const qs = params.toString();
        const resp = await fetch(`${API_BASE_URL}/api/state_wise_count${qs ? `?${qs}` : ''}`, {
          method: 'GET',
          headers: getAuthHeaders(),
        });
        if (!resp.ok) throw new Error(`API error ${resp.status}`);
        const raw = await resp.json();
        // Backend returns { data: [{state, h, m, l, total}, ...] }; also accept
        // a bare array for robustness.
        const rows = Array.isArray(raw?.data) ? raw.data : (Array.isArray(raw) ? raw : []);
        const merged = rows
          .filter((s) => STATE_CENTROIDS[s.state ?? s.name])
          .map((s) => {
            const name = s.state ?? s.name;
            return {
              name,
              centroid: STATE_CENTROIDS[name],
              high:   s.h   ?? s.high   ?? 0,
              medium: s.m   ?? s.medium ?? 0,
              low:    s.l   ?? s.low    ?? 0,
              total:  s.total ?? 0,
            };
          });
        if (!cancelled) setStateData(merged);
      } catch (err) {
        if (!cancelled) setStateError('Failed to load state data from API.');
      } finally {
        if (!cancelled) setStateLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [filters]);

  // Fetch operator pins ([lat, lng, riskCode, id]) for the map's current
  // viewport only — called from the zoomend/moveend handler below rather
  // than on mount, so nothing is fetched until the user actually zooms past
  // the state-bubble view.
  //
  // Client-side cache: each fetched viewport is kept in operatorsCacheRef,
  // tagged `complete` when the backend returned strictly fewer rows than the
  // requested limit (i.e. we know we got every matching point, not a
  // truncated slice — a truncated response can't be trusted for a
  // sub-region either, since we don't know which points got cut). A small
  // pan or zoom-out that lands fully inside a still-fresh `complete` cache
  // entry is served from that entry instead of hitting the network again.
  const operatorsRequestIdRef = useRef(0);
  const operatorsCacheRef = useRef([]); // [{ bounds, complete, operators, fetchedAt }, ...], newest first
  const OPERATOR_CACHE_MAX_ENTRIES = 30;
  const OPERATOR_CACHE_TTL_MS = 3 * 60 * 1000; // underlying risk data can change; don't cache forever

  const fetchOperatorsForViewport = async (map, zoom) => {
    const bounds = map.getBounds().pad(0.25);
    const requestId = ++operatorsRequestIdRef.current;

    const cached = operatorsCacheRef.current.find(
      (entry) => entry.complete
        && (Date.now() - entry.fetchedAt) < OPERATOR_CACHE_TTL_MS
        && entry.bounds.contains(bounds)
    );
    if (cached) {
      const inView = cached.operators.filter(([lat, lng]) => bounds.contains([lat, lng]));
      setOperators(inView);
      setOperatorsError(null);
      return;
    }

    const sw = bounds.getSouthWest();
    const ne = bounds.getNorthEast();
    const limit = operatorLimitForZoom(zoom);
    const activeFilters = filtersRef.current;
    try {
      const params = new URLSearchParams({
        min_lat: sw.lat,
        max_lat: ne.lat,
        min_lng: sw.lng,
        max_lng: ne.lng,
        limit,
      });
      if (activeFilters.ro) params.set('ro', activeFilters.ro);
      if (activeFilters.riskBucket) params.set('risk_bucket', activeFilters.riskBucket);
      if (activeFilters.regCode) params.set('reg_code', activeFilters.regCode);
      if (activeFilters.eaCode) params.set('ea_code', activeFilters.eaCode);
      const resp = await fetch(`${API_BASE_URL}/api/operators?${params}`, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      if (!resp.ok) throw new Error(`API error ${resp.status}`);
      const raw = await resp.json();
      const list = Array.isArray(raw?.operators) ? raw.operators : [];

      // Only commit to display/cache if nothing newer has superseded this
      // request (a later pan/zoom/filter-change) — otherwise a slow response
      // could momentarily flash stale data or poison the cache with it.
      if (requestId === operatorsRequestIdRef.current) {
        operatorsCacheRef.current.unshift({
          bounds,
          complete: list.length < limit,
          operators: list,
          fetchedAt: Date.now(),
        });
        if (operatorsCacheRef.current.length > OPERATOR_CACHE_MAX_ENTRIES) {
          operatorsCacheRef.current.length = OPERATOR_CACHE_MAX_ENTRIES;
        }
        setOperators(list);
        setOperatorsError(null);
      }
    } catch (err) {
      if (requestId === operatorsRequestIdRef.current) {
        setOperatorsError('Failed to load operator pins from API.');
      }
    }
  };

  // Cache entries don't carry which filters produced them, so wipe on every
  // filter change — from then on the cache only ever holds data fetched
  // under the current filters. Bumping the request id first invalidates any
  // still-in-flight fetch from the old filters, so it can't write into the
  // cache after the wipe. If already zoomed into pin view, re-fetch the
  // current viewport immediately so pins update without waiting for the
  // next pan/zoom.
  useEffect(() => {
    operatorsRequestIdRef.current++;
    operatorsCacheRef.current = [];
    const map = leafletMapRef.current;
    if (!map) return;
    const zoom = Math.round(map.getZoom());
    if (zoom >= ZOOM_DISTRICTS) {
      fetchOperatorsForViewport(map, zoom);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const totals = useMemo(() => ({
    high:   stateData.reduce((a, s) => a + s.high,   0),
    medium: stateData.reduce((a, s) => a + s.medium, 0),
    low:    stateData.reduce((a, s) => a + s.low,    0),
    total:  stateData.reduce((a, s) => a + s.total,  0),
  }), [stateData]);

  useEffect(() => {
    if (leafletMapRef.current) return;
    let cancelled = false;

    (async () => {
      try {
        loadCss("https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.min.css");
        await loadScript("https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet-src.min.js");
        // Vendored locally under public/vendor/ (not an npm dependency) so
        // prod builds need no registry access / new-package approval — see
        // public/vendor/README.md. Self-contained global build, no imports.
        await loadScript("/vendor/india-boundary-corrector.js", "IndiaBoundaryCorrector");
        if (cancelled || !mapContainerRef.current) return;

        const L = window.L;
        leafletRef.current = L;
        window.IndiaBoundaryCorrector.extendLeaflet(L);

        const map = L.map(mapContainerRef.current, { center: [22, 80], zoom: 5 });

        // indiaBoundaryCorrected masks the tile provider's internationally-
        // neutral Kashmir line and redraws India's official claimed boundary
        // (J&K/Ladakh, including PoK, as Indian territory) directly on the
        // tiles — required for a government portal. layerConfig is pinned
        // explicitly rather than left to auto-detect since it must match
        // this exact tile style pixel-for-pixel to blend correctly; this
        // URL (CARTO Voyager, retina) is the literal match for
        // 'cartodb-light-retina' in @india-boundary-corrector/layer-configs.
        // pmtilesUrl points at the vendored copy so this never falls back to
        // the package's default jsDelivr CDN URL.
        L.tileLayer.indiaBoundaryCorrected(
          "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
          {
            subdomains: "abcd",
            maxZoom: 19,
            layerConfig: 'cartodb-light-retina',
            pmtilesUrl: '/vendor/india_boundary_corrections.pmtiles',
          }
        ).addTo(map);

        markersLayerRef.current = L.layerGroup().addTo(map);
        leafletMapRef.current = map;

        map.on("zoomend moveend", () => {
          clearTimeout(renderTimerRef.current);
          renderTimerRef.current = setTimeout(() => {
            const zoom = Math.round(map.getZoom());
            setZoomLevel(zoom);
            if (zoom >= ZOOM_DISTRICTS) {
              fetchOperatorsForViewport(map, zoom);
            } else {
              operatorsRequestIdRef.current++; // invalidate any in-flight fetch
              setOperators([]);
            }
          }, 120);
        });

        if (!cancelled) setMapReady(true);
      } catch (e) {
        if (!cancelled) setLoadError("Could not load map. Check your internet connection.");
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(renderTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (!mapReady) return;
    const L = leafletRef.current;
    const map = leafletMapRef.current;
    const layer = markersLayerRef.current;
    layer.clearLayers();

    const zoom = map.getZoom();

    if (zoom < ZOOM_DISTRICTS) {
      stateData.forEach((state) => {
        const short = state.name.length > 14 ? state.name.slice(0, 12) + "…" : state.name;
        const html = `
          <div data-state="${state.name}" style="background:white;border:1.5px solid #aaa;border-radius:10px;padding:5px 8px;font-family:sans-serif;font-size:10px;font-weight:600;color:#222;box-shadow:0 2px 10px rgba(0,0,0,0.14);white-space:nowrap;cursor:pointer;text-align:center;min-width:80px;">
            <div style="font-size:9px;color:#666;margin-bottom:3px;">${short}</div>
            <div style="display:flex;gap:3px;justify-content:center;">
              <span style="background:#FCEBEB;color:#A32D2D;border-radius:3px;padding:1px 5px;">${state.high}H</span>
              <span style="background:#FAEEDA;color:#854F0B;border-radius:3px;padding:1px 5px;">${state.medium}M</span>
              <span style="background:#E1F5EE;color:#0F6E56;border-radius:3px;padding:1px 5px;">${state.low}L</span>
            </div>
          </div>`;
        const icon = L.divIcon({ html, className: "", iconAnchor: [46, 36] });
        L.marker([state.centroid[0], state.centroid[1]], { icon })
          .addTo(layer)
          .on("click", () => {
            setSelectedState(state);
            map.setView([state.centroid[0], state.centroid[1]], ZOOM_OPERATORS + 1, { animate: true });
          });
      });
    } else {
      // operators is already scoped to the current viewport and capped by
      // the backend (see fetchOperatorsForViewport) — no client-side bounds
      // filtering needed here.
      const showLabel = zoom > ZOOM_OPERATORS;
      const dotSize = showLabel ? 14 : 10;
      const anchor = showLabel ? [7, 7] : [5, 5];

      operators.forEach((op) => {
        const lat = op[0], lng = op[1], rc = op[2], opId = op[3];
        const c = RISK_COLORS[rc] || RISK_COLORS.l;

        const html = `
          <div style="display:flex;flex-direction:column;align-items:center;pointer-events:none;">
            <div style="width:${dotSize}px;height:${dotSize}px;border-radius:50%;background:${c.fill};border:2px solid ${c.border};box-shadow:0 1px 5px rgba(0,0,0,0.3);"></div>
            ${showLabel ? `<div style="background:white;border:1px solid #ccc;border-radius:3px;padding:1px 4px;font-size:8px;font-weight:700;color:#111;margin-top:2px;white-space:nowrap;box-shadow:0 1px 3px rgba(0,0,0,0.12);">${opId}</div>` : ""}
          </div>`;

        const icon = L.divIcon({ html, className: "", iconAnchor: anchor });

        const popupHtml = `
          <div style="font-family:sans-serif;min-width:190px;padding:2px 0;">
            <div style="font-weight:700;font-size:13px;color:#111;margin-bottom:6px;">${opId}</div>
            <div style="display:flex;align-items:center;gap:6px;margin-bottom:5px;"><span style="width:10px;height:10px;border-radius:50%;background:${c.fill};border:2px solid ${c.border};display:inline-block;flex-shrink:0;"></span><span style="font-size:12px;color:${c.border};font-weight:600;">${c.label}</span></div>
            <div style="background:#f5f5f5;border-radius:4px;padding:5px 7px;font-family:monospace;font-size:10px;color:#333;line-height:1.6;">Lat: ${lat.toFixed(5)}°N<br/>Lng: ${lng.toFixed(5)}°E</div>
            <div style="padding:6px 8px;text-align:center;margin-top:8px;">
              <button class="map-op-search" data-optid="${opId}" style="font-family:inherit;font-size:12px;padding:6px 10px;border-radius:6px;border:1px solid #ccc;background:#fff;cursor:pointer;">View operator ${opId}</button>
            </div>
          </div>`;

        const marker = L.marker([lat, lng], { icon }).addTo(layer).bindPopup(popupHtml, { maxWidth: 220, offset: [0, -4] });

        // Attach click handler when the popup opens to perform operator search + navigation
        marker.on('popupopen', () => {
          try {
            const popNode = document.querySelector('.leaflet-popup-content');
            if (!popNode) return;
            const btn = popNode.querySelector('.map-op-search');
            if (!btn) return;
            // ensure we don't attach multiple handlers
            if (btn.__handlerAttached) return;
            const handler = async (ev) => {
              ev.preventDefault();
              const opt = btn.getAttribute('data-optid');
              if (!opt) return;
              try {
                const resp = await fetch(`${API_BASE_URL}/api/operator_search`, {
                  method: 'POST',
                  headers: { ...getAuthHeaders() },
                  body: JSON.stringify({ id: opt })
                });
                const data = await resp.json();
                const list = Array.isArray(data) ? data : (Array.isArray(data.data) ? data.data : null);
                const operator = list && list.length > 0 ? list[0] : null;
                navigate('/viewoperators', { state: { initialOperatorData: operator ? [operator] : [], searchedOptId: opt, notFoundMessage: operator ? null : `Operator ${opt} not found.` } });
              } catch (err) {
                // navigate anyway with searched id so UI can show fallback
                navigate('/viewoperators', { state: { searchedOptId: opt } });
              }
            };
            // store marker on element to avoid duplicates
            btn.__handlerAttached = true;
            btn.addEventListener('click', handler);
          } catch (err) {
            // ignore DOM wiring errors
            // console.warn('popup handler attach error', err);
          }
        });
      });
    }
  }, [mapReady, zoomLevel, stateData, operators]);

  const handleStateClick = (state) => {
    setSelectedState(state);
    if (leafletMapRef.current) {
      leafletMapRef.current.setView([state.centroid[0], state.centroid[1]], ZOOM_OPERATORS + 1, { animate: true });
    }
  };

  const handleReset = () => {
    setSelectedState(null);
    if (leafletMapRef.current) leafletMapRef.current.setView([22, 80], 5, { animate: true });
  };

  const handleApplyFilters = () => {
    setSelectedState(null);
    setFilters(draft);
  };

  const handleClearFilters = () => {
    setDraft(DEFAULT_MAP_FILTERS);
    setFilters(DEFAULT_MAP_FILTERS);
    setSearchId('');
    setLocateError(null);
  };

  // Operator ID is a single specific operator, not a category filter —
  // rather than narrowing whatever's currently on screen (which would show
  // nothing unless you already happened to be looking at the right area),
  // look up its coordinates directly and jump the map there. The subsequent
  // zoomend/moveend this triggers re-fetches that viewport through the
  // normal path, honoring whatever ro/risk_bucket/reg/ea filters are active.
  const handleLocateOperator = async () => {
    const id = searchId.trim();
    if (!id) return;
    setLocating(true);
    setLocateError(null);
    try {
      const params = new URLSearchParams({ id });
      const resp = await fetch(`${API_BASE_URL}/api/operators?${params}`, {
        method: 'GET',
        headers: getAuthHeaders(),
      });
      if (!resp.ok) throw new Error(`API error ${resp.status}`);
      const raw = await resp.json();
      const list = Array.isArray(raw?.operators) ? raw.operators : [];
      if (list.length === 0) {
        setLocateError(`Operator ${id} not found or has no location on record.`);
        return;
      }
      const [lat, lng] = list[0];
      setSelectedState(null);
      setOperators(list); // show this pin immediately, ahead of the viewport re-fetch
      if (leafletMapRef.current) {
        leafletMapRef.current.setView([lat, lng], ZOOM_OPERATORS + 1, { animate: true });
      }
    } catch (err) {
      setLocateError(`Failed to locate operator ${id}.`);
    } finally {
      setLocating(false);
    }
  };

  const hasActiveMapFilters = !!(filters.ro || filters.riskBucket || filters.regCode || filters.eaCode);

  const display = selectedState ? { high: selectedState.high, medium: selectedState.medium, low: selectedState.low, total: selectedState.total } : totals;

  const zoneLabel = zoomLevel < ZOOM_DISTRICTS ? "State view — click a bubble to zoom into a state" : zoomLevel <= ZOOM_OPERATORS ? "Operator pins shown — zoom in further for ID labels" : "Operator view — individual operators shown · click any pin for details";

  return (
    <PageWrapper>
      <PageNavigation currentPage="dynamicriskmap" />
      <div style={{ fontFamily: "sans-serif", padding: "16px 20px", maxWidth: "100%", boxSizing: "border-box" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12, gap: 8, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 19, fontWeight: 700, color: "#1a1a1a" }}>India Operator Risk Map</div>
          <div style={{ fontSize: 12, color: "#777", marginTop: 3 }}>{zoneLabel}</div>
          {operatorsError && <div style={{ fontSize: 12, color: "#c00", marginTop: 3 }}>⚠️ {operatorsError}</div>}
        </div>
        {selectedState && (
          <button onClick={handleReset} style={{ fontSize: 13, padding: "6px 16px", cursor: "pointer", border: "1px solid #ccc", borderRadius: 8, background: "#f5f5f5", color: "#333", fontWeight: 500 }}>← All states</button>
        )}
      </div>

      <div style={{ background: "#f8fafc", border: "1px solid #e5e5e5", borderRadius: 10, padding: 12, marginBottom: 12 }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "flex-end" }}>
          <div style={{ minWidth: 150 }}>
            <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: "#555", marginBottom: 4 }}>Regional Office</label>
            <select
              value={draft.ro}
              onChange={e => setDraft(d => ({ ...d, ro: e.target.value, regCode: '', eaCode: '' }))}
              style={{ width: "100%", fontSize: 12, padding: "7px 8px", border: "1px solid #ccc", borderRadius: 8, background: "#fff", color: "#222" }}
            >
              <option value="">All Regional Offices</option>
              {filterOptions.regional_offices.map(ro => <option key={ro} value={ro}>{ro}</option>)}
            </select>
          </div>

          <div style={{ minWidth: 140 }}>
            <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: "#555", marginBottom: 4 }}>Risk Category</label>
            <select
              value={draft.riskBucket}
              onChange={e => setDraft(d => ({ ...d, riskBucket: e.target.value }))}
              style={{ width: "100%", fontSize: 12, padding: "7px 8px", border: "1px solid #ccc", borderRadius: 8, background: "#fff", color: "#222" }}
            >
              <option value="">All Risk Categories</option>
              {filterOptions.risk_buckets.map(rb => <option key={rb} value={rb}>{rb}</option>)}
            </select>
          </div>

          <div style={{ minWidth: 170 }}>
            <NameCodeTypeahead
              label="Registrar"
              options={filterOptions.registrars}
              value={draft.regCode}
              onChange={code => setDraft(d => ({ ...d, regCode: code, eaCode: '' }))}
            />
          </div>

          <div style={{ minWidth: 170 }}>
            <NameCodeTypeahead
              label="EA"
              options={filterOptions.eas}
              value={draft.eaCode}
              onChange={code => setDraft(d => ({ ...d, eaCode: code }))}
            />
          </div>

          <div style={{ minWidth: 190 }}>
            <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: "#555", marginBottom: 4 }}>Locate Operator ID</label>
            <div style={{ display: "flex", gap: 4 }}>
              <input
                type="text"
                value={searchId}
                onChange={e => setSearchId(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleLocateOperator()}
                placeholder="Operator ID..."
                style={{ flex: 1, minWidth: 0, fontSize: 12, padding: "7px 8px", border: "1px solid #ccc", borderRadius: 8, background: "#fff", color: "#222" }}
              />
              <button
                onClick={handleLocateOperator}
                disabled={locating || !searchId.trim()}
                style={{ fontSize: 12, padding: "7px 10px", cursor: locating || !searchId.trim() ? "default" : "pointer", border: "1px solid #378ADD", borderRadius: 8, background: locating ? "#eaf2fb" : "#378ADD", color: locating ? "#378ADD" : "#fff", fontWeight: 500, opacity: !searchId.trim() ? 0.5 : 1 }}
              >
                {locating ? "…" : "Go"}
              </button>
            </div>
          </div>

          <div style={{ display: "flex", gap: 6, marginLeft: "auto" }}>
            {hasActiveMapFilters && (
              <button
                onClick={handleClearFilters}
                style={{ fontSize: 12, padding: "8px 14px", cursor: "pointer", border: "1px solid #ccc", borderRadius: 8, background: "#fff", color: "#555", fontWeight: 500 }}
              >
                Clear
              </button>
            )}
            <button
              onClick={handleApplyFilters}
              style={{ fontSize: 12, padding: "8px 14px", cursor: "pointer", border: "1px solid #378ADD", borderRadius: 8, background: "#378ADD", color: "#fff", fontWeight: 600 }}
            >
              Apply Filters
            </button>
          </div>
        </div>
        {locateError && <div style={{ fontSize: 12, color: "#c00", marginTop: 8 }}>⚠️ {locateError}</div>}
        {hasActiveMapFilters && (
          <div style={{ fontSize: 11, color: "#378ADD", marginTop: 8, fontWeight: 500 }}>
            Filtered results — bubbles, totals and pins reflect the active filters.
          </div>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8, marginBottom: 12 }}>
        {[
          { label: "High Risk", key: "high", color: "#A32D2D", bg: "#FCEBEB" },
          { label: "Medium Risk", key: "medium", color: "#854F0B", bg: "#FAEEDA" },
          { label: "Low Risk", key: "low", color: "#0F6E56", bg: "#E1F5EE" },
          { label: "Total", key: "total", color: "#2C2C2A", bg: "#F2F2F2" },
        ].map(({ label, key, color, bg }) => (
          <div key={key} style={{ background: bg, borderRadius: 8, padding: "10px 14px", border: "0.5px solid #e0e0e0" }}>
            <div style={{ fontSize: 11, color, fontWeight: 500, marginBottom: 3 }}>{selectedState ? `${selectedState.name} · ` : ""}{label}</div>
            <div style={{ fontSize: 26, fontWeight: 700, color }}>{display[key].toLocaleString()}</div>
          </div>
        ))}
      </div>

      <div style={{ position: "relative", borderRadius: 12, overflow: "hidden", border: "1px solid #ddd", marginBottom: 12, boxShadow: "0 2px 16px rgba(0,0,0,0.08)" }}>
        {loadError && (<div style={{ padding: 48, textAlign: "center", color: "#888", fontSize: 13, background: "#fafafa" }}>⚠️ {loadError}</div>)}
        {!mapReady && !loadError && (
          <div style={{ height: 460, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", background: "#f4f5f6", gap: 12 }}>
            <div style={{ width: 36, height: 36, border: "3px solid #ddd", borderTopColor: "#378ADD", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
            <div style={{ fontSize: 13, color: "#888" }}>Loading map…</div>
            <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
          </div>
        )}
        <div ref={mapContainerRef} style={{ height: 460, width: "100%", display: mapReady ? "block" : "none" }} />

        {mapReady && (
          <div style={{ position: "absolute", bottom: 28, right: 10, background: "white", border: "1px solid #ddd", borderRadius: 9, padding: "10px 13px", fontSize: 12, zIndex: 1000, boxShadow: "0 2px 10px rgba(0,0,0,0.12)" }}>
            <div style={{ fontWeight: 700, marginBottom: 7, color: "#333", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.05em" }}>Risk level</div>
            {Object.entries(RISK_COLORS).map(([k, v]) => (
              <div key={k} style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 5 }}>
                <span style={{ width: 11, height: 11, borderRadius: "50%", background: v.fill, border: `2px solid ${v.border}`, display: "inline-block", flexShrink: 0 }} />
                <span style={{ color: "#444", fontSize: 11 }}>{v.label}</span>
              </div>
            ))}
            <div style={{ marginTop: 7, paddingTop: 7, borderTop: "0.5px solid #eee", color: "#999", fontSize: 9, lineHeight: 1.5 }}>
              Zoom {zoomLevel}<br />
              {zoomLevel < ZOOM_DISTRICTS ? "🗺 State view" : zoomLevel <= ZOOM_OPERATORS ? "📍 Operator pins (unlabeled)" : "📍 Operator view"}
            </div>
          </div>
        )}
      </div>

      <div style={{ fontSize: 13, fontWeight: 700, color: "#555", marginBottom: 8, letterSpacing: "0.01em" }}>All states — click to jump in</div>
      {stateError && <div style={{ fontSize: 12, color: "#c00", marginBottom: 8 }}>⚠️ {stateError}</div>}
      {stateLoading && !stateError && <div style={{ fontSize: 12, color: "#888", marginBottom: 8 }}>Loading state data…</div>}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 7, maxHeight: 220, overflowY: "auto", paddingRight: 4, paddingBottom: 4 }}>
        {stateData.map((state) => {
          const active = selectedState?.name === state.name;
          return (
            <div key={state.name} onClick={() => handleStateClick(state)} style={{ background: active ? "#EBF3FC" : "#fafafa", border: active ? "2px solid #378ADD" : "1px solid #e5e5e5", borderRadius: 8, padding: "8px 10px", cursor: "pointer", transition: "border-color .15s, background .15s" }} onMouseEnter={e => { if (!active) e.currentTarget.style.borderColor = "#bbb"; }} onMouseLeave={e => { if (!active) e.currentTarget.style.borderColor = "#e5e5e5"; }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: active ? "#185FA5" : "#222", marginBottom: 5 }}>{state.name}</div>
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                <span style={{ background: "#FCEBEB", color: "#A32D2D", borderRadius: 3, padding: "1px 6px", fontSize: 10, fontWeight: 600 }}>{state.high.toLocaleString()}H</span>
                <span style={{ background: "#FAEEDA", color: "#854F0B", borderRadius: 3, padding: "1px 6px", fontSize: 10, fontWeight: 600 }}>{state.medium.toLocaleString()}M</span>
                <span style={{ background: "#E1F5EE", color: "#0F6E56", borderRadius: 3, padding: "1px 6px", fontSize: 10, fontWeight: 600 }}>{state.low.toLocaleString()}L</span>
                <span style={{ background: "#f0f0f0", color: "#555", borderRadius: 3, padding: "1px 6px", fontSize: 10 }}>{state.total.toLocaleString()}</span>
              </div>
            </div>
          );
        })}
      </div>
      </div>
    </PageWrapper>
  );
}
