const $ = (id) => document.getElementById(id);
let currentTables = [];
let currentColumns = [];

async function api(url, options = {}) {
  const response = await fetch(url, {
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
    ...options
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
function showError(message) {
  $("errorBox").textContent = message;
  $("errorBox").classList.remove("hidden");
}
function clearError() { $("errorBox").classList.add("hidden"); $("errorBox").textContent = ""; }
function option(value, label = value) {
  const el = document.createElement("option"); el.value = value; el.textContent = label; return el;
}
function resetSelect(id, values, firstLabel = null) {
  const select = $(id); select.replaceChildren();
  if (firstLabel !== null) select.append(option("", firstLabel));
  values.forEach(v => select.append(option(v)));
}
async function loadCatalogs() {
  try {
    const data = await api("/api/catalogs");
    resetSelect("catalog", data.catalogs);
    if (!data.catalogs.length) throw new Error("No Trino catalogs were returned.");
    const preferred = data.catalogs.includes("demo") ? "demo" : data.catalogs[0];
    $("catalog").value = preferred;
    await loadSchemas();
  } catch (e) { showError(e.message); $("tableList").textContent = "Catalog unavailable"; }
}
async function loadSchemas() {
  try {
    const data = await api(`/api/schemas?catalog=${encodeURIComponent($("catalog").value)}`);
    resetSelect("schema", data.schemas);
    if (!data.schemas.length) { $("tableList").textContent = "No schemas found"; return; }
    const preferred = data.schemas.includes("public") ? "public" : data.schemas[0];
    $("schema").value = preferred;
    await loadTables();
  } catch (e) { showError(e.message); }
}
async function loadTables() {
  try {
    const data = await api(`/api/tables?catalog=${encodeURIComponent($("catalog").value)}&schema=${encodeURIComponent($("schema").value)}`);
    currentTables = data.tables;
    const list = $("tableList"); list.replaceChildren();
    resetSelect("builderTable", currentTables);
    if (!currentTables.length) list.textContent = "No tables found";
    currentTables.forEach(table => {
      const b = document.createElement("button"); b.className = "table-item";
      b.innerHTML = '<span class="table-symbol">▤</span>';
      const label = document.createElement("span"); label.textContent = table;
      b.append(label); b.addEventListener("click", () => selectTable(table)); list.append(b);
    });
    if (currentTables.length) await selectTable(currentTables[0]);
  } catch (e) { showError(e.message); }
}
async function selectTable(table) {
  $("builderTable").value = table;
  document.querySelectorAll(".table-item").forEach(b => b.classList.toggle("selected", b.textContent.trim() === table));
  try {
    const data = await api(`/api/columns?catalog=${encodeURIComponent($("catalog").value)}&schema=${encodeURIComponent($("schema").value)}&table=${encodeURIComponent(table)}`);
    currentColumns = data.columns;
    resetSelect("dimension", currentColumns.map(c => c.name), "No grouping");
    resetSelect("metric", ["*"].concat(currentColumns.map(c => c.name)));
    $("metric").value = "*"; $("aggregation").value = "COUNT";
    $("sqlEditor").value = `SELECT * FROM ${$("catalog").value}.${$("schema").value}.${table} LIMIT 100`;
    const buttons = [...document.querySelectorAll(".table-item")];
    buttons.forEach(b => b.classList.toggle("selected", b.textContent.trim() === table));
    $("resultMessage").textContent = `${table} selected · ${currentColumns.length} columns`;
  } catch (e) { showError(e.message); }
}
function buildSql() {
  const table = $("builderTable").value;
  if (!table) throw new Error("Choose a source table first.");
  const catalog = $("catalog").value, schema = $("schema").value;
  const fullTable = `${catalog}.${schema}.${table}`;
  const dimension = $("dimension").value;
  const metric = $("metric").value;
  const agg = $("aggregation").value;
  const limit = Math.max(1, Math.min(500, Number($("limit").value) || 100));
  let selectExpr;
  if (metric === "*") selectExpr = "COUNT(*) AS row_count";
  else selectExpr = `${agg}(${metric}) AS ${agg.toLowerCase()}_${metric}`;
  const selectParts = dimension ? [dimension, selectExpr] : [selectExpr];
  return `SELECT ${selectParts.join(", ")}\nFROM ${fullTable}${dimension ? `\nGROUP BY ${dimension}\nORDER BY ${selectExpr.split(" AS ")[1]} DESC` : ""}\nLIMIT ${limit}`;
}
async function runSql(sql) {
  clearError(); $("resultMessage").textContent = "Query running…";
  $("rowCount").textContent = "…";
  try {
    const data = await api("/api/query", {method:"POST", body:JSON.stringify({sql})});
    renderResults(data);
    $("resultMessage").textContent = data.query_id ? `Query completed · ${data.query_id}` : "Query completed";
  } catch (e) { showError(e.message); $("resultMessage").textContent = "Query did not complete"; $("rowCount").textContent = "—"; }
}
function renderResults(data) {
  $("rowCount").textContent = `${data.row_count} row${data.row_count === 1 ? "" : "s"}${data.truncated ? "+" : ""}`;
  if (data.truncated) $("resultMessage").textContent = "Showing the first page of results; the output was truncated.";
  const wrap = $("resultsTable"); wrap.replaceChildren();
  if (!data.columns || !data.columns.length) {
    const empty = document.createElement("div"); empty.className = "empty-state"; empty.textContent = "Query completed with no tabular results."; wrap.append(empty); return;
  }
  const table = document.createElement("table"); table.className = "data-table";
  const thead = document.createElement("thead"), hr = document.createElement("tr");
  data.columns.forEach(c => { const th = document.createElement("th"); th.textContent = c.name; th.title = c.type || ""; hr.append(th); });
  thead.append(hr); table.append(thead);
  const tbody = document.createElement("tbody");
  data.rows.forEach(row => { const tr = document.createElement("tr"); row.forEach(value => { const td = document.createElement("td"); td.textContent = value === null ? "NULL" : String(value); tr.append(td); }); tbody.append(tr); });
  table.append(tbody); wrap.append(table);
}
async function previewTable() {
  const table = $("builderTable").value;
  if (!table) return;
  clearError();
  try {
    const data = await api("/api/preview", {method:"POST", body:JSON.stringify({catalog:$("catalog").value,schema:$("schema").value,table})});
    renderResults(data); $("resultMessage").textContent = `Preview: ${table}`;
  } catch(e) { showError(e.message); }
}
function activateTab(name) {
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
  $("builderPanel").classList.toggle("hidden", name !== "builder");
  $("sqlPanel").classList.toggle("hidden", name !== "sql");
  $("savedPanel").classList.toggle("hidden", name !== "saved");
  if (name === "saved") loadSaved();
}
async function saveQuery() {
  const name = $("saveName").value.trim();
  if (!name) return showError("Enter a name before saving this analysis.");
  try {
    await api("/api/saved-queries", {method:"POST",body:JSON.stringify({name,sql:$("sqlEditor").value})});
    clearError(); $("saveName").value = ""; await loadSaved(); activateTab("saved");
  } catch(e) { showError(e.message); }
}
async function loadSaved() {
  try {
    const data = await api("/api/saved-queries");
    const list = $("savedList"); list.replaceChildren();
    if (!data.queries.length) { list.textContent = "No saved queries yet."; return; }
    data.queries.forEach(q => {
      const item = document.createElement("div"); item.className = "saved-item";
      const info = document.createElement("div"); const title = document.createElement("strong"); title.textContent = q.name;
      const code = document.createElement("code"); code.textContent = q.sql; info.append(title, code);
      const actions = document.createElement("div"); actions.className = "saved-actions";
      const open = document.createElement("button"); open.className = "button secondary"; open.textContent = "Open";
      open.onclick = () => { $("sqlEditor").value = q.sql; activateTab("sql"); };
      const del = document.createElement("button"); del.className = "button secondary"; del.textContent = "Delete";
      del.onclick = async () => { try { await api(`/api/saved-queries/${q.id}`,{method:"DELETE"}); await loadSaved(); } catch(e) { showError(e.message); } };
      actions.append(open, del); item.append(info, actions); list.append(item);
    });
  } catch(e) { showError(e.message); }
}
document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => activateTab(t.dataset.tab)));
$("catalog").addEventListener("change", loadSchemas);
$("schema").addEventListener("change", loadTables);
$("refreshTables").addEventListener("click", loadTables);
$("builderTable").addEventListener("change", () => selectTable($("builderTable").value));
$("buildQuery").addEventListener("click", () => { try { $("sqlEditor").value = buildSql(); activateTab("sql"); } catch(e) { showError(e.message); } });
$("runBuilder").addEventListener("click", () => { try { const sql = buildSql(); $("sqlEditor").value = sql; runSql(sql); } catch(e) { showError(e.message); } });
$("runSql").addEventListener("click", () => runSql($("sqlEditor").value));
$("saveQuery").addEventListener("click", saveQuery);
$("newQuery").addEventListener("click", () => { $("sqlEditor").value = "SELECT * FROM demo.public.sales LIMIT 100"; activateTab("sql"); });
$("tableList").addEventListener("dblclick", previewTable);
$("builderTable").addEventListener("dblclick", previewTable);
loadCatalogs();
