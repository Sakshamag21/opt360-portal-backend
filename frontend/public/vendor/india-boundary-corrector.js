"use strict";
var IndiaBoundaryCorrector = (() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __export = (target, all) => {
    for (var name in all)
      __defProp(target, name, { get: all[name], enumerable: true });
  };
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

  // src/index.js
  var index_exports = {};
  __export(index_exports, {
    LayerConfig: () => LayerConfig,
    extendLeaflet: () => extendLeaflet,
    getPmtilesUrl: () => getPmtilesUrl,
    layerConfigs: () => layerConfigs
  });

  // ../data/version.js
  var packageVersion = "0.2.2";

  // ../data/index.js
  var import_meta = {};
  var PACKAGE_NAME = "@india-boundary-corrector/data";
  var PMTILES_FILENAME = "india_boundary_corrections.pmtiles.gz";
  var FALLBACK_CDNS = /* @__PURE__ */ new Set(["esm.sh", "skypack.dev", "cdn.skypack.dev", "unpkg.com"]);
  var DEFAULT_CDN_URL = `https://cdn.jsdelivr.net/npm/${PACKAGE_NAME}@${packageVersion}/${PMTILES_FILENAME}`;
  var CURRENT_SCRIPT_URL = typeof document !== "undefined" && document.currentScript && document.currentScript.src || null;
  function detectPmtilesUrl() {
    let scriptUrl = null;
    try {
      if (typeof import_meta !== "undefined" && import_meta.url) {
        scriptUrl = import_meta.url;
      }
    } catch {
    }
    if (!scriptUrl && CURRENT_SCRIPT_URL) {
      scriptUrl = CURRENT_SCRIPT_URL;
    }
    if (scriptUrl) {
      return resolvePmtilesUrl(scriptUrl);
    }
    return DEFAULT_CDN_URL;
  }
  function resolvePmtilesUrl(scriptUrl) {
    const moduleUrl = new URL(".", scriptUrl);
    if (FALLBACK_CDNS.has(moduleUrl.hostname)) {
      return DEFAULT_CDN_URL;
    }
    return new URL(PMTILES_FILENAME, moduleUrl).href;
  }
  var cachedPmtilesUrl = null;
  function getPmtilesUrl() {
    if (cachedPmtilesUrl === null) {
      cachedPmtilesUrl = detectPmtilesUrl();
    }
    return cachedPmtilesUrl;
  }

  // ../layer-configs/dist/index.js
  var configs_default = [
    {
      id: "cartodb-dark",
      tileUrlTemplates: [
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png",
        "https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_nolabels/{z}/{x}/{y}.png"
      ],
      lineWidthStops: { "0": 1, "2": 1, "3": 1, "10": 2, "12": 2 },
      lineStyles: [
        { color: "rgb(40, 40, 40)", layerSuffix: "ne", endZoom: 4 },
        { color: "rgb(40, 40, 40)", layerSuffix: "ne-disp", endZoom: 4 },
        { color: "rgb(40, 40, 40)", layerSuffix: "osm", startZoom: 5 },
        { color: "rgb(40, 40, 40)", layerSuffix: "osm-disp", startZoom: 5 },
        { color: "rgb(40, 40, 40)", layerSuffix: "osm-internal", startZoom: 5, widthFraction: 0.3, dashArray: [2, 2], delWidthFactor: 2 },
        { color: "rgb(40, 40, 40)", layerSuffix: "ne-internal", startZoom: 4, endZoom: 4, widthFraction: 0.3, dashArray: [2, 2], delWidthFactor: 3 }
      ]
    },
    {
      id: "cartodb-dark-retina",
      tileUrlTemplates: [
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}{r}.png",
        "https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_nolabels/{z}/{x}/{y}{r}.png"
      ],
      lineWidthStops: { "0": 1.5, "2": 1.5, "3": 1.5, "6": 2.5, "10": 3 },
      lineStyles: [
        { color: "rgb(40, 40, 40)", layerSuffix: "ne", endZoom: 4 },
        { color: "rgb(40, 40, 40)", layerSuffix: "ne-disp", endZoom: 4 },
        { color: "rgb(40, 40, 40)", layerSuffix: "osm", startZoom: 5 },
        { color: "rgb(40, 40, 40)", layerSuffix: "osm-disp", startZoom: 5 },
        { color: "rgb(40, 40, 40)", layerSuffix: "osm-internal", startZoom: 5, widthFraction: 0.3, dashArray: [4, 4], delWidthFactor: 2 },
        { color: "rgb(40, 40, 40)", layerSuffix: "ne-internal", startZoom: 4, endZoom: 4, widthFraction: 0.3, dashArray: [4, 4], delWidthFactor: 3 }
      ]
    },
    {
      id: "cartodb-light",
      tileUrlTemplates: [
        "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
        "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_nolabels/{z}/{x}/{y}.png",
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}.png",
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}.png"
      ],
      lineWidthStops: { "1": 0.5, "2": 0.75, "3": 0.75, "4": 1, "5": 1, "7": 1.75, "16": 2.5 },
      lineStyles: [
        { color: "rgb(235, 214, 214)", layerSuffix: "ne", endZoom: 4, lineExtensionFactor: 0.1, delWidthFactor: 2.5 },
        { color: "rgb(235, 214, 214)", layerSuffix: "ne-disp", endZoom: 4, delWidthFactor: 0 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm", alpha: 0.1, startZoom: 6, lineWidthStops: { "6": 9, "10": 8, "14": 8 }, lineExtensionFactor: 0.1 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm", startZoom: 5, lineExtensionFactor: 0.1 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm-disp", startZoom: 5, delWidthFactor: 0 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm-internal", startZoom: 5, widthFraction: 0.5, dashArray: [2, 2], delWidthFactor: 2 },
        { color: "rgb(235, 214, 214)", layerSuffix: "ne-internal", startZoom: 4, endZoom: 4, widthFraction: 0.5, dashArray: [2, 2], delWidthFactor: 2.5 }
      ]
    },
    {
      id: "cartodb-light-retina",
      tileUrlTemplates: [
        "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}{r}.png",
        "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_nolabels/{z}/{x}/{y}{r}.png",
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png",
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}{r}.png"
      ],
      lineWidthStops: { "1": 1, "3": 1, "4": 2, "5": 2, "6": 2.5, "7": 3, "8": 3, "10": 4, "11": 4, "12": 4 },
      lineStyles: [
        { color: "rgb(235, 214, 214)", layerSuffix: "ne", endZoom: 4, lineExtensionFactor: 0.1, delWidthFactor: 2.5 },
        { color: "rgb(235, 214, 214)", layerSuffix: "ne-disp", endZoom: 4, delWidthFactor: 0 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm", alpha: 0.1, startZoom: 6, lineWidthStops: { "6": 20, "8": 19, "10": 18, "12": 17 }, lineExtensionFactor: 0.1 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm", startZoom: 5, lineExtensionFactor: 0.1 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm-disp", startZoom: 5, delWidthFactor: 0 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm-internal", startZoom: 5, widthFraction: 0.5, dashArray: [4, 4], delWidthFactor: 2 },
        { color: "rgb(235, 214, 214)", layerSuffix: "ne-internal", startZoom: 4, endZoom: 4, widthFraction: 0.5, dashArray: [4, 4], delWidthFactor: 2.5 }
      ]
    },
    {
      id: "open-topo",
      tileUrlTemplates: [
        "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        "https://tile.opentopomap.org/{z}/{x}/{y}.png",
        "https://{s}.tile.top-o-map.de/{z}/{x}/{y}.png",
        "https://tile.top-o-map.de/{z}/{x}/{y}.png"
      ],
      lineWidthStops: { "4": 0.75, "5": 1, "6": 1.25, "7": 1.5, "8": 1.75, "9": 1.25, "10": 1.25, "13": 1.5 },
      lineStyles: [
        { color: "rgb(83, 83, 83)", layerSuffix: "ne", startZoom: 4, endZoom: 6 },
        { color: "rgb(173, 173, 173)", layerSuffix: "osm", startZoom: 7, endZoom: 8, alpha: 0.5, widthFraction: 4 },
        { color: "rgb(83, 83, 83)", layerSuffix: "osm", startZoom: 7, endZoom: 8 },
        { color: "rgb(83, 83, 83)", layerSuffix: "osm-internal", widthFraction: 0.75, startZoom: 7, endZoom: 8 },
        { color: "rgb(199, 158, 204)", layerSuffix: "osm", startZoom: 9, widthFraction: 7, alpha: 0.6, lineExtensionFactor: 0.2 },
        { color: "rgb(175, 41, 203)", layerSuffix: "osm", startZoom: 9, lineExtensionFactor: 0.2 },
        { color: "rgb(199, 158, 204)", layerSuffix: "osm-internal", startZoom: 9, widthFraction: 2.25, alpha: 0.6, lineExtensionFactor: 0.2 },
        { color: "rgb(175, 41, 203)", layerSuffix: "osm-internal", startZoom: 9, widthFactor: 0.75, lineExtensionFactor: 0.2 }
      ]
    },
    {
      id: "osm-carto",
      tileUrlTemplates: [
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      ],
      lineWidthStops: { "3": 0.7, "4": 1, "10": 3.75 },
      lineStyles: [
        { color: "rgb(200, 180, 200)", layerSuffix: "osm", startZoom: 4, delWidthFactor: 1.5 },
        { color: "rgb(160, 120, 160)", layerSuffix: "osm", startZoom: 4, widthFraction: 0.333, dashArray: [30, 2, 8, 2], delWidthFactor: 0 },
        { color: "rgb(200, 180, 200)", layerSuffix: "osm-internal", startZoom: 4, widthFraction: 0.45 },
        { color: "rgb(160, 120, 160)", layerSuffix: "osm-internal", startZoom: 4, widthFraction: 0.15, dashArray: [10, 4, 2] }
      ]
    },
    {
      id: "osm-hot",
      tileUrlTemplates: [
        "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        "https://tile.openstreetmap.fr/hot/{z}/{x}/{y}.png"
      ],
      lineWidthStops: { "2": 3, "3": 3, "7": 3, "8": 3.5, "9": 3.5 },
      lineStyles: [
        { color: "rgb(149, 175, 180)", layerSuffix: "osm", lineExtensionFactor: 0.25, startZoom: 2 },
        { color: "rgb(89, 117, 123)", layerSuffix: "osm", widthFraction: 0.33, lineExtensionFactor: 0.25, startZoom: 2 },
        { color: "rgb(172, 163, 163)", layerSuffix: "osm-internal", widthFraction: 0.33, startZoom: 4, dashArray: [7, 7] }
      ]
    }
  ];
  var INFINITY = -1;
  var MIN_LINE_WIDTH = 0.1;
  var DEFAULT_LINE_WIDTH = 1;
  function interpolateLineWidth(zoom, lineWidthStops) {
    const zooms = Object.keys(lineWidthStops).map(Number).sort((a, b2) => a - b2);
    if (lineWidthStops[zoom] !== void 0) {
      return lineWidthStops[zoom];
    }
    if (zoom < zooms[0]) {
      const z1 = zooms[0];
      const z2 = zooms[1];
      const w1 = lineWidthStops[z1];
      const w2 = lineWidthStops[z2];
      const slope = (w2 - w1) / (z2 - z1);
      return Math.max(MIN_LINE_WIDTH, w1 + slope * (zoom - z1));
    }
    if (zoom > zooms[zooms.length - 1]) {
      const z1 = zooms[zooms.length - 2];
      const z2 = zooms[zooms.length - 1];
      const w1 = lineWidthStops[z1];
      const w2 = lineWidthStops[z2];
      const slope = (w2 - w1) / (z2 - z1);
      return Math.max(MIN_LINE_WIDTH, w2 + slope * (zoom - z2));
    }
    for (let i2 = 0; i2 < zooms.length - 1; i2++) {
      if (zoom > zooms[i2] && zoom < zooms[i2 + 1]) {
        const z1 = zooms[i2];
        const z2 = zooms[i2 + 1];
        const w1 = lineWidthStops[z1];
        const w2 = lineWidthStops[z2];
        const t = (zoom - z1) / (z2 - z1);
        return w1 + t * (w2 - w1);
      }
    }
    return DEFAULT_LINE_WIDTH;
  }
  function templateToRegex(template) {
    const groups = [];
    const hasRetina = template.includes("{r}");
    const hasExtension = /\.(png|jpg|jpeg|webp|gif)$/i.test(template);
    let pattern = template.replace(/[.*+?^${}()|[\]\\]/g, (char) => {
      if (char === "{" || char === "}") return char;
      return "\\" + char;
    }).replace(/^https:\/\//, "https?://").replace(/^http:\/\//, "https?://").replace(/\{[a-z0-9]-[a-z0-9]\}/gi, () => {
      groups.push("s");
      return "([a-z0-9]+)";
    }).replace(/\{(z|x|y|s|r)\}/gi, (_2, name) => {
      const lowerName = name.toLowerCase();
      groups.push(lowerName);
      if (lowerName === "s") {
        return "([a-z0-9]+)";
      }
      if (lowerName === "r") {
        return "(@\\d+x)";
      }
      return "(\\d+)";
    });
    if (!hasRetina) {
      if (hasExtension) {
        pattern = pattern.replace(/(\\\.(png|jpg|jpeg|webp|gif))/, "(?!@\\d+x)$1");
      } else {
        pattern = pattern + "(?!@\\d+x)";
      }
    }
    return { pattern: new RegExp("^" + pattern + "(\\?.*)?$", "i"), groups };
  }
  function templateToTemplateRegex(template) {
    const hasRetina = template.includes("{r}");
    const hasExtension = /\.(png|jpg|jpeg|webp|gif)$/i.test(template);
    let pattern = template.replace(/[.*+?^${}()|[\]\\]/g, (char) => {
      if (char === "{" || char === "}") return char;
      return "\\" + char;
    }).replace(/^https:\/\//, "https?://").replace(/^http:\/\//, "https?://").replace(/\{([a-z0-9])-([a-z0-9])\}/gi, (_2, start, end) => `(\\{${start}-${end}\\}|\\{s\\}|[a-z0-9]+)`).replace(/\{(z|x|y|s|r)\}/gi, (_2, name) => {
      const lowerName = name.toLowerCase();
      if (lowerName === "s") {
        return "(\\{s\\}|\\{[a-z0-9]-[a-z0-9]\\}|[a-z0-9]+)";
      }
      if (lowerName === "r") {
        return "(\\{r\\}|@\\d+x)";
      }
      return `\\{${lowerName}\\}`;
    });
    if (!hasRetina) {
      if (hasExtension) {
        pattern = pattern.replace(/(\\\.(png|jpg|jpeg|webp|gif))/, "(?!@\\d+x|\\{r\\})$1");
      } else {
        pattern = pattern + "(?!@\\d+x|\\{r\\})";
      }
    }
    return new RegExp("^" + pattern + "(\\?.*)?$", "i");
  }
  function isValidColor(color) {
    if (typeof color !== "string" || !color.trim()) return false;
    if (typeof CSS !== "undefined" && CSS.supports) {
      return CSS.supports("color", color);
    }
    const trimmed = color.trim().toLowerCase();
    if (/^#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/.test(trimmed)) return true;
    if (/^(rgb|hsl)a?\(/.test(trimmed)) return true;
    if (/^[a-z]+$/.test(trimmed)) return true;
    return false;
  }
  function validateLineWidthStops(lineWidthStops, prefix) {
    if (!lineWidthStops || typeof lineWidthStops !== "object" || Array.isArray(lineWidthStops)) {
      throw new Error(`${prefix}: lineWidthStops must be an object`);
    }
    const stopKeys = Object.keys(lineWidthStops);
    if (stopKeys.length < 2) {
      throw new Error(`${prefix}: lineWidthStops must have at least 2 entries`);
    }
    for (const key of stopKeys) {
      const zoom = Number(key);
      if (!Number.isInteger(zoom) || zoom < 0) {
        throw new Error(`${prefix}: lineWidthStops keys must be non-negative integers, got "${key}"`);
      }
      if (typeof lineWidthStops[key] !== "number" || lineWidthStops[key] <= 0) {
        throw new Error(`${prefix}: lineWidthStops values must be positive numbers`);
      }
    }
  }
  var LineStyle = class _LineStyle {
    /**
     * Validate a LineStyle configuration object.
     * @param {Object} obj - The object to validate
     * @param {number} [index] - Optional index for error messages (when validating in an array)
     * @param {boolean} [requireLineWidthStops=false] - Whether lineWidthStops is required
     * @throws {Error} If validation fails
     */
    static validateJSON(obj, index, requireLineWidthStops = false) {
      const prefix = index !== void 0 ? `lineStyles[${index}]` : "LineStyle";
      if (!obj || typeof obj !== "object") {
        throw new Error(`${prefix}: must be an object`);
      }
      if (!obj.color || typeof obj.color !== "string") {
        throw new Error(`${prefix}: color must be a non-empty string`);
      }
      if (!isValidColor(obj.color)) {
        throw new Error(`${prefix}: color "${obj.color}" is not a valid CSS color`);
      }
      if (!obj.layerSuffix || typeof obj.layerSuffix !== "string") {
        throw new Error(`${prefix}: layerSuffix must be a non-empty string`);
      }
      if (obj.widthFraction !== void 0 && (typeof obj.widthFraction !== "number" || obj.widthFraction <= 0)) {
        throw new Error(`${prefix}: widthFraction must be a positive number`);
      }
      if (obj.dashArray !== void 0 && !Array.isArray(obj.dashArray)) {
        throw new Error(`${prefix}: dashArray must be an array`);
      }
      if (obj.alpha !== void 0 && (typeof obj.alpha !== "number" || obj.alpha < 0 || obj.alpha > 1)) {
        throw new Error(`${prefix}: alpha must be a number between 0 and 1`);
      }
      if (obj.startZoom !== void 0 && (typeof obj.startZoom !== "number" || obj.startZoom < 0)) {
        throw new Error(`${prefix}: startZoom must be a non-negative number`);
      }
      if (obj.endZoom !== void 0 && (typeof obj.endZoom !== "number" || obj.endZoom < 0 && obj.endZoom !== INFINITY)) {
        throw new Error(`${prefix}: endZoom must be a non-negative number or INFINITY (${INFINITY})`);
      }
      if (obj.lineExtensionFactor !== void 0 && (typeof obj.lineExtensionFactor !== "number" || obj.lineExtensionFactor < 0)) {
        throw new Error(`${prefix}: lineExtensionFactor must be a non-negative number`);
      }
      if (obj.delWidthFactor !== void 0 && (typeof obj.delWidthFactor !== "number" || obj.delWidthFactor < 0)) {
        throw new Error(`${prefix}: delWidthFactor must be a non-negative number`);
      }
      if (requireLineWidthStops && obj.lineWidthStops === void 0) {
        throw new Error(`${prefix}: lineWidthStops is required`);
      }
      if (obj.lineWidthStops !== void 0) {
        validateLineWidthStops(obj.lineWidthStops, prefix);
      }
    }
    /**
     * @param {Object} options
     * @param {string} options.color - CSS color string
     * @param {string} options.layerSuffix - Layer suffix (e.g., 'osm', 'ne', 'osm-disp')
     * @param {Object<number, number>} options.lineWidthStops - Line width stops for this style
     * @param {number} [options.widthFraction=1.0] - Multiplier for base line width
     * @param {number[]} [options.dashArray] - Dash pattern for dashed lines
     * @param {number} [options.alpha=1.0] - Opacity (0-1)
     * @param {number} [options.startZoom=0] - Minimum zoom level for this style
     * @param {number} [options.endZoom=INFINITY] - Maximum zoom level for this style (INFINITY means no limit)
     * @param {number} [options.lineExtensionFactor=0.0] - Factor to extend lines by (multiplied by deletion line width)
     * @param {number} [options.delWidthFactor=1.5] - Factor to multiply line width for deletion blur
     */
    constructor({ color, layerSuffix, lineWidthStops, widthFraction = 1, dashArray, alpha = 1, startZoom = 0, endZoom = INFINITY, lineExtensionFactor = 0, delWidthFactor = 1.5 }) {
      this.color = color;
      this.layerSuffix = layerSuffix;
      this.lineWidthStops = lineWidthStops;
      this.widthFraction = widthFraction;
      this.dashArray = dashArray;
      this.alpha = alpha;
      this.startZoom = startZoom;
      this.endZoom = endZoom;
      this.lineExtensionFactor = lineExtensionFactor;
      this.delWidthFactor = delWidthFactor;
    }
    /**
     * Get base line width for this style at a given zoom level.
     * @param {number} zoom - Zoom level
     * @returns {number}
     */
    getLineWidth(zoom) {
      return interpolateLineWidth(zoom, this.lineWidthStops);
    }
    /**
     * Check if this style is active at the given zoom level.
     * @param {number} z - Zoom level
     * @returns {boolean}
     */
    isActiveAtZoom(z2) {
      return z2 >= this.startZoom && (this.endZoom === INFINITY || z2 <= this.endZoom);
    }
    /**
     * Serialize to plain object.
     * @returns {Object}
     */
    toJSON() {
      return {
        color: this.color,
        layerSuffix: this.layerSuffix,
        lineWidthStops: this.lineWidthStops,
        widthFraction: this.widthFraction,
        dashArray: this.dashArray,
        alpha: this.alpha,
        startZoom: this.startZoom,
        endZoom: this.endZoom,
        lineExtensionFactor: this.lineExtensionFactor,
        delWidthFactor: this.delWidthFactor
      };
    }
    /**
     * Create from plain object with validation.
     * @param {Object} obj
     * @param {number} [index] - Optional index for error messages
     * @returns {LineStyle}
     */
    static fromJSON(obj, index) {
      _LineStyle.validateJSON(obj, index, true);
      return new _LineStyle(obj);
    }
  };
  var LayerConfig = class _LayerConfig {
    /**
     * Validate a LayerConfig configuration object.
     * Also validates all lineStyles within the config.
     * @param {Object} obj - The object to validate
     * @throws {Error} If validation fails
     */
    static validateJSON(obj) {
      if (!obj || typeof obj !== "object") {
        throw new Error("LayerConfig: must be an object");
      }
      if (!obj.id || typeof obj.id !== "string") {
        throw new Error("LayerConfig: id must be a non-empty string");
      }
      if (obj.id.includes("/")) {
        throw new Error(`LayerConfig: id cannot contain slashes: "${obj.id}"`);
      }
      const id = obj.id;
      if (obj.lineWidthStops !== void 0) {
        if (!obj.lineWidthStops || typeof obj.lineWidthStops !== "object" || Array.isArray(obj.lineWidthStops)) {
          throw new Error(`LayerConfig "${id}": lineWidthStops must be an object`);
        }
        const stopKeys = Object.keys(obj.lineWidthStops);
        if (stopKeys.length < 2) {
          throw new Error(`LayerConfig "${id}": lineWidthStops must have at least 2 entries`);
        }
        for (const key of stopKeys) {
          const zoom = Number(key);
          if (!Number.isInteger(zoom) || zoom < 0) {
            throw new Error(`LayerConfig "${id}": lineWidthStops keys must be non-negative integers, got "${key}"`);
          }
          if (typeof obj.lineWidthStops[key] !== "number" || obj.lineWidthStops[key] <= 0) {
            throw new Error(`LayerConfig "${id}": lineWidthStops values must be positive numbers`);
          }
        }
      }
      if (!Array.isArray(obj.lineStyles) || obj.lineStyles.length === 0) {
        throw new Error(`LayerConfig "${id}": lineStyles must be a non-empty array`);
      }
      for (let i2 = 0; i2 < obj.lineStyles.length; i2++) {
        LineStyle.validateJSON(obj.lineStyles[i2], i2);
      }
    }
    constructor({
      id,
      // Tile URL templates for matching (e.g., "https://{s}.tile.example.com/{z}/{x}/{y}.png")
      tileUrlTemplates = [],
      // Line width stops: map of zoom level to line width (at least 2 entries)
      // Note: interpolated/extrapolated line width is capped at a minimum of 0.5
      lineWidthStops = { 1: 0.5, 10: 2.5 },
      // Line styles array - each element describes a line to draw from a specific layer
      // { color: string, layerSuffix: string, widthFraction?: number, dashArray?: number[], 
      //   startZoom?: number, endZoom?: number, lineExtensionFactor?: number, delWidthFactor?: number }
      // Lines are drawn in array order. layerSuffix determines which PMTiles layer to use.
      lineStyles
    }) {
      this.id = id;
      const templates = Array.isArray(tileUrlTemplates) ? tileUrlTemplates : tileUrlTemplates ? [tileUrlTemplates] : [];
      this.tileUrlTemplates = templates;
      this._compiledPatterns = templates.map((t) => templateToRegex(t));
      this._templatePatterns = templates.map((t) => templateToTemplateRegex(t));
      this.lineWidthStops = lineWidthStops;
      this.lineStyles = lineStyles.map((style) => {
        if (style instanceof LineStyle) {
          return style;
        }
        const styleWithStops = style.lineWidthStops ? style : { ...style, lineWidthStops };
        return new LineStyle(styleWithStops);
      });
    }
    /**
     * Get line styles active at a given zoom level
     * @param {number} z - Zoom level
     * @returns {LineStyle[]}
     */
    getLineStylesForZoom(z2) {
      return this.lineStyles.filter((style) => style.isActiveAtZoom(z2));
    }
    /**
     * Get unique layer suffixes from styles active at a given zoom level
     * @param {number} z - Zoom level
     * @returns {string[]}
     */
    getLayerSuffixesForZoom(z2) {
      const activeStyles = this.getLineStylesForZoom(z2);
      return [...new Set(activeStyles.map((s) => s.layerSuffix))];
    }
    /**
     * Check if this config matches the given template URLs (with {z}/{x}/{y} placeholders)
     * @param {string | string[]} templates - Single template URL or array of template URLs
     * @returns {boolean}
     */
    matchTemplate(templates) {
      if (this._templatePatterns.length === 0) return false;
      const urls = Array.isArray(templates) ? templates : [templates];
      if (urls.length === 0) return false;
      return urls.some(
        (url) => this._templatePatterns.some((pattern) => pattern.test(url))
      );
    }
    /**
     * Check if this config matches the given tile URLs (with actual coordinates)
     * @param {string | string[]} tiles - Single tile URL or array of tile URLs
     * @returns {boolean}
     */
    matchTileUrl(tiles) {
      if (this._compiledPatterns.length === 0) return false;
      const urls = Array.isArray(tiles) ? tiles : [tiles];
      if (urls.length === 0) return false;
      return urls.some(
        (url) => this._compiledPatterns.some(({ pattern }) => pattern.test(url))
      );
    }
    /**
     * Extract tile coordinates (z, x, y) from a URL using this config's templates
     * @param {string} url - Tile URL to extract coordinates from
     * @returns {{ z: number, x: number, y: number } | null}
     */
    extractCoords(url) {
      for (const { pattern, groups } of this._compiledPatterns) {
        const match = url.match(pattern);
        if (match) {
          const result = {};
          for (let i2 = 0; i2 < groups.length; i2++) {
            const name = groups[i2];
            const value = match[i2 + 1];
            if (name === "z" || name === "x" || name === "y") {
              result[name] = parseInt(value, 10);
            }
          }
          if ("z" in result && "x" in result && "y" in result) {
            return { z: result.z, x: result.x, y: result.y };
          }
        }
      }
      return null;
    }
    /**
     * Serialize the config to a plain object for postMessage
     * @returns {Object}
     */
    toJSON() {
      return {
        id: this.id,
        tileUrlTemplates: this.tileUrlTemplates,
        lineWidthStops: this.lineWidthStops,
        lineStyles: this.lineStyles.map((s) => s.toJSON())
      };
    }
    /**
     * Create a LayerConfig from a plain object with validation.
     * @param {Object} obj
     * @returns {LayerConfig}
     * @throws {Error} If validation fails
     */
    static fromJSON(obj) {
      _LayerConfig.validateJSON(obj);
      return new _LayerConfig(obj);
    }
  };
  var LayerConfigRegistry = class _LayerConfigRegistry {
    constructor() {
      this.registry = {};
    }
    /**
     * Get a layer config by id
     */
    get(id) {
      return this.registry[id];
    }
    /**
     * Register a new layer config
     */
    register(config) {
      this.registry[config.id] = config;
    }
    /**
     * Remove a layer config by id
     */
    remove(id) {
      if (!this.registry[id]) return false;
      delete this.registry[id];
      return true;
    }
    /**
     * Detect layer config from tile URL templates (with {z}/{x}/{y} placeholders)
     * @param {string | string[]} templates - Single template URL or array of template URLs
     */
    detectFromTemplates(templates) {
      if (!templates || Array.isArray(templates) && templates.length === 0) return void 0;
      for (const config of Object.values(this.registry)) {
        if (config.matchTemplate(templates)) {
          return config;
        }
      }
      return void 0;
    }
    /**
     * Detect layer config from actual tile URLs (with numeric coordinates)
     * @param {string | string[]} urls - Single tile URL or array of tile URLs
     */
    detectFromTileUrls(urls) {
      if (!urls || Array.isArray(urls) && urls.length === 0) return void 0;
      for (const config of Object.values(this.registry)) {
        if (config.matchTileUrl(urls)) {
          return config;
        }
      }
      return void 0;
    }
    /**
     * Get all available layer config ids
     */
    getAvailableIds() {
      return Object.keys(this.registry);
    }
    /**
     * Create a new registry with all configs from this registry plus extra configs.
     * @param {LayerConfig[]} extraLayerConfigs - Additional configs to add
     * @returns {LayerConfigRegistry} A new registry with merged configs
     */
    createMergedRegistry(extraLayerConfigs) {
      const registry = new _LayerConfigRegistry();
      for (const id of this.getAvailableIds()) {
        registry.register(this.get(id));
      }
      if (extraLayerConfigs && extraLayerConfigs.length > 0) {
        for (const config of extraLayerConfigs) {
          registry.register(config);
        }
      }
      return registry;
    }
    /**
     * Parse a tile URL into its components: layer config and coordinates
     * @param {string} url - Tile URL to parse
     * @returns {{ layerConfig: LayerConfig, coords: { z: number, x: number, y: number } } | null}
     */
    parseTileUrl(url) {
      const layerConfig = this.detectFromTileUrls([url]);
      if (!layerConfig) return null;
      const coords = layerConfig.extractCoords(url);
      if (!coords) return null;
      return { layerConfig, coords };
    }
  };
  var layerConfigs = new LayerConfigRegistry();
  for (const configData of configs_default) {
    layerConfigs.register(new LayerConfig(configData));
  }

  // ../tilefixer/dist/index.js
  var __defProp2 = Object.defineProperty;
  var __defNormalProp = (obj, key, value) => key in obj ? __defProp2(obj, key, { enumerable: true, configurable: true, writable: true, value }) : obj[key] = value;
  var __publicField = (obj, key, value) => __defNormalProp(obj, typeof key !== "symbol" ? key + "" : key, value);
  var u8 = Uint8Array;
  var u16 = Uint16Array;
  var i32 = Int32Array;
  var fleb = new u8([
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    1,
    1,
    1,
    1,
    2,
    2,
    2,
    2,
    3,
    3,
    3,
    3,
    4,
    4,
    4,
    4,
    5,
    5,
    5,
    5,
    0,
    /* unused */
    0,
    0,
    /* impossible */
    0
  ]);
  var fdeb = new u8([
    0,
    0,
    0,
    0,
    1,
    1,
    2,
    2,
    3,
    3,
    4,
    4,
    5,
    5,
    6,
    6,
    7,
    7,
    8,
    8,
    9,
    9,
    10,
    10,
    11,
    11,
    12,
    12,
    13,
    13,
    /* unused */
    0,
    0
  ]);
  var clim = new u8([16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]);
  var freb = function(eb, start) {
    var b2 = new u16(31);
    for (var i2 = 0; i2 < 31; ++i2) {
      b2[i2] = start += 1 << eb[i2 - 1];
    }
    var r = new i32(b2[30]);
    for (var i2 = 1; i2 < 30; ++i2) {
      for (var j2 = b2[i2]; j2 < b2[i2 + 1]; ++j2) {
        r[j2] = j2 - b2[i2] << 5 | i2;
      }
    }
    return { b: b2, r };
  };
  var _a = freb(fleb, 2);
  var fl = _a.b;
  var revfl = _a.r;
  fl[28] = 258, revfl[258] = 28;
  var _b = freb(fdeb, 0);
  var fd = _b.b;
  var revfd = _b.r;
  var rev = new u16(32768);
  for (i = 0; i < 32768; ++i) {
    x2 = (i & 43690) >> 1 | (i & 21845) << 1;
    x2 = (x2 & 52428) >> 2 | (x2 & 13107) << 2;
    x2 = (x2 & 61680) >> 4 | (x2 & 3855) << 4;
    rev[i] = ((x2 & 65280) >> 8 | (x2 & 255) << 8) >> 1;
  }
  var x2;
  var i;
  var hMap = (function(cd, mb, r) {
    var s = cd.length;
    var i2 = 0;
    var l2 = new u16(mb);
    for (; i2 < s; ++i2) {
      if (cd[i2])
        ++l2[cd[i2] - 1];
    }
    var le = new u16(mb);
    for (i2 = 1; i2 < mb; ++i2) {
      le[i2] = le[i2 - 1] + l2[i2 - 1] << 1;
    }
    var co;
    if (r) {
      co = new u16(1 << mb);
      var rvb = 15 - mb;
      for (i2 = 0; i2 < s; ++i2) {
        if (cd[i2]) {
          var sv = i2 << 4 | cd[i2];
          var r_1 = mb - cd[i2];
          var v2 = le[cd[i2] - 1]++ << r_1;
          for (var m2 = v2 | (1 << r_1) - 1; v2 <= m2; ++v2) {
            co[rev[v2] >> rvb] = sv;
          }
        }
      }
    } else {
      co = new u16(s);
      for (i2 = 0; i2 < s; ++i2) {
        if (cd[i2]) {
          co[i2] = rev[le[cd[i2] - 1]++] >> 15 - cd[i2];
        }
      }
    }
    return co;
  });
  var flt = new u8(288);
  for (i = 0; i < 144; ++i)
    flt[i] = 8;
  var i;
  for (i = 144; i < 256; ++i)
    flt[i] = 9;
  var i;
  for (i = 256; i < 280; ++i)
    flt[i] = 7;
  var i;
  for (i = 280; i < 288; ++i)
    flt[i] = 8;
  var i;
  var fdt = new u8(32);
  for (i = 0; i < 32; ++i)
    fdt[i] = 5;
  var i;
  var flrm = /* @__PURE__ */ hMap(flt, 9, 1);
  var fdrm = /* @__PURE__ */ hMap(fdt, 5, 1);
  var max = function(a) {
    var m2 = a[0];
    for (var i2 = 1; i2 < a.length; ++i2) {
      if (a[i2] > m2)
        m2 = a[i2];
    }
    return m2;
  };
  var bits = function(d, p, m2) {
    var o = p / 8 | 0;
    return (d[o] | d[o + 1] << 8) >> (p & 7) & m2;
  };
  var bits16 = function(d, p) {
    var o = p / 8 | 0;
    return (d[o] | d[o + 1] << 8 | d[o + 2] << 16) >> (p & 7);
  };
  var shft = function(p) {
    return (p + 7) / 8 | 0;
  };
  var slc = function(v2, s, e) {
    if (s == null || s < 0)
      s = 0;
    if (e == null || e > v2.length)
      e = v2.length;
    return new u8(v2.subarray(s, e));
  };
  var ec = [
    "unexpected EOF",
    "invalid block type",
    "invalid length/literal",
    "invalid distance",
    "stream finished",
    "no stream handler",
    ,
    "no callback",
    "invalid UTF-8 data",
    "extra field too long",
    "date not in range 1980-2099",
    "filename too long",
    "stream finishing",
    "invalid zip data"
    // determined by unknown compression method
  ];
  var err = function(ind, msg, nt) {
    var e = new Error(msg || ec[ind]);
    e.code = ind;
    if (Error.captureStackTrace)
      Error.captureStackTrace(e, err);
    if (!nt)
      throw e;
    return e;
  };
  var inflt = function(dat, st, buf, dict) {
    var sl = dat.length, dl = dict ? dict.length : 0;
    if (!sl || st.f && !st.l)
      return buf || new u8(0);
    var noBuf = !buf;
    var resize = noBuf || st.i != 2;
    var noSt = st.i;
    if (noBuf)
      buf = new u8(sl * 3);
    var cbuf = function(l3) {
      var bl = buf.length;
      if (l3 > bl) {
        var nbuf = new u8(Math.max(bl * 2, l3));
        nbuf.set(buf);
        buf = nbuf;
      }
    };
    var final = st.f || 0, pos = st.p || 0, bt = st.b || 0, lm = st.l, dm = st.d, lbt = st.m, dbt = st.n;
    var tbts = sl * 8;
    do {
      if (!lm) {
        final = bits(dat, pos, 1);
        var type = bits(dat, pos + 1, 3);
        pos += 3;
        if (!type) {
          var s = shft(pos) + 4, l2 = dat[s - 4] | dat[s - 3] << 8, t = s + l2;
          if (t > sl) {
            if (noSt)
              err(0);
            break;
          }
          if (resize)
            cbuf(bt + l2);
          buf.set(dat.subarray(s, t), bt);
          st.b = bt += l2, st.p = pos = t * 8, st.f = final;
          continue;
        } else if (type == 1)
          lm = flrm, dm = fdrm, lbt = 9, dbt = 5;
        else if (type == 2) {
          var hLit = bits(dat, pos, 31) + 257, hcLen = bits(dat, pos + 10, 15) + 4;
          var tl = hLit + bits(dat, pos + 5, 31) + 1;
          pos += 14;
          var ldt = new u8(tl);
          var clt = new u8(19);
          for (var i2 = 0; i2 < hcLen; ++i2) {
            clt[clim[i2]] = bits(dat, pos + i2 * 3, 7);
          }
          pos += hcLen * 3;
          var clb = max(clt), clbmsk = (1 << clb) - 1;
          var clm = hMap(clt, clb, 1);
          for (var i2 = 0; i2 < tl; ) {
            var r = clm[bits(dat, pos, clbmsk)];
            pos += r & 15;
            var s = r >> 4;
            if (s < 16) {
              ldt[i2++] = s;
            } else {
              var c = 0, n = 0;
              if (s == 16)
                n = 3 + bits(dat, pos, 3), pos += 2, c = ldt[i2 - 1];
              else if (s == 17)
                n = 3 + bits(dat, pos, 7), pos += 3;
              else if (s == 18)
                n = 11 + bits(dat, pos, 127), pos += 7;
              while (n--)
                ldt[i2++] = c;
            }
          }
          var lt = ldt.subarray(0, hLit), dt = ldt.subarray(hLit);
          lbt = max(lt);
          dbt = max(dt);
          lm = hMap(lt, lbt, 1);
          dm = hMap(dt, dbt, 1);
        } else
          err(1);
        if (pos > tbts) {
          if (noSt)
            err(0);
          break;
        }
      }
      if (resize)
        cbuf(bt + 131072);
      var lms = (1 << lbt) - 1, dms = (1 << dbt) - 1;
      var lpos = pos;
      for (; ; lpos = pos) {
        var c = lm[bits16(dat, pos) & lms], sym = c >> 4;
        pos += c & 15;
        if (pos > tbts) {
          if (noSt)
            err(0);
          break;
        }
        if (!c)
          err(2);
        if (sym < 256)
          buf[bt++] = sym;
        else if (sym == 256) {
          lpos = pos, lm = null;
          break;
        } else {
          var add = sym - 254;
          if (sym > 264) {
            var i2 = sym - 257, b2 = fleb[i2];
            add = bits(dat, pos, (1 << b2) - 1) + fl[i2];
            pos += b2;
          }
          var d = dm[bits16(dat, pos) & dms], dsym = d >> 4;
          if (!d)
            err(3);
          pos += d & 15;
          var dt = fd[dsym];
          if (dsym > 3) {
            var b2 = fdeb[dsym];
            dt += bits16(dat, pos) & (1 << b2) - 1, pos += b2;
          }
          if (pos > tbts) {
            if (noSt)
              err(0);
            break;
          }
          if (resize)
            cbuf(bt + 131072);
          var end = bt + add;
          if (bt < dt) {
            var shift = dl - dt, dend = Math.min(dt, end);
            if (shift + bt < 0)
              err(3);
            for (; bt < dend; ++bt)
              buf[bt] = dict[shift + bt];
          }
          for (; bt < end; ++bt)
            buf[bt] = buf[bt - dt];
        }
      }
      st.l = lm, st.p = lpos, st.b = bt, st.f = final;
      if (lm)
        final = 1, st.m = lbt, st.d = dm, st.n = dbt;
    } while (!final);
    return bt != buf.length && noBuf ? slc(buf, 0, bt) : buf.subarray(0, bt);
  };
  var et = /* @__PURE__ */ new u8(0);
  var gzs = function(d) {
    if (d[0] != 31 || d[1] != 139 || d[2] != 8)
      err(6, "invalid gzip data");
    var flg = d[3];
    var st = 10;
    if (flg & 4)
      st += (d[10] | d[11] << 8) + 2;
    for (var zs = (flg >> 3 & 1) + (flg >> 4 & 1); zs > 0; zs -= !d[st++])
      ;
    return st + (flg & 2);
  };
  var gzl = function(d) {
    var l2 = d.length;
    return (d[l2 - 4] | d[l2 - 3] << 8 | d[l2 - 2] << 16 | d[l2 - 1] << 24) >>> 0;
  };
  var zls = function(d, dict) {
    if ((d[0] & 15) != 8 || d[0] >> 4 > 7 || (d[0] << 8 | d[1]) % 31)
      err(6, "invalid zlib data");
    if ((d[1] >> 5 & 1) == +!dict)
      err(6, "invalid zlib data: " + (d[1] & 32 ? "need" : "unexpected") + " dictionary");
    return (d[1] >> 3 & 4) + 2;
  };
  function inflateSync(data, opts) {
    return inflt(data, { i: 2 }, opts && opts.out, opts && opts.dictionary);
  }
  function gunzipSync(data, opts) {
    var st = gzs(data);
    if (st + 8 > data.length)
      err(6, "invalid gzip data");
    return inflt(data.subarray(st, -8), { i: 2 }, opts && opts.out || new u8(gzl(data)), opts && opts.dictionary);
  }
  function unzlibSync(data, opts) {
    return inflt(data.subarray(zls(data, opts && opts.dictionary), -4), { i: 2 }, opts && opts.out, opts && opts.dictionary);
  }
  function decompressSync(data, opts) {
    return data[0] == 31 && data[1] == 139 && data[2] == 8 ? gunzipSync(data, opts) : (data[0] & 15) != 8 || data[0] >> 4 > 7 || (data[0] << 8 | data[1]) % 31 ? inflateSync(data, opts) : unzlibSync(data, opts);
  }
  var td = typeof TextDecoder != "undefined" && /* @__PURE__ */ new TextDecoder();
  var tds = 0;
  try {
    td.decode(et, { stream: true });
    tds = 1;
  } catch (e) {
  }
  var z = Object.defineProperty;
  var b = Math.pow;
  var l = (i2, e) => z(i2, "name", { value: e, configurable: true });
  var m = (i2, e, t) => new Promise((r, n) => {
    var s = (u) => {
      try {
        a(t.next(u));
      } catch (c) {
        n(c);
      }
    }, o = (u) => {
      try {
        a(t.throw(u));
      } catch (c) {
        n(c);
      }
    }, a = (u) => u.done ? r(u.value) : Promise.resolve(u.value).then(s, o);
    a((t = t.apply(i2, e)).next());
  });
  var re = l((i2, e) => {
    let t = false, r = "", n = L.GridLayer.extend({ createTile: l((s, o) => {
      let a = document.createElement("img"), u = new AbortController(), c = u.signal;
      return a.cancel = () => {
        u.abort();
      }, t || (i2.getHeader().then((d) => {
        d.tileType === 1 ? console.error("Error: archive contains MVT vector tiles, but leafletRasterLayer is for displaying raster tiles. See https://github.com/protomaps/PMTiles/tree/main/js for details.") : d.tileType === 2 ? r = "image/png" : d.tileType === 3 ? r = "image/jpeg" : d.tileType === 4 ? r = "image/webp" : d.tileType === 5 && (r = "image/avif");
      }), t = true), i2.getZxy(s.z, s.x, s.y, c).then((d) => {
        if (d) {
          let h = new Blob([d.data], { type: r }), p = window.URL.createObjectURL(h);
          a.src = p, a.cancel = void 0, o(void 0, a);
        }
      }).catch((d) => {
        if (d.name !== "AbortError") throw d;
      }), a;
    }, "createTile"), _removeTile: l(function(s) {
      let o = this._tiles[s];
      o && (o.el.cancel && o.el.cancel(), o.el.width = 0, o.el.height = 0, o.el.deleted = true, L.DomUtil.remove(o.el), delete this._tiles[s], this.fire("tileunload", { tile: o.el, coords: this._keyToTileCoords(s) }));
    }, "_removeTile") });
    return new n(e);
  }, "leafletRasterLayer");
  var j = l((i2) => (e, t) => {
    if (t instanceof AbortController) return i2(e, t);
    let r = new AbortController();
    return i2(e, r).then((n) => t(void 0, n.data, n.cacheControl || "", n.expires || ""), (n) => t(n)).catch((n) => t(n)), { cancel: l(() => r.abort(), "cancel") };
  }, "v3compat");
  var T = class T2 {
    constructor(e) {
      this.tilev4 = l((e2, t) => m(this, null, function* () {
        if (e2.type === "json") {
          let p = e2.url.substr(10), y = this.tiles.get(p);
          if (y || (y = new x(p), this.tiles.set(p, y)), this.metadata) return { data: yield y.getTileJson(e2.url) };
          let f = yield y.getHeader();
          return (f.minLon >= f.maxLon || f.minLat >= f.maxLat) && console.error(`Bounds of PMTiles archive ${f.minLon},${f.minLat},${f.maxLon},${f.maxLat} are not valid.`), { data: { tiles: [`${e2.url}/{z}/{x}/{y}`], minzoom: f.minZoom, maxzoom: f.maxZoom, bounds: [f.minLon, f.minLat, f.maxLon, f.maxLat] } };
        }
        let r = new RegExp(/pmtiles:\/\/(.+)\/(\d+)\/(\d+)\/(\d+)/), n = e2.url.match(r);
        if (!n) throw new Error("Invalid PMTiles protocol URL");
        let s = n[1], o = this.tiles.get(s);
        o || (o = new x(s), this.tiles.set(s, o));
        let a = n[2], u = n[3], c = n[4], d = yield o.getHeader(), h = yield o == null ? void 0 : o.getZxy(+a, +u, +c, t.signal);
        if (h) return { data: new Uint8Array(h.data), cacheControl: h.cacheControl, expires: h.expires };
        if (d.tileType === 1) {
          if (this.errorOnMissingTile) throw new Error("Tile not found.");
          return { data: new Uint8Array() };
        }
        return { data: null };
      }), "tilev4");
      this.tile = j(this.tilev4);
      this.tiles = /* @__PURE__ */ new Map(), this.metadata = (e == null ? void 0 : e.metadata) || false, this.errorOnMissingTile = (e == null ? void 0 : e.errorOnMissingTile) || false;
    }
    add(e) {
      this.tiles.set(e.source.getKey(), e);
    }
    get(e) {
      return this.tiles.get(e);
    }
  };
  l(T, "Protocol");
  function w(i2, e) {
    return (e >>> 0) * 4294967296 + (i2 >>> 0);
  }
  l(w, "toNum");
  function F(i2, e) {
    let t = e.buf, r = t[e.pos++], n = (r & 112) >> 4;
    if (r < 128 || (r = t[e.pos++], n |= (r & 127) << 3, r < 128) || (r = t[e.pos++], n |= (r & 127) << 10, r < 128) || (r = t[e.pos++], n |= (r & 127) << 17, r < 128) || (r = t[e.pos++], n |= (r & 127) << 24, r < 128) || (r = t[e.pos++], n |= (r & 1) << 31, r < 128)) return w(i2, n);
    throw new Error("Expected varint not more than 10 bytes");
  }
  l(F, "readVarintRemainder");
  function v(i2) {
    let e = i2.buf, t = e[i2.pos++], r = t & 127;
    return t < 128 || (t = e[i2.pos++], r |= (t & 127) << 7, t < 128) || (t = e[i2.pos++], r |= (t & 127) << 14, t < 128) || (t = e[i2.pos++], r |= (t & 127) << 21, t < 128) ? r : (t = e[i2.pos], r |= (t & 15) << 28, F(r, i2));
  }
  l(v, "readVarint");
  function k(i2, e, t, r) {
    if (r === 0) {
      t === 1 && (e[0] = i2 - 1 - e[0], e[1] = i2 - 1 - e[1]);
      let n = e[0];
      e[0] = e[1], e[1] = n;
    }
  }
  l(k, "rotate");
  function N(i2, e) {
    let t = b(2, i2), r = e, n = e, s = e, o = [0, 0], a = 1;
    for (; a < t; ) r = 1 & s / 2, n = 1 & (s ^ r), k(a, o, r, n), o[0] += a * r, o[1] += a * n, s = s / 4, a *= 2;
    return [i2, o[0], o[1]];
  }
  l(N, "idOnLevel");
  var q = [0, 1, 5, 21, 85, 341, 1365, 5461, 21845, 87381, 349525, 1398101, 5592405, 22369621, 89478485, 357913941, 1431655765, 5726623061, 22906492245, 91625968981, 366503875925, 1466015503701, 5864062014805, 23456248059221, 93824992236885, 375299968947541, 1501199875790165];
  function G(i2, e, t) {
    if (i2 > 26) throw new Error("Tile zoom level exceeds max safe number limit (26)");
    if (e > b(2, i2) - 1 || t > b(2, i2) - 1) throw new Error("tile x/y outside zoom level bounds");
    let r = q[i2], n = b(2, i2), s = 0, o = 0, a = 0, u = [e, t], c = n / 2;
    for (; c > 0; ) s = (u[0] & c) > 0 ? 1 : 0, o = (u[1] & c) > 0 ? 1 : 0, a += c * c * (3 * s ^ o), k(c, u, s, o), c = c / 2;
    return r + a;
  }
  l(G, "zxyToTileId");
  function ie(i2) {
    let e = 0, t = 0;
    for (let r = 0; r < 27; r++) {
      let n = (1 << r) * (1 << r);
      if (e + n > i2) return N(r, i2 - e);
      e += n;
    }
    throw new Error("Tile zoom level exceeds max safe number limit (26)");
  }
  l(ie, "tileIdToZxy");
  var J = ((s) => (s[s.Unknown = 0] = "Unknown", s[s.None = 1] = "None", s[s.Gzip = 2] = "Gzip", s[s.Brotli = 3] = "Brotli", s[s.Zstd = 4] = "Zstd", s))(J || {});
  function D(i2, e) {
    return m(this, null, function* () {
      if (e === 1 || e === 0) return i2;
      if (e === 2) {
        if (typeof globalThis.DecompressionStream == "undefined") return decompressSync(new Uint8Array(i2));
        let t = new Response(i2).body;
        if (!t) throw new Error("Failed to read response stream");
        let r = t.pipeThrough(new globalThis.DecompressionStream("gzip"));
        return new Response(r).arrayBuffer();
      }
      throw new Error("Compression method not supported");
    });
  }
  l(D, "defaultDecompress");
  var O = ((o) => (o[o.Unknown = 0] = "Unknown", o[o.Mvt = 1] = "Mvt", o[o.Png = 2] = "Png", o[o.Jpeg = 3] = "Jpeg", o[o.Webp = 4] = "Webp", o[o.Avif = 5] = "Avif", o))(O || {});
  function _(i2) {
    return i2 === 1 ? ".mvt" : i2 === 2 ? ".png" : i2 === 3 ? ".jpg" : i2 === 4 ? ".webp" : i2 === 5 ? ".avif" : "";
  }
  l(_, "tileTypeExt");
  var Y = 127;
  function Q(i2, e) {
    let t = 0, r = i2.length - 1;
    for (; t <= r; ) {
      let n = r + t >> 1, s = e - i2[n].tileId;
      if (s > 0) t = n + 1;
      else if (s < 0) r = n - 1;
      else return i2[n];
    }
    return r >= 0 && (i2[r].runLength === 0 || e - i2[r].tileId < i2[r].runLength) ? i2[r] : null;
  }
  l(Q, "findTile");
  var A = class A2 {
    constructor(e) {
      this.file = e;
    }
    getKey() {
      return this.file.name;
    }
    getBytes(e, t) {
      return m(this, null, function* () {
        return { data: yield this.file.slice(e, e + t).arrayBuffer() };
      });
    }
  };
  l(A, "FileSource");
  var U = class U2 {
    constructor(e, t = new Headers()) {
      this.url = e, this.customHeaders = t, this.mustReload = false;
      let r = "";
      "navigator" in globalThis && (r = globalThis.navigator.userAgent || "");
      let n = r.indexOf("Windows") > -1, s = /Chrome|Chromium|Edg|OPR|Brave/.test(r);
      this.chromeWindowsNoCache = false, n && s && (this.chromeWindowsNoCache = true);
    }
    getKey() {
      return this.url;
    }
    setHeaders(e) {
      this.customHeaders = e;
    }
    getBytes(e, t, r, n) {
      return m(this, null, function* () {
        let s, o;
        r ? o = r : (s = new AbortController(), o = s.signal);
        let a = new Headers(this.customHeaders);
        a.set("range", `bytes=${e}-${e + t - 1}`);
        let u;
        this.mustReload ? u = "reload" : this.chromeWindowsNoCache && (u = "no-store");
        let c = yield fetch(this.url, { signal: o, cache: u, headers: a });
        if (e === 0 && c.status === 416) {
          let y = c.headers.get("Content-Range");
          if (!y || !y.startsWith("bytes */")) throw new Error("Missing content-length on 416 response");
          let f = +y.substr(8);
          c = yield fetch(this.url, { signal: o, cache: "reload", headers: { range: `bytes=0-${f - 1}` } });
        }
        let d = c.headers.get("Etag");
        if (d != null && d.startsWith("W/") && (d = null), c.status === 416 || n && d && d !== n) throw this.mustReload = true, new E(`Server returned non-matching ETag ${n} after one retry. Check browser extensions and servers for issues that may affect correct ETag headers.`);
        if (c.status >= 300) throw new Error(`Bad response code: ${c.status}`);
        let h = c.headers.get("Content-Length");
        if (c.status === 200 && (!h || +h > t)) throw s && s.abort(), new Error("Server returned no content-length header or content-length exceeding request. Check that your storage backend supports HTTP Byte Serving.");
        return { data: yield c.arrayBuffer(), etag: d || void 0, cacheControl: c.headers.get("Cache-Control") || void 0, expires: c.headers.get("Expires") || void 0 };
      });
    }
  };
  l(U, "FetchSource");
  var C = U;
  function g(i2, e) {
    let t = i2.getUint32(e + 4, true), r = i2.getUint32(e + 0, true);
    return t * b(2, 32) + r;
  }
  l(g, "getUint64");
  function X(i2, e) {
    let t = new DataView(i2), r = t.getUint8(7);
    if (r > 3) throw new Error(`Archive is spec version ${r} but this library supports up to spec version 3`);
    return { specVersion: r, rootDirectoryOffset: g(t, 8), rootDirectoryLength: g(t, 16), jsonMetadataOffset: g(t, 24), jsonMetadataLength: g(t, 32), leafDirectoryOffset: g(t, 40), leafDirectoryLength: g(t, 48), tileDataOffset: g(t, 56), tileDataLength: g(t, 64), numAddressedTiles: g(t, 72), numTileEntries: g(t, 80), numTileContents: g(t, 88), clustered: t.getUint8(96) === 1, internalCompression: t.getUint8(97), tileCompression: t.getUint8(98), tileType: t.getUint8(99), minZoom: t.getUint8(100), maxZoom: t.getUint8(101), minLon: t.getInt32(102, true) / 1e7, minLat: t.getInt32(106, true) / 1e7, maxLon: t.getInt32(110, true) / 1e7, maxLat: t.getInt32(114, true) / 1e7, centerZoom: t.getUint8(118), centerLon: t.getInt32(119, true) / 1e7, centerLat: t.getInt32(123, true) / 1e7, etag: e };
  }
  l(X, "bytesToHeader");
  function Z(i2) {
    let e = { buf: new Uint8Array(i2), pos: 0 }, t = v(e), r = [], n = 0;
    for (let s = 0; s < t; s++) {
      let o = v(e);
      r.push({ tileId: n + o, offset: 0, length: 0, runLength: 1 }), n += o;
    }
    for (let s = 0; s < t; s++) r[s].runLength = v(e);
    for (let s = 0; s < t; s++) r[s].length = v(e);
    for (let s = 0; s < t; s++) {
      let o = v(e);
      o === 0 && s > 0 ? r[s].offset = r[s - 1].offset + r[s - 1].length : r[s].offset = o - 1;
    }
    return r;
  }
  l(Z, "deserializeIndex");
  var R = class R2 extends Error {
  };
  l(R, "EtagMismatch");
  var E = R;
  function K(i2, e) {
    return m(this, null, function* () {
      let t = yield i2.getBytes(0, 16384);
      if (new DataView(t.data).getUint16(0, true) !== 19792) throw new Error("Wrong magic number for PMTiles archive");
      let n = t.data.slice(0, Y), s = X(n, t.etag), o = t.data.slice(s.rootDirectoryOffset, s.rootDirectoryOffset + s.rootDirectoryLength), a = `${i2.getKey()}|${s.etag || ""}|${s.rootDirectoryOffset}|${s.rootDirectoryLength}`, u = Z(yield e(o, s.internalCompression));
      return [s, [a, u.length, u]];
    });
  }
  l(K, "getHeaderAndRoot");
  function I(i2, e, t, r, n) {
    return m(this, null, function* () {
      let s = yield i2.getBytes(t, r, void 0, n.etag), o = yield e(s.data, n.internalCompression), a = Z(o);
      if (a.length === 0) throw new Error("Empty directory is invalid");
      return a;
    });
  }
  l(I, "getDirectory");
  var H = class H2 {
    constructor(e = 100, t = true, r = D) {
      this.cache = /* @__PURE__ */ new Map(), this.maxCacheEntries = e, this.counter = 1, this.decompress = r;
    }
    getHeader(e) {
      return m(this, null, function* () {
        let t = e.getKey(), r = this.cache.get(t);
        if (r) return r.lastUsed = this.counter++, r.data;
        let n = yield K(e, this.decompress);
        return n[1] && this.cache.set(n[1][0], { lastUsed: this.counter++, data: n[1][2] }), this.cache.set(t, { lastUsed: this.counter++, data: n[0] }), this.prune(), n[0];
      });
    }
    getDirectory(e, t, r, n) {
      return m(this, null, function* () {
        let s = `${e.getKey()}|${n.etag || ""}|${t}|${r}`, o = this.cache.get(s);
        if (o) return o.lastUsed = this.counter++, o.data;
        let a = yield I(e, this.decompress, t, r, n);
        return this.cache.set(s, { lastUsed: this.counter++, data: a }), this.prune(), a;
      });
    }
    prune() {
      if (this.cache.size > this.maxCacheEntries) {
        let e = 1 / 0, t;
        this.cache.forEach((r, n) => {
          r.lastUsed < e && (e = r.lastUsed, t = n);
        }), t && this.cache.delete(t);
      }
    }
    invalidate(e) {
      return m(this, null, function* () {
        this.cache.delete(e.getKey());
      });
    }
  };
  l(H, "ResolvedValueCache");
  var M = class M2 {
    constructor(e = 100, t = true, r = D) {
      this.cache = /* @__PURE__ */ new Map(), this.invalidations = /* @__PURE__ */ new Map(), this.maxCacheEntries = e, this.counter = 1, this.decompress = r;
    }
    getHeader(e) {
      return m(this, null, function* () {
        let t = e.getKey(), r = this.cache.get(t);
        if (r) return r.lastUsed = this.counter++, yield r.data;
        let n = new Promise((s, o) => {
          K(e, this.decompress).then((a) => {
            a[1] && this.cache.set(a[1][0], { lastUsed: this.counter++, data: Promise.resolve(a[1][2]) }), s(a[0]), this.prune();
          }).catch((a) => {
            o(a);
          });
        });
        return this.cache.set(t, { lastUsed: this.counter++, data: n }), n;
      });
    }
    getDirectory(e, t, r, n) {
      return m(this, null, function* () {
        let s = `${e.getKey()}|${n.etag || ""}|${t}|${r}`, o = this.cache.get(s);
        if (o) return o.lastUsed = this.counter++, yield o.data;
        let a = new Promise((u, c) => {
          I(e, this.decompress, t, r, n).then((d) => {
            u(d), this.prune();
          }).catch((d) => {
            c(d);
          });
        });
        return this.cache.set(s, { lastUsed: this.counter++, data: a }), a;
      });
    }
    prune() {
      if (this.cache.size >= this.maxCacheEntries) {
        let e = 1 / 0, t;
        this.cache.forEach((r, n) => {
          r.lastUsed < e && (e = r.lastUsed, t = n);
        }), t && this.cache.delete(t);
      }
    }
    invalidate(e) {
      return m(this, null, function* () {
        let t = e.getKey();
        if (this.invalidations.get(t)) return yield this.invalidations.get(t);
        this.cache.delete(e.getKey());
        let r = new Promise((n, s) => {
          this.getHeader(e).then((o) => {
            n(), this.invalidations.delete(t);
          }).catch((o) => {
            s(o);
          });
        });
        this.invalidations.set(t, r);
      });
    }
  };
  l(M, "SharedPromiseCache");
  var P = M;
  var B = class B2 {
    constructor(e, t, r) {
      typeof e == "string" ? this.source = new C(e) : this.source = e, r ? this.decompress = r : this.decompress = D, t ? this.cache = t : this.cache = new P();
    }
    getHeader() {
      return m(this, null, function* () {
        return yield this.cache.getHeader(this.source);
      });
    }
    getZxyAttempt(e, t, r, n) {
      return m(this, null, function* () {
        let s = G(e, t, r), o = yield this.cache.getHeader(this.source);
        if (e < o.minZoom || e > o.maxZoom) return;
        let a = o.rootDirectoryOffset, u = o.rootDirectoryLength;
        for (let c = 0; c <= 3; c++) {
          let d = yield this.cache.getDirectory(this.source, a, u, o), h = Q(d, s);
          if (h) {
            if (h.runLength > 0) {
              let p = yield this.source.getBytes(o.tileDataOffset + h.offset, h.length, n, o.etag);
              return { data: yield this.decompress(p.data, o.tileCompression), cacheControl: p.cacheControl, expires: p.expires };
            }
            a = o.leafDirectoryOffset + h.offset, u = h.length;
          } else return;
        }
        throw new Error("Maximum directory depth exceeded");
      });
    }
    getZxy(e, t, r, n) {
      return m(this, null, function* () {
        try {
          return yield this.getZxyAttempt(e, t, r, n);
        } catch (s) {
          if (s instanceof E) return this.cache.invalidate(this.source), yield this.getZxyAttempt(e, t, r, n);
          throw s;
        }
      });
    }
    getMetadataAttempt() {
      return m(this, null, function* () {
        let e = yield this.cache.getHeader(this.source), t = yield this.source.getBytes(e.jsonMetadataOffset, e.jsonMetadataLength, void 0, e.etag), r = yield this.decompress(t.data, e.internalCompression), n = new TextDecoder("utf-8");
        return JSON.parse(n.decode(r));
      });
    }
    getMetadata() {
      return m(this, null, function* () {
        try {
          return yield this.getMetadataAttempt();
        } catch (e) {
          if (e instanceof E) return this.cache.invalidate(this.source), yield this.getMetadataAttempt();
          throw e;
        }
      });
    }
    getTileJson(e) {
      return m(this, null, function* () {
        let t = yield this.getHeader(), r = yield this.getMetadata(), n = _(t.tileType);
        return { tilejson: "3.0.0", scheme: "xyz", tiles: [`${e}/{z}/{x}/{y}${n}`], vector_layers: r.vector_layers, attribution: r.attribution, description: r.description, name: r.name, version: r.version, bounds: [t.minLon, t.minLat, t.maxLon, t.maxLat], center: [t.centerLon, t.centerLat, t.centerZoom], minzoom: t.minZoom, maxzoom: t.maxZoom };
      });
    }
  };
  l(B, "PMTiles");
  var x = B;
  function Point(x22, y) {
    this.x = x22;
    this.y = y;
  }
  Point.prototype = {
    /**
     * Clone this point, returning a new point that can be modified
     * without affecting the old one.
     * @return {Point} the clone
     */
    clone() {
      return new Point(this.x, this.y);
    },
    /**
     * Add this point's x & y coordinates to another point,
     * yielding a new point.
     * @param {Point} p the other point
     * @return {Point} output point
     */
    add(p) {
      return this.clone()._add(p);
    },
    /**
     * Subtract this point's x & y coordinates to from point,
     * yielding a new point.
     * @param {Point} p the other point
     * @return {Point} output point
     */
    sub(p) {
      return this.clone()._sub(p);
    },
    /**
     * Multiply this point's x & y coordinates by point,
     * yielding a new point.
     * @param {Point} p the other point
     * @return {Point} output point
     */
    multByPoint(p) {
      return this.clone()._multByPoint(p);
    },
    /**
     * Divide this point's x & y coordinates by point,
     * yielding a new point.
     * @param {Point} p the other point
     * @return {Point} output point
     */
    divByPoint(p) {
      return this.clone()._divByPoint(p);
    },
    /**
     * Multiply this point's x & y coordinates by a factor,
     * yielding a new point.
     * @param {number} k factor
     * @return {Point} output point
     */
    mult(k2) {
      return this.clone()._mult(k2);
    },
    /**
     * Divide this point's x & y coordinates by a factor,
     * yielding a new point.
     * @param {number} k factor
     * @return {Point} output point
     */
    div(k2) {
      return this.clone()._div(k2);
    },
    /**
     * Rotate this point around the 0, 0 origin by an angle a,
     * given in radians
     * @param {number} a angle to rotate around, in radians
     * @return {Point} output point
     */
    rotate(a) {
      return this.clone()._rotate(a);
    },
    /**
     * Rotate this point around p point by an angle a,
     * given in radians
     * @param {number} a angle to rotate around, in radians
     * @param {Point} p Point to rotate around
     * @return {Point} output point
     */
    rotateAround(a, p) {
      return this.clone()._rotateAround(a, p);
    },
    /**
     * Multiply this point by a 4x1 transformation matrix
     * @param {[number, number, number, number]} m transformation matrix
     * @return {Point} output point
     */
    matMult(m2) {
      return this.clone()._matMult(m2);
    },
    /**
     * Calculate this point but as a unit vector from 0, 0, meaning
     * that the distance from the resulting point to the 0, 0
     * coordinate will be equal to 1 and the angle from the resulting
     * point to the 0, 0 coordinate will be the same as before.
     * @return {Point} unit vector point
     */
    unit() {
      return this.clone()._unit();
    },
    /**
     * Compute a perpendicular point, where the new y coordinate
     * is the old x coordinate and the new x coordinate is the old y
     * coordinate multiplied by -1
     * @return {Point} perpendicular point
     */
    perp() {
      return this.clone()._perp();
    },
    /**
     * Return a version of this point with the x & y coordinates
     * rounded to integers.
     * @return {Point} rounded point
     */
    round() {
      return this.clone()._round();
    },
    /**
     * Return the magnitude of this point: this is the Euclidean
     * distance from the 0, 0 coordinate to this point's x and y
     * coordinates.
     * @return {number} magnitude
     */
    mag() {
      return Math.sqrt(this.x * this.x + this.y * this.y);
    },
    /**
     * Judge whether this point is equal to another point, returning
     * true or false.
     * @param {Point} other the other point
     * @return {boolean} whether the points are equal
     */
    equals(other) {
      return this.x === other.x && this.y === other.y;
    },
    /**
     * Calculate the distance from this point to another point
     * @param {Point} p the other point
     * @return {number} distance
     */
    dist(p) {
      return Math.sqrt(this.distSqr(p));
    },
    /**
     * Calculate the distance from this point to another point,
     * without the square root step. Useful if you're comparing
     * relative distances.
     * @param {Point} p the other point
     * @return {number} distance
     */
    distSqr(p) {
      const dx = p.x - this.x, dy = p.y - this.y;
      return dx * dx + dy * dy;
    },
    /**
     * Get the angle from the 0, 0 coordinate to this point, in radians
     * coordinates.
     * @return {number} angle
     */
    angle() {
      return Math.atan2(this.y, this.x);
    },
    /**
     * Get the angle from this point to another point, in radians
     * @param {Point} b the other point
     * @return {number} angle
     */
    angleTo(b2) {
      return Math.atan2(this.y - b2.y, this.x - b2.x);
    },
    /**
     * Get the angle between this point and another point, in radians
     * @param {Point} b the other point
     * @return {number} angle
     */
    angleWith(b2) {
      return this.angleWithSep(b2.x, b2.y);
    },
    /**
     * Find the angle of the two vectors, solving the formula for
     * the cross product a x b = |a||b|sin(θ) for θ.
     * @param {number} x the x-coordinate
     * @param {number} y the y-coordinate
     * @return {number} the angle in radians
     */
    angleWithSep(x22, y) {
      return Math.atan2(
        this.x * y - this.y * x22,
        this.x * x22 + this.y * y
      );
    },
    /** @param {[number, number, number, number]} m */
    _matMult(m2) {
      const x22 = m2[0] * this.x + m2[1] * this.y, y = m2[2] * this.x + m2[3] * this.y;
      this.x = x22;
      this.y = y;
      return this;
    },
    /** @param {Point} p */
    _add(p) {
      this.x += p.x;
      this.y += p.y;
      return this;
    },
    /** @param {Point} p */
    _sub(p) {
      this.x -= p.x;
      this.y -= p.y;
      return this;
    },
    /** @param {number} k */
    _mult(k2) {
      this.x *= k2;
      this.y *= k2;
      return this;
    },
    /** @param {number} k */
    _div(k2) {
      this.x /= k2;
      this.y /= k2;
      return this;
    },
    /** @param {Point} p */
    _multByPoint(p) {
      this.x *= p.x;
      this.y *= p.y;
      return this;
    },
    /** @param {Point} p */
    _divByPoint(p) {
      this.x /= p.x;
      this.y /= p.y;
      return this;
    },
    _unit() {
      this._div(this.mag());
      return this;
    },
    _perp() {
      const y = this.y;
      this.y = this.x;
      this.x = -y;
      return this;
    },
    /** @param {number} angle */
    _rotate(angle) {
      const cos = Math.cos(angle), sin = Math.sin(angle), x22 = cos * this.x - sin * this.y, y = sin * this.x + cos * this.y;
      this.x = x22;
      this.y = y;
      return this;
    },
    /**
     * @param {number} angle
     * @param {Point} p
     */
    _rotateAround(angle, p) {
      const cos = Math.cos(angle), sin = Math.sin(angle), x22 = p.x + cos * (this.x - p.x) - sin * (this.y - p.y), y = p.y + sin * (this.x - p.x) + cos * (this.y - p.y);
      this.x = x22;
      this.y = y;
      return this;
    },
    _round() {
      this.x = Math.round(this.x);
      this.y = Math.round(this.y);
      return this;
    },
    constructor: Point
  };
  Point.convert = function(p) {
    if (p instanceof Point) {
      return (
        /** @type {Point} */
        p
      );
    }
    if (Array.isArray(p)) {
      return new Point(+p[0], +p[1]);
    }
    if (p.x !== void 0 && p.y !== void 0) {
      return new Point(+p.x, +p.y);
    }
    throw new Error("Expected [x, y] or {x, y} point format");
  };
  var VectorTileFeature = class {
    /**
     * @param {Pbf} pbf
     * @param {number} end
     * @param {number} extent
     * @param {string[]} keys
     * @param {(number | string | boolean)[]} values
     */
    constructor(pbf, end, extent, keys, values) {
      this.properties = {};
      this.extent = extent;
      this.type = 0;
      this.id = void 0;
      this._pbf = pbf;
      this._geometry = -1;
      this._keys = keys;
      this._values = values;
      pbf.readFields(readFeature, this, end);
    }
    loadGeometry() {
      const pbf = this._pbf;
      pbf.pos = this._geometry;
      const end = pbf.readVarint() + pbf.pos;
      const lines = [];
      let line;
      let cmd = 1;
      let length = 0;
      let x22 = 0;
      let y = 0;
      while (pbf.pos < end) {
        if (length <= 0) {
          const cmdLen = pbf.readVarint();
          cmd = cmdLen & 7;
          length = cmdLen >> 3;
        }
        length--;
        if (cmd === 1 || cmd === 2) {
          x22 += pbf.readSVarint();
          y += pbf.readSVarint();
          if (cmd === 1) {
            if (line) lines.push(line);
            line = [];
          }
          if (line) line.push(new Point(x22, y));
        } else if (cmd === 7) {
          if (line) {
            line.push(line[0].clone());
          }
        } else {
          throw new Error(`unknown command ${cmd}`);
        }
      }
      if (line) lines.push(line);
      return lines;
    }
    bbox() {
      const pbf = this._pbf;
      pbf.pos = this._geometry;
      const end = pbf.readVarint() + pbf.pos;
      let cmd = 1, length = 0, x22 = 0, y = 0, x1 = Infinity, x222 = -Infinity, y1 = Infinity, y2 = -Infinity;
      while (pbf.pos < end) {
        if (length <= 0) {
          const cmdLen = pbf.readVarint();
          cmd = cmdLen & 7;
          length = cmdLen >> 3;
        }
        length--;
        if (cmd === 1 || cmd === 2) {
          x22 += pbf.readSVarint();
          y += pbf.readSVarint();
          if (x22 < x1) x1 = x22;
          if (x22 > x222) x222 = x22;
          if (y < y1) y1 = y;
          if (y > y2) y2 = y;
        } else if (cmd !== 7) {
          throw new Error(`unknown command ${cmd}`);
        }
      }
      return [x1, y1, x222, y2];
    }
    /**
     * @param {number} x
     * @param {number} y
     * @param {number} z
     * @return {Feature}
     */
    toGeoJSON(x22, y, z2) {
      const size = this.extent * Math.pow(2, z2), x0 = this.extent * x22, y0 = this.extent * y, vtCoords = this.loadGeometry();
      function projectPoint(p) {
        return [
          (p.x + x0) * 360 / size - 180,
          360 / Math.PI * Math.atan(Math.exp((1 - (p.y + y0) * 2 / size) * Math.PI)) - 90
        ];
      }
      function projectLine(line) {
        return line.map(projectPoint);
      }
      let geometry;
      if (this.type === 1) {
        const points = [];
        for (const line of vtCoords) {
          points.push(line[0]);
        }
        const coordinates = projectLine(points);
        geometry = points.length === 1 ? { type: "Point", coordinates: coordinates[0] } : { type: "MultiPoint", coordinates };
      } else if (this.type === 2) {
        const coordinates = vtCoords.map(projectLine);
        geometry = coordinates.length === 1 ? { type: "LineString", coordinates: coordinates[0] } : { type: "MultiLineString", coordinates };
      } else if (this.type === 3) {
        const polygons = classifyRings(vtCoords);
        const coordinates = [];
        for (const polygon of polygons) {
          coordinates.push(polygon.map(projectLine));
        }
        geometry = coordinates.length === 1 ? { type: "Polygon", coordinates: coordinates[0] } : { type: "MultiPolygon", coordinates };
      } else {
        throw new Error("unknown feature type");
      }
      const result = {
        type: "Feature",
        geometry,
        properties: this.properties
      };
      if (this.id != null) {
        result.id = this.id;
      }
      return result;
    }
  };
  VectorTileFeature.types = ["Unknown", "Point", "LineString", "Polygon"];
  function readFeature(tag, feature, pbf) {
    if (tag === 1) feature.id = pbf.readVarint();
    else if (tag === 2) readTag(pbf, feature);
    else if (tag === 3) feature.type = /** @type {0 | 1 | 2 | 3} */
    pbf.readVarint();
    else if (tag === 4) feature._geometry = pbf.pos;
  }
  function readTag(pbf, feature) {
    const end = pbf.readVarint() + pbf.pos;
    while (pbf.pos < end) {
      const key = feature._keys[pbf.readVarint()];
      const value = feature._values[pbf.readVarint()];
      feature.properties[key] = value;
    }
  }
  function classifyRings(rings) {
    const len = rings.length;
    if (len <= 1) return [rings];
    const polygons = [];
    let polygon, ccw;
    for (let i2 = 0; i2 < len; i2++) {
      const area = signedArea(rings[i2]);
      if (area === 0) continue;
      if (ccw === void 0) ccw = area < 0;
      if (ccw === area < 0) {
        if (polygon) polygons.push(polygon);
        polygon = [rings[i2]];
      } else if (polygon) {
        polygon.push(rings[i2]);
      }
    }
    if (polygon) polygons.push(polygon);
    return polygons;
  }
  function signedArea(ring) {
    let sum = 0;
    for (let i2 = 0, len = ring.length, j2 = len - 1, p1, p2; i2 < len; j2 = i2++) {
      p1 = ring[i2];
      p2 = ring[j2];
      sum += (p2.x - p1.x) * (p1.y + p2.y);
    }
    return sum;
  }
  var VectorTileLayer = class {
    /**
     * @param {Pbf} pbf
     * @param {number} [end]
     */
    constructor(pbf, end) {
      this.version = 1;
      this.name = "";
      this.extent = 4096;
      this.length = 0;
      this._pbf = pbf;
      this._keys = [];
      this._values = [];
      this._features = [];
      pbf.readFields(readLayer, this, end);
      this.length = this._features.length;
    }
    /** return feature `i` from this layer as a `VectorTileFeature`
     * @param {number} i
     */
    feature(i2) {
      if (i2 < 0 || i2 >= this._features.length) throw new Error("feature index out of bounds");
      this._pbf.pos = this._features[i2];
      const end = this._pbf.readVarint() + this._pbf.pos;
      return new VectorTileFeature(this._pbf, end, this.extent, this._keys, this._values);
    }
  };
  function readLayer(tag, layer, pbf) {
    if (tag === 15) layer.version = pbf.readVarint();
    else if (tag === 1) layer.name = pbf.readString();
    else if (tag === 5) layer.extent = pbf.readVarint();
    else if (tag === 2) layer._features.push(pbf.pos);
    else if (tag === 3) layer._keys.push(pbf.readString());
    else if (tag === 4) layer._values.push(readValueMessage(pbf));
  }
  function readValueMessage(pbf) {
    let value = null;
    const end = pbf.readVarint() + pbf.pos;
    while (pbf.pos < end) {
      const tag = pbf.readVarint() >> 3;
      value = tag === 1 ? pbf.readString() : tag === 2 ? pbf.readFloat() : tag === 3 ? pbf.readDouble() : tag === 4 ? pbf.readVarint64() : tag === 5 ? pbf.readVarint() : tag === 6 ? pbf.readSVarint() : tag === 7 ? pbf.readBoolean() : null;
    }
    if (value == null) {
      throw new Error("unknown feature value");
    }
    return value;
  }
  var VectorTile = class {
    /**
     * @param {Pbf} pbf
     * @param {number} [end]
     */
    constructor(pbf, end) {
      this.layers = pbf.readFields(readTile, {}, end);
    }
  };
  function readTile(tag, layers, pbf) {
    if (tag === 3) {
      const layer = new VectorTileLayer(pbf, pbf.readVarint() + pbf.pos);
      if (layer.length) layers[layer.name] = layer;
    }
  }
  var SHIFT_LEFT_32 = (1 << 16) * (1 << 16);
  var SHIFT_RIGHT_32 = 1 / SHIFT_LEFT_32;
  var TEXT_DECODER_MIN_LENGTH = 12;
  var utf8TextDecoder = typeof TextDecoder === "undefined" ? null : new TextDecoder("utf-8");
  var PBF_VARINT = 0;
  var PBF_FIXED64 = 1;
  var PBF_BYTES = 2;
  var PBF_FIXED32 = 5;
  var Pbf = class {
    /**
     * @param {Uint8Array | ArrayBuffer} [buf]
     */
    constructor(buf = new Uint8Array(16)) {
      this.buf = ArrayBuffer.isView(buf) ? buf : new Uint8Array(buf);
      this.dataView = new DataView(this.buf.buffer);
      this.pos = 0;
      this.type = 0;
      this.length = this.buf.length;
    }
    // === READING =================================================================
    /**
     * @template T
     * @param {(tag: number, result: T, pbf: Pbf) => void} readField
     * @param {T} result
     * @param {number} [end]
     */
    readFields(readField, result, end = this.length) {
      while (this.pos < end) {
        const val = this.readVarint(), tag = val >> 3, startPos = this.pos;
        this.type = val & 7;
        readField(tag, result, this);
        if (this.pos === startPos) this.skip(val);
      }
      return result;
    }
    /**
     * @template T
     * @param {(tag: number, result: T, pbf: Pbf) => void} readField
     * @param {T} result
     */
    readMessage(readField, result) {
      return this.readFields(readField, result, this.readVarint() + this.pos);
    }
    readFixed32() {
      const val = this.dataView.getUint32(this.pos, true);
      this.pos += 4;
      return val;
    }
    readSFixed32() {
      const val = this.dataView.getInt32(this.pos, true);
      this.pos += 4;
      return val;
    }
    // 64-bit int handling is based on github.com/dpw/node-buffer-more-ints (MIT-licensed)
    readFixed64() {
      const val = this.dataView.getUint32(this.pos, true) + this.dataView.getUint32(this.pos + 4, true) * SHIFT_LEFT_32;
      this.pos += 8;
      return val;
    }
    readSFixed64() {
      const val = this.dataView.getUint32(this.pos, true) + this.dataView.getInt32(this.pos + 4, true) * SHIFT_LEFT_32;
      this.pos += 8;
      return val;
    }
    readFloat() {
      const val = this.dataView.getFloat32(this.pos, true);
      this.pos += 4;
      return val;
    }
    readDouble() {
      const val = this.dataView.getFloat64(this.pos, true);
      this.pos += 8;
      return val;
    }
    /**
     * @param {boolean} [isSigned]
     */
    readVarint(isSigned) {
      const buf = this.buf;
      let val, b2;
      b2 = buf[this.pos++];
      val = b2 & 127;
      if (b2 < 128) return val;
      b2 = buf[this.pos++];
      val |= (b2 & 127) << 7;
      if (b2 < 128) return val;
      b2 = buf[this.pos++];
      val |= (b2 & 127) << 14;
      if (b2 < 128) return val;
      b2 = buf[this.pos++];
      val |= (b2 & 127) << 21;
      if (b2 < 128) return val;
      b2 = buf[this.pos];
      val |= (b2 & 15) << 28;
      return readVarintRemainder(val, isSigned, this);
    }
    readVarint64() {
      return this.readVarint(true);
    }
    readSVarint() {
      const num = this.readVarint();
      return num % 2 === 1 ? (num + 1) / -2 : num / 2;
    }
    readBoolean() {
      return Boolean(this.readVarint());
    }
    readString() {
      const end = this.readVarint() + this.pos;
      const pos = this.pos;
      this.pos = end;
      if (end - pos >= TEXT_DECODER_MIN_LENGTH && utf8TextDecoder) {
        return utf8TextDecoder.decode(this.buf.subarray(pos, end));
      }
      return readUtf8(this.buf, pos, end);
    }
    readBytes() {
      const end = this.readVarint() + this.pos, buffer = this.buf.subarray(this.pos, end);
      this.pos = end;
      return buffer;
    }
    // verbose for performance reasons; doesn't affect gzipped size
    /**
     * @param {number[]} [arr]
     * @param {boolean} [isSigned]
     */
    readPackedVarint(arr = [], isSigned) {
      const end = this.readPackedEnd();
      while (this.pos < end) arr.push(this.readVarint(isSigned));
      return arr;
    }
    /** @param {number[]} [arr] */
    readPackedSVarint(arr = []) {
      const end = this.readPackedEnd();
      while (this.pos < end) arr.push(this.readSVarint());
      return arr;
    }
    /** @param {boolean[]} [arr] */
    readPackedBoolean(arr = []) {
      const end = this.readPackedEnd();
      while (this.pos < end) arr.push(this.readBoolean());
      return arr;
    }
    /** @param {number[]} [arr] */
    readPackedFloat(arr = []) {
      const end = this.readPackedEnd();
      while (this.pos < end) arr.push(this.readFloat());
      return arr;
    }
    /** @param {number[]} [arr] */
    readPackedDouble(arr = []) {
      const end = this.readPackedEnd();
      while (this.pos < end) arr.push(this.readDouble());
      return arr;
    }
    /** @param {number[]} [arr] */
    readPackedFixed32(arr = []) {
      const end = this.readPackedEnd();
      while (this.pos < end) arr.push(this.readFixed32());
      return arr;
    }
    /** @param {number[]} [arr] */
    readPackedSFixed32(arr = []) {
      const end = this.readPackedEnd();
      while (this.pos < end) arr.push(this.readSFixed32());
      return arr;
    }
    /** @param {number[]} [arr] */
    readPackedFixed64(arr = []) {
      const end = this.readPackedEnd();
      while (this.pos < end) arr.push(this.readFixed64());
      return arr;
    }
    /** @param {number[]} [arr] */
    readPackedSFixed64(arr = []) {
      const end = this.readPackedEnd();
      while (this.pos < end) arr.push(this.readSFixed64());
      return arr;
    }
    readPackedEnd() {
      return this.type === PBF_BYTES ? this.readVarint() + this.pos : this.pos + 1;
    }
    /** @param {number} val */
    skip(val) {
      const type = val & 7;
      if (type === PBF_VARINT) while (this.buf[this.pos++] > 127) {
      }
      else if (type === PBF_BYTES) this.pos = this.readVarint() + this.pos;
      else if (type === PBF_FIXED32) this.pos += 4;
      else if (type === PBF_FIXED64) this.pos += 8;
      else throw new Error(`Unimplemented type: ${type}`);
    }
    // === WRITING =================================================================
    /**
     * @param {number} tag
     * @param {number} type
     */
    writeTag(tag, type) {
      this.writeVarint(tag << 3 | type);
    }
    /** @param {number} min */
    realloc(min) {
      let length = this.length || 16;
      while (length < this.pos + min) length *= 2;
      if (length !== this.length) {
        const buf = new Uint8Array(length);
        buf.set(this.buf);
        this.buf = buf;
        this.dataView = new DataView(buf.buffer);
        this.length = length;
      }
    }
    finish() {
      this.length = this.pos;
      this.pos = 0;
      return this.buf.subarray(0, this.length);
    }
    /** @param {number} val */
    writeFixed32(val) {
      this.realloc(4);
      this.dataView.setInt32(this.pos, val, true);
      this.pos += 4;
    }
    /** @param {number} val */
    writeSFixed32(val) {
      this.realloc(4);
      this.dataView.setInt32(this.pos, val, true);
      this.pos += 4;
    }
    /** @param {number} val */
    writeFixed64(val) {
      this.realloc(8);
      this.dataView.setInt32(this.pos, val & -1, true);
      this.dataView.setInt32(this.pos + 4, Math.floor(val * SHIFT_RIGHT_32), true);
      this.pos += 8;
    }
    /** @param {number} val */
    writeSFixed64(val) {
      this.realloc(8);
      this.dataView.setInt32(this.pos, val & -1, true);
      this.dataView.setInt32(this.pos + 4, Math.floor(val * SHIFT_RIGHT_32), true);
      this.pos += 8;
    }
    /** @param {number} val */
    writeVarint(val) {
      val = +val || 0;
      if (val > 268435455 || val < 0) {
        writeBigVarint(val, this);
        return;
      }
      this.realloc(4);
      this.buf[this.pos++] = val & 127 | (val > 127 ? 128 : 0);
      if (val <= 127) return;
      this.buf[this.pos++] = (val >>>= 7) & 127 | (val > 127 ? 128 : 0);
      if (val <= 127) return;
      this.buf[this.pos++] = (val >>>= 7) & 127 | (val > 127 ? 128 : 0);
      if (val <= 127) return;
      this.buf[this.pos++] = val >>> 7 & 127;
    }
    /** @param {number} val */
    writeSVarint(val) {
      this.writeVarint(val < 0 ? -val * 2 - 1 : val * 2);
    }
    /** @param {boolean} val */
    writeBoolean(val) {
      this.writeVarint(+val);
    }
    /** @param {string} str */
    writeString(str) {
      str = String(str);
      this.realloc(str.length * 4);
      this.pos++;
      const startPos = this.pos;
      this.pos = writeUtf8(this.buf, str, this.pos);
      const len = this.pos - startPos;
      if (len >= 128) makeRoomForExtraLength(startPos, len, this);
      this.pos = startPos - 1;
      this.writeVarint(len);
      this.pos += len;
    }
    /** @param {number} val */
    writeFloat(val) {
      this.realloc(4);
      this.dataView.setFloat32(this.pos, val, true);
      this.pos += 4;
    }
    /** @param {number} val */
    writeDouble(val) {
      this.realloc(8);
      this.dataView.setFloat64(this.pos, val, true);
      this.pos += 8;
    }
    /** @param {Uint8Array} buffer */
    writeBytes(buffer) {
      const len = buffer.length;
      this.writeVarint(len);
      this.realloc(len);
      for (let i2 = 0; i2 < len; i2++) this.buf[this.pos++] = buffer[i2];
    }
    /**
     * @template T
     * @param {(obj: T, pbf: Pbf) => void} fn
     * @param {T} obj
     */
    writeRawMessage(fn, obj) {
      this.pos++;
      const startPos = this.pos;
      fn(obj, this);
      const len = this.pos - startPos;
      if (len >= 128) makeRoomForExtraLength(startPos, len, this);
      this.pos = startPos - 1;
      this.writeVarint(len);
      this.pos += len;
    }
    /**
     * @template T
     * @param {number} tag
     * @param {(obj: T, pbf: Pbf) => void} fn
     * @param {T} obj
     */
    writeMessage(tag, fn, obj) {
      this.writeTag(tag, PBF_BYTES);
      this.writeRawMessage(fn, obj);
    }
    /**
     * @param {number} tag
     * @param {number[]} arr
     */
    writePackedVarint(tag, arr) {
      if (arr.length) this.writeMessage(tag, writePackedVarint, arr);
    }
    /**
     * @param {number} tag
     * @param {number[]} arr
     */
    writePackedSVarint(tag, arr) {
      if (arr.length) this.writeMessage(tag, writePackedSVarint, arr);
    }
    /**
     * @param {number} tag
     * @param {boolean[]} arr
     */
    writePackedBoolean(tag, arr) {
      if (arr.length) this.writeMessage(tag, writePackedBoolean, arr);
    }
    /**
     * @param {number} tag
     * @param {number[]} arr
     */
    writePackedFloat(tag, arr) {
      if (arr.length) this.writeMessage(tag, writePackedFloat, arr);
    }
    /**
     * @param {number} tag
     * @param {number[]} arr
     */
    writePackedDouble(tag, arr) {
      if (arr.length) this.writeMessage(tag, writePackedDouble, arr);
    }
    /**
     * @param {number} tag
     * @param {number[]} arr
     */
    writePackedFixed32(tag, arr) {
      if (arr.length) this.writeMessage(tag, writePackedFixed32, arr);
    }
    /**
     * @param {number} tag
     * @param {number[]} arr
     */
    writePackedSFixed32(tag, arr) {
      if (arr.length) this.writeMessage(tag, writePackedSFixed32, arr);
    }
    /**
     * @param {number} tag
     * @param {number[]} arr
     */
    writePackedFixed64(tag, arr) {
      if (arr.length) this.writeMessage(tag, writePackedFixed64, arr);
    }
    /**
     * @param {number} tag
     * @param {number[]} arr
     */
    writePackedSFixed64(tag, arr) {
      if (arr.length) this.writeMessage(tag, writePackedSFixed64, arr);
    }
    /**
     * @param {number} tag
     * @param {Uint8Array} buffer
     */
    writeBytesField(tag, buffer) {
      this.writeTag(tag, PBF_BYTES);
      this.writeBytes(buffer);
    }
    /**
     * @param {number} tag
     * @param {number} val
     */
    writeFixed32Field(tag, val) {
      this.writeTag(tag, PBF_FIXED32);
      this.writeFixed32(val);
    }
    /**
     * @param {number} tag
     * @param {number} val
     */
    writeSFixed32Field(tag, val) {
      this.writeTag(tag, PBF_FIXED32);
      this.writeSFixed32(val);
    }
    /**
     * @param {number} tag
     * @param {number} val
     */
    writeFixed64Field(tag, val) {
      this.writeTag(tag, PBF_FIXED64);
      this.writeFixed64(val);
    }
    /**
     * @param {number} tag
     * @param {number} val
     */
    writeSFixed64Field(tag, val) {
      this.writeTag(tag, PBF_FIXED64);
      this.writeSFixed64(val);
    }
    /**
     * @param {number} tag
     * @param {number} val
     */
    writeVarintField(tag, val) {
      this.writeTag(tag, PBF_VARINT);
      this.writeVarint(val);
    }
    /**
     * @param {number} tag
     * @param {number} val
     */
    writeSVarintField(tag, val) {
      this.writeTag(tag, PBF_VARINT);
      this.writeSVarint(val);
    }
    /**
     * @param {number} tag
     * @param {string} str
     */
    writeStringField(tag, str) {
      this.writeTag(tag, PBF_BYTES);
      this.writeString(str);
    }
    /**
     * @param {number} tag
     * @param {number} val
     */
    writeFloatField(tag, val) {
      this.writeTag(tag, PBF_FIXED32);
      this.writeFloat(val);
    }
    /**
     * @param {number} tag
     * @param {number} val
     */
    writeDoubleField(tag, val) {
      this.writeTag(tag, PBF_FIXED64);
      this.writeDouble(val);
    }
    /**
     * @param {number} tag
     * @param {boolean} val
     */
    writeBooleanField(tag, val) {
      this.writeVarintField(tag, +val);
    }
  };
  function readVarintRemainder(l2, s, p) {
    const buf = p.buf;
    let h, b2;
    b2 = buf[p.pos++];
    h = (b2 & 112) >> 4;
    if (b2 < 128) return toNum(l2, h, s);
    b2 = buf[p.pos++];
    h |= (b2 & 127) << 3;
    if (b2 < 128) return toNum(l2, h, s);
    b2 = buf[p.pos++];
    h |= (b2 & 127) << 10;
    if (b2 < 128) return toNum(l2, h, s);
    b2 = buf[p.pos++];
    h |= (b2 & 127) << 17;
    if (b2 < 128) return toNum(l2, h, s);
    b2 = buf[p.pos++];
    h |= (b2 & 127) << 24;
    if (b2 < 128) return toNum(l2, h, s);
    b2 = buf[p.pos++];
    h |= (b2 & 1) << 31;
    if (b2 < 128) return toNum(l2, h, s);
    throw new Error("Expected varint not more than 10 bytes");
  }
  function toNum(low, high, isSigned) {
    return isSigned ? high * 4294967296 + (low >>> 0) : (high >>> 0) * 4294967296 + (low >>> 0);
  }
  function writeBigVarint(val, pbf) {
    let low, high;
    if (val >= 0) {
      low = val % 4294967296 | 0;
      high = val / 4294967296 | 0;
    } else {
      low = ~(-val % 4294967296);
      high = ~(-val / 4294967296);
      if (low ^ 4294967295) {
        low = low + 1 | 0;
      } else {
        low = 0;
        high = high + 1 | 0;
      }
    }
    if (val >= 18446744073709552e3 || val < -18446744073709552e3) {
      throw new Error("Given varint doesn't fit into 10 bytes");
    }
    pbf.realloc(10);
    writeBigVarintLow(low, high, pbf);
    writeBigVarintHigh(high, pbf);
  }
  function writeBigVarintLow(low, high, pbf) {
    pbf.buf[pbf.pos++] = low & 127 | 128;
    low >>>= 7;
    pbf.buf[pbf.pos++] = low & 127 | 128;
    low >>>= 7;
    pbf.buf[pbf.pos++] = low & 127 | 128;
    low >>>= 7;
    pbf.buf[pbf.pos++] = low & 127 | 128;
    low >>>= 7;
    pbf.buf[pbf.pos] = low & 127;
  }
  function writeBigVarintHigh(high, pbf) {
    const lsb = (high & 7) << 4;
    pbf.buf[pbf.pos++] |= lsb | ((high >>>= 3) ? 128 : 0);
    if (!high) return;
    pbf.buf[pbf.pos++] = high & 127 | ((high >>>= 7) ? 128 : 0);
    if (!high) return;
    pbf.buf[pbf.pos++] = high & 127 | ((high >>>= 7) ? 128 : 0);
    if (!high) return;
    pbf.buf[pbf.pos++] = high & 127 | ((high >>>= 7) ? 128 : 0);
    if (!high) return;
    pbf.buf[pbf.pos++] = high & 127 | ((high >>>= 7) ? 128 : 0);
    if (!high) return;
    pbf.buf[pbf.pos++] = high & 127;
  }
  function makeRoomForExtraLength(startPos, len, pbf) {
    const extraLen = len <= 16383 ? 1 : len <= 2097151 ? 2 : len <= 268435455 ? 3 : Math.floor(Math.log(len) / (Math.LN2 * 7));
    pbf.realloc(extraLen);
    for (let i2 = pbf.pos - 1; i2 >= startPos; i2--) pbf.buf[i2 + extraLen] = pbf.buf[i2];
  }
  function writePackedVarint(arr, pbf) {
    for (let i2 = 0; i2 < arr.length; i2++) pbf.writeVarint(arr[i2]);
  }
  function writePackedSVarint(arr, pbf) {
    for (let i2 = 0; i2 < arr.length; i2++) pbf.writeSVarint(arr[i2]);
  }
  function writePackedFloat(arr, pbf) {
    for (let i2 = 0; i2 < arr.length; i2++) pbf.writeFloat(arr[i2]);
  }
  function writePackedDouble(arr, pbf) {
    for (let i2 = 0; i2 < arr.length; i2++) pbf.writeDouble(arr[i2]);
  }
  function writePackedBoolean(arr, pbf) {
    for (let i2 = 0; i2 < arr.length; i2++) pbf.writeBoolean(arr[i2]);
  }
  function writePackedFixed32(arr, pbf) {
    for (let i2 = 0; i2 < arr.length; i2++) pbf.writeFixed32(arr[i2]);
  }
  function writePackedSFixed32(arr, pbf) {
    for (let i2 = 0; i2 < arr.length; i2++) pbf.writeSFixed32(arr[i2]);
  }
  function writePackedFixed64(arr, pbf) {
    for (let i2 = 0; i2 < arr.length; i2++) pbf.writeFixed64(arr[i2]);
  }
  function writePackedSFixed64(arr, pbf) {
    for (let i2 = 0; i2 < arr.length; i2++) pbf.writeSFixed64(arr[i2]);
  }
  function readUtf8(buf, pos, end) {
    let str = "";
    let i2 = pos;
    while (i2 < end) {
      const b0 = buf[i2];
      let c = null;
      let bytesPerSequence = b0 > 239 ? 4 : b0 > 223 ? 3 : b0 > 191 ? 2 : 1;
      if (i2 + bytesPerSequence > end) break;
      let b1, b2, b3;
      if (bytesPerSequence === 1) {
        if (b0 < 128) {
          c = b0;
        }
      } else if (bytesPerSequence === 2) {
        b1 = buf[i2 + 1];
        if ((b1 & 192) === 128) {
          c = (b0 & 31) << 6 | b1 & 63;
          if (c <= 127) {
            c = null;
          }
        }
      } else if (bytesPerSequence === 3) {
        b1 = buf[i2 + 1];
        b2 = buf[i2 + 2];
        if ((b1 & 192) === 128 && (b2 & 192) === 128) {
          c = (b0 & 15) << 12 | (b1 & 63) << 6 | b2 & 63;
          if (c <= 2047 || c >= 55296 && c <= 57343) {
            c = null;
          }
        }
      } else if (bytesPerSequence === 4) {
        b1 = buf[i2 + 1];
        b2 = buf[i2 + 2];
        b3 = buf[i2 + 3];
        if ((b1 & 192) === 128 && (b2 & 192) === 128 && (b3 & 192) === 128) {
          c = (b0 & 15) << 18 | (b1 & 63) << 12 | (b2 & 63) << 6 | b3 & 63;
          if (c <= 65535 || c >= 1114112) {
            c = null;
          }
        }
      }
      if (c === null) {
        c = 65533;
        bytesPerSequence = 1;
      } else if (c > 65535) {
        c -= 65536;
        str += String.fromCharCode(c >>> 10 & 1023 | 55296);
        c = 56320 | c & 1023;
      }
      str += String.fromCharCode(c);
      i2 += bytesPerSequence;
    }
    return str;
  }
  function writeUtf8(buf, str, pos) {
    for (let i2 = 0, c, lead; i2 < str.length; i2++) {
      c = str.charCodeAt(i2);
      if (c > 55295 && c < 57344) {
        if (lead) {
          if (c < 56320) {
            buf[pos++] = 239;
            buf[pos++] = 191;
            buf[pos++] = 189;
            lead = c;
            continue;
          } else {
            c = lead - 55296 << 10 | c - 56320 | 65536;
            lead = null;
          }
        } else {
          if (c > 56319 || i2 + 1 === str.length) {
            buf[pos++] = 239;
            buf[pos++] = 191;
            buf[pos++] = 189;
          } else {
            lead = c;
          }
          continue;
        }
      } else if (lead) {
        buf[pos++] = 239;
        buf[pos++] = 191;
        buf[pos++] = 189;
        lead = null;
      }
      if (c < 128) {
        buf[pos++] = c;
      } else {
        if (c < 2048) {
          buf[pos++] = c >> 6 | 192;
        } else {
          if (c < 65536) {
            buf[pos++] = c >> 12 | 224;
          } else {
            buf[pos++] = c >> 18 | 240;
            buf[pos++] = c >> 12 & 63 | 128;
          }
          buf[pos++] = c >> 6 & 63 | 128;
        }
        buf[pos++] = c & 63 | 128;
      }
    }
    return pos;
  }
  function toIndex(z2, x22, y) {
    return `${x22}:${y}:${z2}`;
  }
  function countFeatures(corrections) {
    let count = 0;
    for (const features of Object.values(corrections)) {
      count += features.length;
    }
    return count;
  }
  function parseTile(buffer) {
    const tile = new VectorTile(new Pbf(buffer));
    const result = {};
    for (const [layerName, layer] of Object.entries(tile.layers)) {
      const features = [];
      for (let i2 = 0; i2 < layer.length; i2++) {
        const feature = layer.feature(i2);
        features.push({
          id: feature.id,
          type: feature.type,
          properties: feature.properties,
          geometry: feature.loadGeometry(),
          extent: layer.extent
        });
      }
      result[layerName] = features;
    }
    return result;
  }
  function transformForOverzoom(corrections, scale, offsetX, offsetY) {
    const result = {};
    for (const [layerName, features] of Object.entries(corrections)) {
      result[layerName] = features.map((feature) => {
        const extent = feature.extent;
        const childExtent = extent / scale;
        const startX = offsetX * childExtent;
        const startY = offsetY * childExtent;
        const newGeometry = feature.geometry.map((ring) => {
          return ring.map((point) => {
            const x22 = (point.x - startX) * scale;
            const y = (point.y - startY) * scale;
            return { x: x22, y };
          });
        });
        return {
          ...feature,
          geometry: newGeometry,
          // Keep original extent since we scaled coordinates to match
          extent
        };
      });
    }
    return result;
  }
  var CorrectionsSource = class {
    /**
     * @param {string} pmtilesUrl - URL to the PMTiles file
     * @param {Object} [options] - Options
     * @param {number} [options.cacheMaxFeatures=10000] - Maximum number of features to cache
     * @param {number} [options.maxDataZoom] - Maximum zoom level in PMTiles (auto-detected if not provided)
     */
    constructor(pmtilesUrl, options = {}) {
      this.pmtilesUrl = pmtilesUrl;
      this.pmtiles = new x(pmtilesUrl);
      this.cacheMaxFeatures = options.cacheMaxFeatures;
      this.maxDataZoom = options.maxDataZoom;
      this.cache = /* @__PURE__ */ new Map();
      this.inflight = /* @__PURE__ */ new Map();
      this.cachedFeatureCount = 0;
      this.emptyKeys = /* @__PURE__ */ new Set();
      this.nonEmptyKeys = /* @__PURE__ */ new Set();
    }
    /**
     * Get the PMTiles source object.
     * @returns {PMTiles}
     */
    getSource() {
      return this.pmtiles;
    }
    /**
     * Clear the tile cache.
     */
    clearCache() {
      this.cache.clear();
      this.inflight.clear();
      this.cachedFeatureCount = 0;
      this.emptyKeys.clear();
      this.nonEmptyKeys.clear();
    }
    /**
     * Evict cache entries to stay under the feature limit.
     * Empty entries are evicted first (cheap to re-fetch from PMTiles directory cache).
     * Within each category, evicts LRU (least recently used) entries.
     * @private
     */
    _evictIfNeeded() {
      while (this.cachedFeatureCount > this.cacheMaxFeatures && this.cache.size > 1) {
        const targetSet = this.emptyKeys.size > 0 ? this.emptyKeys : this.nonEmptyKeys;
        if (targetSet.size === 0) break;
        let evictKey = void 0;
        let minUsed = Infinity;
        for (const key of targetSet) {
          const entry = this.cache.get(key);
          if (entry && entry.used < minUsed) {
            minUsed = entry.used;
            evictKey = key;
          }
        }
        if (!evictKey) break;
        const evicted = this.cache.get(evictKey);
        this.cachedFeatureCount -= evicted.featureCount;
        targetSet.delete(evictKey);
        this.cache.delete(evictKey);
      }
    }
    /**
     * Auto-detect max zoom from PMTiles metadata.
     * @returns {Promise<number>}
     * @private
     */
    async _getMaxDataZoom() {
      if (this.maxDataZoom !== void 0) {
        return this.maxDataZoom;
      }
      const header = await this.pmtiles.getHeader();
      this.maxDataZoom = header.maxZoom;
      return this.maxDataZoom;
    }
    /**
     * Fetch and parse a tile from PMTiles.
     * Implements in-flight request deduplication from protomaps-leaflet.
     * @param {number} z
     * @param {number} x
     * @param {number} y
     * @param {AbortSignal} [signal] - Optional abort signal
     * @returns {Promise<Object<string, Array>>}
     * @private
     */
    async _fetchTile(z2, x22, y, signal) {
      const idx = toIndex(z2, x22, y);
      return new Promise((resolve, reject) => {
        const entry = this.cache.get(idx);
        if (entry) {
          entry.used = performance.now();
          resolve(entry.data);
          return;
        }
        const ifentry = this.inflight.get(idx);
        if (ifentry) {
          ifentry.push({ resolve, reject });
          return;
        }
        this.inflight.set(idx, []);
        this.pmtiles.getZxy(z2, x22, y, signal).then((result) => {
          let data;
          if (result) {
            data = parseTile(result.data);
          } else {
            data = {};
          }
          const featureCount = countFeatures(data);
          const empty = featureCount === 0;
          this.cache.set(idx, { used: performance.now(), data, featureCount, empty });
          this.cachedFeatureCount += featureCount;
          (empty ? this.emptyKeys : this.nonEmptyKeys).add(idx);
          const ifentry2 = this.inflight.get(idx);
          if (ifentry2) {
            for (const waiter of ifentry2) {
              waiter.resolve(data);
            }
          }
          this.inflight.delete(idx);
          resolve(data);
          this._evictIfNeeded();
        }).catch((e) => {
          const ifentry2 = this.inflight.get(idx);
          if (ifentry2) {
            for (const waiter of ifentry2) {
              waiter.reject(e);
            }
          }
          this.inflight.delete(idx);
          reject(e);
        });
      });
    }
    /**
     * Get corrections for a tile as a dict of layer name to features.
     * Supports overzoom beyond maxDataZoom by scaling parent tile data.
     * @param {number} z - Zoom level
     * @param {number} x - Tile X coordinate
     * @param {number} y - Tile Y coordinate
     * @param {AbortSignal} [signal] - Optional abort signal
     * @returns {Promise<Object<string, Array>>} Map of layer name to array of features
     */
    async get(z2, x22, y, signal) {
      const maxDataZoom = await this._getMaxDataZoom();
      if (z2 > maxDataZoom) {
        const zoomDiff = z2 - maxDataZoom;
        const scale = 1 << zoomDiff;
        const parentX = Math.floor(x22 / scale);
        const parentY = Math.floor(y / scale);
        const offsetX = x22 % scale;
        const offsetY = y % scale;
        const corrections = await this._fetchTile(maxDataZoom, parentX, parentY, signal);
        if (Object.keys(corrections).length > 0) {
          return transformForOverzoom(corrections, scale, offsetX, offsetY);
        }
        return {};
      }
      return await this._fetchTile(z2, x22, y, signal);
    }
  };
  var configs_default2 = [
    {
      id: "cartodb-dark",
      tileUrlTemplates: [
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png",
        "https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_nolabels/{z}/{x}/{y}.png"
      ],
      lineWidthStops: { "0": 1, "2": 1, "3": 1, "10": 2, "12": 2 },
      lineStyles: [
        { color: "rgb(40, 40, 40)", layerSuffix: "ne", endZoom: 4 },
        { color: "rgb(40, 40, 40)", layerSuffix: "ne-disp", endZoom: 4 },
        { color: "rgb(40, 40, 40)", layerSuffix: "osm", startZoom: 5 },
        { color: "rgb(40, 40, 40)", layerSuffix: "osm-disp", startZoom: 5 },
        { color: "rgb(40, 40, 40)", layerSuffix: "osm-internal", startZoom: 5, widthFraction: 0.3, dashArray: [2, 2], delWidthFactor: 2 },
        { color: "rgb(40, 40, 40)", layerSuffix: "ne-internal", startZoom: 4, endZoom: 4, widthFraction: 0.3, dashArray: [2, 2], delWidthFactor: 3 }
      ]
    },
    {
      id: "cartodb-dark-retina",
      tileUrlTemplates: [
        "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_all/{z}/{x}/{y}{r}.png",
        "https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_nolabels/{z}/{x}/{y}{r}.png"
      ],
      lineWidthStops: { "0": 1.5, "2": 1.5, "3": 1.5, "6": 2.5, "10": 3 },
      lineStyles: [
        { color: "rgb(40, 40, 40)", layerSuffix: "ne", endZoom: 4 },
        { color: "rgb(40, 40, 40)", layerSuffix: "ne-disp", endZoom: 4 },
        { color: "rgb(40, 40, 40)", layerSuffix: "osm", startZoom: 5 },
        { color: "rgb(40, 40, 40)", layerSuffix: "osm-disp", startZoom: 5 },
        { color: "rgb(40, 40, 40)", layerSuffix: "osm-internal", startZoom: 5, widthFraction: 0.3, dashArray: [4, 4], delWidthFactor: 2 },
        { color: "rgb(40, 40, 40)", layerSuffix: "ne-internal", startZoom: 4, endZoom: 4, widthFraction: 0.3, dashArray: [4, 4], delWidthFactor: 3 }
      ]
    },
    {
      id: "cartodb-light",
      tileUrlTemplates: [
        "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
        "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_nolabels/{z}/{x}/{y}.png",
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}.png",
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}.png",
        "https://basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}.png"
      ],
      lineWidthStops: { "1": 0.5, "2": 0.75, "3": 0.75, "4": 1, "5": 1, "7": 1.75, "16": 2.5 },
      lineStyles: [
        { color: "rgb(235, 214, 214)", layerSuffix: "ne", endZoom: 4, lineExtensionFactor: 0.1, delWidthFactor: 2.5 },
        { color: "rgb(235, 214, 214)", layerSuffix: "ne-disp", endZoom: 4, delWidthFactor: 0 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm", alpha: 0.1, startZoom: 6, lineWidthStops: { "6": 9, "10": 8, "14": 8 }, lineExtensionFactor: 0.1 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm", startZoom: 5, lineExtensionFactor: 0.1 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm-disp", startZoom: 5, delWidthFactor: 0 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm-internal", startZoom: 5, widthFraction: 0.5, dashArray: [2, 2], delWidthFactor: 2 },
        { color: "rgb(235, 214, 214)", layerSuffix: "ne-internal", startZoom: 4, endZoom: 4, widthFraction: 0.5, dashArray: [2, 2], delWidthFactor: 2.5 }
      ]
    },
    {
      id: "cartodb-light-retina",
      tileUrlTemplates: [
        "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_all/{z}/{x}/{y}{r}.png",
        "https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png",
        "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_nolabels/{z}/{x}/{y}{r}.png",
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png",
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}{r}.png",
        "https://basemaps.cartocdn.com/rastertiles/voyager_labels_under/{z}/{x}/{y}{r}.png"
      ],
      lineWidthStops: { "1": 1, "3": 1, "4": 2, "5": 2, "6": 2.5, "7": 3, "8": 3, "10": 4, "11": 4, "12": 4 },
      lineStyles: [
        { color: "rgb(235, 214, 214)", layerSuffix: "ne", endZoom: 4, lineExtensionFactor: 0.1, delWidthFactor: 2.5 },
        { color: "rgb(235, 214, 214)", layerSuffix: "ne-disp", endZoom: 4, delWidthFactor: 0 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm", alpha: 0.1, startZoom: 6, lineWidthStops: { "6": 20, "8": 19, "10": 18, "12": 17 }, lineExtensionFactor: 0.1 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm", startZoom: 5, lineExtensionFactor: 0.1 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm-disp", startZoom: 5, delWidthFactor: 0 },
        { color: "rgb(235, 214, 214)", layerSuffix: "osm-internal", startZoom: 5, widthFraction: 0.5, dashArray: [4, 4], delWidthFactor: 2 },
        { color: "rgb(235, 214, 214)", layerSuffix: "ne-internal", startZoom: 4, endZoom: 4, widthFraction: 0.5, dashArray: [4, 4], delWidthFactor: 2.5 }
      ]
    },
    {
      id: "open-topo",
      tileUrlTemplates: [
        "https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        "https://tile.opentopomap.org/{z}/{x}/{y}.png",
        "https://{s}.tile.top-o-map.de/{z}/{x}/{y}.png",
        "https://tile.top-o-map.de/{z}/{x}/{y}.png"
      ],
      lineWidthStops: { "4": 0.75, "5": 1, "6": 1.25, "7": 1.5, "8": 1.75, "9": 1.25, "10": 1.25, "13": 1.5 },
      lineStyles: [
        { color: "rgb(83, 83, 83)", layerSuffix: "ne", startZoom: 4, endZoom: 6 },
        { color: "rgb(173, 173, 173)", layerSuffix: "osm", startZoom: 7, endZoom: 8, alpha: 0.5, widthFraction: 4 },
        { color: "rgb(83, 83, 83)", layerSuffix: "osm", startZoom: 7, endZoom: 8 },
        { color: "rgb(83, 83, 83)", layerSuffix: "osm-internal", widthFraction: 0.75, startZoom: 7, endZoom: 8 },
        { color: "rgb(199, 158, 204)", layerSuffix: "osm", startZoom: 9, widthFraction: 7, alpha: 0.6, lineExtensionFactor: 0.2 },
        { color: "rgb(175, 41, 203)", layerSuffix: "osm", startZoom: 9, lineExtensionFactor: 0.2 },
        { color: "rgb(199, 158, 204)", layerSuffix: "osm-internal", startZoom: 9, widthFraction: 2.25, alpha: 0.6, lineExtensionFactor: 0.2 },
        { color: "rgb(175, 41, 203)", layerSuffix: "osm-internal", startZoom: 9, widthFactor: 0.75, lineExtensionFactor: 0.2 }
      ]
    },
    {
      id: "osm-carto",
      tileUrlTemplates: [
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      ],
      lineWidthStops: { "3": 0.7, "4": 1, "10": 3.75 },
      lineStyles: [
        { color: "rgb(200, 180, 200)", layerSuffix: "osm", startZoom: 4, delWidthFactor: 1.5 },
        { color: "rgb(160, 120, 160)", layerSuffix: "osm", startZoom: 4, widthFraction: 0.333, dashArray: [30, 2, 8, 2], delWidthFactor: 0 },
        { color: "rgb(200, 180, 200)", layerSuffix: "osm-internal", startZoom: 4, widthFraction: 0.45 },
        { color: "rgb(160, 120, 160)", layerSuffix: "osm-internal", startZoom: 4, widthFraction: 0.15, dashArray: [10, 4, 2] }
      ]
    },
    {
      id: "osm-hot",
      tileUrlTemplates: [
        "https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
        "https://tile.openstreetmap.fr/hot/{z}/{x}/{y}.png"
      ],
      lineWidthStops: { "2": 3, "3": 3, "7": 3, "8": 3.5, "9": 3.5 },
      lineStyles: [
        { color: "rgb(149, 175, 180)", layerSuffix: "osm", lineExtensionFactor: 0.25, startZoom: 2 },
        { color: "rgb(89, 117, 123)", layerSuffix: "osm", widthFraction: 0.33, lineExtensionFactor: 0.25, startZoom: 2 },
        { color: "rgb(172, 163, 163)", layerSuffix: "osm-internal", widthFraction: 0.33, startZoom: 4, dashArray: [7, 7] }
      ]
    }
  ];
  var INFINITY2 = -1;
  var MIN_LINE_WIDTH2 = 0.1;
  var DEFAULT_LINE_WIDTH2 = 1;
  function interpolateLineWidth2(zoom, lineWidthStops) {
    const zooms = Object.keys(lineWidthStops).map(Number).sort((a, b2) => a - b2);
    if (lineWidthStops[zoom] !== void 0) {
      return lineWidthStops[zoom];
    }
    if (zoom < zooms[0]) {
      const z1 = zooms[0];
      const z2 = zooms[1];
      const w1 = lineWidthStops[z1];
      const w2 = lineWidthStops[z2];
      const slope = (w2 - w1) / (z2 - z1);
      return Math.max(MIN_LINE_WIDTH2, w1 + slope * (zoom - z1));
    }
    if (zoom > zooms[zooms.length - 1]) {
      const z1 = zooms[zooms.length - 2];
      const z2 = zooms[zooms.length - 1];
      const w1 = lineWidthStops[z1];
      const w2 = lineWidthStops[z2];
      const slope = (w2 - w1) / (z2 - z1);
      return Math.max(MIN_LINE_WIDTH2, w2 + slope * (zoom - z2));
    }
    for (let i2 = 0; i2 < zooms.length - 1; i2++) {
      if (zoom > zooms[i2] && zoom < zooms[i2 + 1]) {
        const z1 = zooms[i2];
        const z2 = zooms[i2 + 1];
        const w1 = lineWidthStops[z1];
        const w2 = lineWidthStops[z2];
        const t = (zoom - z1) / (z2 - z1);
        return w1 + t * (w2 - w1);
      }
    }
    return DEFAULT_LINE_WIDTH2;
  }
  function templateToRegex2(template) {
    const groups = [];
    const hasRetina = template.includes("{r}");
    const hasExtension = /\.(png|jpg|jpeg|webp|gif)$/i.test(template);
    let pattern = template.replace(/[.*+?^${}()|[\]\\]/g, (char) => {
      if (char === "{" || char === "}") return char;
      return "\\" + char;
    }).replace(/^https:\/\//, "https?://").replace(/^http:\/\//, "https?://").replace(/\{[a-z0-9]-[a-z0-9]\}/gi, () => {
      groups.push("s");
      return "([a-z0-9]+)";
    }).replace(/\{(z|x|y|s|r)\}/gi, (_2, name) => {
      const lowerName = name.toLowerCase();
      groups.push(lowerName);
      if (lowerName === "s") {
        return "([a-z0-9]+)";
      }
      if (lowerName === "r") {
        return "(@\\d+x)";
      }
      return "(\\d+)";
    });
    if (!hasRetina) {
      if (hasExtension) {
        pattern = pattern.replace(/(\\\.(png|jpg|jpeg|webp|gif))/, "(?!@\\d+x)$1");
      } else {
        pattern = pattern + "(?!@\\d+x)";
      }
    }
    return { pattern: new RegExp("^" + pattern + "(\\?.*)?$", "i"), groups };
  }
  function templateToTemplateRegex2(template) {
    const hasRetina = template.includes("{r}");
    const hasExtension = /\.(png|jpg|jpeg|webp|gif)$/i.test(template);
    let pattern = template.replace(/[.*+?^${}()|[\]\\]/g, (char) => {
      if (char === "{" || char === "}") return char;
      return "\\" + char;
    }).replace(/^https:\/\//, "https?://").replace(/^http:\/\//, "https?://").replace(/\{([a-z0-9])-([a-z0-9])\}/gi, (_2, start, end) => `(\\{${start}-${end}\\}|\\{s\\}|[a-z0-9]+)`).replace(/\{(z|x|y|s|r)\}/gi, (_2, name) => {
      const lowerName = name.toLowerCase();
      if (lowerName === "s") {
        return "(\\{s\\}|\\{[a-z0-9]-[a-z0-9]\\}|[a-z0-9]+)";
      }
      if (lowerName === "r") {
        return "(\\{r\\}|@\\d+x)";
      }
      return `\\{${lowerName}\\}`;
    });
    if (!hasRetina) {
      if (hasExtension) {
        pattern = pattern.replace(/(\\\.(png|jpg|jpeg|webp|gif))/, "(?!@\\d+x|\\{r\\})$1");
      } else {
        pattern = pattern + "(?!@\\d+x|\\{r\\})";
      }
    }
    return new RegExp("^" + pattern + "(\\?.*)?$", "i");
  }
  function isValidColor2(color) {
    if (typeof color !== "string" || !color.trim()) return false;
    if (typeof CSS !== "undefined" && CSS.supports) {
      return CSS.supports("color", color);
    }
    const trimmed = color.trim().toLowerCase();
    if (/^#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/.test(trimmed)) return true;
    if (/^(rgb|hsl)a?\(/.test(trimmed)) return true;
    if (/^[a-z]+$/.test(trimmed)) return true;
    return false;
  }
  function validateLineWidthStops2(lineWidthStops, prefix) {
    if (!lineWidthStops || typeof lineWidthStops !== "object" || Array.isArray(lineWidthStops)) {
      throw new Error(`${prefix}: lineWidthStops must be an object`);
    }
    const stopKeys = Object.keys(lineWidthStops);
    if (stopKeys.length < 2) {
      throw new Error(`${prefix}: lineWidthStops must have at least 2 entries`);
    }
    for (const key of stopKeys) {
      const zoom = Number(key);
      if (!Number.isInteger(zoom) || zoom < 0) {
        throw new Error(`${prefix}: lineWidthStops keys must be non-negative integers, got "${key}"`);
      }
      if (typeof lineWidthStops[key] !== "number" || lineWidthStops[key] <= 0) {
        throw new Error(`${prefix}: lineWidthStops values must be positive numbers`);
      }
    }
  }
  var LineStyle2 = class _LineStyle2 {
    /**
     * Validate a LineStyle configuration object.
     * @param {Object} obj - The object to validate
     * @param {number} [index] - Optional index for error messages (when validating in an array)
     * @param {boolean} [requireLineWidthStops=false] - Whether lineWidthStops is required
     * @throws {Error} If validation fails
     */
    static validateJSON(obj, index, requireLineWidthStops = false) {
      const prefix = index !== void 0 ? `lineStyles[${index}]` : "LineStyle";
      if (!obj || typeof obj !== "object") {
        throw new Error(`${prefix}: must be an object`);
      }
      if (!obj.color || typeof obj.color !== "string") {
        throw new Error(`${prefix}: color must be a non-empty string`);
      }
      if (!isValidColor2(obj.color)) {
        throw new Error(`${prefix}: color "${obj.color}" is not a valid CSS color`);
      }
      if (!obj.layerSuffix || typeof obj.layerSuffix !== "string") {
        throw new Error(`${prefix}: layerSuffix must be a non-empty string`);
      }
      if (obj.widthFraction !== void 0 && (typeof obj.widthFraction !== "number" || obj.widthFraction <= 0)) {
        throw new Error(`${prefix}: widthFraction must be a positive number`);
      }
      if (obj.dashArray !== void 0 && !Array.isArray(obj.dashArray)) {
        throw new Error(`${prefix}: dashArray must be an array`);
      }
      if (obj.alpha !== void 0 && (typeof obj.alpha !== "number" || obj.alpha < 0 || obj.alpha > 1)) {
        throw new Error(`${prefix}: alpha must be a number between 0 and 1`);
      }
      if (obj.startZoom !== void 0 && (typeof obj.startZoom !== "number" || obj.startZoom < 0)) {
        throw new Error(`${prefix}: startZoom must be a non-negative number`);
      }
      if (obj.endZoom !== void 0 && (typeof obj.endZoom !== "number" || obj.endZoom < 0 && obj.endZoom !== INFINITY2)) {
        throw new Error(`${prefix}: endZoom must be a non-negative number or INFINITY (${INFINITY2})`);
      }
      if (obj.lineExtensionFactor !== void 0 && (typeof obj.lineExtensionFactor !== "number" || obj.lineExtensionFactor < 0)) {
        throw new Error(`${prefix}: lineExtensionFactor must be a non-negative number`);
      }
      if (obj.delWidthFactor !== void 0 && (typeof obj.delWidthFactor !== "number" || obj.delWidthFactor < 0)) {
        throw new Error(`${prefix}: delWidthFactor must be a non-negative number`);
      }
      if (requireLineWidthStops && obj.lineWidthStops === void 0) {
        throw new Error(`${prefix}: lineWidthStops is required`);
      }
      if (obj.lineWidthStops !== void 0) {
        validateLineWidthStops2(obj.lineWidthStops, prefix);
      }
    }
    /**
     * @param {Object} options
     * @param {string} options.color - CSS color string
     * @param {string} options.layerSuffix - Layer suffix (e.g., 'osm', 'ne', 'osm-disp')
     * @param {Object<number, number>} options.lineWidthStops - Line width stops for this style
     * @param {number} [options.widthFraction=1.0] - Multiplier for base line width
     * @param {number[]} [options.dashArray] - Dash pattern for dashed lines
     * @param {number} [options.alpha=1.0] - Opacity (0-1)
     * @param {number} [options.startZoom=0] - Minimum zoom level for this style
     * @param {number} [options.endZoom=INFINITY] - Maximum zoom level for this style (INFINITY means no limit)
     * @param {number} [options.lineExtensionFactor=0.0] - Factor to extend lines by (multiplied by deletion line width)
     * @param {number} [options.delWidthFactor=1.5] - Factor to multiply line width for deletion blur
     */
    constructor({ color, layerSuffix, lineWidthStops, widthFraction = 1, dashArray, alpha = 1, startZoom = 0, endZoom = INFINITY2, lineExtensionFactor = 0, delWidthFactor = 1.5 }) {
      this.color = color;
      this.layerSuffix = layerSuffix;
      this.lineWidthStops = lineWidthStops;
      this.widthFraction = widthFraction;
      this.dashArray = dashArray;
      this.alpha = alpha;
      this.startZoom = startZoom;
      this.endZoom = endZoom;
      this.lineExtensionFactor = lineExtensionFactor;
      this.delWidthFactor = delWidthFactor;
    }
    /**
     * Get base line width for this style at a given zoom level.
     * @param {number} zoom - Zoom level
     * @returns {number}
     */
    getLineWidth(zoom) {
      return interpolateLineWidth2(zoom, this.lineWidthStops);
    }
    /**
     * Check if this style is active at the given zoom level.
     * @param {number} z - Zoom level
     * @returns {boolean}
     */
    isActiveAtZoom(z2) {
      return z2 >= this.startZoom && (this.endZoom === INFINITY2 || z2 <= this.endZoom);
    }
    /**
     * Serialize to plain object.
     * @returns {Object}
     */
    toJSON() {
      return {
        color: this.color,
        layerSuffix: this.layerSuffix,
        lineWidthStops: this.lineWidthStops,
        widthFraction: this.widthFraction,
        dashArray: this.dashArray,
        alpha: this.alpha,
        startZoom: this.startZoom,
        endZoom: this.endZoom,
        lineExtensionFactor: this.lineExtensionFactor,
        delWidthFactor: this.delWidthFactor
      };
    }
    /**
     * Create from plain object with validation.
     * @param {Object} obj
     * @param {number} [index] - Optional index for error messages
     * @returns {LineStyle}
     */
    static fromJSON(obj, index) {
      _LineStyle2.validateJSON(obj, index, true);
      return new _LineStyle2(obj);
    }
  };
  var LayerConfig2 = class _LayerConfig2 {
    /**
     * Validate a LayerConfig configuration object.
     * Also validates all lineStyles within the config.
     * @param {Object} obj - The object to validate
     * @throws {Error} If validation fails
     */
    static validateJSON(obj) {
      if (!obj || typeof obj !== "object") {
        throw new Error("LayerConfig: must be an object");
      }
      if (!obj.id || typeof obj.id !== "string") {
        throw new Error("LayerConfig: id must be a non-empty string");
      }
      if (obj.id.includes("/")) {
        throw new Error(`LayerConfig: id cannot contain slashes: "${obj.id}"`);
      }
      const id = obj.id;
      if (obj.lineWidthStops !== void 0) {
        if (!obj.lineWidthStops || typeof obj.lineWidthStops !== "object" || Array.isArray(obj.lineWidthStops)) {
          throw new Error(`LayerConfig "${id}": lineWidthStops must be an object`);
        }
        const stopKeys = Object.keys(obj.lineWidthStops);
        if (stopKeys.length < 2) {
          throw new Error(`LayerConfig "${id}": lineWidthStops must have at least 2 entries`);
        }
        for (const key of stopKeys) {
          const zoom = Number(key);
          if (!Number.isInteger(zoom) || zoom < 0) {
            throw new Error(`LayerConfig "${id}": lineWidthStops keys must be non-negative integers, got "${key}"`);
          }
          if (typeof obj.lineWidthStops[key] !== "number" || obj.lineWidthStops[key] <= 0) {
            throw new Error(`LayerConfig "${id}": lineWidthStops values must be positive numbers`);
          }
        }
      }
      if (!Array.isArray(obj.lineStyles) || obj.lineStyles.length === 0) {
        throw new Error(`LayerConfig "${id}": lineStyles must be a non-empty array`);
      }
      for (let i2 = 0; i2 < obj.lineStyles.length; i2++) {
        LineStyle2.validateJSON(obj.lineStyles[i2], i2);
      }
    }
    constructor({
      id,
      // Tile URL templates for matching (e.g., "https://{s}.tile.example.com/{z}/{x}/{y}.png")
      tileUrlTemplates = [],
      // Line width stops: map of zoom level to line width (at least 2 entries)
      // Note: interpolated/extrapolated line width is capped at a minimum of 0.5
      lineWidthStops = { 1: 0.5, 10: 2.5 },
      // Line styles array - each element describes a line to draw from a specific layer
      // { color: string, layerSuffix: string, widthFraction?: number, dashArray?: number[], 
      //   startZoom?: number, endZoom?: number, lineExtensionFactor?: number, delWidthFactor?: number }
      // Lines are drawn in array order. layerSuffix determines which PMTiles layer to use.
      lineStyles
    }) {
      this.id = id;
      const templates = Array.isArray(tileUrlTemplates) ? tileUrlTemplates : tileUrlTemplates ? [tileUrlTemplates] : [];
      this.tileUrlTemplates = templates;
      this._compiledPatterns = templates.map((t) => templateToRegex2(t));
      this._templatePatterns = templates.map((t) => templateToTemplateRegex2(t));
      this.lineWidthStops = lineWidthStops;
      this.lineStyles = lineStyles.map((style) => {
        if (style instanceof LineStyle2) {
          return style;
        }
        const styleWithStops = style.lineWidthStops ? style : { ...style, lineWidthStops };
        return new LineStyle2(styleWithStops);
      });
    }
    /**
     * Get line styles active at a given zoom level
     * @param {number} z - Zoom level
     * @returns {LineStyle[]}
     */
    getLineStylesForZoom(z2) {
      return this.lineStyles.filter((style) => style.isActiveAtZoom(z2));
    }
    /**
     * Get unique layer suffixes from styles active at a given zoom level
     * @param {number} z - Zoom level
     * @returns {string[]}
     */
    getLayerSuffixesForZoom(z2) {
      const activeStyles = this.getLineStylesForZoom(z2);
      return [...new Set(activeStyles.map((s) => s.layerSuffix))];
    }
    /**
     * Check if this config matches the given template URLs (with {z}/{x}/{y} placeholders)
     * @param {string | string[]} templates - Single template URL or array of template URLs
     * @returns {boolean}
     */
    matchTemplate(templates) {
      if (this._templatePatterns.length === 0) return false;
      const urls = Array.isArray(templates) ? templates : [templates];
      if (urls.length === 0) return false;
      return urls.some(
        (url) => this._templatePatterns.some((pattern) => pattern.test(url))
      );
    }
    /**
     * Check if this config matches the given tile URLs (with actual coordinates)
     * @param {string | string[]} tiles - Single tile URL or array of tile URLs
     * @returns {boolean}
     */
    matchTileUrl(tiles) {
      if (this._compiledPatterns.length === 0) return false;
      const urls = Array.isArray(tiles) ? tiles : [tiles];
      if (urls.length === 0) return false;
      return urls.some(
        (url) => this._compiledPatterns.some(({ pattern }) => pattern.test(url))
      );
    }
    /**
     * Extract tile coordinates (z, x, y) from a URL using this config's templates
     * @param {string} url - Tile URL to extract coordinates from
     * @returns {{ z: number, x: number, y: number } | null}
     */
    extractCoords(url) {
      for (const { pattern, groups } of this._compiledPatterns) {
        const match = url.match(pattern);
        if (match) {
          const result = {};
          for (let i2 = 0; i2 < groups.length; i2++) {
            const name = groups[i2];
            const value = match[i2 + 1];
            if (name === "z" || name === "x" || name === "y") {
              result[name] = parseInt(value, 10);
            }
          }
          if ("z" in result && "x" in result && "y" in result) {
            return { z: result.z, x: result.x, y: result.y };
          }
        }
      }
      return null;
    }
    /**
     * Serialize the config to a plain object for postMessage
     * @returns {Object}
     */
    toJSON() {
      return {
        id: this.id,
        tileUrlTemplates: this.tileUrlTemplates,
        lineWidthStops: this.lineWidthStops,
        lineStyles: this.lineStyles.map((s) => s.toJSON())
      };
    }
    /**
     * Create a LayerConfig from a plain object with validation.
     * @param {Object} obj
     * @returns {LayerConfig}
     * @throws {Error} If validation fails
     */
    static fromJSON(obj) {
      _LayerConfig2.validateJSON(obj);
      return new _LayerConfig2(obj);
    }
  };
  var LayerConfigRegistry2 = class _LayerConfigRegistry2 {
    constructor() {
      this.registry = {};
    }
    /**
     * Get a layer config by id
     */
    get(id) {
      return this.registry[id];
    }
    /**
     * Register a new layer config
     */
    register(config) {
      this.registry[config.id] = config;
    }
    /**
     * Remove a layer config by id
     */
    remove(id) {
      if (!this.registry[id]) return false;
      delete this.registry[id];
      return true;
    }
    /**
     * Detect layer config from tile URL templates (with {z}/{x}/{y} placeholders)
     * @param {string | string[]} templates - Single template URL or array of template URLs
     */
    detectFromTemplates(templates) {
      if (!templates || Array.isArray(templates) && templates.length === 0) return void 0;
      for (const config of Object.values(this.registry)) {
        if (config.matchTemplate(templates)) {
          return config;
        }
      }
      return void 0;
    }
    /**
     * Detect layer config from actual tile URLs (with numeric coordinates)
     * @param {string | string[]} urls - Single tile URL or array of tile URLs
     */
    detectFromTileUrls(urls) {
      if (!urls || Array.isArray(urls) && urls.length === 0) return void 0;
      for (const config of Object.values(this.registry)) {
        if (config.matchTileUrl(urls)) {
          return config;
        }
      }
      return void 0;
    }
    /**
     * Get all available layer config ids
     */
    getAvailableIds() {
      return Object.keys(this.registry);
    }
    /**
     * Create a new registry with all configs from this registry plus extra configs.
     * @param {LayerConfig[]} extraLayerConfigs - Additional configs to add
     * @returns {LayerConfigRegistry} A new registry with merged configs
     */
    createMergedRegistry(extraLayerConfigs) {
      const registry = new _LayerConfigRegistry2();
      for (const id of this.getAvailableIds()) {
        registry.register(this.get(id));
      }
      if (extraLayerConfigs && extraLayerConfigs.length > 0) {
        for (const config of extraLayerConfigs) {
          registry.register(config);
        }
      }
      return registry;
    }
    /**
     * Parse a tile URL into its components: layer config and coordinates
     * @param {string} url - Tile URL to parse
     * @returns {{ layerConfig: LayerConfig, coords: { z: number, x: number, y: number } } | null}
     */
    parseTileUrl(url) {
      const layerConfig = this.detectFromTileUrls([url]);
      if (!layerConfig) return null;
      const coords = layerConfig.extractCoords(url);
      if (!coords) return null;
      return { layerConfig, coords };
    }
  };
  var layerConfigs2 = new LayerConfigRegistry2();
  for (const configData of configs_default2) {
    layerConfigs2.register(new LayerConfig2(configData));
  }
  var TileFetchError = class _TileFetchError extends Error {
    /**
     * @param {number} status - HTTP status code
     * @param {string} [url] - The URL that failed
     * @param {string} [body] - Response body text
     */
    constructor(status, url, body) {
      super(`Tile fetch failed: ${status}`);
      this.name = "TileFetchError";
      this.status = status;
      this.url = url;
      this.body = body;
    }
    /**
     * Create a TileFetchError from a failed Response.
     * @param {Response} response - The failed fetch response
     * @returns {Promise<TileFetchError>}
     */
    static async fromResponse(response) {
      let body;
      try {
        body = await response.text();
      } catch {
      }
      return new _TileFetchError(response.status, response.url, body);
    }
  };
  var DEFAULT_TILE_EXTENT = 4096;
  function buildFetchOptions(crossOrigin, referrerPolicy) {
    const options = {};
    if (crossOrigin === "use-credentials") {
      options.mode = "cors";
      options.credentials = "include";
    } else if (crossOrigin === "anonymous" || crossOrigin === "" || crossOrigin === true) {
      options.mode = "cors";
      options.credentials = "omit";
    } else {
      options.mode = "cors";
      options.credentials = "same-origin";
    }
    if (referrerPolicy) {
      options.referrerPolicy = referrerPolicy;
    }
    return options;
  }
  function getFeaturesBoundingBox(features, tileSize, padding = 0) {
    let minX = Infinity, minY = Infinity;
    let maxX = -Infinity, maxY = -Infinity;
    for (const feature of features) {
      const scale = tileSize / feature.extent;
      for (const ring of feature.geometry) {
        for (const point of ring) {
          const px = point.x * scale;
          const py = point.y * scale;
          if (px < minX) minX = px;
          if (py < minY) minY = py;
          if (px > maxX) maxX = px;
          if (py > maxY) maxY = py;
        }
      }
    }
    return {
      minX: Math.max(0, Math.floor(minX - padding)),
      minY: Math.max(0, Math.floor(minY - padding)),
      maxX: Math.min(tileSize, Math.ceil(maxX + padding)),
      maxY: Math.min(tileSize, Math.ceil(maxY + padding))
    };
  }
  function medianFromHistogram(histogram, values) {
    const count = values.length;
    if (count === 0) return 0;
    histogram.fill(0);
    for (let i2 = 0; i2 < count; i2++) {
      histogram[values[i2]]++;
    }
    const medianPos = count >> 1;
    let cumulative = 0;
    for (let v2 = 0; v2 < 256; v2++) {
      cumulative += histogram[v2];
      if (cumulative > medianPos) {
        return v2;
      }
    }
    return 0;
  }
  function applyMedianBlurAlongPath(ctx, features, lineWidth, tileSize, maskCanvas) {
    if (features.length === 0) return;
    const imageData = ctx.getImageData(0, 0, tileSize, tileSize);
    const data = imageData.data;
    const width = tileSize;
    const height = tileSize;
    if (!maskCanvas || maskCanvas.width !== tileSize || maskCanvas.height !== tileSize) {
      maskCanvas = new OffscreenCanvas(tileSize, tileSize);
    }
    const maskCtx = maskCanvas.getContext("2d", { willReadFrequently: true });
    maskCtx.fillStyle = "black";
    maskCtx.fillRect(0, 0, tileSize, tileSize);
    maskCtx.strokeStyle = "white";
    maskCtx.lineWidth = lineWidth;
    maskCtx.lineCap = "round";
    maskCtx.lineJoin = "round";
    for (const feature of features) {
      const scale = tileSize / feature.extent;
      for (const ring of feature.geometry) {
        if (ring.length === 0) continue;
        maskCtx.beginPath();
        maskCtx.moveTo(ring[0].x * scale, ring[0].y * scale);
        for (let i2 = 1; i2 < ring.length; i2++) {
          maskCtx.lineTo(ring[i2].x * scale, ring[i2].y * scale);
        }
        maskCtx.stroke();
      }
    }
    const maskData = maskCtx.getImageData(0, 0, tileSize, tileSize).data;
    const radius = Math.max(2, Math.ceil(lineWidth / 2) + 1);
    const output = new Uint8ClampedArray(data);
    const bbox = getFeaturesBoundingBox(features, tileSize, radius);
    const histogram = new Uint16Array(256);
    const rValues = [];
    const gValues = [];
    const bValues = [];
    for (let y = bbox.minY; y < bbox.maxY; y++) {
      for (let x22 = bbox.minX; x22 < bbox.maxX; x22++) {
        const maskIdx = (y * width + x22) * 4;
        if (maskData[maskIdx] < 128) continue;
        rValues.length = 0;
        gValues.length = 0;
        bValues.length = 0;
        for (let dy = -radius; dy <= radius; dy++) {
          for (let dx = -radius; dx <= radius; dx++) {
            const nx = x22 + dx;
            const ny = y + dy;
            if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
            const nMaskIdx = (ny * width + nx) * 4;
            if (maskData[nMaskIdx] >= 128) continue;
            const nIdx = nMaskIdx;
            rValues.push(data[nIdx]);
            gValues.push(data[nIdx + 1]);
            bValues.push(data[nIdx + 2]);
          }
        }
        if (rValues.length >= 3) {
          const idx = maskIdx;
          output[idx] = medianFromHistogram(histogram, rValues);
          output[idx + 1] = medianFromHistogram(histogram, gValues);
          output[idx + 2] = medianFromHistogram(histogram, bValues);
        }
      }
    }
    ctx.putImageData(new ImageData(output, width, height), 0, 0);
  }
  function isAtExtentEdge(coord, extent, tolerance = 0.01) {
    const tol = extent * tolerance;
    return coord <= tol || coord >= extent - tol;
  }
  function extendFeaturesEnds(features, extensionLength) {
    return features.map((feature) => {
      const extent = feature.extent;
      const newGeometry = feature.geometry.map((ring) => {
        if (ring.length < 2) return ring;
        const newRing = [...ring];
        const start = ring[0];
        const second = ring[1];
        if (!isAtExtentEdge(start.x, extent) && !isAtExtentEdge(start.y, extent)) {
          const dx = start.x - second.x;
          const dy = start.y - second.y;
          const len = Math.sqrt(dx * dx + dy * dy);
          if (len > 0) {
            const ux = dx / len;
            const uy = dy / len;
            newRing[0] = {
              x: start.x + ux * extensionLength,
              y: start.y + uy * extensionLength
            };
          }
        }
        const lastIdx = ring.length - 1;
        const end = ring[lastIdx];
        const prev = ring[lastIdx - 1];
        if (!isAtExtentEdge(end.x, extent) && !isAtExtentEdge(end.y, extent)) {
          const dx = end.x - prev.x;
          const dy = end.y - prev.y;
          const len = Math.sqrt(dx * dx + dy * dy);
          if (len > 0) {
            const ux = dx / len;
            const uy = dy / len;
            newRing[lastIdx] = {
              x: end.x + ux * extensionLength,
              y: end.y + uy * extensionLength
            };
          }
        }
        return newRing;
      });
      return { ...feature, geometry: newGeometry };
    });
  }
  function extendFeaturesByFactor(features, extensionFactor, delLineWidth, tileSize) {
    if (!features || features.length === 0 || extensionFactor <= 0) {
      return features;
    }
    const extent = features[0]?.extent || DEFAULT_TILE_EXTENT;
    const extensionLength = delLineWidth * extensionFactor / tileSize * extent;
    return extendFeaturesEnds(features, extensionLength);
  }
  function drawFeatures(ctx, features, color, lineWidth, tileSize, dashArray, alpha) {
    const prevAlpha = ctx.globalAlpha;
    if (alpha !== void 0) {
      ctx.globalAlpha = alpha;
    }
    ctx.strokeStyle = color;
    ctx.lineWidth = lineWidth;
    ctx.lineJoin = "round";
    if (dashArray && dashArray.length > 0) {
      ctx.setLineDash(dashArray);
      ctx.lineCap = "butt";
    } else {
      ctx.setLineDash([]);
      ctx.lineCap = "round";
    }
    for (const feature of features) {
      const scale = tileSize / feature.extent;
      for (const ring of feature.geometry) {
        if (ring.length === 0) continue;
        ctx.beginPath();
        ctx.moveTo(ring[0].x * scale, ring[0].y * scale);
        for (let i2 = 1; i2 < ring.length; i2++) {
          ctx.lineTo(ring[i2].x * scale, ring[i2].y * scale);
        }
        ctx.stroke();
      }
    }
    if (alpha !== void 0) {
      ctx.globalAlpha = prevAlpha;
    }
  }
  var _TileFixer = class _TileFixer2 {
    /**
     * Set the default maximum features to cache for new TileFixer instances.
     * @param {number} maxFeatures - Maximum features to cache
     */
    static setDefaultCacheMaxFeatures(maxFeatures) {
      _TileFixer2._defaultCacheMaxFeatures = maxFeatures;
    }
    /**
     * Get or create a TileFixer instance for a given PMTiles URL.
     * Reuses existing instances for the same URL.
     * @param {string} pmtilesUrl - URL to the PMTiles file
     * @returns {TileFixer}
     */
    static getOrCreate(pmtilesUrl) {
      let instance = _TileFixer2._instances.get(pmtilesUrl);
      if (!instance) {
        instance = new _TileFixer2(pmtilesUrl, {
          cacheMaxFeatures: _TileFixer2._defaultCacheMaxFeatures
        });
        _TileFixer2._instances.set(pmtilesUrl, instance);
      }
      return instance;
    }
    /**
     * @param {string} pmtilesUrl - URL to the PMTiles file
     * @param {Object} [options] - Options
     * @param {number} [options.cacheMaxFeatures] - Maximum number of features to cache
     * @param {number} [options.maxDataZoom] - Maximum zoom level in PMTiles (auto-detected if not provided)
     */
    constructor(pmtilesUrl, options = {}) {
      this.correctionsSource = new CorrectionsSource(pmtilesUrl, options);
      this._canvas = null;
      this._maskCanvas = null;
    }
    /**
     * Get the PMTiles source object.
     * @returns {PMTiles}
     */
    getSource() {
      return this.correctionsSource.getSource();
    }
    /**
     * Clear the tile cache.
     */
    clearCache() {
      this.correctionsSource.clearCache();
    }
    /**
     * Get corrections for a tile as a dict of layer name to features.
     * Supports overzoom beyond maxDataZoom by scaling parent tile data.
     * @param {number} z - Zoom level
     * @param {number} x - Tile X coordinate
     * @param {number} y - Tile Y coordinate
     * @param {AbortSignal} [signal] - Optional abort signal
     * @returns {Promise<Object<string, Array>>} Map of layer name to array of features
     */
    async getCorrections(z2, x22, y, signal) {
      return await this.correctionsSource.get(z2, x22, y, signal);
    }
    /**
     * Apply corrections to a raster tile.
     * @param {Object<string, Array>} corrections - Feature map from getCorrections
     * @param {ArrayBuffer} rasterTile - The original raster tile as ArrayBuffer
     * @param {Object} layerConfig - Layer configuration with colors and styles
     * @param {number} zoom - Current zoom level
     * @returns {Promise<ArrayBuffer>} The corrected tile as ArrayBuffer (PNG)
     */
    async fixTile(corrections, rasterTile, layerConfig, zoom) {
      let activeLineStyles;
      if (layerConfig.getLineStylesForZoom) {
        activeLineStyles = layerConfig.getLineStylesForZoom(zoom);
      } else {
        const allStyles = layerConfig.lineStyles || [];
        activeLineStyles = allStyles.filter((style) => {
          const styleStart = style.startZoom ?? 0;
          const styleEnd = style.endZoom ?? INFINITY2;
          return zoom >= styleStart && (styleEnd === INFINITY2 || zoom <= styleEnd);
        });
      }
      if (activeLineStyles.length === 0) {
        return rasterTile;
      }
      const layerSuffixes = [...new Set(activeLineStyles.map((s) => s.layerSuffix))];
      const blob = new Blob([rasterTile]);
      const imageBitmap = await createImageBitmap(blob);
      const tileSize = imageBitmap.width;
      if (!this._canvas || this._canvas.width !== tileSize) {
        this._canvas = new OffscreenCanvas(tileSize, tileSize);
      }
      const canvas = this._canvas;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      ctx.drawImage(imageBitmap, 0, 0, tileSize, tileSize);
      const delLineWidthBySuffix = {};
      for (const suffix of layerSuffixes) {
        const stylesForSuffix = activeLineStyles.filter((s) => s.layerSuffix === suffix);
        const maxDelWidth = Math.max(...stylesForSuffix.map(
          (s) => s.getLineWidth(zoom) * s.widthFraction * s.delWidthFactor
        ));
        delLineWidthBySuffix[suffix] = maxDelWidth;
      }
      for (const suffix of layerSuffixes) {
        const delLineWidth = delLineWidthBySuffix[suffix];
        if (delLineWidth === 0) continue;
        const delLayerName = `to-del-${suffix}`;
        const delFeatures = corrections[delLayerName] || [];
        if (delFeatures.length > 0) {
          if (!this._maskCanvas || this._maskCanvas.width !== tileSize) {
            this._maskCanvas = new OffscreenCanvas(tileSize, tileSize);
          }
          applyMedianBlurAlongPath(ctx, delFeatures, delLineWidth, tileSize, this._maskCanvas);
        }
      }
      for (const style of activeLineStyles) {
        const { color, widthFraction, dashArray, alpha, lineExtensionFactor, layerSuffix } = style;
        const addLayerName = `to-add-${layerSuffix}`;
        let addFeatures = corrections[addLayerName] || [];
        if (addFeatures.length > 0) {
          const delLineWidth = delLineWidthBySuffix[layerSuffix];
          if (lineExtensionFactor > 0) {
            addFeatures = extendFeaturesByFactor(addFeatures, lineExtensionFactor, delLineWidth, tileSize);
          }
          const lineWidth = style.getLineWidth(zoom) * widthFraction;
          drawFeatures(ctx, addFeatures, color, lineWidth, tileSize, dashArray, alpha);
        }
      }
      const outputBlob = await canvas.convertToBlob({ type: "image/png" });
      return outputBlob.arrayBuffer();
    }
    /**
     * Fetch a tile, apply corrections, and return the result.
     * @param {string} tileUrl - URL of the raster tile
     * @param {number} z - Zoom level
     * @param {number} x - Tile X coordinate
     * @param {number} y - Tile Y coordinate
     * @param {Object} layerConfig - Layer configuration with colors and styles
     * @param {Object} [fetchOptions] - Fetch options passed to fetch()
     * @param {AbortSignal} [fetchOptions.signal] - Abort signal for fetch
     * @param {RequestMode} [fetchOptions.mode] - Fetch mode (e.g., 'cors')
     * @param {RequestCredentials} [fetchOptions.credentials] - Fetch credentials (e.g., 'omit', 'include')
     * @param {string} [fetchOptions.referrer] - Referrer URL or empty string for none
     * @param {ReferrerPolicy} [fetchOptions.referrerPolicy] - Referrer policy (e.g., 'no-referrer', 'origin')
     * @param {boolean} [fallbackOnCorrectionFailure=true] - Return original tile if corrections fail
     * @returns {Promise<{data: ArrayBuffer, wasFixed: boolean}>}
     */
    async fetchAndFixTile(tileUrl, z2, x22, y, layerConfig, fetchOptions = {}, fallbackOnCorrectionFailure = true) {
      const { signal } = fetchOptions;
      if (!layerConfig) {
        const response = await fetch(tileUrl, fetchOptions);
        if (!response.ok) throw await TileFetchError.fromResponse(response);
        return { data: await response.arrayBuffer(), wasFixed: false };
      }
      const [tileResult, correctionsResult] = await Promise.allSettled([
        fetch(tileUrl, fetchOptions).then(async (r) => {
          if (!r.ok) throw await TileFetchError.fromResponse(r);
          return r.arrayBuffer();
        }),
        this.getCorrections(z2, x22, y, signal)
      ]);
      signal?.throwIfAborted();
      if (tileResult.status === "rejected") {
        throw tileResult.reason;
      }
      const tileData = tileResult.value;
      const correctionsFailed = correctionsResult.status === "rejected";
      const correctionsError = correctionsFailed ? correctionsResult.reason : null;
      if (correctionsFailed && !fallbackOnCorrectionFailure) {
        throw correctionsError;
      }
      const corrections = correctionsResult.status === "fulfilled" ? correctionsResult.value : {};
      const hasCorrections = Object.values(corrections).some((arr) => arr && arr.length > 0);
      if (!hasCorrections) {
        return { data: tileData, wasFixed: false, correctionsFailed, correctionsError };
      }
      const fixedData = await this.fixTile(corrections, tileData, layerConfig, z2);
      return { data: fixedData, wasFixed: true, correctionsFailed: false, correctionsError: null };
    }
  };
  __publicField(_TileFixer, "_instances", /* @__PURE__ */ new Map());
  __publicField(_TileFixer, "_defaultCacheMaxFeatures", 25e3);
  var TileFixer = _TileFixer;

  // src/index.js
  function extendLeaflet(L2) {
    if (L2.TileLayer.IndiaBoundaryCorrected) {
      return;
    }
    L2.TileLayer.IndiaBoundaryCorrected = L2.TileLayer.extend({
      options: {
        pmtilesUrl: null,
        layerConfig: null,
        extraLayerConfigs: null,
        fallbackOnCorrectionFailure: true
      },
      initialize: function(url, options) {
        L2.TileLayer.prototype.initialize.call(this, url, options);
        this._pmtilesUrl = this.options.pmtilesUrl ?? getPmtilesUrl();
        this._tileFixer = TileFixer.getOrCreate(this._pmtilesUrl);
        this._registry = layerConfigs.createMergedRegistry(this.options.extraLayerConfigs);
        if (typeof this.options.layerConfig === "string") {
          this._layerConfig = this._registry.get(this.options.layerConfig);
        } else if (this.options.layerConfig) {
          this._layerConfig = this.options.layerConfig;
        } else {
          this._layerConfig = this._registry.detectFromTemplates([url]);
        }
        if (!this._layerConfig) {
          console.warn("[L.TileLayer.IndiaBoundaryCorrected] Could not detect layer config from URL. Corrections will not be applied.");
        }
      },
      createTile: function(coords, done) {
        const tile = document.createElement("img");
        const controller = new AbortController();
        const signal = controller.signal;
        tile.cancel = () => controller.abort();
        tile.alt = "";
        if (this.options.crossOrigin || this.options.crossOrigin === "") {
          tile.crossOrigin = this.options.crossOrigin === true ? "" : this.options.crossOrigin;
        }
        if (typeof this.options.referrerPolicy === "string") {
          tile.referrerPolicy = this.options.referrerPolicy;
        }
        if (!this._layerConfig) {
          tile.onload = () => done(null, tile);
          tile.onerror = (e) => done(e, tile);
          tile.src = this.getTileUrl(coords);
          return tile;
        }
        const tileUrl = this.getTileUrl(coords);
        const z2 = coords.z;
        const x3 = coords.x;
        const y = coords.y;
        const fallbackOnCorrectionFailure = this.options.fallbackOnCorrectionFailure;
        const fetchOptions = buildFetchOptions(this.options.crossOrigin, this.options.referrerPolicy);
        fetchOptions.signal = signal;
        this._tileFixer.fetchAndFixTile(tileUrl, z2, x3, y, this._layerConfig, fetchOptions, fallbackOnCorrectionFailure).then(({ data, correctionsFailed, correctionsError }) => {
          if (correctionsFailed) {
            console.warn("[L.TileLayer.IndiaBoundaryCorrected] Corrections fetch failed:", correctionsError);
            this.fire("correctionerror", { error: correctionsError, coords: { z: z2, x: x3, y }, tileUrl });
          }
          const blob = new Blob([data]);
          tile.src = URL.createObjectURL(blob);
          tile.cancel = void 0;
          tile.onload = () => {
            URL.revokeObjectURL(tile.src);
            done(null, tile);
          };
          tile.onerror = (e) => {
            URL.revokeObjectURL(tile.src);
            done(e, tile);
          };
        }).catch((err2) => {
          if (err2.name !== "AbortError") {
            console.warn("[L.TileLayer.IndiaBoundaryCorrected] Tile fetch failed:", err2);
            done(err2, tile);
          }
        });
        return tile;
      },
      _removeTile: function(key) {
        const tile = this._tiles[key];
        if (!tile) return;
        if (tile.el.cancel) tile.el.cancel();
        L2.TileLayer.prototype._removeTile.call(this, key);
      },
      getTileFixer: function() {
        return this._tileFixer;
      },
      getLayerConfig: function() {
        return this._layerConfig;
      }
    });
    L2.tileLayer.indiaBoundaryCorrected = function(url, options) {
      return new L2.TileLayer.IndiaBoundaryCorrected(url, options);
    };
  }
  return __toCommonJS(index_exports);
})();
//# sourceMappingURL=index.global.js.map