const routes = ["import", "summary", "insights", "compare"];
const API_BASE = (() => {
  const fromWindow = window.AIMSOLO_API_BASE;
  const fromMeta = document.querySelector('meta[name="api-base"]')?.content;
  const raw = fromWindow || fromMeta || "http://localhost:8000";
  return String(raw).replace(/\/+$/, "");
})();
const screens = routes.reduce((acc, route) => {
  const el = document.getElementById(`screen-${route}`);
  if (el) acc[route] = el;
  return acc;
}, {});

const appState = {
  sessionId: null,
  source: "mock",
  summary: null,
  insights: null,
  compare: null,
  error: null,
  loading: false,
  compareSelection: {
    referenceLap: null,
    targetLap: null,
  },
  trackMap: null,
  selectedSegmentId: null,
  mapView: { x: 0, y: 0, w: 1000, h: 1000 },
  mapKey: null,
  compareMap: null,
  compareMapView: { x: 0, y: 0, w: 1000, h: 1000 },
  compareMapKey: null,
  meta: {
    track_name: null,
    direction: null,
    session_date: null,
    rider_name: null,
    bike_name: null,
    session_id: null,
  },
  selection: {
    track: null,
    direction: null,
    date: null,
    rider: null,
    bike: null,
    session: null,
  },
  import: {
    filePath: "",
    fileName: "",
  },
};

function setRoute(route) {
  const target = routes.includes(route) ? route : "import";
  Object.entries(screens).forEach(([name, el]) => {
    el.classList.toggle("active", name === target);
  });
  if (window.location.hash.replace("#", "") !== target) {
    window.location.hash = target;
  }
}

function readRoute() {
  const hash = window.location.hash.replace("#", "").trim();
  return routes.includes(hash) ? hash : "import";
}

function bindRouteButtons() {
  document.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-route]");
    if (!btn) return;
    event.preventDefault();
    const route = btn.dataset.route;
    if (btn.dataset.compareLap) {
      const lap = Number(btn.dataset.compareLap);
      if (!Number.isNaN(lap)) {
        appState.compareSelection.targetLap = lap;
      }
    }
    setRoute(route);
    if (route === "import" && btn.closest(".status")) {
      hydrateFromApi({ force: true });
    }
    ensureDataForRoute(route);
  });
}

function initImport() {
  const analyzeNow = document.getElementById("analyze-now");
  const dropzone = qs(".dropzone");
  const fileInput = document.getElementById("csv-file");
  const filePathInput = document.getElementById("file-path");

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", (event) => {
      if (event.target.closest("button") || event.target.closest("input")) return;
      fileInput.click();
    });
    dropzone.addEventListener("dragover", (event) => event.preventDefault());
    dropzone.addEventListener("drop", (event) => {
      event.preventDefault();
      const file = event.dataTransfer?.files?.[0];
      if (file) handleSelectedFile(file);
    });
  }

  if (fileInput) {
    fileInput.addEventListener("change", (event) => {
      const file = event.target.files?.[0];
      if (file) handleSelectedFile(file);
    });
  }

  if (filePathInput) {
    filePathInput.addEventListener("input", () => {
      appState.import.filePath = filePathInput.value.trim();
      updateDropzoneNote();
    });
    filePathInput.addEventListener("click", (event) => event.stopPropagation());
  }

  if (analyzeNow) {
    analyzeNow.addEventListener("click", async (event) => {
      event.stopPropagation();
      await runImportAndLoad({ force: true, routeAfter: "summary" });
    });
  }
}

function qs(selector, root = document) {
  return root.querySelector(selector);
}

function qsa(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

function setText(el, value) {
  if (el) el.textContent = value ?? "";
}

function clearChildren(el) {
  if (!el) return;
  while (el.firstChild) el.removeChild(el.firstChild);
}

function parseLapTime(value) {
  if (!value) return null;
  const match = String(value).trim().match(/(\d+):(\d{2}\.\d{3})/);
  if (!match) return null;
  const minutes = Number(match[1]);
  const seconds = Number(match[2]);
  return minutes * 60 + seconds;
}

function parseGain(value) {
  if (value == null) return null;
  const match = String(value).match(/[-+]?\d*\.?\d+/);
  if (!match) return null;
  const num = Number(match[0]);
  return Number.isNaN(num) ? null : num;
}

function formatDelta(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return "--";
  const sign = seconds > 0 ? "+" : "";
  return `${sign}${seconds.toFixed(2)}`;
}

function getUnits() {
  return (
    appState.insights?.units ||
    appState.summary?.units ||
    appState.compare?.units ||
    "metric"
  );
}

function setStatusBadge(source) {
  const badge = qs(".status .badge");
  if (!badge) return;
  badge.classList.toggle("offline", source !== "api");
  badge.textContent = source === "api" ? "Live" : "Mock";
}

function ensureErrorBanner() {
  let banner = qs("#api-error");
  if (banner) return banner;
  const header = qs(".topbar");
  if (!header) return null;
  banner = document.createElement("div");
  banner.id = "api-error";
  banner.style.display = "none";
  banner.style.marginTop = "12px";
  banner.style.padding = "10px 14px";
  banner.style.borderRadius = "10px";
  banner.style.fontSize = "0.9rem";
  banner.style.background = "#4b1d1d";
  banner.style.color = "#ffecec";
  banner.style.border = "1px solid #7a2b2b";
  banner.style.boxShadow = "0 6px 18px rgba(0,0,0,0.2)";
  header.appendChild(banner);
  return banner;
}

function setApiError(message) {
  appState.error = message;
  const banner = ensureErrorBanner();
  if (!banner) return;
  if (!message) {
    banner.style.display = "none";
    banner.textContent = "";
    return;
  }
  banner.textContent = message;
  banner.style.display = "block";
}

function apiUrl(path) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${normalized}`;
}

function setLoading(isLoading) {
  appState.loading = isLoading;
  const analyzeNow = document.getElementById("analyze-now");
  if (analyzeNow) {
    analyzeNow.disabled = isLoading;
    analyzeNow.textContent = isLoading ? "Analyzing..." : "Analyze now";
  }
}

function setSelectValue(selectId, label) {
  if (!label) return;
  const select = document.getElementById(selectId);
  if (!select) return;
  const match = Array.from(select.options).find((opt) => opt.textContent === label);
  if (!match) {
    const option = document.createElement("option");
    option.value = label;
    option.textContent = label;
    select.appendChild(option);
  }
  select.value = label;
}

function applyMeta(meta) {
  if (!meta) return;
  appState.meta = {
    track_name: meta.track_name ?? appState.meta.track_name,
    direction: meta.direction ?? appState.meta.direction,
    session_date: meta.session_date ?? appState.meta.session_date,
    rider_name: meta.rider_name ?? appState.meta.rider_name,
    bike_name: meta.bike_name ?? appState.meta.bike_name,
    session_id: meta.session_id ?? appState.meta.session_id,
  };
  setSelectValue("track-select", appState.meta.track_name);
  setSelectValue("direction-select", appState.meta.direction);
  setSelectValue("date-select", appState.meta.session_date);
  setSelectValue("rider-select", appState.meta.rider_name);
  setSelectValue("bike-select", appState.meta.bike_name);
  if (appState.meta.session_id) {
    setSelectValue("session-select", `Session ${appState.meta.session_id}`);
  }
}

function normalizeTrackPoints(points) {
  if (!points || points.length === 0) return null;
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  points.forEach(([x, y]) => {
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  });
  const width = 1000;
  const height = 1000;
  const padding = 50;
  const rangeX = Math.max(1e-6, maxX - minX);
  const rangeY = Math.max(1e-6, maxY - minY);
  const scale = Math.min((width - 2 * padding) / rangeX, (height - 2 * padding) / rangeY);
  const offsetX = padding + (width - 2 * padding - rangeX * scale) / 2;
  const offsetY = padding + (height - 2 * padding - rangeY * scale) / 2;
  return points.map(([x, y, dist]) => [
    offsetX + (x - minX) * scale,
    offsetY + (maxY - y) * scale,
    dist,
  ]);
}

function buildPath(points) {
  if (!points || points.length === 0) return "";
  const [firstX, firstY] = points[0];
  let d = `M ${firstX.toFixed(1)} ${firstY.toFixed(1)}`;
  for (let i = 1; i < points.length; i += 1) {
    const [x, y] = points[i];
    d += ` L ${x.toFixed(1)} ${y.toFixed(1)}`;
  }
  return d;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function getMapView(svg) {
  return svg.id === "compare-map" ? appState.compareMapView : appState.mapView;
}

function setMapView(svg, view) {
  if (svg.id === "compare-map") {
    appState.compareMapView = view;
  } else {
    appState.mapView = view;
  }
}

function applyMapView(svg) {
  const view = getMapView(svg);
  svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.w} ${view.h}`);
}

function resetMapViewFor(svg) {
  setMapView(svg, { x: 0, y: 0, w: 1000, h: 1000 });
}

function attachMapControls(svg) {
  if (svg.dataset.zoomBound) return;
  svg.dataset.zoomBound = "1";

  svg.addEventListener(
    "wheel",
    (event) => {
      event.preventDefault();
      const rect = svg.getBoundingClientRect();
      const mouseX = (event.clientX - rect.left) / rect.width;
      const mouseY = (event.clientY - rect.top) / rect.height;
      const scale = event.deltaY < 0 ? 0.9 : 1.1;
      const view = getMapView(svg);
      let newW = view.w * scale;
      let newH = view.h * scale;
      newW = clamp(newW, 200, 2000);
      newH = clamp(newH, 200, 2000);
      const dx = (view.w - newW) * mouseX;
      const dy = (view.h - newH) * mouseY;
      const maxX = 1000 - newW;
      const maxY = 1000 - newH;
      setMapView(svg, {
        x: clamp(view.x + dx, 0, Math.max(0, maxX)),
        y: clamp(view.y + dy, 0, Math.max(0, maxY)),
        w: newW,
        h: newH,
      });
      applyMapView(svg);
    },
    { passive: false }
  );

  let panStart = null;
  svg.addEventListener("pointerdown", (event) => {
    panStart = {
      x: event.clientX,
      y: event.clientY,
      view: { ...getMapView(svg) },
    };
    svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener("pointermove", (event) => {
    if (!panStart) return;
    const rect = svg.getBoundingClientRect();
    const dx = (event.clientX - panStart.x) * (panStart.view.w / rect.width);
    const dy = (event.clientY - panStart.y) * (panStart.view.h / rect.height);
    const newX = panStart.view.x - dx;
    const newY = panStart.view.y - dy;
    const maxX = 1000 - panStart.view.w;
    const maxY = 1000 - panStart.view.h;
    setMapView(svg, {
      x: clamp(newX, 0, Math.max(0, maxX)),
      y: clamp(newY, 0, Math.max(0, maxY)),
      w: panStart.view.w,
      h: panStart.view.h,
    });
    applyMapView(svg);
  });
  const endPan = (event) => {
    if (!panStart) return;
    svg.releasePointerCapture(event.pointerId);
    panStart = null;
  };
  svg.addEventListener("pointerup", endPan);
  svg.addEventListener("pointercancel", endPan);

  svg.addEventListener("dblclick", () => {
    resetMapViewFor(svg);
    applyMapView(svg);
  });
}

function zoomMap(svg, scale) {
  const view = getMapView(svg);
  const cx = view.x + view.w / 2;
  const cy = view.y + view.h / 2;
  let newW = view.w * scale;
  let newH = view.h * scale;
  newW = clamp(newW, 200, 2000);
  newH = clamp(newH, 200, 2000);
  const newX = clamp(cx - newW / 2, 0, Math.max(0, 1000 - newW));
  const newY = clamp(cy - newH / 2, 0, Math.max(0, 1000 - newH));
  setMapView(svg, { x: newX, y: newY, w: newW, h: newH });
  applyMapView(svg);
}

function renderTrackMap(selectedSegmentId) {
  const svg = qs("#track-map");
  const meta = qs("#track-map-meta");
  if (!svg || !meta) return;
  const map = appState.trackMap;
  const refPoints = map?.reference_points || map?.points;
  const tgtPoints = map?.target_points;
  if (!map || !refPoints || refPoints.length === 0) {
    svg.innerHTML = "";
    meta.textContent = "Track map unavailable for this session.";
    return;
  }
  const mapKey = `${map.reference_lap ?? "ref"}-${map.target_lap ?? "tgt"}-${map.track_direction ?? ""}`;
  if (appState.mapKey !== mapKey) {
    appState.mapKey = mapKey;
    resetMapViewFor(svg);
  }
  const normalizedRef = normalizeTrackPoints(refPoints);
  const normalizedTgt = tgtPoints ? normalizeTrackPoints(tgtPoints) : null;
  if (!normalizedRef) {
    svg.innerHTML = "";
    meta.textContent = "Track map unavailable for this session.";
    return;
  }
  const basePath = buildPath(normalizedRef);
  const targetPath = normalizedTgt ? buildPath(normalizedTgt) : "";
  let highlightPath = "";
  let highlightRefPath = "";
  let apexPoint = null;
  let highlightLabel = "";
  if (selectedSegmentId && map.segments) {
    const segment =
      map.segments.find((seg) => seg.id === selectedSegmentId) ||
      map.segments.find((seg) => selectedSegmentId && seg.id?.endsWith(selectedSegmentId));
    if (segment) {
      const segPoints = normalizedTgt
        ? normalizedTgt.filter(([, , dist]) => dist >= segment.start_m && dist <= segment.end_m)
        : normalizedRef.filter(([, , dist]) => dist >= segment.start_m && dist <= segment.end_m);
      const refSegPoints = normalizedRef.filter(([, , dist]) => dist >= segment.start_m && dist <= segment.end_m);
      highlightPath = buildPath(segPoints);
      highlightRefPath = buildPath(refSegPoints);
      if (segment.apex_m != null) {
        let best = null;
        (normalizedTgt || normalizedRef).forEach((pt) => {
          const dist = pt[2];
          if (dist == null) return;
          const delta = Math.abs(dist - segment.apex_m);
          if (!best || delta < best.delta) {
            best = { pt, delta };
          }
        });
        if (best) apexPoint = best.pt;
      }
      highlightLabel = segment.label || segment.id || "";
      meta.textContent = `Highlight: ${highlightLabel}`;
    }
  }
  if (!highlightLabel) {
    meta.textContent = "Select an insight to highlight its segment.";
  }
  const refLabel = map.reference_lap ? `Reference Lap ${map.reference_lap}` : "Reference";
  const tgtLabel = map.target_lap ? `Target Lap ${map.target_lap}` : "Target";
  meta.textContent = highlightLabel
    ? `Highlight: ${highlightLabel} • ${tgtLabel} vs ${refLabel}`
    : `${tgtLabel} vs ${refLabel}`;
  svg.innerHTML = `
    <path class="track-base" d="${basePath}" />
    ${targetPath ? `<path class="track-target" d="${targetPath}" />` : ""}
    <path class="track-reference" d="${basePath}" />
    ${highlightRefPath ? `<path class="track-highlight ref" d="${highlightRefPath}" />` : ""}
    ${highlightPath ? `<path class="track-highlight" d="${highlightPath}" />` : ""}
    ${apexPoint ? `<circle class="track-apex" cx="${apexPoint[0].toFixed(1)}" cy="${apexPoint[1].toFixed(1)}" r="10" />` : ""}
  `;
  applyMapView(svg);
  attachMapControls(svg);
}

function renderCompareMap() {
  const svg = qs("#compare-map");
  if (!svg) return;
  const map = appState.compareMap || appState.trackMap;
  const refPoints = map?.points_a || map?.reference_points || map?.points;
  const tgtPoints = map?.points_b || map?.target_points;
  if (!refPoints || refPoints.length === 0) {
    svg.innerHTML = "";
    return;
  }
  const mapKey = `${map?.lap_a ?? map?.reference_lap ?? "ref"}-${map?.lap_b ?? map?.target_lap ?? "tgt"}`;
  if (appState.compareMapKey !== mapKey) {
    appState.compareMapKey = mapKey;
    resetMapViewFor(svg);
  }
  const normalizedRef = normalizeTrackPoints(refPoints);
  const normalizedTgt = tgtPoints ? normalizeTrackPoints(tgtPoints) : null;
  if (!normalizedRef) {
    svg.innerHTML = "";
    return;
  }
  const basePath = buildPath(normalizedRef);
  const targetPath = normalizedTgt ? buildPath(normalizedTgt) : "";
  svg.innerHTML = `
    <path class="track-base" d="${basePath}" />
    ${targetPath ? `<path class="track-target" d="${targetPath}" />` : ""}
    <path class="track-reference" d="${basePath}" />
  `;
  applyMapView(svg);
  attachMapControls(svg);
}

function updateDropzoneNote(message) {
  const note = document.getElementById("dropzone-note");
  if (!note) return;
  if (message) {
    note.textContent = message;
    return;
  }
  if (appState.import.filePath) {
    note.textContent = `Using path: ${appState.import.filePath}`;
    return;
  }
  if (appState.import.fileName) {
    note.textContent = `Selected: ${appState.import.fileName} (paste full path to import)`;
    return;
  }
  note.textContent = "No file selected";
}

function handleSelectedFile(file) {
  appState.import.fileName = file?.name || "";
  updateDropzoneNote();
}

function readFilePath() {
  const input = document.getElementById("file-path");
  if (!input) return "";
  return input.value.trim();
}

function createMockData() {
  return {
    session_id: "mock-session",
    track_name: "Laguna Seca",
    direction: "CW",
    track_direction: "Laguna Seca CW",
    session_date: "Feb 4",
    analytics_version: "0.1.0-local",
    summary: {
      track_name: "Laguna Seca",
      direction: "CW",
      track_direction: "Laguna Seca CW",
      analytics_version: "0.1.0-local",
      units: "imperial",
      cards: [
        { id: "best_lap", label: "Best Lap", value: "1:32.418", delta: "-0.213", trend: "up" },
        { id: "avg_lap", label: "Avg Lap", value: "1:33.201", delta: "+0.145", trend: "down" },
        { id: "consistency", label: "Consistency", value: "92%", delta: "+3%", trend: "up" },
      ],
      laps: [
        { lap: 1, time: "1:33.021", sector_times: ["0:31.112", "0:30.540", "0:31.369"], is_best: false },
        { lap: 2, time: "1:32.418", sector_times: ["0:30.980", "0:30.312", "0:31.126"], is_best: true },
        { lap: 3, time: "1:33.164", sector_times: ["0:31.230", "0:30.600", "0:31.334"], is_best: false },
      ],
    },
    insights: {
      track_name: "Laguna Seca",
      direction: "CW",
      track_direction: "Laguna Seca CW",
      analytics_version: "0.1.0-local",
      units: "imperial",
      items: [
        {
          id: "trail_braking",
          title: "Longer trail braking into T3",
          confidence: 0.78,
          gain: "+0.18",
          detail: "Maintain 5% brake to apex for better rotation.",
        },
        {
          id: "throttle_pickup",
          title: "Earlier throttle in T7",
          confidence: 0.64,
          gain: "+0.09",
          detail: "Smooth to 70% throttle by mid-corner.",
        },
      ],
    },
    compare: {
      track_name: "Laguna Seca",
      direction: "CW",
      track_direction: "Laguna Seca CW",
      analytics_version: "0.1.0-local",
      units: "imperial",
      comparison: {
        reference_lap: 2,
        target_lap: 3,
        delta_by_sector: ["-0.10", "+0.04", "+0.09"],
        brake_points: [
          { corner: "T3", delta_m: -5 },
          { corner: "T7", delta_m: 3 },
        ],
      },
    },
  };
}

async function apiFetch(path, options) {
  const response = await fetch(apiUrl(path), options);
  if (!response.ok) {
    throw new Error(`api_error:${response.status}`);
  }
  return response.json();
}

function describeApiError(error, context) {
  if (!error) return "Unknown API error.";
  if (error.message?.startsWith("api_error:")) {
    const status = error.message.split(":")[1];
    return `API error ${status} from ${API_BASE}${context ? ` (${context})` : ""}.`;
  }
  if (error.message?.startsWith("api_payload:")) {
    const [, endpoint, detail] = error.message.split(":");
    return `API response error from ${endpoint}${detail ? `: ${detail}` : ""}.`;
  }
  if (error.name === "TypeError") {
    return `Network/CORS error: unable to reach ${API_BASE}.`;
  }
  return `API error: ${error.message || "unknown failure"}.`;
}

async function loadSession(filePath) {
  try {
    const bodyPayload = filePath ? { file_path: filePath } : {};
    const payload = await apiFetch("/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bodyPayload),
    });
    if (!payload?.session_id) throw new Error("missing_session");
    applyMeta(payload);
    return payload;
  } catch (error) {
    setApiError(describeApiError(error, "import"));
    return null;
  }
}

async function loadEndpoint(path) {
  try {
    const data = await apiFetch(path);
    if (data?.error) {
      const detail = data.detail || data.error;
      throw new Error(`api_payload:${path}:${detail}`);
    }
    return data;
  } catch (error) {
    setApiError(describeApiError(error, path));
    return null;
  }
}

function clearSummary() {
  setText(qs(".best-lap .big-time"), "--");
  setText(qs(".best-lap .meta"), "--");
  setText(qs(".consistency .meta"), "--");
  const alerts = qs(".alerts ul");
  if (alerts) {
    clearChildren(alerts);
    const li = document.createElement("li");
    li.textContent = "No alerts yet - waiting on analysis";
    alerts.appendChild(li);
  }
  const lapTable = qs(".lap-table");
  if (lapTable) {
    qsa(".lap-row", lapTable).forEach((row) => row.remove());
  }
}

function renderSummary(summary) {
  if (!summary) {
    clearSummary();
    return;
  }
  const cards = summary.cards || [];
  const best = cards.find((card) => card.id === "best_lap") || cards[0];
  const consistency = cards.find((card) => card.id === "consistency") || cards[2];

  setText(qs(".best-lap .big-time"), best?.value || "--");
  setText(
    qs(".best-lap .meta"),
    best ? `Delta ${best.delta ?? "--"} - ${best.label ?? "Best Lap"}` : "--"
  );
  setText(qs(".consistency .meta"), consistency ? `${consistency.value} - ${consistency.delta}` : "--");

  const alerts = qs(".alerts ul");
  if (alerts) {
    clearChildren(alerts);
    const items = (appState.insights?.items || []).slice(0, 3);
    if (items.length === 0) {
      const li = document.createElement("li");
      li.textContent = "No alerts yet - waiting on analysis";
      alerts.appendChild(li);
    } else {
      items.forEach((item) => {
        const li = document.createElement("li");
        li.textContent = item.title;
        alerts.appendChild(li);
      });
    }
  }

  const lapTable = qs(".lap-table");
  if (lapTable) {
    qsa(".lap-row", lapTable).forEach((row) => row.remove());
    const laps = summary.laps || [];
    const bestLap = laps.find((lap) => lap.is_best) || laps[0];
    const bestSeconds = parseLapTime(bestLap?.time);
    if (bestLap?.lap != null) {
      appState.compareSelection.referenceLap = bestLap.lap;
    }
    laps.forEach((lap) => {
      const row = document.createElement("div");
      row.className = "lap-row";
      const lapSeconds = parseLapTime(lap.time);
      const delta = bestSeconds != null && lapSeconds != null ? lapSeconds - bestSeconds : null;
      row.innerHTML = `
        <div>${lap.lap}</div>
        <div>${lap.time ?? "--"}</div>
        <div>${formatDelta(delta)}</div>
        <div class="valid">Yes</div>
        <button class="ghost" data-route="compare" data-compare-lap="${lap.lap}">Compare</button>
      `;
      lapTable.appendChild(row);
    });
  }
}

function clearInsights() {
  const list = qs(".insight-list");
  if (!list) return;
  clearChildren(list);
  const article = document.createElement("article");
  article.className = "card insight";
  article.innerHTML = `
    <div class="card-head">
      <h3>Insights not ready</h3>
      <span class="badge low">Low</span>
    </div>
    <p>Run analysis to generate coaching insights.</p>
    <div class="card-foot">
      <span class="gain">--</span>
      <button class="ghost">Why?</button>
    </div>
  `;
  list.appendChild(article);
  setText(qs(".map-meta"), "Selected: Overview");
}

function formatEvidence(evidence = {}) {
  const rows = [];
  const push = (label, value) => {
    if (value == null || Number.isNaN(value)) return;
    rows.push(`${label}: ${value}`);
  };
  const num = (value, digits = 2) => (value == null ? null : Number(value).toFixed(digits));
  const units = getUnits();
  const distLabel = units === "imperial" ? "ft" : "m";
  const speedLabel = units === "imperial" ? "mph" : "km/h";
  push(
    "Brake point delta",
    evidence.brake_point_delta_m != null ? `${num(evidence.brake_point_delta_m)} ${distLabel}` : null
  );
  push(
    "Throttle pickup delta",
    evidence.pickup_delta_m != null ? `${num(evidence.pickup_delta_m)} ${distLabel}` : null
  );
  push(
    "Throttle pickup delta",
    evidence.pickup_delta_s != null ? `${num(evidence.pickup_delta_s, 3)} s` : null
  );
  push(
    "Neutral throttle",
    evidence.neutral_throttle_s != null ? `${num(evidence.neutral_throttle_s, 2)} s` : null
  );
  push(
    "Neutral throttle",
    evidence.neutral_throttle_dist_m != null ? `${num(evidence.neutral_throttle_dist_m)} ${distLabel}` : null
  );
  push(
    "Speed change while coasting",
    evidence.neutral_speed_delta_kmh != null ? `${num(evidence.neutral_speed_delta_kmh, 2)} ${speedLabel}` : null
  );
  push(
    "Line variance",
    evidence.line_stddev_m != null ? `${num(evidence.line_stddev_m, 2)} ${distLabel}` : null
  );
  push(
    "Line variance delta",
    evidence.line_stddev_delta_m != null ? `${num(evidence.line_stddev_delta_m, 2)} ${distLabel}` : null
  );
  push(
    "Apex variability",
    evidence.apex_stddev_m != null ? `${num(evidence.apex_stddev_m, 2)} ${distLabel}` : null
  );
  push(
    "Recommended apex",
    evidence.apex_recommend_m != null ? `${num(evidence.apex_recommend_m, 0)} ${distLabel}` : null
  );
  push(
    "Apex offset",
    evidence.apex_bias_m != null ? `${num(evidence.apex_bias_m, 1)} ${distLabel}` : null
  );
  push(
    "Trend laps",
    evidence.trend_laps != null ? `${num(evidence.trend_laps, 0)}` : null
  );
  push(
    "Trend sessions",
    evidence.trend_session_count != null ? `${num(evidence.trend_session_count, 0)}` : null
  );
  let trendStrength = evidence.trend_strength;
  if (trendStrength != null) {
    const normalized = String(trendStrength).toLowerCase();
    if (normalized === "light") {
      trendStrength = "emerging";
    }
  }
  push("Trend strength", trendStrength != null ? `${trendStrength}` : null);
  push(
    "Min speed delta",
    evidence.min_speed_delta_kmh != null ? `${num(evidence.min_speed_delta_kmh, 2)} ${speedLabel}` : null
  );
  push(
    "Apex delta",
    evidence.apex_delta_m != null ? `${num(evidence.apex_delta_m, 2)} ${distLabel}` : null
  );
  push(
    "Exit speed delta",
    evidence.exit_speed_delta_kmh != null ? `${num(evidence.exit_speed_delta_kmh, 2)} ${speedLabel}` : null
  );
  push(
    "Accel delta",
    evidence.inline_acc_rise_delta_g != null ? `${num(evidence.inline_acc_rise_delta_g, 3)} g` : null
  );
  push(
    "Entry speed delta",
    evidence.entry_speed_delta_kmh != null ? `${num(evidence.entry_speed_delta_kmh, 2)} ${speedLabel}` : null
  );
  push("Yaw ratio", evidence.yaw_rms_ratio != null ? `${num(evidence.yaw_rms_ratio, 2)}x` : null);
  push(
    "Segment time delta",
    evidence.segment_time_delta_s != null ? `${num(evidence.segment_time_delta_s, 3)} s` : null
  );
  return rows;
}

function actionStepsFor(ruleId) {
  switch (ruleId) {
    case "early_braking":
      return [
        "Move brake marker 10-15m later.",
        "Keep a light trail brake to the apex.",
        "Verify entry speed rises without overshooting.",
      ];
    case "late_throttle_pickup":
      return [
        "Start throttle pickup sooner after the apex.",
        "Aim for a smooth, earlier roll-on.",
        "Check exit speed improves without running wide.",
      ];
    case "neutral_throttle":
      return [
        "Avoid coasting: choose brake or throttle.",
        "Hold a small maintenance throttle if stable.",
        "Re-check segment time after each change.",
      ];
    case "line_inconsistency":
      return [
        "Choose one reference line and repeat it.",
        "Use fixed turn-in and apex markers.",
        "Reduce mid-corner corrections.",
      ];
    case "corner_speed_loss":
      return [
        "Focus on a higher apex speed.",
        "Release brake earlier to carry speed.",
        "Confirm exit stays stable.",
      ];
    case "exit_speed":
      return [
        "Prioritize earlier drive on exit.",
        "Pick up throttle at or just after apex.",
        "Track exit speed vs. reference.",
      ];
    case "entry_speed":
      return [
        "Carry more speed into the corner.",
        "Avoid over-slowing with early braking.",
        "Compare entry speed delta next lap.",
      ];
    case "steering_smoothness":
      return [
        "Smooth initial steering input.",
        "Reduce mid-corner corrections.",
        "Focus on consistent yaw with higher min speed.",
      ];
    default:
      return ["Run a focused lap and compare segment deltas."];
  }
}

function renderInsights(insights) {
  if (!insights) {
    clearInsights();
    return;
  }
  const list = qs(".insight-list");
  if (!list) return;
  clearChildren(list);
  const rawItems = insights.items || [];
  const deduped = [];
  const seen = new Set();
  rawItems.forEach((item) => {
    const key = `${item.title || ""}|${item.detail || ""}`;
    if (seen.has(key)) return;
    seen.add(key);
    deduped.push(item);
  });
  deduped.forEach((item, index) => {
    const confidence = Number(item.confidence ?? 0);
    const badgeClass = confidence >= 0.75 ? "high" : confidence >= 0.5 ? "med" : "low";
    const badgeLabel = confidence >= 0.75 ? "High" : confidence >= 0.5 ? "Med" : "Low";
    const segmentId = item.segment_id || item.corner_id;
    const segmentLabel = segmentId ? `Segment ${segmentId}` : "";
    const evidenceRows = formatEvidence(item.evidence || {});
    const actions =
      Array.isArray(item.actions) && item.actions.length > 0
        ? item.actions
        : actionStepsFor(item.rule_id || item.id);
    const options = Array.isArray(item.options) ? item.options : [];
    const article = document.createElement("article");
    article.className = "card insight";
    if (segmentId) {
      article.dataset.segmentId = segmentId;
    }
    article.style.setProperty("--delay", `${index * 80}ms`);
    const gainValue = parseGain(item.gain);
    const gainText = gainValue != null ? `${gainValue.toFixed(3)}s` : "";
    article.innerHTML = `
      <div class="card-head">
        <h3>${item.title ?? "Insight"}</h3>
        <span class="badge ${badgeClass}">${badgeLabel}</span>
      </div>
      <p>${item.detail ?? ""}</p>
      ${segmentLabel ? `<div class="meta">${segmentLabel}</div>` : ""}
      <div class="card-foot">
        <span class="gain">${gainText}</span>
        <button class="ghost">Why?</button>
      </div>
      <div class="insight-details" style="display: none;">
        <div class="meta">Why this matters</div>
        <ul>
          ${evidenceRows.map((row) => `<li>${row}</li>`).join("")}
        </ul>
        <div class="meta">What to do</div>
        <ul>
          ${actions.map((step) => `<li>${step}</li>`).join("")}
        </ul>
        ${
          options.length > 0
            ? `<div class="meta">Alternate lines</div>
        <ul>
          ${options.map((row) => `<li>${row}</li>`).join("")}
        </ul>`
            : ""
        }
      </div>
    `;
    list.appendChild(article);
  });

  const context = qs("#insights-context");
  if (context) {
    const rider = insights.rider_name || appState.meta.rider_name || "Unknown rider";
    const bike = insights.bike_name || appState.meta.bike_name || "Unknown bike";
    const track = insights.track_name || appState.meta.track_name || "Unknown track";
    const direction = insights.direction || appState.meta.direction || "";
    const session = appState.meta.session_id ? `Session ${appState.meta.session_id}` : "Session";
    context.innerHTML = `
      <div><strong>${session}</strong></div>
      <div>${track} ${direction ? `(${direction})` : ""}</div>
      <div>${rider} • ${bike}</div>
    `;
  }

  const deltaList = qs("#delta-list");
  if (deltaList) {
    clearChildren(deltaList);
    const comparison = appState.compare?.comparison || {};
    const segments = comparison.delta_by_segment || [];
    const sectors = comparison.delta_by_sector || [];
    if (segments.length > 0) {
      segments.forEach((seg) => {
        const row = document.createElement("div");
        row.className = "delta-row";
        row.textContent = `${seg.segment_id ?? "Segment"}: ${formatDelta(seg.delta_s)}s`;
        deltaList.appendChild(row);
      });
    } else if (sectors.length > 0) {
      sectors.forEach((delta, index) => {
        const row = document.createElement("div");
        row.className = "delta-row";
        row.textContent = `Sector ${index + 1}: ${delta ?? "--"}`;
        deltaList.appendChild(row);
      });
    } else {
      const row = document.createElement("div");
      row.className = "delta-row";
      row.textContent = "No segment deltas available yet.";
      deltaList.appendChild(row);
    }
  }

  const summary = qs("#insight-summary");
  if (summary) {
    clearChildren(summary);
    const total = deduped.length;
    const high = deduped.filter((item) => (item.confidence ?? 0) >= 0.75).length;
    const med = deduped.filter((item) => (item.confidence ?? 0) >= 0.5 && (item.confidence ?? 0) < 0.75).length;
    const low = total - high - med;
    const topGain = deduped
      .map((item) => parseGain(item.gain))
      .filter((value) => value != null)
      .sort((a, b) => b - a)[0];
    const rows = [
      `Insights: ${total}`,
      `High confidence: ${high}`,
      `Medium confidence: ${med}`,
      `Low confidence: ${low}`,
      topGain != null ? `Largest gain: +${topGain.toFixed(3)}s` : "Largest gain: --",
    ];
    rows.forEach((text) => {
      const row = document.createElement("div");
      row.className = "delta-row";
      row.textContent = text;
      summary.appendChild(row);
    });
  }

  if (insights.track_map) {
    appState.trackMap = insights.track_map;
  }
  renderTrackMap(appState.selectedSegmentId);
}

function clearCompare() {
  const selects = qsa("#screen-compare select");
  selects.forEach((select) => {
    clearChildren(select);
    const option = document.createElement("option");
    option.textContent = "No laps available";
    option.value = "";
    select.appendChild(option);
  });
  const table = qs(".compare-table");
  if (table) {
    qsa(".table-row", table).forEach((row) => row.remove());
  }
}

function renderCompare(compare) {
  if (!compare) {
    clearCompare();
    return;
  }
  const comparison = compare.comparison || {};
  const laps = appState.summary?.laps || [];
  const selects = qsa("#screen-compare select");
  selects.forEach((select) => {
    clearChildren(select);
    if (laps.length === 0) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "No laps available";
      select.appendChild(option);
      return;
    }
    laps.forEach((lap) => {
      const option = document.createElement("option");
      option.value = lap.lap;
      option.textContent = `Lap ${lap.lap} - ${lap.time ?? "--"}${lap.is_best ? " (Best)" : ""}`;
      select.appendChild(option);
    });
  });
  if (selects[0] && comparison.reference_lap) selects[0].value = String(comparison.reference_lap);
  if (selects[1] && comparison.target_lap) selects[1].value = String(comparison.target_lap);
  if (selects[0] && appState.compareSelection.referenceLap) {
    selects[0].value = String(appState.compareSelection.referenceLap);
  }
  if (selects[1] && appState.compareSelection.targetLap) {
    selects[1].value = String(appState.compareSelection.targetLap);
  }
  const lapA = selects[0]?.value;
  const lapB = selects[1]?.value;
  if (lapA) appState.compareSelection.referenceLap = Number(lapA);
  if (lapB) appState.compareSelection.targetLap = Number(lapB);
  fetchCompareMap(lapA, lapB);

  const table = qs(".compare-table");
  if (table) {
    qsa(".table-row", table).forEach((row) => row.remove());
    const segments = comparison.delta_by_segment || [];
    const sectors = comparison.delta_by_sector || [];
    if (segments.length > 0) {
      segments.forEach((segment) => {
        const row = document.createElement("div");
        row.className = "table-row";
        row.innerHTML = `
          <div>${segment.segment_id ?? "--"}</div>
          <div>--</div>
          <div>--</div>
          <div>--</div>
          <div class="delta">${formatDelta(segment.delta_s)}</div>
        `;
        table.appendChild(row);
      });
    } else if (sectors.length > 0) {
      sectors.forEach((delta, index) => {
        const row = document.createElement("div");
        row.className = "table-row";
        row.innerHTML = `
          <div>S${index + 1}</div>
          <div>--</div>
          <div>--</div>
          <div>--</div>
          <div class="delta">${delta ?? "--"}</div>
        `;
        table.appendChild(row);
      });
    }
  }
  renderCompareMap();
}

async function fetchCompareMap(lapA, lapB) {
  if (!appState.sessionId) return;
  const params = new URLSearchParams();
  if (lapA) params.set("lap_a", lapA);
  if (lapB) params.set("lap_b", lapB);
  const path = `/map/${appState.sessionId}?${params.toString()}`;
  const map = await loadEndpoint(path);
  if (map) {
    appState.compareMap = map;
    renderCompareMap();
  }
}

function applyData(data, source) {
  appState.source = source;
  appState.summary = data.summary;
  appState.insights = data.insights;
  appState.compare = data.compare;
  setStatusBadge(source);
  applyMeta(data.summary || data.insights || data.compare);
  if (data.insights?.track_map) {
    appState.trackMap = data.insights.track_map;
  }
  renderSummary(appState.summary);
  renderInsights(appState.insights);
  renderCompare(appState.compare);
}

async function hydrateFromApi({ force, filePath } = {}) {
  setApiError(null);
  setLoading(true);
  const session = await loadSession(filePath);
  if (!session?.session_id) {
    if (force) setApiError(`Using mock data. API unavailable at ${API_BASE}.`);
    applyData(createMockData(), "mock");
    setLoading(false);
    return null;
  }
  appState.sessionId = session.session_id;
  const [summary, insights, compare] = await Promise.all([
    loadEndpoint(`/summary/${session.session_id}`),
    loadEndpoint(`/insights/${session.session_id}`),
    loadEndpoint(`/compare/${session.session_id}`),
  ]);
  if (!summary || !insights || !compare) {
    if (force) setApiError(`Data not ready for session ${session.session_id}.`);
    applyData({ summary: summary || null, insights: insights || null, compare: compare || null }, "api");
    setLoading(false);
    return session;
  }
  applyData({ summary, insights, compare }, session.source === "mock" ? "mock" : "api");
  setLoading(false);
  return session;
}

async function runImportAndLoad({ force, routeAfter } = {}) {
  if (appState.loading) return;
  const filePath = readFilePath();
  appState.import.filePath = filePath;
  updateDropzoneNote();
  const session = await hydrateFromApi({ force, filePath });
  if (session && routeAfter) setRoute(routeAfter);
}

async function ensureDataForRoute(route) {
  if (route === "import") return;
  if (appState.loading) return;
  if (!appState.sessionId) {
    await hydrateFromApi({ force: false });
    return;
  }
  if (!appState.summary || !appState.insights || !appState.compare) {
    await hydrateFromApi({ force: false, filePath: appState.import.filePath });
  }
}

function bindSelectionControls() {
  const bindings = [
    { id: "track-select", key: "track" },
    { id: "direction-select", key: "direction" },
    { id: "date-select", key: "date" },
    { id: "rider-select", key: "rider" },
    { id: "bike-select", key: "bike" },
    { id: "session-select", key: "session" },
  ];
  bindings.forEach(({ id, key }) => {
    const el = document.getElementById(id);
    if (!el) return;
    appState.selection[key] = el.value;
    el.addEventListener("change", () => {
      appState.selection[key] = el.value;
      updateDropzoneNote();
    });
  });
}

function bindInsightButtons() {
  document.addEventListener("click", (event) => {
    const btn = event.target.closest(".insight .ghost");
    if (!btn) return;
    const card = btn.closest(".insight");
    if (!card) return;
    card.classList.toggle("expanded");
    const details = card.querySelector(".insight-details");
    if (details) {
      const show = card.classList.contains("expanded");
      details.style.display = show ? "block" : "none";
    }
    if (card.dataset.segmentId) {
      appState.selectedSegmentId = card.dataset.segmentId;
      renderTrackMap(appState.selectedSegmentId);
    }
    btn.textContent = card.classList.contains("expanded") ? "Less" : "Why?";
  });
}

function bindMapButtons() {
  document.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-map-action]");
    if (!btn) return;
    const target = btn.dataset.mapTarget;
    const action = btn.dataset.mapAction;
    const svg = target === "compare" ? qs("#compare-map") : qs("#track-map");
    if (!svg) return;
    if (action === "zoom-in") {
      zoomMap(svg, 0.9);
    } else if (action === "zoom-out") {
      zoomMap(svg, 1.1);
    } else if (action === "reset") {
      resetMapViewFor(svg);
      applyMapView(svg);
    }
  });
}
function bindCompareSelectors() {
  const selects = qsa("#screen-compare select");
  selects.forEach((select) => {
    select.addEventListener("change", async () => {
      if (!appState.sessionId) return;
      const compare = await loadEndpoint(
        `/compare/${appState.sessionId}?reference_lap=${selects[0]?.value || ""}&target_lap=${selects[1]?.value || ""}`
      );
      if (compare) {
        appState.compare = compare;
        renderCompare(compare);
      }
    });
  });
}

function init() {
  bindRouteButtons();
  initImport();
  bindSelectionControls();
  bindInsightButtons();
  bindMapButtons();
  bindCompareSelectors();
  setRoute(readRoute());
  hydrateFromApi();
  updateDropzoneNote();

  window.addEventListener("hashchange", () => {
    const route = readRoute();
    setRoute(route);
    ensureDataForRoute(route);
  });
}

document.addEventListener("DOMContentLoaded", init);
