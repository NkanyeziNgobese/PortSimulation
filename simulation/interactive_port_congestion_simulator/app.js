// Web dashboard for exported simulation results (no dependencies).
(function () {
  const DATA_PATHS = {
    baseline: "../../outputs/web/baseline.json",
    improved: "../../outputs/web/improved.json",
    metadata: "../../outputs/web/metadata.json"
  };

  const KPI_METRICS = [
    { key: "total_time", label: "Total time" },
    { key: "yard_dwell", label: "Yard dwell" },
    { key: "scan_wait", label: "Scan wait" },
    { key: "loading_wait", label: "Loading wait" },
    { key: "gate_wait", label: "Gate wait" }
  ];

  const STAGE_METRICS = [
    { key: "scan_wait", label: "Scan wait" },
    { key: "yard_to_scan_wait", label: "Yard to scan wait" },
    { key: "yard_to_truck_wait", label: "Yard to truck wait" },
    { key: "yard_equipment_wait", label: "Yard equipment wait" },
    { key: "loading_wait", label: "Loading wait" },
    { key: "gate_wait", label: "Gate wait" },
    { key: "customs_queue_wait", label: "Customs queue" },
    { key: "customs_inspection_time", label: "Customs inspection" },
    { key: "customs_hold_delay", label: "Customs hold" },
    { key: "rebook_delay", label: "Rebook delay" },
    { key: "pre_pickup_wait", label: "Pre-pickup wait" },
    { key: "ready_to_pickup_wait", label: "Ready to pickup wait" }
  ];

  const CHART_CONFIG = [
    { key: "total_time", label: "Total time (min)", canvas: "totalTimeHist", color: "#5eb8ff" },
    { key: "yard_dwell", label: "Yard dwell (min)", canvas: "yardDwellHist", color: "#7de0c5" },
    { key: "scan_wait", label: "Scan wait (min)", canvas: "scanWaitHist", color: "#f4b400" },
    { key: "loading_wait", label: "Loading wait (min)", canvas: "loadingWaitHist", color: "#ff8c42" },
    { key: "gate_wait", label: "Gate wait (min)", canvas: "gateWaitHist", color: "#ff6b6b" }
  ];

  const state = {
    baseline: null,
    improved: null,
    metadata: null,
    active: "baseline"
  };

  const $ = (id) => document.getElementById(id);

  const toNumber = (value) => {
    if (value === null || value === undefined || value === "") return null;
    const num = Number(value);
    return Number.isFinite(num) ? num : null;
  };

  const mean = (values) => {
    if (!values.length) return null;
    return values.reduce((sum, v) => sum + v, 0) / values.length;
  };

  const percentile = (values, p) => {
    if (!values.length) return null;
    const sorted = [...values].sort((a, b) => a - b);
    const idx = (sorted.length - 1) * p;
    const lower = Math.floor(idx);
    const upper = Math.ceil(idx);
    if (lower === upper) return sorted[lower];
    return sorted[lower] + (sorted[upper] - sorted[lower]) * (idx - lower);
  };

  const formatStat = (value) => {
    if (value === null || value === undefined || Number.isNaN(value)) return "n/a";
    return value.toFixed(1);
  };

  const collectMetric = (records, key) => records
    .map((row) => toNumber(row[key]))
    .filter((value) => value !== null);

  const fetchJson = (path) => fetch(path, { cache: "no-store" })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Failed to load ${path} (${response.status})`);
      }
      return response.json();
    });

  const normalizePayload = (data, scenarioFallback) => {
    if (Array.isArray(data)) {
      return { scenario: scenarioFallback, records: data, columns: Object.keys(data[0] || {}) };
    }
    if (data && Array.isArray(data.records)) return data;
    return { scenario: scenarioFallback, records: [], columns: [] };
  };

  const setStatus = (text, isError) => {
    const el = $("dataStatus");
    if (!el) return;
    el.textContent = text;
    el.classList.toggle("error", Boolean(isError));
  };

  const setActiveScenario = (scenario) => {
    state.active = scenario;
    $("baselineBtn").classList.toggle("primary", scenario === "baseline");
    $("improvedBtn").classList.toggle("primary", scenario === "improved");
    $("activeScenarioLabel").textContent = scenario === "baseline" ? "Baseline" : "Improved Dwell";
    renderActiveScenario();
  };

  const renderKpiColumn = (containerId, records, title) => {
    const grid = $(containerId);
    if (!grid) return;
    grid.innerHTML = "";

    if (!records || !records.length) {
      grid.innerHTML = `<div class="hint">No ${title.toLowerCase()} records loaded.</div>`;
      return;
    }

    KPI_METRICS.forEach((metric) => {
      const values = collectMetric(records, metric.key);
      const stats = {
        mean: mean(values),
        median: percentile(values, 0.5),
        p90: percentile(values, 0.9),
        p95: percentile(values, 0.95)
      };

      const card = document.createElement("div");
      card.className = "kpi-card";
      card.innerHTML = `
        <div class="kpi-title">${metric.label}</div>
        <div class="kpi-stats">
          <div>Mean <span>${formatStat(stats.mean)}</span></div>
          <div>Median <span>${formatStat(stats.median)}</span></div>
          <div>p90 <span>${formatStat(stats.p90)}</span></div>
          <div>p95 <span>${formatStat(stats.p95)}</span></div>
        </div>
      `;
      grid.appendChild(card);
    });
  };

  const drawHistogram = (canvas, values, color, label) => {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!values.length) {
      ctx.fillStyle = "#9fb3ce";
      ctx.font = "12px " + getComputedStyle(document.body).fontFamily;
      ctx.fillText("No data", 12, 20);
      return;
    }

    const bins = 18;
    const maxVal = Math.max(...values);
    const minVal = 0;
    const binWidth = (maxVal - minVal) / bins || 1;
    const counts = new Array(bins).fill(0);

    values.forEach((value) => {
      const idx = Math.min(bins - 1, Math.floor((value - minVal) / binWidth));
      counts[idx] += 1;
    });

    const maxCount = Math.max(...counts, 1);
    const padding = 32;
    const barWidth = (canvas.width - padding * 2) / bins;

    counts.forEach((count, i) => {
      const x = padding + i * barWidth;
      const h = (canvas.height - padding * 2) * (count / maxCount);
      ctx.fillStyle = color;
      ctx.fillRect(x, canvas.height - padding - h, barWidth - 2, h);
    });

    ctx.fillStyle = "#dfe9ff";
    ctx.font = "12px " + getComputedStyle(document.body).fontFamily;
    ctx.fillText(label, padding, padding - 10);
  };

  const renderDistributions = (records) => {
    CHART_CONFIG.forEach((chart) => {
      const values = collectMetric(records, chart.key);
      const canvas = $(chart.canvas);
      if (canvas) drawHistogram(canvas, values, chart.color, chart.label);
    });
  };

  const renderLongTail = (records) => {
    const container = $("tailMetrics");
    const tableBody = $("outlierTable").querySelector("tbody");
    container.innerHTML = "";
    tableBody.innerHTML = "";

    const totals = collectMetric(records, "total_time");
    if (!totals.length) {
      container.innerHTML = '<div class="hint">No total_time values available.</div>';
      return;
    }

    const p95 = percentile(totals, 0.95);
    const p99 = percentile(totals, 0.99);

    const metricsCard = document.createElement("div");
    metricsCard.className = "tail-card";
    metricsCard.innerHTML = `
      <div class="tail-label">Total time</div>
      <div class="tail-stats">
        <div>p95 <span>${formatStat(p95)}</span></div>
        <div>p99 <span>${formatStat(p99)}</span></div>
      </div>
    `;
    container.appendChild(metricsCard);

    const outliers = records
      .map((row, idx) => ({
        idx,
        id: row.container_id ?? row.container ?? `#${idx}`,
        flow: row.flow_type ?? "-",
        total: toNumber(row.total_time)
      }))
      .filter((row) => row.total !== null)
      .sort((a, b) => b.total - a.total)
      .slice(0, 10);

    outliers.forEach((row, i) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${i + 1}</td>
        <td>${row.id}</td>
        <td>${row.flow}</td>
        <td>${formatStat(row.total)}</td>
      `;
      tableBody.appendChild(tr);
    });
  };

  const renderBottlenecks = (records) => {
    const container = $("bottleneckList");
    container.innerHTML = "";

    const totalValues = collectMetric(records, "total_time");
    const totalMean = mean(totalValues);
    if (!totalMean) {
      container.innerHTML = '<div class="hint">No total_time available for bottleneck ranking.</div>';
      return;
    }

    const rows = STAGE_METRICS.map((stage) => {
      const values = collectMetric(records, stage.key);
      const stageMean = mean(values);
      if (!stageMean) return null;
      return {
        label: stage.label,
        mean: stageMean,
        contribution: stageMean / totalMean
      };
    }).filter(Boolean);

    rows.sort((a, b) => b.contribution - a.contribution);

    rows.forEach((row) => {
      const item = document.createElement("div");
      item.className = "bottleneck-row";
      const percent = Math.min(100, row.contribution * 100);
      item.innerHTML = `
        <div class="bottleneck-label">${row.label}</div>
        <div class="bottleneck-bar"><div class="bar-fill" style="width: ${percent.toFixed(1)}%"></div></div>
        <div class="bottleneck-value">${percent.toFixed(1)}%</div>
      `;
      container.appendChild(item);
    });
  };

  const renderSources = () => {
    const tableBody = $("sourcesTable").querySelector("tbody");
    tableBody.innerHTML = "";

    if (!state.metadata || !state.metadata.metrics) {
      tableBody.innerHTML = '<tr><td colspan="3" class="hint">No metadata loaded.</td></tr>';
      return;
    }

    const rows = Object.entries(state.metadata.metrics)
      .sort(([a], [b]) => a.localeCompare(b));

    rows.forEach(([metric, info]) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${metric}</td>
        <td>${info.unit || "unitless"}</td>
        <td>${info.source_anchor ? info.source_anchor.reference : ""}</td>
      `;
      tableBody.appendChild(tr);
    });
  };

  const renderActiveScenario = () => {
    const activeRecords = state.active === "baseline"
      ? state.baseline?.records || []
      : state.improved?.records || [];

    renderDistributions(activeRecords);
    renderLongTail(activeRecords);
    renderBottlenecks(activeRecords);
  };

  const renderAll = () => {
    renderKpiColumn("baselineKpiGrid", state.baseline?.records || [], "Baseline");
    renderKpiColumn("improvedKpiGrid", state.improved?.records || [], "Improved Dwell");
    renderSources();
    renderActiveScenario();
  };

  const loadAll = () => {
    setStatus("Loading outputs...", false);
    return Promise.all([
      fetchJson(DATA_PATHS.baseline),
      fetchJson(DATA_PATHS.improved),
      fetchJson(DATA_PATHS.metadata)
    ])
      .then(([baseline, improved, metadata]) => {
        state.baseline = normalizePayload(baseline, "baseline");
        state.improved = normalizePayload(improved, "improved");
        state.metadata = metadata || null;
        setStatus("Outputs loaded", false);

        if (metadata && metadata.exported_at) {
          $("runTimestamp").textContent = `Run timestamp: ${metadata.exported_at}`;
        }

        renderAll();
      })
      .catch((error) => {
        setStatus(`Load failed: ${error.message}`, true);
        console.error(error);
      });
  };

  const init = () => {
    $("baselineBtn").addEventListener("click", () => setActiveScenario("baseline"));
    $("improvedBtn").addEventListener("click", () => setActiveScenario("improved"));
    $("reloadBtn").addEventListener("click", loadAll);
    loadAll();
  };

  document.addEventListener("DOMContentLoaded", init);
})();
