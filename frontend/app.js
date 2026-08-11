// ==========================================================================
// SmartSupply — Frontend (vanilla JS)
// Se conecta a la API FastAPI del backend. Ajusta API_BASE si despliegas
// el backend en otra URL/puerto.
// ==========================================================================
const API_BASE = "http://localhost:8000/api";

const SECTION_COLOR = {
  "Cuarto": "var(--c-cuarto)",
  "Cocina": "var(--c-cocina)",
  "Baño": "var(--c-bano)",
  "Sala/Recepción": "var(--c-sala)",
};

const els = {
  plaqueGrid: document.getElementById("plaque-grid"),
  ordersTray: document.getElementById("orders-tray"),
  ordersHistory: document.getElementById("orders-history"),
  ledger: document.getElementById("ledger"),
  runBtn: document.getElementById("btn-run-agent"),
  statusPill: document.getElementById("agent-status"),
  toast: document.getElementById("toast"),
};

function showToast(msg) {
  els.toast.textContent = msg;
  els.toast.classList.add("show");
  setTimeout(() => els.toast.classList.remove("show"), 3200);
}

function setAgentStatus(state, label) {
  const dotClass = { idle: "dot--idle", working: "dot--working", done: "dot--done" }[state];
  els.statusPill.innerHTML = `<span class="dot ${dotClass}"></span> ${label}`;
}

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

// ---------------- Dashboard (plaquetas por sección) ----------------
async function cargarDashboard() {
  const data = await fetchJSON(`${API_BASE}/dashboard`);
  els.plaqueGrid.innerHTML = "";

  Object.entries(data).forEach(([seccion, info]) => {
    const color = SECTION_COLOR[seccion] || "var(--brass)";
    const critico = info.items_criticos > 0;

    const plaque = document.createElement("div");
    plaque.className = `plaque ${critico ? "has-alert" : ""}`;
    plaque.style.setProperty("--section-color", color);
    plaque.innerHTML = `
      <div class="plaque-rivet"></div>
      <div class="plaque-label">Sección</div>
      <div class="plaque-title">${seccion}</div>
      <div class="gauge"><div class="gauge-fill" style="width:${info.salud_pct}%"></div></div>
      <div class="plaque-stats">
        <span>Salud <strong>${info.salud_pct}%</strong></span>
        <span>${info.items_criticos}/${info.total_items} críticos</span>
      </div>
      <div class="plaque-alert">
        ⚠ ${info.items_criticos} ítem(s) bajo el mínimo
        ${info.ordenes_pendientes ? `· ${info.ordenes_pendientes} orden(es) pendiente(s)` : ""}
      </div>
    `;
    els.plaqueGrid.appendChild(plaque);
  });
}

// ---------------- Órdenes pendientes / historial ----------------
function renderItemsTable(items) {
  const rows = items.map(it => `
    <tr>
      <td>
        ${it.item}
        <span class="item-justif">${it.justificacion}</span>
      </td>
      <td>${it.cantidad_a_pedir} (stock ${it.stock_actual}/${it.stock_minimo})</td>
      <td>${it.proveedor_elegido}</td>
      <td>$${it.subtotal.toFixed(2)}</td>
    </tr>
  `).join("");

  return `
    <table class="order-items">
      <thead>
        <tr><th>Ítem</th><th>Cantidad</th><th>Proveedor</th><th>Subtotal</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderOrderCard(orden, { withActions }) {
  const color = SECTION_COLOR[orden.seccion] || "var(--brass)";
  const fecha = new Date(orden.creado_en).toLocaleString();

  const footer = withActions
    ? `
      <div class="order-actions">
        <button class="btn btn--approve" data-action="aprobar" data-id="${orden.id}">Aprobar Pedido</button>
        <button class="btn btn--reject" data-action="rechazar" data-id="${orden.id}">Rechazar</button>
      </div>`
    : `<span class="order-decision-stamp order-decision-stamp--${orden.estado}">${orden.estado}</span>`;

  return `
    <div class="order-card" style="--section-color:${color}" id="order-${orden.id}">
      <div class="order-head">
        <span class="order-section-tag">${orden.seccion}</span>
        <span class="order-id">Orden #${orden.id} · ${fecha}</span>
      </div>
      <p class="order-reasoning">${orden.razonamiento_general || ""}</p>
      ${renderItemsTable(orden.items)}
      <div class="order-footer">
        <div class="order-total">Total estimado: <strong>$${orden.total_estimado.toFixed(2)}</strong></div>
        ${footer}
      </div>
    </div>
  `;
}

async function cargarOrdenes() {
  const todas = await fetchJSON(`${API_BASE}/ordenes`);
  const pendientes = todas.filter(o => o.estado === "pendiente");
  const resueltas = todas.filter(o => o.estado !== "pendiente");

  els.ordersTray.innerHTML = pendientes.length
    ? pendientes.map(o => renderOrderCard(o, { withActions: true })).join("")
    : `<p class="empty-state">Aún no hay propuestas. Ejecuta el agente para generarlas.</p>`;

  els.ordersHistory.innerHTML = resueltas.length
    ? resueltas.map(o => renderOrderCard(o, { withActions: false })).join("")
    : `<p class="empty-state">Sin decisiones registradas todavía.</p>`;
}

async function resolverOrden(id, accion) {
  const boton = document.querySelector(`[data-id="${id}"][data-action="${accion}"]`);
  if (boton) boton.disabled = true;

  try {
    await fetchJSON(`${API_BASE}/ordenes/${id}/${accion}`, {
      method: "POST",
      body: JSON.stringify({ admin: "Administrador" }),
    });
    showToast(accion === "aprobar" ? "Pedido aprobado ✔" : "Pedido rechazado ✖");
    await Promise.all([cargarOrdenes(), cargarDashboard(), cargarLogs()]);
  } catch (e) {
    showToast("Error al procesar la orden: " + e.message);
    if (boton) boton.disabled = false;
  }
}

els.ordersTray.addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  resolverOrden(btn.dataset.id, btn.dataset.action);
});

// ---------------- Bitácora de trazabilidad ----------------
const ACTOR_LABEL = { agente: "Agente", humano: "Humano", sistema: "Sistema" };

async function cargarLogs() {
  const logs = await fetchJSON(`${API_BASE}/logs`);
  els.ledger.innerHTML = logs.length
    ? logs.map(l => `
        <div class="log-row">
          <span>${new Date(l.timestamp).toLocaleString()}</span>
          <span class="log-actor log-actor--${l.actor}">${ACTOR_LABEL[l.actor] || l.actor}</span>
          <span class="log-detail"><strong>${l.accion}</strong> — ${l.detalle}</span>
        </div>
      `).join("")
    : `<p class="empty-state">Sin registros todavía.</p>`;
}

// ---------------- Ejecutar agente ----------------
els.runBtn.addEventListener("click", async () => {
  els.runBtn.disabled = true;
  setAgentStatus("working", "Analizando secciones…");
  try {
    const resultado = await fetchJSON(`${API_BASE}/agente/ejecutar`, { method: "POST" });
    setAgentStatus("done", "Análisis completo");
    showToast(resultado.mensaje);
    await Promise.all([cargarDashboard(), cargarOrdenes(), cargarLogs()]);
  } catch (e) {
    setAgentStatus("idle", "Error al ejecutar");
    showToast("Error: " + e.message);
  } finally {
    els.runBtn.disabled = false;
  }
});

// ---------------- Carga inicial ----------------
(async function init() {
  try {
    await Promise.all([cargarDashboard(), cargarOrdenes(), cargarLogs()]);
  } catch (e) {
    showToast("No se pudo conectar al backend. ¿Está corriendo en localhost:8000?");
  }
})();
