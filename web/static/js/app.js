const state = {
  selectedFile: null,
  pendingApproval: null,
  pendingTaskId: null,
};

const views = {
  upload: { title: "Upload & Process", subtitle: "Upload a ZIP of utility bill PDFs to begin" },
  bills: { title: "Extracted Bills", subtitle: "Review structured bill data extracted by local Gemma" },
  payments: { title: "Payment Queue", subtitle: "Prioritized bills ready for mock provider payment" },
  report: { title: "Audit Report", subtitle: "Summary statistics, confirmations, and audit timeline" },
};

const agentFeed = document.getElementById("agent-feed");
const approvalModal = document.getElementById("approval-modal");

function setView(name) {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === name);
  });
  document.querySelectorAll(".view").forEach((section) => {
    section.classList.toggle("active", section.id === `view-${name}`);
  });
  document.getElementById("view-title").textContent = views[name].title;
  document.getElementById("view-subtitle").textContent = views[name].subtitle;
  if (name === "bills") loadBills();
  if (name === "payments") loadTasks();
  if (name === "report") loadReport();
}

function clearAgentFeed() {
  agentFeed.innerHTML = `<div class="agent-empty"><p>Agent steps will appear here as bills are processed or payments are prepared.</p></div>`;
}

function appendAgentStep(event) {
  if (event.type === "ping") return;
  if (event.type === "done") {
    appendAgentStep({
      type: "step",
      kind: event.result?.success === false ? "error" : "success",
      title: event.result?.success === false ? "Run failed" : "Run complete",
      detail: JSON.stringify(event.result || {}, null, 0).slice(0, 180),
      timestamp: event.timestamp,
    });
    return;
  }

  const empty = agentFeed.querySelector(".agent-empty");
  if (empty) empty.remove();

  const el = document.createElement("div");
  el.className = `agent-step ${event.kind || "thinking"}`;
  const time = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "";
  el.innerHTML = `
    <div class="step-head">${iconForKind(event.kind)} ${labelForKind(event.kind)} · ${time}</div>
    <div class="step-title">${escapeHtml(event.title || "")}</div>
    ${event.detail ? `<div class="step-detail">${escapeHtml(event.detail)}</div>` : ""}
  `;
  agentFeed.appendChild(el);
  agentFeed.scrollTop = agentFeed.scrollHeight;

  if (event.kind === "permission" && event.meta) {
    showApprovalModal(event.meta);
  }
}

function iconForKind(kind) {
  return ({
    thinking: "💭",
    tool: "🔧",
    success: "✅",
    warning: "⚠️",
    error: "❌",
    permission: "🛡️",
  }[kind] || "•");
}

function labelForKind(kind) {
  return ({
    thinking: "Thinking",
    tool: "Tool",
    success: "Success",
    warning: "Warning",
    error: "Error",
    permission: "Permission",
  }[kind] || "Step");
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function showApprovalModal(data) {
  state.pendingApproval = data;
  state.pendingTaskId = data.task_id;
  document.getElementById("approval-details").innerHTML = `
    <div class="approval-row"><span>Provider</span><strong>${escapeHtml(data.provider || "")}</strong></div>
    <div class="approval-row"><span>Account</span><strong>${escapeHtml(data.account_number_masked || "")}</strong></div>
    <div class="approval-row"><span>Amount</span><strong>$${escapeHtml(data.amount || "")}</strong></div>
    <div class="approval-row"><span>Payment method</span><strong>${escapeHtml(data.payment_method || "")}</strong></div>
    <div class="approval-row"><span>Scheduled date</span><strong>${escapeHtml(data.scheduled_date || "")}</strong></div>
  `;
  approvalModal.classList.remove("hidden");
}

function hideApprovalModal() {
  approvalModal.classList.add("hidden");
  state.pendingApproval = null;
}

async function listenToRun(runId, onDone) {
  const source = new EventSource(`/api/runs/${runId}/events`);
  source.onmessage = (message) => {
    const event = JSON.parse(message.data);
    appendAgentStep(event);
    if (event.type === "done") {
      source.close();
      onDone?.(event.result);
    }
  };
  source.onerror = () => source.close();
}

async function loadStatus() {
  const res = await fetch("/api/status");
  const data = await res.json();
  const card = document.getElementById("ollama-status");
  card.classList.toggle("online", data.ollama_available);
  card.classList.toggle("offline", !data.ollama_available);
  card.querySelector("p").textContent = data.ollama_available
    ? `Connected · ${data.model}`
    : `Unavailable · run ollama serve`;
  document.getElementById("model-badge").textContent = data.model;
}

async function loadBills() {
  const res = await fetch("/api/bills");
  const data = await res.json();
  const tbody = document.querySelector("#bills-table tbody");
  tbody.innerHTML = data.bills.map((bill) => `
    <tr>
      <td>${escapeHtml(bill.provider)}</td>
      <td>${escapeHtml(bill.utility_type)}</td>
      <td>${escapeHtml(bill.masked_account)}</td>
      <td>$${bill.amount_due.toFixed(2)}</td>
      <td>${escapeHtml(bill.due_date)}</td>
      <td>${(bill.confidence * 100).toFixed(0)}%</td>
      <td><span class="status-pill status-${bill.status}">${escapeHtml(bill.status.replaceAll("_", " "))}</span></td>
      <td>${escapeHtml(bill.review_reason || "—")}</td>
    </tr>
  `).join("") || `<tr><td colspan="8">No bills yet. Upload a ZIP to get started.</td></tr>`;
}

async function loadTasks() {
  const res = await fetch("/api/tasks");
  const data = await res.json();
  const grid = document.getElementById("task-grid");
  grid.innerHTML = data.tasks.map((task) => `
    <div class="task-card">
      <div>
        <h4>${escapeHtml(task.provider)} · $${Number(task.amount_due).toFixed(2)}</h4>
        <p>Priority ${task.priority} · Due ${escapeHtml(task.due_date)} · <span class="status-pill status-${task.status}">${escapeHtml(task.status.replaceAll("_", " "))}</span></p>
      </div>
      <button class="btn btn-primary prepare-btn" data-task-id="${task.task_id}" ${task.status === "completed" ? "disabled" : ""}>
        Prepare Mock Payment
      </button>
    </div>
  `).join("") || `<p style="color: var(--text-muted)">No payment tasks yet.</p>`;

  grid.querySelectorAll(".prepare-btn").forEach((btn) => {
    btn.addEventListener("click", () => preparePayment(btn.dataset.taskId));
  });
}

async function preparePayment(taskId) {
  clearAgentFeed();
  appendAgentStep({ type: "step", kind: "thinking", title: "Starting payment preparation agent", detail: taskId });
  const res = await fetch(`/api/tasks/${taskId}/prepare`, { method: "POST" });
  const data = await res.json();
  listenToRun(data.run_id, (result) => {
    if (result?.approval) showApprovalModal(result.approval);
    loadTasks();
    loadBills();
  });
}

async function submitPayment(approved) {
  if (!state.pendingTaskId) return;
  hideApprovalModal();
  appendAgentStep({
    type: "step",
    kind: approved ? "success" : "warning",
    title: approved ? "User approved mock payment" : "User denied mock payment",
  });
  const res = await fetch(`/api/tasks/${state.pendingTaskId}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved }),
  });
  const data = await res.json();
  listenToRun(data.run_id, () => {
    loadTasks();
    loadBills();
    loadReport();
    state.pendingTaskId = null;
  });
}

async function loadReport() {
  const res = await fetch("/api/report");
  const data = await res.json();
  const s = data.summary;
  document.getElementById("report-summary").innerHTML = `
    <div class="report-card"><span>Total Bills</span><strong>${s.total_bills}</strong></div>
    <div class="report-card"><span>Amount Due</span><strong>$${s.total_amount_due.toFixed(2)}</strong></div>
    <div class="report-card"><span>Paid</span><strong>${s.paid}</strong></div>
    <div class="report-card"><span>Pending</span><strong>${s.pending}</strong></div>
  `;

  document.querySelector("#transactions-table tbody").innerHTML =
    data.transactions.map((t) => `
      <tr>
        <td>${escapeHtml(t.provider)}</td>
        <td>$${Number(t.amount).toFixed(2)}</td>
        <td>${escapeHtml(t.confirmation_number || "—")}</td>
        <td>${escapeHtml(t.status || "—")}</td>
      </tr>
    `).join("") || `<tr><td colspan="4">No transactions yet.</td></tr>`;

  document.getElementById("audit-timeline").innerHTML = data.events.map((e) => `
    <div class="timeline-item">
      <strong>${escapeHtml(e.event_type.replaceAll("_", " "))}</strong>
      <div>${escapeHtml(e.actor)} · job ${escapeHtml(e.job_id)}</div>
      <small>${new Date(e.timestamp).toLocaleString()}</small>
    </div>
  `).join("") || `<p style="color: var(--text-muted)">No audit events yet.</p>`;
}

async function processUpload() {
  if (!state.selectedFile) return;
  clearAgentFeed();
  appendAgentStep({ type: "step", kind: "thinking", title: "Uploading ZIP archive", detail: state.selectedFile.name });

  const form = new FormData();
  form.append("file", state.selectedFile);
  const res = await fetch("/api/jobs/upload", { method: "POST", body: form });
  const data = await res.json();

  listenToRun(data.run_id, (result) => {
    if (!result) return;
    document.getElementById("upload-metrics").hidden = false;
    document.getElementById("metric-bills").textContent = result.bills_created ?? 0;
    document.getElementById("metric-review").textContent = result.bills_needing_review ?? 0;
    document.getElementById("metric-dups").textContent = result.duplicates_detected ?? 0;
    loadBills();
    loadTasks();
  });
}

function setupUpload() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");

  dropzone.addEventListener("click", () => fileInput.click());
  document.getElementById("browse-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.click();
  });

  ["dragenter", "dragover"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((evt) => {
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files[0];
    if (file) selectFile(file);
  });

  fileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) selectFile(file);
  });

  document.getElementById("process-btn").addEventListener("click", processUpload);
}

function selectFile(file) {
  if (!file.name.toLowerCase().endsWith(".zip")) {
    appendAgentStep({ type: "step", kind: "error", title: "Invalid file", detail: "Please upload a ZIP file." });
    return;
  }
  state.selectedFile = file;
  document.getElementById("upload-meta").hidden = false;
  document.getElementById("selected-file").textContent = file.name;
}

document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => setView(btn.dataset.view));
});
document.getElementById("clear-agent").addEventListener("click", clearAgentFeed);
document.getElementById("refresh-bills").addEventListener("click", loadBills);
document.getElementById("refresh-tasks").addEventListener("click", loadTasks);
document.getElementById("approve-payment").addEventListener("click", () => submitPayment(true));
document.getElementById("cancel-payment").addEventListener("click", () => submitPayment(false));
document.getElementById("deny-payment").addEventListener("click", hideApprovalModal);

setupUpload();
loadStatus();
setView("upload");
