const plotlyLayoutBase = {
  paper_bgcolor: "#ffffff",
  plot_bgcolor: "#fafafa",
  font: { color: "#1f2937", size: 11 },
  margin: { t: 36, r: 12, l: 48, b: 40 },
};

function setStatus(text) {
  const el = document.getElementById("statusLine");
  if (el) el.textContent = text;
}

function setTyping(on) {
  const el = document.getElementById("typing");
  if (!el) return;
  el.hidden = !on;
}

function renderMessages(messages) {
  const thread = document.getElementById("chatThread");
  if (!thread) return;
  thread.innerHTML = "";
  const list = Array.isArray(messages) ? messages : [];
  for (const m of list) {
    const role = m.role === "assistant" ? "ai" : "user";
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    const label = document.createElement("span");
    label.className = "role";
    label.textContent = role === "user" ? "You" : "Assistant";
    div.appendChild(label);
    div.appendChild(document.createTextNode(m.content || ""));
    thread.appendChild(div);
  }
  thread.scrollTop = thread.scrollHeight;
}

function readMaterialsPayload() {
  const fc = document.getElementById("fcMPa")?.value;
  const fy = document.getElementById("fyMPa")?.value;
  const sbc = document.getElementById("sbcKPa")?.value;
  const materials = {};
  if (fc !== undefined && fc !== "") materials.fc_MPa = parseFloat(fc);
  if (fy !== undefined && fy !== "") materials.fy_MPa = parseFloat(fy);
  if (sbc !== undefined && sbc !== "") materials.sbc_kPa = parseFloat(sbc);
  return materials;
}

function applyProjectToForm(project) {
  const code = (project.building_code || "US").toUpperCase();
  const sel = document.getElementById("buildingCode");
  if (sel) {
    const opt = Array.from(sel.options).find((o) => o.value === code);
    sel.value = opt ? code : "US";
  }
  const mats = project.materials || {};
  const fcEl = document.getElementById("fcMPa");
  const fyEl = document.getElementById("fyMPa");
  const sbcEl = document.getElementById("sbcKPa");
  if (fcEl) fcEl.value = mats.fc_MPa != null ? mats.fc_MPa : "";
  if (fyEl) fyEl.value = mats.fy_MPa != null ? mats.fy_MPa : "";
  if (sbcEl) sbcEl.value = mats.sbc_kPa != null ? mats.sbc_kPa : "";
}

async function postSettings() {
  const building_code = document.getElementById("buildingCode")?.value || "US";
  const materials = readMaterialsPayload();
  await fetch("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ building_code, materials }),
  });
}

function heatColor(u) {
  const t = Math.max(0, Math.min(1, u));
  const h = (1 - t) * 130;
  return `hsl(${h}, 78%, 42%)`;
}

function buildMomentMap(project) {
  const res = project.last_result;
  if (!res || !res.ok || !res.results || !res.results.member_forces) return null;
  const map = {};
  let maxM = 0;
  for (const row of res.results.member_forces) {
    const id = String(row.member_id);
    const m = Number(row.moment_max_kNm) || 0;
    map[id] = m;
    if (m > maxM) maxM = m;
  }
  return { map, maxM };
}

function tabActivate(name) {
  document.querySelectorAll(".tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === name);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.id === `panel-${name}`);
  });
  if (window.Plotly) {
    ["chartLevels", "chartBeams", "chartCols", "chartReact"].forEach((id) => {
      const node = document.getElementById(id);
      if (node) Plotly.Plots.resize(node);
    });
    Plotly.Plots.resize("plot3d");
  }
}

function draw3D(project) {
  const nodes = project.nodes || {};
  const members = project.members || {};
  const supports = project.supports || {};
  const traces = [];
  const mm = buildMomentMap(project);

  const nodeIds = Object.keys(nodes);
  if (nodeIds.length === 0) {
    Plotly.newPlot(
      "plot3d",
      [],
      {
        ...plotlyLayoutBase,
        title: { text: "3D frame (empty)", font: { size: 14 } },
        scene: {
          xaxis: { title: "X (m)" },
          yaxis: { title: "Y (m)" },
          zaxis: { title: "Z (m)" },
        },
      },
      { responsive: true, displaylogo: false }
    );
    return;
  }

  const nodeX = [];
  const nodeY = [];
  const nodeZ = [];
  for (const nid of nodeIds) {
    const [x, y, z] = nodes[nid];
    nodeX.push(x);
    nodeY.push(y);
    nodeZ.push(z);
  }

  traces.push({
    type: "scatter3d",
    mode: "markers+text",
    x: nodeX,
    y: nodeY,
    z: nodeZ,
    text: nodeIds,
    textposition: "top center",
    marker: { size: 5, color: "#111827" },
    name: "Nodes",
  });

  for (const mid of Object.keys(members)) {
    const [ni, nj] = members[mid];
    const a = nodes[String(ni)] || nodes[ni];
    const b = nodes[String(nj)] || nodes[nj];
    if (!a || !b) continue;
    let lineColor = "#10a37f";
    let lineWidth = 7;
    if (mm && mm.maxM > 1e-6) {
      const mval = mm.map[String(mid)] ?? 0;
      lineColor = heatColor(mval / mm.maxM);
      lineWidth = 8;
    }
    traces.push({
      type: "scatter3d",
      mode: "lines",
      x: [a[0], b[0]],
      y: [a[1], b[1]],
      z: [a[2], b[2]],
      line: { width: lineWidth, color: lineColor },
      showlegend: false,
      hovertemplate: mm
        ? `Member ${mid}<br>|M|max ≈ ${(mm.map[String(mid)] ?? 0).toFixed(2)} kNm<extra></extra>`
        : `Member ${mid}<extra></extra>`,
    });
  }

  const fxX = [];
  const fxY = [];
  const fxZ = [];
  const pnX = [];
  const pnY = [];
  const pnZ = [];

  for (const nid of Object.keys(supports)) {
    const [x, y, z] = nodes[nid];
    if (supports[nid] === "fixed") {
      fxX.push(x);
      fxY.push(y);
      fxZ.push(z);
    } else {
      pnX.push(x);
      pnY.push(y);
      pnZ.push(z);
    }
  }

  if (fxX.length) {
    traces.push({
      type: "scatter3d",
      mode: "markers",
      x: fxX,
      y: fxY,
      z: fxZ,
      marker: { size: 8, color: "#ef4444", symbol: "square" },
      name: "Fixed",
    });
  }

  if (pnX.length) {
    traces.push({
      type: "scatter3d",
      mode: "markers",
      x: pnX,
      y: pnY,
      z: pnZ,
      marker: { size: 8, color: "#f59e0b", symbol: "circle" },
      name: "Pinned",
    });
  }

  const titleText = mm && mm.maxM > 1e-6
    ? "3D frame — member color = |M|max (green low → red high)"
    : "3D structural frame (uniform green until FEM is run)";

  Plotly.newPlot(
    "plot3d",
    traces,
    {
      ...plotlyLayoutBase,
      title: { text: titleText, font: { size: 13 } },
      scene: {
        xaxis: { title: "X (m)" },
        yaxis: { title: "Y (m)" },
        zaxis: { title: "Z (m)" },
        bgcolor: "#fafafa",
      },
    },
    { responsive: true, displaylogo: false }
  );
}

function emptyChart(elId, title) {
  Plotly.newPlot(
    elId,
    [],
    {
      ...plotlyLayoutBase,
      title: { text: title, font: { size: 12 } },
      annotations: [
        {
          text: "Run Build & Analyze",
          xref: "paper",
          yref: "paper",
          x: 0.5,
          y: 0.5,
          showarrow: false,
          font: { color: "#9ca3af", size: 12 },
        },
      ],
    },
    { responsive: true, displaylogo: false }
  );
}

function drawCharts(charts) {
  if (!window.Plotly) return;
  if (!charts || !charts.level_curve) {
    emptyChart("chartLevels", "Level drift (max |ux|)");
    emptyChart("chartBeams", "Beam |M|max");
    emptyChart("chartCols", "Column |M|max");
    emptyChart("chartReact", "Support Rz");
    return;
  }

  const lc = charts.level_curve;
  Plotly.newPlot(
    "chartLevels",
    [
      {
        x: lc.z_levels_m,
        y: lc.max_abs_ux_mm,
        type: "scatter",
        mode: "lines+markers",
        line: { color: "#2563eb" },
        name: "mm",
      },
    ],
    {
      ...plotlyLayoutBase,
      title: { text: "Max |ux| per level (mm)", font: { size: 12 } },
      xaxis: { title: "Z level (m)" },
      yaxis: { title: "mm" },
    },
    { responsive: true, displaylogo: false }
  );

  const bm = charts.beam_moments;
  Plotly.newPlot(
    "chartBeams",
    [
      {
        x: bm.ids,
        y: bm.moment_kNm,
        type: "bar",
        marker: { color: "#10a37f" },
      },
    ],
    {
      ...plotlyLayoutBase,
      title: { text: "Beams: |M|max (kNm)", font: { size: 12 } },
      xaxis: { title: "Member" },
      yaxis: { title: "kNm" },
    },
    { responsive: true, displaylogo: false }
  );

  const cm = charts.column_moments;
  Plotly.newPlot(
    "chartCols",
    [
      {
        x: cm.ids,
        y: cm.moment_kNm,
        type: "bar",
        marker: { color: "#7c3aed" },
      },
    ],
    {
      ...plotlyLayoutBase,
      title: { text: "Columns: |M|max (kNm)", font: { size: 12 } },
      xaxis: { title: "Member" },
      yaxis: { title: "kNm" },
    },
    { responsive: true, displaylogo: false }
  );

  const rr = charts.reactions;
  Plotly.newPlot(
    "chartReact",
    [
      {
        x: rr.nodes.map(String),
        y: rr.Fz_kN,
        type: "bar",
        marker: { color: "#ea580c" },
      },
    ],
    {
      ...plotlyLayoutBase,
      title: { text: "Vertical reaction Fz (kN)", font: { size: 12 } },
      xaxis: { title: "Node" },
      yaxis: { title: "kN" },
    },
    { responsive: true, displaylogo: false }
  );
}

function updateUI(project, brainStatus) {
  applyProjectToForm(project);

  const nodes = project.nodes || {};
  const members = project.members || {};
  const supports = project.supports || {};
  const loads = project.nodal_loads || {};
  const sections = project.family_sections || {};

  document.getElementById("modelCard").textContent =
`Nodes           : ${Object.keys(nodes).length}
Members         : ${Object.keys(members).length}
Supports        : ${Object.keys(supports).length}
Nodal loads     : ${Object.keys(loads).length}
Beam section    : ${sections.beam || "-"}
Column section  : ${sections.column || "-"}
Brace section   : ${sections.brace || "-"}
Building code   : ${project.building_code || "-"}`;

  if (project.last_result && project.last_result.ok) {
    const r = project.last_result.results;
    document.getElementById("resultCard").textContent =
`Roof drift (ux) : ${r.roof_disp_mm.toFixed(2)} mm
Drift limit     : ${r.drift_limit_mm.toFixed(2)} mm
Drift check     : ${r.drift_result}
Beam groups     : ${r.beam_groups.length}
Column groups   : ${r.column_groups.length}`;
  } else {
    document.getElementById("resultCard").textContent =
      project.last_result && !project.last_result.ok
        ? project.last_result.message || "Analysis failed."
        : "No analysis yet.";
  }

  const rep = project.last_report;
  document.getElementById("textSummary").textContent = rep?.summary || "Run Build & Analyze to populate this tab.";
  document.getElementById("textAnalysis").textContent = rep?.analysis || "";
  document.getElementById("textDesign").textContent = rep?.design || "";
  document.getElementById("textRec").textContent = rep?.recommendation
    ? `Recommendations\n\n${rep.recommendation}\n\nConclusion\n\n${rep.conclusion || ""}`
    : rep?.conclusion || "";

  const etabs = project.last_etabs_export || "";
  document.getElementById("etabsExport").textContent = etabs || "No export yet.";

  renderMessages(project.messages || []);
  draw3D(project);
  drawCharts(project.last_charts);

  if (brainStatus) {
    const pill = document.getElementById("brainStatus");
    if (pill) pill.textContent = brainStatus;
  }
}

async function fetchState() {
  const res = await fetch("/api/state");
  const data = await res.json();
  if (data.ok) {
    updateUI(data.project, data.brain_status);
  }
}

async function buildAndAnalyze() {
  const input = document.getElementById("messageInput");
  const text = input.value.trim();
  if (!text) return;

  setTyping(true);
  setStatus("Building model and running FEM…");

  const building_code = document.getElementById("buildingCode")?.value || "US";
  const materials = readMaterialsPayload();

  const res = await fetch("/api/build-analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text, building_code, materials, auto_analyze: true }),
  });

  const data = await res.json();
  setTyping(false);

  if (data.ok && data.project) {
    input.value = "";
    updateUI(data.project, data.brain_status);
    setStatus("Updated model, analysis, and graphs.");
    tabActivate("summary");
  } else {
    setStatus(data.message || "Build failed.");
    addLocalMessage("user", text);
    addLocalMessage("ai", data.message || "Request failed.");
  }
}

function addLocalMessage(role, content) {
  const thread = document.getElementById("chatThread");
  if (!thread) return;
  const div = document.createElement("div");
  div.className = `msg ${role === "user" ? "user" : "ai"}`;
  const label = document.createElement("span");
  label.className = "role";
  label.textContent = role === "user" ? "You" : "Assistant";
  div.appendChild(label);
  div.appendChild(document.createTextNode(content));
  thread.appendChild(div);
  thread.scrollTop = thread.scrollHeight;
}

async function askFollowUp() {
  const input = document.getElementById("messageInput");
  const text = input.value.trim();
  if (!text) return;

  await postSettings();

  setTyping(true);
  setStatus("Answering…");

  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text }),
  });

  const data = await res.json();
  setTyping(false);

  if (data.ok) {
    input.value = "";
    await fetchState();
    setStatus("Answered.");
  } else {
    setStatus(data.message || "Chat failed.");
    addLocalMessage("user", text);
    addLocalMessage("ai", data.message || "Chat failed.");
  }
}

async function loadSample() {
  setTyping(true);
  setStatus("Loading sample…");
  const res = await fetch("/api/model", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: "run_sample" }),
  });
  const data = await res.json();
  setTyping(false);
  if (data.ok && data.project) {
    updateUI(data.project, null);
    setStatus(data.message || "Sample loaded.");
  }
}

async function runFEMOnly() {
  setTyping(true);
  setStatus("Running FEM…");
  const res = await fetch("/api/model", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: "run_fem" }),
  });
  const data = await res.json();
  setTyping(false);
  if (data.ok && data.project) {
    updateUI(data.project, null);
    setStatus(data.message || "FEM done.");
    tabActivate("summary");
  }
}

async function undoState() {
  const res = await fetch("/api/undo", { method: "POST" });
  const data = await res.json();
  if (data.ok && data.project) {
    updateUI(data.project, null);
    setStatus(data.message || "Undo OK.");
  }
}

async function downloadEngineeringPack() {
  setStatus("Preparing download…");
  try {
    const res = await fetch("/api/export-pack");
    const data = await res.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    a.href = URL.createObjectURL(blob);
    a.download = `balmores-strux-pack-${stamp}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus("Downloaded JSON pack (geometry, loads, FEM, report, ETABS text).");
  } catch {
    setStatus("Download failed.");
  }
}

function wireEvents() {
  document.getElementById("btnBuild")?.addEventListener("click", () => buildAndAnalyze());
  document.getElementById("btnAsk")?.addEventListener("click", () => askFollowUp());
  document.getElementById("btnDownloadPack")?.addEventListener("click", () => downloadEngineeringPack());
  document.getElementById("btnSample")?.addEventListener("click", async () => {
    await loadSample();
    await runFEMOnly();
  });
  document.getElementById("btnUndo")?.addEventListener("click", () => undoState());

  document.getElementById("buildingCode")?.addEventListener("change", () => {
    postSettings().then(fetchState);
  });
  ["fcMPa", "fyMPa", "sbcKPa"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", () => {
      postSettings().then(fetchState);
    });
  });

  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => tabActivate(btn.dataset.tab));
  });

  document.getElementById("btnCopyEtabs")?.addEventListener("click", async () => {
    const t = document.getElementById("etabsExport")?.textContent || "";
    try {
      await navigator.clipboard.writeText(t);
      setStatus("ETABS text copied.");
    } catch {
      setStatus("Copy failed — select text manually.");
    }
  });

  const ta = document.getElementById("messageInput");
  ta?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (e.ctrlKey) {
        askFollowUp();
      } else {
        buildAndAnalyze();
      }
    }
  });
}

window.addEventListener("load", () => {
  wireEvents();
  fetchState();
});

window.addEventListener("resize", () => {
  if (window.Plotly) {
    Plotly.Plots.resize("plot3d");
    ["chartLevels", "chartBeams", "chartCols", "chartReact"].forEach((id) => {
      const n = document.getElementById(id);
      if (n) Plotly.Plots.resize(n);
    });
  }
});
