const routes = ["import", "summary", "insights", "compare"];
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
    setRoute(btn.dataset.route);
  });
}

function initImport() {
  const analyzeNow = document.getElementById("analyze-now");
  if (analyzeNow) {
    analyzeNow.addEventListener("click", () => setRoute("summary"));
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

function formatDelta(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return "--";
  const sign = seconds > 0 ? "+" : "";
  return `${sign}${seconds.toFixed(2)}`;
}

function setStatusBadge(source) {
  const badge = qs(".status .badge");
  if (!badge) return;
  badge.classList.toggle("offline", source !== "api");
  badge.textContent = source === "api" ? "Live" : "Mock";
}

function createMockData() {
  return {
    session_id: "mock-session",
    track_name: "Laguna Seca",
    direction: "CW",
    track_direction: "Laguna Seca CW",
    analytics_version: "0.1.0-local",
    summary: {
      track_name: "Laguna Seca",
      direction: "CW",
      track_direction: "Laguna Seca CW",
      analytics_version: "0.1.0-local",
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
  const response = await fetch(path, options);
  if (!response.ok) {
    throw new Error(`api_error:${response.status}`);
  }
  return response.json();
}

async function loadSession() {
  try {
    const payload = await apiFetch("/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!payload?.session_id) throw new Error("missing_session");
    return payload;
  } catch (error) {
    return null;
  }
}

async function loadEndpoint(path) {
  try {
    return await apiFetch(path);
  } catch (error) {
    return null;
  }
}

function renderSummary(summary) {
  if (!summary) return;
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
        <button class="ghost" data-route="compare">Compare</button>
      `;
      lapTable.appendChild(row);
    });
  }
}

function renderInsights(insights) {
  if (!insights) return;
  const list = qs(".insight-list");
  if (!list) return;
  clearChildren(list);
  (insights.items || []).forEach((item, index) => {
    const confidence = Number(item.confidence ?? 0);
    const badgeClass = confidence >= 0.75 ? "high" : confidence >= 0.5 ? "med" : "low";
    const badgeLabel = confidence >= 0.75 ? "High" : confidence >= 0.5 ? "Med" : "Low";
    const article = document.createElement("article");
    article.className = "card insight";
    article.style.setProperty("--delay", `${index * 80}ms`);
    const gainText = item.gain ? `${item.gain}s` : "";
    article.innerHTML = `
      <div class="card-head">
        <h3>${item.title ?? "Insight"}</h3>
        <span class="badge ${badgeClass}">${badgeLabel}</span>
      </div>
      <p>${item.detail ?? ""}</p>
      <div class="card-foot">
        <span class="gain">${gainText}</span>
        <button class="ghost">Why?</button>
      </div>
    `;
    list.appendChild(article);
  });

  const mapMeta = qs(".map-meta");
  setText(
    mapMeta,
    `Selected: ${insights.items?.[0]?.title ?? "Overview"} - ${insights.track_direction ?? ""}`.trim()
  );
}

function renderCompare(compare) {
  if (!compare) return;
  const comparison = compare.comparison || {};
  const laps = appState.summary?.laps || [];
  const selects = qsa("#screen-compare select");
  selects.forEach((select) => {
    clearChildren(select);
    laps.forEach((lap) => {
      const option = document.createElement("option");
      option.value = lap.lap;
      option.textContent = `Lap ${lap.lap} - ${lap.time ?? "--"}${lap.is_best ? " (Best)" : ""}`;
      select.appendChild(option);
    });
  });
  if (selects[0] && comparison.reference_lap) selects[0].value = String(comparison.reference_lap);
  if (selects[1] && comparison.target_lap) selects[1].value = String(comparison.target_lap);

  const table = qs(".compare-table");
  if (table) {
    qsa(".table-row", table).forEach((row) => row.remove());
    (comparison.brake_points || []).forEach((point) => {
      const row = document.createElement("div");
      row.className = "table-row";
      row.innerHTML = `
        <div>${point.corner ?? "--"}</div>
        <div>--</div>
        <div>--</div>
        <div>--</div>
        <div class="delta">${point.delta_m ?? "--"}m</div>
      `;
      table.appendChild(row);
    });
  }
}

function applyData(data, source) {
  appState.source = source;
  appState.summary = data.summary;
  appState.insights = data.insights;
  appState.compare = data.compare;
  setStatusBadge(source);
  renderSummary(appState.summary);
  renderInsights(appState.insights);
  renderCompare(appState.compare);
}

async function hydrateFromApi() {
  const session = await loadSession();
  if (!session?.session_id) {
    applyData(createMockData(), "mock");
    return;
  }
  appState.sessionId = session.session_id;
  const [summary, insights, compare] = await Promise.all([
    loadEndpoint(`/summary/${session.session_id}`),
    loadEndpoint(`/insights/${session.session_id}`),
    loadEndpoint(`/compare/${session.session_id}`),
  ]);
  if (!summary || summary.error || !insights || insights.error || !compare || compare.error) {
    applyData(createMockData(), "mock");
    return;
  }
  applyData({ summary, insights, compare }, session.source === "mock" ? "mock" : "api");
}

function init() {
  bindRouteButtons();
  initImport();
  setRoute(readRoute());
  hydrateFromApi();

  window.addEventListener("hashchange", () => {
    setRoute(readRoute());
  });
}

document.addEventListener("DOMContentLoaded", init);
