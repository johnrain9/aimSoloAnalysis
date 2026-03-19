const routes = ["import", "summary", "insights", "compare", "corner"];
const API_BASE = (() => {
  const fromWindow = window.AIMSOLO_API_BASE;
  const fromMeta = document.querySelector('meta[name="api-base"]')?.content;
  const raw = fromWindow || fromMeta || "http://localhost:8000";
  return String(raw).replace(/\/+$/, "");
})();

const appState = {
  route: "import",
  sessionId: null,
  source: "mock",
  loading: false,
  error: "",
  import: {
    filePath: "",
    fileName: "",
  },
  meta: {
    session_id: null,
    track_name: null,
    direction: null,
    rider_name: null,
    bike_name: null,
  },
  summary: null,
  insights: null,
  compare: null,
  trackMap: null,
  compareMap: null,
  selectedInsightId: null,
  selectedSegmentId: null,
  compareSelection: {
    referenceLap: null,
    targetLap: null,
  },
};

function qs(selector, root = document) {
  return root.querySelector(selector);
}

function qsa(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

function setRoute(route) {
  const nextRoute = routes.includes(route) ? route : "import";
  appState.route = nextRoute;
  qsa(".screen").forEach((screen) => {
    screen.classList.toggle("active", screen.id === `screen-${nextRoute}`);
  });
  qsa("[data-route]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.route === nextRoute);
  });
  if (window.location.hash.replace("#", "") !== nextRoute) {
    window.location.hash = nextRoute;
  }
}

function readRoute() {
  const hash = window.location.hash.replace("#", "").trim();
  return routes.includes(hash) ? hash : "import";
}

function setLoading(isLoading) {
  appState.loading = isLoading;
  const button = qs("#analyze-now");
  if (!button) return;
  button.disabled = isLoading;
  button.textContent = isLoading ? "Analyzing..." : "Analyze now";
}

function setError(message) {
  appState.error = message || "";
  const banner = qs("#error-banner");
  if (!banner) return;
  if (!message) {
    banner.hidden = true;
    banner.textContent = "";
    return;
  }
  banner.hidden = false;
  banner.textContent = message;
}

function setConnectionBadge(source) {
  const badge = qs("#connection-badge");
  if (!badge) return;
  badge.textContent = source === "api" ? "Live" : "Offline";
  badge.className = source === "api" ? "status-badge status-live" : "status-badge status-offline";
}

function setSessionBadge() {
  const badge = qs("#session-badge");
  if (!badge) return;
  if (!appState.sessionId) {
    badge.textContent = "No session";
    return;
  }
  const track = appState.meta.track_name || "Track";
  badge.textContent = `${track} • Session ${appState.sessionId}`;
}

function updateDropzoneNote(message) {
  const note = qs("#dropzone-note");
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
    note.textContent = `Selected: ${appState.import.fileName}. Paste a full path for import.`;
    return;
  }
  note.textContent = "No file selected.";
}

function applyMeta(meta) {
  if (!meta) return;
  appState.meta = {
    session_id: meta.session_id ?? appState.meta.session_id,
    track_name: meta.track_name ?? appState.meta.track_name,
    direction: meta.direction ?? appState.meta.direction,
    rider_name: meta.rider_name ?? appState.meta.rider_name,
    bike_name: meta.bike_name ?? appState.meta.bike_name,
  };
  appState.sessionId = meta.session_id ?? appState.sessionId;
  setSessionBadge();
}

function apiUrl(path) {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

async function apiFetch(path, options) {
  const response = await fetch(apiUrl(path), options);
  if (!response.ok) {
    throw new Error(`api_error:${response.status}:${path}`);
  }
  return response.json();
}

function describeApiError(error) {
  if (!error) return "Unknown API error.";
  if (error.message?.startsWith("api_error:")) {
    const [, status, path] = error.message.split(":");
    return `API error ${status} from ${path}.`;
  }
  if (error.name === "TypeError") {
    return `Network/CORS error: unable to reach ${API_BASE}.`;
  }
  return `API error: ${error.message || "unknown failure"}.`;
}

function createMockMap() {
  const reference = [
    [60, 840, 0],
    [170, 720, 120],
    [340, 650, 240],
    [510, 610, 360],
    [730, 550, 480],
    [860, 430, 600],
    [820, 260, 720],
    [630, 170, 840],
    [410, 170, 960],
    [190, 240, 1080],
    [70, 420, 1200],
    [60, 840, 1320],
  ];
  const target = reference.map(([x, y, d], index) => [x + (index % 2 === 0 ? 18 : -12), y + (index < 6 ? -14 : 10), d]);
  return {
    reference_lap: 2,
    target_lap: 3,
    track_direction: "Laguna Seca CW",
    reference_points: reference,
    target_points: target,
    segments: [
      { id: "T3", label: "T3", start_m: 180, apex_m: 250, end_m: 360 },
      { id: "T7", label: "T7", start_m: 600, apex_m: 700, end_m: 820 },
    ],
    units: "imperial",
    unit_contract: {
      system: "imperial",
      distance: "ft",
      speed: "mph",
      time: "s",
    },
  };
}

function createMockData() {
  const trackMap = createMockMap();
  return {
    summary: {
      session_id: "mock-session",
      track_name: "Laguna Seca",
      direction: "CW",
      track_direction: "Laguna Seca CW",
      analytics_version: "0.1.0-local",
      rider_name: "Maddie",
      bike_name: "RS 660",
      units: "imperial",
      cards: [
        { id: "best_lap", label: "Best Lap", value: "1:32.418", delta: "-0.213", trend: "up" },
        { id: "avg_lap", label: "Avg Lap", value: "1:33.201", delta: "+0.783", trend: "down" },
        { id: "consistency", label: "Consistency", value: "92%", delta: "+3%", trend: "up" },
      ],
      laps: [
        { lap: 1, time: "1:33.021", sector_times: ["0:31.112", "0:30.540", "0:31.369"], is_best: false },
        { lap: 2, time: "1:32.418", sector_times: ["0:30.980", "0:30.312", "0:31.126"], is_best: true },
        { lap: 3, time: "1:33.164", sector_times: ["0:31.230", "0:30.600", "0:31.334"], is_best: false },
      ],
    },
    insights: {
      session_id: "mock-session",
      track_name: "Laguna Seca",
      direction: "CW",
      track_direction: "Laguna Seca CW",
      analytics_version: "0.1.0-local",
      rider_name: "Maddie",
      bike_name: "RS 660",
      units: "imperial",
      unit_contract: {
        system: "imperial",
        distance: "ft",
        speed: "mph",
        time: "s",
      },
      track_map: trackMap,
      items: [
        {
          id: "line_inconsistency",
          rule_id: "line_inconsistency",
          title: "T3 line consistency",
          phase: "mid",
          did: "At T3 (mid phase), line spread is about 3.0 ft wider than reference.",
          should: "T3: initiate turn-in at about 387 ft lap distance each lap, then hold one apex marker.",
          because: "Because line variance is elevated (6.2 ft), timing and speed consistency drop through mid.",
          operational_action: "T3: initiate turn-in at about 387 ft lap distance each lap, then hold one apex marker.",
          causal_reason: "Because line variance is elevated (6.2 ft), timing and speed consistency drop through mid.",
          risk_tier: "Primary",
          risk_reason: "Evidence quality and context support this as a main next-session focus.",
          data_quality_note: "gps accuracy good (3.3 ft); 10 satellites",
          uncertainty_note: "High confidence from current telemetry quality.",
          success_check: "Rider check: repeat the same turn-in and apex marker for the next 3 laps.",
          expected_gain_s: 0.18,
          experimental_protocol: null,
          is_primary_focus: true,
          confidence: 0.8,
          confidence_label: "high",
          gain: "+0.180",
          time_gain_s: 0.18,
          detail: "At T3 (mid phase), line spread is about 3.0 ft wider than reference.",
          actions: ["Repeat one turn-in marker.", "Hold one apex marker.", "Avoid extra mid-corner corrections."],
          options: [],
          segment_id: "T3",
          corner_id: "T3",
          corner_label: "T3",
          evidence: {
            turn_in_target_dist_m: 387,
            turn_in_reference_dist_m: 397,
            turn_in_rider_avg_dist_m: 389,
          },
          comparison: "Lap 8 vs best Lap 3",
          quality_gate: { decision: "pass" },
          gain_trace: { final_expected_gain_s: 0.18 },
        },
        {
          id: "late_throttle_pickup",
          rule_id: "late_throttle_pickup",
          title: "T7 drive timing",
          phase: "exit",
          did: "At T7 (exit phase), throttle pickup starts about 18.0 ft later than reference.",
          should: "At T7, begin drive sooner after apex for the next 2 laps without widening exit.",
          because: "Because throttle pickup is delayed by 18.0 ft, exit drive starts late.",
          operational_action: "At T7, begin drive sooner after apex for the next 2 laps without widening exit.",
          causal_reason: "Because throttle pickup is delayed by 18.0 ft, exit drive starts late.",
          risk_tier: "Experimental",
          risk_reason: "Plausible gain with uncertainty; run as a bounded test before adopting as primary focus.",
          data_quality_note: "gps accuracy fair (4.8 ft); 8 satellites",
          uncertainty_note: "Medium confidence; uncertainty from no IMU channels.",
          success_check: "Rider check: begin drive sooner after apex for the next 2 laps without widening exit.",
          expected_gain_s: 0.09,
          experimental_protocol: {
            expected_gain_s: 0.09,
            risk: "Do not add lean or run wide.",
            bounds: "2 laps only.",
            abort_criteria: "Abort if the bike runs wide at exit.",
          },
          is_primary_focus: false,
          confidence: 0.64,
          confidence_label: "medium",
          gain: "+0.090",
          time_gain_s: 0.09,
          detail: "At T7 (exit phase), throttle pickup starts about 18.0 ft later than reference.",
          actions: ["Roll on sooner after apex.", "Keep the same exit line.", "Abort if it pushes wide."],
          options: [],
          segment_id: "T7",
          corner_id: "T7",
          corner_label: "T7",
          evidence: {
            pickup_delta_m: 18,
            exit_speed_delta_kmh: 1.4,
          },
          comparison: "Lap 8 vs best Lap 3",
          quality_gate: { decision: "pass" },
          gain_trace: { final_expected_gain_s: 0.09 },
        },
      ],
    },
    compare: {
      session_id: "mock-session",
      track_name: "Laguna Seca",
      direction: "CW",
      track_direction: "Laguna Seca CW",
      analytics_version: "0.1.0-local",
      rider_name: "Maddie",
      bike_name: "RS 660",
      units: "imperial",
      comparison: {
        reference_lap: 2,
        target_lap: 3,
        delta_by_segment: [
          { segment_id: "T3", delta_s: 0.08 },
          { segment_id: "T7", delta_s: 0.04 },
        ],
        delta_by_sector: [],
      },
    },
    compareMap: {
      session_id: "mock-session",
      lap_a: 2,
      lap_b: 3,
      track_direction: "Laguna Seca CW",
      points_a: trackMap.reference_points,
      points_b: trackMap.target_points,
      units: "imperial",
      unit_contract: {
        system: "imperial",
        distance: "ft",
        speed: "mph",
        time: "s",
      },
    },
  };
}

function bestInsight(items) {
  if (!Array.isArray(items) || items.length === 0) return null;
  return items.find((item) => item.is_primary_focus) || items[0];
}

function selectedInsight() {
  const items = appState.insights?.items || [];
  return items.find((item) => item.id === appState.selectedInsightId) || bestInsight(items);
}

function bindRouteButtons() {
  document.addEventListener("click", (event) => {
    const routeButton = event.target.closest("[data-route]");
    if (!routeButton) return;
    event.preventDefault();
    const route = routeButton.dataset.route;
    setRoute(route);
    ensureDataForRoute(route);
  });
}

function bindCompareSelectors() {
  const ref = qs("#compare-reference");
  const target = qs("#compare-target");
  [ref, target].forEach((select) => {
    if (!select || select.dataset.bound === "true") return;
    select.dataset.bound = "true";
    select.addEventListener("change", async () => {
      appState.compareSelection.referenceLap = ref?.value ? Number(ref.value) : null;
      appState.compareSelection.targetLap = target?.value ? Number(target.value) : null;
      await loadCompareData();
      renderCompare(appState.compare);
    });
  });
}

function bindInsightButtons() {
  const list = qs("#insight-list");
  if (!list || list.dataset.bound === "true") return;
  list.dataset.bound = "true";
  list.addEventListener("click", (event) => {
    const button = event.target.closest("[data-insight-select]");
    if (!button) return;
    const insightId = button.dataset.insightSelect;
    const segmentId = button.dataset.segmentId || "";
    appState.selectedInsightId = insightId;
    appState.selectedSegmentId = segmentId || null;
    renderInsights(appState.insights);
    renderTrackMap(appState.selectedSegmentId);
    renderCorner();
  });
}

function formatDelta(value) {
  if (value == null || Number.isNaN(Number(value))) return "--";
  const numeric = Number(value);
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(3)}s`;
}

function renderSummary(summary) {
  const cardsRoot = qs("#summary-cards");
  const tableRoot = qs("#lap-table-body");
  if (!cardsRoot || !tableRoot) return;
  cardsRoot.innerHTML = "";
  tableRoot.innerHTML = "";
  if (!summary || summary.error === "not_ready") {
    cardsRoot.innerHTML = '<article class="metric-card"><div class="metric-label">Summary</div><div class="metric-value">Not ready</div></article>';
    tableRoot.innerHTML = '<div class="lap-row"><span>--</span><span>Waiting</span><span>--</span><span>--</span><span>--</span></div>';
    return;
  }

  (summary.cards || []).forEach((card) => {
    const node = document.createElement("article");
    node.className = "metric-card";
    node.innerHTML = `
      <div class="metric-label">${card.label}</div>
      <div class="metric-value">${card.value}</div>
      <div class="metric-delta">${card.delta}</div>
    `;
    cardsRoot.appendChild(node);
  });

  (summary.laps || []).forEach((lap) => {
    const row = document.createElement("div");
    row.className = "lap-row";
    row.innerHTML = `
      <span>${lap.lap}</span>
      <span>${lap.time}</span>
      <span>${(lap.sector_times || []).join(" / ")}</span>
      <span>${lap.is_best ? "Best" : ""}</span>
      <button type="button" class="secondary-action" data-route="compare">Compare</button>
    `;
    tableRoot.appendChild(row);
  });
}

function heroTelemetry(item) {
  const gain = item?.expected_gain_s != null ? `Gain ${formatDelta(item.expected_gain_s)}` : "Gain --";
  const confidence = item?.confidence != null ? `Confidence ${Math.round(Number(item.confidence) * 100)}%` : "Confidence --";
  const risk = item?.risk_tier ? `Risk ${item.risk_tier}` : "Risk --";
  return [gain, confidence, risk].map((text) => `<span>${text}</span>`).join("");
}

function renderTop1Briefing(item, source) {
  const hero = qs("#top1-hero");
  if (!hero) return;
  hero.dataset.top1Source = source || "empty";
  qs("#top1-priority-line").textContent = item?.corner_label ? `${item.corner_label} • ${item.phase}` : "Waiting for analysis";
  qs("#top1-title").textContent = item?.title || "No recommendation yet";
  qs("#top1-reason").textContent = item?.detail || "Run analysis to load the rewritten briefing surface.";
  qs("#top1-did").textContent = item?.did || "No data yet.";
  qs("#top1-should").textContent = item?.should || "No data yet.";
  qs("#top1-because").textContent = item?.because || "No data yet.";
  qs("#top1-success-check").textContent = item?.success_check || "No data yet.";
  qs("#top1-telemetry").innerHTML = item ? heroTelemetry(item) : "<span>Gain --</span><span>Confidence --</span><span>Risk --</span>";
}

function renderDidVsShouldPanel(item) {
  const root = qs("#did-vs-should-stack");
  if (!root) return;
  if (!item) {
    root.innerHTML = '<div class="stack-note">Select an insight to inspect its structured coaching payload.</div>';
    return;
  }
  root.innerHTML = `
    <article class="stack-row">
      <div class="stack-key">Did</div>
      <div class="stack-value">${item.did || "--"}</div>
    </article>
    <article class="stack-row">
      <div class="stack-key">Should</div>
      <div class="stack-value">${item.should || "--"}</div>
    </article>
    <article class="stack-row">
      <div class="stack-key">Because</div>
      <div class="stack-value">${item.because || "--"}</div>
    </article>
    <article class="stack-row">
      <div class="stack-key">Success check</div>
      <div class="stack-value">${item.success_check || "--"}</div>
    </article>
  `;
}

function renderInsights(insights) {
  const list = qs("#insight-list");
  const context = qs("#insights-context");
  const deltaList = qs("#delta-list");
  const summary = qs("#insight-summary");
  if (!list || !context || !deltaList || !summary) return;

  list.innerHTML = "";
  deltaList.innerHTML = "";
  summary.innerHTML = "";

  if (!insights || insights.error === "not_ready") {
    renderTop1Briefing(null, "empty");
    renderDidVsShouldPanel(null);
    list.innerHTML = '<article class="insight-card insight-secondary"><div class="card-eyebrow">Waiting</div><h3>Insights not ready</h3><p>Run analysis to generate coaching recommendations.</p></article>';
    context.innerHTML = "<div>Session context unavailable.</div>";
    renderTrackMap(null);
    renderCorner();
    return;
  }

  const items = Array.isArray(insights.items) ? insights.items : [];
  const topItem = bestInsight(items);
  if (!appState.selectedInsightId && topItem) {
    appState.selectedInsightId = topItem.id;
    appState.selectedSegmentId = topItem.segment_id || topItem.corner_id || null;
  }
  const selected = selectedInsight();
  renderTop1Briefing(topItem, topItem?.is_primary_focus ? "primary_focus" : "rank_fallback");
  renderDidVsShouldPanel(selected);

  items.forEach((item, index) => {
    const isTop1 = topItem && item.id === topItem.id;
    const isSelected = selected && item.id === selected.id;
    const article = document.createElement("article");
    article.className = isTop1 ? "insight-card insight-top1" : "insight-card insight-secondary";
    article.dataset.visualPriority = isTop1 ? "top1" : "secondary";
    article.dataset.insightId = item.id;
    article.innerHTML = `
      <div class="card-eyebrow">${isTop1 ? "Top 1" : `#${index + 1}`}</div>
      <h3>${item.title}</h3>
      <p>${item.detail || item.because || ""}</p>
      <div class="card-meta">
        <span>${item.corner_label || item.corner_id || "Corner"}</span>
        <span>${item.phase || "phase?"}</span>
        <span>${item.risk_tier || "Unspecified"}</span>
        <span>${item.confidence != null ? `${Math.round(Number(item.confidence) * 100)}%` : "--"}</span>
      </div>
      <div class="card-footer">
        <span class="gain-pill">${item.expected_gain_s != null ? formatDelta(item.expected_gain_s) : item.gain || "--"}</span>
        <button
          type="button"
          class="${isSelected ? "primary-action" : "secondary-action"}"
          data-insight-select="${item.id}"
          data-segment-id="${item.segment_id || item.corner_id || ""}"
        >Inspect</button>
      </div>
    `;
    list.appendChild(article);
  });

  context.innerHTML = `
    <div><strong>${insights.track_name || appState.meta.track_name || "Track"}</strong> ${insights.direction || ""}</div>
    <div>${insights.rider_name || appState.meta.rider_name || "Rider"} • ${insights.bike_name || appState.meta.bike_name || "Bike"}</div>
    <div>Session ${insights.session_id || appState.sessionId || "--"}</div>
  `;

  const compare = appState.compare?.comparison || {};
  const segmentDeltas = compare.delta_by_segment || [];
  if (segmentDeltas.length > 0) {
    deltaList.innerHTML = segmentDeltas
      .map((segment) => `<div class="delta-row">${segment.segment_id}: ${formatDelta(segment.delta_s)}</div>`)
      .join("");
  } else {
    deltaList.innerHTML = '<div class="delta-row">No segment deltas loaded yet.</div>';
  }

  const primaryCount = items.filter((item) => item.is_primary_focus).length;
  summary.innerHTML = `
    <div class="delta-row">Insights: ${items.length}</div>
    <div class="delta-row">Primary focus items: ${primaryCount}</div>
    <div class="delta-row">Selected corner: ${selected?.corner_label || "--"}</div>
  `;

  appState.trackMap = insights.track_map || appState.trackMap;
  renderTrackMap(appState.selectedSegmentId);
  renderCorner();
}

function buildPath(points) {
  if (!points || points.length === 0) return "";
  const [firstX, firstY] = points[0];
  let path = `M ${firstX} ${firstY}`;
  for (let idx = 1; idx < points.length; idx += 1) {
    const [x, y] = points[idx];
    path += ` L ${x} ${y}`;
  }
  return path;
}

function filterSegmentPoints(points, segment) {
  if (!segment) return [];
  return (points || []).filter((point) => point[2] >= segment.start_m && point[2] <= segment.end_m);
}

function renderTrackMap(selectedSegmentId) {
  const svg = qs("#track-map");
  const meta = qs("#track-map-meta");
  if (!svg || !meta) return;
  const map = appState.trackMap;
  if (!map || !(map.reference_points || []).length) {
    svg.innerHTML = "";
    meta.textContent = "Track map unavailable for this session.";
    return;
  }

  const reference = map.reference_points || [];
  const target = map.target_points || [];
  const segment = (map.segments || []).find((item) => item.id === selectedSegmentId) || null;
  const highlightTarget = filterSegmentPoints(target.length ? target : reference, segment);
  const highlightReference = filterSegmentPoints(reference, segment);
  const highlightLabel = segment?.label || "Overview";

  svg.innerHTML = `
    <path class="track-reference" d="${buildPath(reference)}"></path>
    <path class="track-target" d="${buildPath(target.length ? target : reference)}"></path>
    ${highlightReference.length ? `<path class="track-highlight ref" d="${buildPath(highlightReference)}"></path>` : ""}
    ${highlightTarget.length ? `<path class="track-highlight" d="${buildPath(highlightTarget)}"></path>` : ""}
  `;
  meta.textContent = selectedSegmentId
    ? `Highlight: ${highlightLabel} • Target vs Reference`
    : "Highlight: Overview • Target vs Reference";
}

function renderCompare(compare) {
  const refSelect = qs("#compare-reference");
  const targetSelect = qs("#compare-target");
  const table = qs("#compare-table");
  if (!refSelect || !targetSelect || !table) return;
  refSelect.innerHTML = "";
  targetSelect.innerHTML = "";
  table.innerHTML = "";

  const laps = appState.summary?.laps || [];
  if (laps.length === 0) {
    table.innerHTML = "<div class='delta-row'>No laps available.</div>";
    return;
  }

  laps.forEach((lap) => {
    const optionA = document.createElement("option");
    optionA.value = String(lap.lap);
    optionA.textContent = `Lap ${lap.lap}`;
    refSelect.appendChild(optionA);
    const optionB = optionA.cloneNode(true);
    targetSelect.appendChild(optionB);
  });

  const comparison = compare?.comparison || {};
  refSelect.value = String(appState.compareSelection.referenceLap || comparison.reference_lap || laps[0].lap);
  targetSelect.value = String(appState.compareSelection.targetLap || comparison.target_lap || laps[laps.length - 1].lap);

  const rows = comparison.delta_by_segment?.length
    ? comparison.delta_by_segment.map((segment) => `${segment.segment_id}: ${formatDelta(segment.delta_s)}`)
    : (comparison.delta_by_sector || []).map((delta, index) => `Sector ${index + 1}: ${delta || "--"}`);
  table.innerHTML = rows.length ? rows.map((row) => `<div class="delta-row">${row}</div>`).join("") : "<div class='delta-row'>No compare data yet.</div>";
  renderCompareMap();
}

function renderCompareMap() {
  const svg = qs("#compare-map");
  if (!svg) return;
  const map = appState.compareMap;
  if (!map || !(map.points_a || []).length || !(map.points_b || []).length) {
    svg.innerHTML = "";
    return;
  }
  svg.innerHTML = `
    <path class="track-reference" d="${buildPath(map.points_a)}"></path>
    <path class="track-target" d="${buildPath(map.points_b)}"></path>
  `;
}

function renderCorner() {
  const root = qs("#corner-detail");
  if (!root) return;
  const item = selectedInsight();
  if (!item) {
    root.innerHTML = "<div class='stack-note'>Select an insight to populate corner detail.</div>";
    return;
  }
  root.innerHTML = `
    <div class="corner-kicker">${item.corner_label || item.corner_id || "Corner"}</div>
    <h3>${item.title}</h3>
    <div class="corner-grid">
      <article class="corner-card">
        <div class="semantic-label">Action</div>
        <p>${item.should || item.operational_action || "--"}</p>
      </article>
      <article class="corner-card">
        <div class="semantic-label">Why</div>
        <p>${item.because || item.causal_reason || "--"}</p>
      </article>
      <article class="corner-card">
        <div class="semantic-label">Risk</div>
        <p>${item.risk_tier || "--"} • ${item.risk_reason || ""}</p>
      </article>
      <article class="corner-card">
        <div class="semantic-label">Success check</div>
        <p>${item.success_check || "--"}</p>
      </article>
    </div>
  `;
}

function renderApp() {
  renderSummary(appState.summary);
  renderInsights(appState.insights);
  renderCompare(appState.compare);
  renderCorner();
  setConnectionBadge(appState.source);
  setSessionBadge();
  updateDropzoneNote();
}

async function loadSession(filePath) {
  try {
    const payload = await apiFetch("/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(filePath ? { file_path: filePath } : {}),
    });
    applyMeta(payload);
    appState.sessionId = payload.session_id;
    appState.source = "api";
    return payload;
  } catch (error) {
    setError(describeApiError(error));
    return null;
  }
}

async function loadEndpoint(path) {
  try {
    const payload = await apiFetch(path);
    if (payload?.error) {
      return payload;
    }
    return payload;
  } catch (error) {
    setError(describeApiError(error));
    return null;
  }
}

async function loadCompareData() {
  if (!appState.sessionId) return;
  const params = new URLSearchParams();
  if (appState.compareSelection.referenceLap != null) {
    params.set("reference_lap", String(appState.compareSelection.referenceLap));
  }
  if (appState.compareSelection.targetLap != null) {
    params.set("target_lap", String(appState.compareSelection.targetLap));
  }
  const comparePath = `/compare/${appState.sessionId}${params.toString() ? `?${params}` : ""}`;
  const compare = await loadEndpoint(comparePath);
  if (compare) {
    appState.compare = compare;
    const comparison = compare.comparison || {};
    appState.compareSelection.referenceLap = comparison.reference_lap ?? appState.compareSelection.referenceLap;
    appState.compareSelection.targetLap = comparison.target_lap ?? appState.compareSelection.targetLap;
  }
  const mapParams = new URLSearchParams();
  if (appState.compareSelection.referenceLap != null) {
    mapParams.set("lap_a", String(appState.compareSelection.referenceLap));
  }
  if (appState.compareSelection.targetLap != null) {
    mapParams.set("lap_b", String(appState.compareSelection.targetLap));
  }
  const compareMap = await loadEndpoint(`/map/${appState.sessionId}${mapParams.toString() ? `?${mapParams}` : ""}`);
  if (compareMap && !compareMap.error) {
    appState.compareMap = compareMap;
  }
}

async function hydrateFromApi({ force, filePath } = {}) {
  if (!force && appState.sessionId) return true;
  setError("");
  setLoading(true);
  const session = await loadSession(filePath);
  if (!session) {
    setLoading(false);
    return false;
  }
  const summary = await loadEndpoint(`/summary/${session.session_id}`);
  const insights = await loadEndpoint(`/insights/${session.session_id}`);
  appState.summary = summary || appState.summary;
  appState.insights = insights || appState.insights;
  if (insights?.track_map) {
    appState.trackMap = insights.track_map;
  }
  await loadCompareData();
  setLoading(false);
  renderApp();
  return true;
}

async function runImportAndLoad({ force, routeAfter } = {}) {
  appState.import.filePath = qs("#file-path")?.value.trim() || appState.import.filePath;
  const ok = await hydrateFromApi({ force: force === true, filePath: appState.import.filePath });
  if (ok && routeAfter) {
    setRoute(routeAfter);
  }
}

async function ensureDataForRoute(route) {
  if (route === "import") return;
  if (!appState.sessionId) {
    const hydrated = await hydrateFromApi({ force: false, filePath: appState.import.filePath });
    if (!hydrated && appState.source !== "api") {
      const mock = createMockData();
      appState.summary = mock.summary;
      appState.insights = mock.insights;
      appState.compare = mock.compare;
      appState.trackMap = mock.trackMap;
      appState.compareMap = mock.compareMap;
      applyMeta(mock.summary);
      appState.sessionId = mock.summary.session_id;
      appState.source = "mock";
      appState.compareSelection.referenceLap = mock.compare.comparison.reference_lap;
      appState.compareSelection.targetLap = mock.compare.comparison.target_lap;
      if (!appState.selectedInsightId) {
        appState.selectedInsightId = mock.insights.items[0].id;
        appState.selectedSegmentId = mock.insights.items[0].segment_id;
      }
    }
  } else if (route === "compare") {
    await loadCompareData();
  }
  renderApp();
}

function bindImportControls() {
  const fileInput = qs("#csv-file");
  const filePath = qs("#file-path");
  const browse = qs("#browse-file");
  const analyze = qs("#analyze-now");

  filePath?.addEventListener("input", () => {
    appState.import.filePath = filePath.value.trim();
    updateDropzoneNote();
  });

  browse?.addEventListener("click", () => fileInput?.click());

  fileInput?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    appState.import.fileName = file?.name || "";
    updateDropzoneNote();
  });

  analyze?.addEventListener("click", async () => {
    await runImportAndLoad({ force: true, routeAfter: "summary" });
  });
}

function init() {
  bindRouteButtons();
  bindImportControls();
  bindCompareSelectors();
  bindInsightButtons();
  window.addEventListener("hashchange", () => {
    setRoute(readRoute());
    ensureDataForRoute(appState.route);
  });
  setRoute(readRoute());
  renderApp();
  ensureDataForRoute(appState.route);
}

init();
