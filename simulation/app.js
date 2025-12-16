// Lightweight, browser-only discrete-event simulation mirroring the SimPy notebook:
// ship → crane offloading → yard dwell → scanning → truck loading → gate-out.
// Queues are FIFO; resources are capacity-constrained; service times are stochastic
// where the Python model used randomness (triangular for loading/gate).
(function () {
  const MINUTES_PER_DAY = 24 * 60;

  // Baseline parameters copied from the notebook.
  const defaults = {
    numCranes: 16,
    craneMovesPerHour: 18,
    dwellPolicy: "baseline", // baseline: 3/5/7 days, improved: 2/3/4 days
    numScanners: 2,
    scanTime: 10,
    numLoaders: 2,
    loadMin: 20,
    loadMode: 30,
    loadMax: 40,
    numGates: 1,
    gateMin: 5,
    gateMode: 8,
    gateMax: 15,
    arrivalRatePerHour: 12, // mean arrival every 5 minutes
    simDays: 7,
    yardCapacity: 10000
  };

  const dwellMinutes = {
    baseline: [3, 5, 7].map(d => d * MINUTES_PER_DAY),
    improved: [2, 3, 4].map(d => d * MINUTES_PER_DAY)
  };

  const state = {
    currentLabel: "—",
    lastRuns: {
      baseline: null,
      improved: null
    }
  };

  // ---------- Helpers ----------
  const $ = id => document.getElementById(id);
  const mean = arr => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
  const round1 = v => Math.round(v * 10) / 10;
  const pick = arr => arr[Math.floor(Math.random() * arr.length)];

  const randExp = meanVal => -Math.log(1 - Math.random()) * meanVal;
  const randTriangular = (min, mode, max) => {
    const u = Math.random();
    const c = (mode - min) / (max - min);
    if (u < c) {
      return min + Math.sqrt(u * (max - min) * (mode - min));
    }
    return max - Math.sqrt((1 - u) * (max - min) * (max - mode));
  };

  class MinHeap {
    constructor() { this.data = []; }
    push(node) {
      this.data.push(node);
      this.#bubbleUp(this.data.length - 1);
    }
    pop() {
      if (this.data.length === 0) return null;
      const min = this.data[0];
      const end = this.data.pop();
      if (this.data.length) {
        this.data[0] = end;
        this.#sinkDown(0);
      }
      return min;
    }
    size() { return this.data.length; }
    #bubbleUp(n) {
      const element = this.data[n];
      while (n > 0) {
        const parentN = Math.floor((n + 1) / 2) - 1;
        const parent = this.data[parentN];
        if (element.time < parent.time || (element.time === parent.time && element.seq < parent.seq)) {
          this.data[parentN] = element;
          this.data[n] = parent;
          n = parentN;
        } else break;
      }
    }
    #sinkDown(n) {
      const length = this.data.length;
      const element = this.data[n];
      while (true) {
        const rChild = (n + 1) * 2;
        const lChild = rChild - 1;
        let swap = null;
        if (lChild < length) {
          const left = this.data[lChild];
          if (left.time < element.time || (left.time === element.time && left.seq < element.seq)) {
            swap = lChild;
          }
        }
        if (rChild < length) {
          const right = this.data[rChild];
          if (
            (swap === null && (right.time < element.time || (right.time === element.time && right.seq < element.seq))) ||
            (swap !== null && (right.time < this.data[swap].time || (right.time === this.data[swap].time && right.seq < this.data[swap].seq)))
          ) {
            swap = rChild;
          }
        }
        if (swap === null) break;
        this.data[n] = this.data[swap];
        this.data[swap] = element;
        n = swap;
      }
    }
  }

  // ---------- Simulation core ----------
  function runSimulation(params) {
    let now = 0;
    let seq = 0;
    const stopTime = params.simDays * MINUTES_PER_DAY;
    const events = new MinHeap();

    const queueSeries = {
      scan: [{ time: 0, value: 0 }],
      load: [{ time: 0, value: 0 }],
      gate: [{ time: 0, value: 0 }]
    };

    const recordQueuePoint = (key, t, len) => {
      const arr = queueSeries[key];
      if (!arr) return;
      const last = arr[arr.length - 1];
      if (last && last.time === t) {
        last.value = len;
      } else {
        arr.push({ time: t, value: len });
      }
    };

    const createResource = (name, capacity, queueKey = null) => ({
      name,
      capacity,
      busy: 0,
      queue: [],
      queueKey
    });

    const cranes = createResource("cranes", params.numCranes);
    const scanners = createResource("scanners", params.numScanners, "scan");
    const loaders = createResource("loaders", params.numLoaders, "load");
    const gates = createResource("gates", params.numGates, "gate");

    const metrics = [];

    const schedule = (time, fn) => events.push({ time, seq: seq++, fn });

    const startService = (resource, stageKey, container, serviceFn, onFinish, startTime) => {
      const tStart = startTime;
      container[`${stageKey}_start`] = tStart;
      const service = serviceFn();
      resource.busy += 1;
      schedule(tStart + service, () => {
        resource.busy -= 1;
        container[`${stageKey}_end`] = tStart + service;
        onFinish();
        // Pull next from queue (FIFO)
        if (resource.queue.length > 0) {
          const next = resource.queue.shift();
          if (resource.queueKey) recordQueuePoint(resource.queueKey, tStart + service, resource.queue.length);
          startService(resource, stageKey, next.container, next.serviceFn, next.onFinish, tStart + service);
        }
      });
    };

    // Request resource with FIFO queue and queue length tracking.
    const requestResource = (resource, stageKey, container, serviceFn, onFinish) => {
      container[`${stageKey}_queue_enter`] = now;
      if (resource.busy < resource.capacity) {
        startService(resource, stageKey, container, serviceFn, onFinish, now);
      } else {
        resource.queue.push({ container, serviceFn, onFinish });
        if (resource.queueKey) recordQueuePoint(resource.queueKey, now, resource.queue.length);
      }
    };

    const dwellSampler = () => {
      const choices = params.dwellPolicy === "improved" ? dwellMinutes.improved : dwellMinutes.baseline;
      return pick(choices);
    };

    // Container lifecycle: called when a gate-out completes.
    const recordExit = (c) => {
      const row = {
        arrival_time: c.arrival_time,
        exit_time: c.exit_time,
        yard_entry_time: c.yard_entry_time,
        yard_exit_time: c.yard_exit_time,
        scan_start: c.scan_start,
        scan_queue_enter: c.scan_queue_enter,
        loading_start: c.loading_start,
        loading_queue_enter: c.loading_queue_enter,
        gate_start: c.gate_start,
        gate_queue_enter: c.gate_queue_enter
      };
      row.total_time = row.exit_time - row.arrival_time;
      row.yard_dwell = row.yard_exit_time - row.yard_entry_time;
      row.scan_wait = row.scan_start - row.scan_queue_enter;
      row.loading_wait = row.loading_start - row.loading_queue_enter;
      row.gate_wait = row.gate_start - row.gate_queue_enter;
      metrics.push(row);
    };

    const afterGate = (container) => {
      container.exit_time = now;
      recordExit(container);
    };

    const afterLoading = (container) => {
      // Yard slot freed once truck departs the stack.
      requestResource(gates, "gate", container, () => randTriangular(params.gateMin, params.gateMode, params.gateMax), () => afterGate(container));
    };

    const afterScan = (container) => {
      requestResource(loaders, "loading", container, () => randTriangular(params.loadMin, params.loadMode, params.loadMax), () => afterLoading(container));
    };

    const startScanAfterDwell = (container) => {
      requestResource(scanners, "scan", container, () => params.scanTime, () => afterScan(container));
    };

    const afterCrane = (container) => {
      container.yard_entry_time = now;
      const dwell = dwellSampler();
      const exitTime = now + dwell;
      container.yard_exit_time = exitTime;
      schedule(exitTime, () => {
        now = exitTime;
        startScanAfterDwell(container);
      });
    };

    const arrivalEvent = (arrivalTime) => {
      if (arrivalTime >= stopTime) return;
      const container = { id: metrics.length, arrival_time: arrivalTime };
      requestResource(cranes, "crane", container, () => 60 / params.craneMovesPerHour, () => afterCrane(container));
      // Schedule next arrival
      const inter = randExp(60 / params.arrivalRatePerHour);
      schedule(arrivalTime + inter, () => arrivalEvent(arrivalTime + inter));
    };

    // Seed first arrival slightly after time zero to mirror the notebook's first env.timeout(interarrival).
    const firstInterarrival = randExp(60 / params.arrivalRatePerHour);
    schedule(firstInterarrival, () => arrivalEvent(firstInterarrival));

    // Event loop
    while (events.size() > 0) {
      const evt = events.pop();
      if (!evt) break;
      now = evt.time;
      evt.fn();
    }

    const maxTime = metrics.length ? Math.max(...metrics.map(m => m.exit_time)) : 0;
    ["scan", "load", "gate"].forEach(key => {
      const arr = queueSeries[key];
      if (arr.length) {
        const last = arr[arr.length - 1];
        if (last.time < maxTime) arr.push({ time: maxTime, value: last.value });
      }
    });

    return { metrics, queueSeries, maxTime };
  }

  // ---------- Rendering ----------
  function updateMetrics(label, stats) {
    state.currentLabel = label;
    $("runLabel").textContent = label;
    const grid = $("metricsGrid");
    grid.innerHTML = "";
    if (!stats || stats.count === 0) {
      grid.innerHTML = "<div class='hint'>No completed containers in this run.</div>";
      $("bottleneckBox").textContent = "Bottleneck: —";
      return;
    }
    const entries = [
      ["Containers completed", stats.count.toString()],
      ["Avg total time (minutes)", round1(stats.avgTotal).toString()],
      ["Avg yard dwell (minutes)", round1(stats.avgDwell).toString()],
      ["Avg scan wait (minutes)", round1(stats.avgScanWait).toString()],
      ["Avg loading wait (minutes)", round1(stats.avgLoadingWait).toString()],
      ["Avg gate wait (minutes)", round1(stats.avgGateWait).toString()]
    ];
    entries.forEach(([labelText, val]) => {
      const card = document.createElement("div");
      card.className = "metric";
      card.innerHTML = `<div class="label">${labelText}</div><div class="value">${val}</div>`;
      grid.appendChild(card);
    });
    $("bottleneckBox").textContent = `Bottleneck: ${stats.bottleneck}`;
  }

  function drawLineChart(canvas, series) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const padding = 48;
    const maxX = Math.max(...series.map(s => (s.points.length ? s.points[s.points.length - 1].time : 0)), 1);
    const maxY = Math.max(...series.map(s => Math.max(...s.points.map(p => p.value), 0)), 1);
    const xScale = (canvas.width - padding * 2) / maxX;
    const yScale = (canvas.height - padding * 2) / maxY;

    const drawAxes = () => {
      ctx.strokeStyle = "#24304b";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(padding, canvas.height - padding);
      ctx.lineTo(canvas.width - padding, canvas.height - padding);
      ctx.moveTo(padding, canvas.height - padding);
      ctx.lineTo(padding, padding);
      ctx.stroke();
      ctx.fillStyle = "#9fb3ce";
      ctx.font = "12px " + getComputedStyle(document.body).fontFamily;
      ctx.fillText("Time (minutes)", canvas.width / 2 - 30, canvas.height - 14);
      ctx.save();
      ctx.translate(14, canvas.height / 2 + 20);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText("Queue length (waiting)", 0, 0);
      ctx.restore();
    };

    const plotSeries = (points, color) => {
      if (!points.length) return;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      points.forEach((p, idx) => {
        const x = padding + p.time * xScale;
        const y = canvas.height - padding - p.value * yScale;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    };

    drawAxes();

    series.forEach(s => plotSeries(s.points, s.color));

    // Legend
    const legendY = padding - 18;
    series.forEach((s, idx) => {
      const lx = padding + idx * 120;
      ctx.fillStyle = s.color;
      ctx.fillRect(lx, legendY, 14, 4);
      ctx.fillStyle = "#dfe9ff";
      ctx.fillText(s.label, lx + 20, legendY + 6);
    });
  }

  function drawHistogram(canvas, values, color, label) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!values || values.length === 0) {
      ctx.fillStyle = "#9fb3ce";
      ctx.font = "12px " + getComputedStyle(document.body).fontFamily;
      ctx.fillText("No data yet", 14, 24);
      return;
    }
    const bins = 18;
    const maxVal = Math.max(...values);
    const minVal = 0;
    const binWidth = (maxVal - minVal) / bins || 1;
    const counts = new Array(bins).fill(0);
    values.forEach(v => {
      const idx = Math.min(bins - 1, Math.floor((v - minVal) / binWidth));
      counts[idx] += 1;
    });
    const maxCount = Math.max(...counts, 1);
    const padding = 32;
    const barWidth = (canvas.width - padding * 2) / bins;
    counts.forEach((c, i) => {
      const x = padding + i * barWidth;
      const h = (canvas.height - padding * 2) * (c / maxCount);
      ctx.fillStyle = color;
      ctx.fillRect(x, canvas.height - padding - h, barWidth - 2, h);
    });
    ctx.fillStyle = "#dfe9ff";
    ctx.font = "12px " + getComputedStyle(document.body).fontFamily;
    ctx.fillText(label, padding, padding - 10);
  }

  function buildStats(run) {
    const rows = run.metrics;
    if (!rows.length) return null;
    const totals = rows.map(r => r.total_time);
    const dwell = rows.map(r => r.yard_dwell);
    const scanWaits = rows.map(r => r.scan_wait);
    const loadWaits = rows.map(r => r.loading_wait);
    const gateWaits = rows.map(r => r.gate_wait);
    const bottlenecks = [
      { name: "Scanning", value: mean(scanWaits) },
      { name: "Loading", value: mean(loadWaits) },
      { name: "Gate-Out", value: mean(gateWaits) }
    ];
    bottlenecks.sort((a, b) => b.value - a.value);
    return {
      count: rows.length,
      avgTotal: mean(totals),
      avgDwell: mean(dwell),
      avgScanWait: mean(scanWaits),
      avgLoadingWait: mean(loadWaits),
      avgGateWait: mean(gateWaits),
      bottleneck: bottlenecks[0]?.name || "—",
      waits: { scanWaits, loadWaits, gateWaits }
    };
  }

  function render(runLabel, runResult) {
    const stats = buildStats(runResult);
    updateMetrics(runLabel, stats);
    if (stats) {
      drawLineChart($("queueChart"), [
        { label: "Scanning", color: "#5eb8ff", points: runResult.queueSeries.scan },
        { label: "Loading", color: "#f4b400", points: runResult.queueSeries.load },
        { label: "Gate", color: "#ff6b6b", points: runResult.queueSeries.gate }
      ]);
      drawHistogram($("scanHist"), stats.waits.scanWaits, "#5eb8ff", "Scan wait (minutes)");
      drawHistogram($("loadHist"), stats.waits.loadWaits, "#f4b400", "Loading wait (minutes)");
      drawHistogram($("gateHist"), stats.waits.gateWaits, "#ff6b6b", "Gate wait (minutes)");
    } else {
      ["queueChart", "scanHist", "loadHist", "gateHist"].forEach(id => {
        const c = $(id);
        c.getContext("2d").clearRect(0, 0, c.width, c.height);
      });
    }
  }

  function renderComparison() {
    const tbody = $("comparisonTable").querySelector("tbody");
    tbody.innerHTML = "";
    const base = state.lastRuns.baseline;
    const imp = state.lastRuns.improved;
    if (!base || !imp) {
      const row = document.createElement("tr");
      row.innerHTML = `<td colspan="4" class="hint">Run both baseline and improved to compare.</td>`;
      tbody.appendChild(row);
      return;
    }
    const rows = [
      ["Avg total time (min)", base.avgTotal, imp.avgTotal],
      ["Avg yard dwell (min)", base.avgDwell, imp.avgDwell],
      ["Avg scan wait (min)", base.avgScanWait, imp.avgScanWait],
      ["Avg loading wait (min)", base.avgLoadingWait, imp.avgLoadingWait],
      ["Avg gate wait (min)", base.avgGateWait, imp.avgGateWait]
    ];
    rows.forEach(([label, b, i]) => {
      const delta = b === 0 ? 0 : ((i - b) / b) * 100;
      const cls = delta <= 0 ? "good" : "bad";
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${label}</td>
        <td>${round1(b)}</td>
        <td>${round1(i)}</td>
        <td class="${cls}">${round1(delta)}%</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // ---------- UI wiring ----------
  function setInputs(cfg) {
    $("numCranes").value = cfg.numCranes;
    $("craneMph").value = cfg.craneMovesPerHour;
    $("dwellPolicy").value = cfg.dwellPolicy;
    $("numScanners").value = cfg.numScanners;
    $("scanTime").value = cfg.scanTime;
    $("numLoaders").value = cfg.numLoaders;
    $("loadMin").value = cfg.loadMin;
    $("loadMode").value = cfg.loadMode;
    $("loadMax").value = cfg.loadMax;
    $("numGates").value = cfg.numGates;
    $("gateMin").value = cfg.gateMin;
    $("gateMode").value = cfg.gateMode;
    $("gateMax").value = cfg.gateMax;
    $("arrivalRate").value = cfg.arrivalRatePerHour;
    $("simDays").value = cfg.simDays;
  }

  function readInputs() {
    return {
      numCranes: parseInt($("numCranes").value, 10),
      craneMovesPerHour: parseFloat($("craneMph").value),
      dwellPolicy: $("dwellPolicy").value,
      numScanners: parseInt($("numScanners").value, 10),
      scanTime: parseFloat($("scanTime").value),
      numLoaders: parseInt($("numLoaders").value, 10),
      loadMin: parseFloat($("loadMin").value),
      loadMode: parseFloat($("loadMode").value),
      loadMax: parseFloat($("loadMax").value),
      numGates: parseInt($("numGates").value, 10),
      gateMin: parseFloat($("gateMin").value),
      gateMode: parseFloat($("gateMode").value),
      gateMax: parseFloat($("gateMax").value),
      arrivalRatePerHour: parseFloat($("arrivalRate").value),
      simDays: parseInt($("simDays").value, 10),
      yardCapacity: defaults.yardCapacity
    };
  }

  function runAndRender(label, cfgOverride) {
    const cfg = cfgOverride || readInputs();
    const run = runSimulation(cfg);
    render(label, run);
    const stats = buildStats(run);
    if (label === "Baseline") state.lastRuns.baseline = stats;
    if (label === "Improved dwell") state.lastRuns.improved = stats;
    renderComparison();
  }

  function resetAll() {
    setInputs(defaults);
    state.currentLabel = "—";
    state.lastRuns.baseline = null;
    state.lastRuns.improved = null;
    $("metricsGrid").innerHTML = "";
    $("bottleneckBox").textContent = "Bottleneck: —";
    $("runLabel").textContent = "—";
    ["queueChart", "scanHist", "loadHist", "gateHist"].forEach(id => {
      const c = $(id);
      c.getContext("2d").clearRect(0, 0, c.width, c.height);
    });
    renderComparison();
  }

  function init() {
    setInputs(defaults);

    $("baselineBtn").addEventListener("click", () => {
      setInputs({ ...defaults, dwellPolicy: "baseline" });
      runAndRender("Baseline", { ...defaults, dwellPolicy: "baseline" });
    });

    $("improvedBtn").addEventListener("click", () => {
      setInputs({ ...defaults, dwellPolicy: "improved" });
      runAndRender("Improved dwell", { ...defaults, dwellPolicy: "improved" });
    });

    $("customBtn").addEventListener("click", () => {
      runAndRender("Custom", readInputs());
    });

    $("resetBtn").addEventListener("click", resetAll);

    // Initial baseline run on load to populate the dashboard.
    runAndRender("Baseline", defaults);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
