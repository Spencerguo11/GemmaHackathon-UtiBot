const state = {
  selectedFile: null,
  pendingApproval: null,
  pendingTaskId: null,
  pendingToolApproval: null,
  currentRunId: null,
  activeRunCount: 0,
  activeEventSource: null,
  chatSessionId: localStorage.getItem("chatSessionId") || null,
  skipUserEcho: false,
  currentAssistantBlock: null,
  turns: new Map(),
  activeTurnId: null,
};

const views = {
  workspace: { title: "Workspace", subtitle: "Chat with the agent or upload a ZIP manually" },
  bills: { title: "Extracted Bills", subtitle: "Structured bill data with pay-online URLs" },
  payments: { title: "Payment Queue", subtitle: "Prioritized bills ready for mock provider payment" },
  report: { title: "Audit Report", subtitle: "Summary statistics, confirmations, and audit timeline" },
};

const agentFeed = document.getElementById("agent-feed");
const approvalModal = document.getElementById("approval-modal");
const chatInput = document.getElementById("chat-input");
const chatSendBtn = document.getElementById("chat-send");
const chatStopBtn = document.getElementById("chat-stop");
const agentStatus = document.getElementById("agent-status");
const agentStatusText = document.getElementById("agent-status-text");
const historyPanel = document.getElementById("history-panel");
const historyList = document.getElementById("history-list");

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

function scrollFeedToBottom() {
  agentFeed.scrollTop = agentFeed.scrollHeight;
}

function ensureFeedReady() {
  const empty = agentFeed.querySelector(".agent-empty");
  if (empty) empty.remove();
}

function clearAgentFeed() {
  state.turns.clear();
  state.activeTurnId = null;
  state.currentAssistantBlock = null;
  agentFeed.innerHTML = `<div class="agent-empty"><p>Every tool execution requires your approval before it runs. Ask the agent to find ZIP files, parse bills, and extract pay-online URLs.</p></div>`;
}

function setComposerEnabled(enabled) {
  chatInput.disabled = !enabled;
  chatSendBtn.disabled = !enabled;
}

function setRunControls(active) {
  chatStopBtn.disabled = !active;
  if (active) {
    chatSendBtn.disabled = true;
    chatInput.disabled = false;
  }
}

function showAgentStatus(text) {
  agentStatusText.textContent = text;
  agentStatus.classList.remove("hidden");
}

function hideAgentStatus() {
  agentStatus.classList.add("hidden");
}

function appendMessageRow(role, content) {
  ensureFeedReady();
  const row = document.createElement("div");
  row.className = `msg-row ${role}`;
  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = role === "user" ? "You" : "AI";
  const body = document.createElement("div");
  body.className = "msg-body";
  const contentEl = document.createElement("div");
  contentEl.className = "msg-content";
  contentEl.textContent = content;
  body.appendChild(contentEl);
  row.appendChild(avatar);
  row.appendChild(body);
  agentFeed.appendChild(row);
  scrollFeedToBottom();
  return { row, body, contentEl };
}

function appendChatBubble(role, content) {
  return appendMessageRow(role, content);
}

function beginAssistantResponse() {
  ensureFeedReady();
  const row = document.createElement("div");
  row.className = "msg-row assistant";
  row.innerHTML = `
    <div class="msg-avatar">AI</div>
    <div class="msg-body">
      <div class="msg-content assistant-interim" hidden></div>
      <div class="msg-activity"></div>
    </div>
  `;
  agentFeed.appendChild(row);
  state.currentAssistantBlock = {
    row,
    contentEl: row.querySelector(".msg-content"),
    activityEl: row.querySelector(".msg-activity"),
    summaryEl: null,
  };
  scrollFeedToBottom();
  return state.currentAssistantBlock;
}

function updateAssistantInterim(content) {
  if (!state.currentAssistantBlock || !content) return;
  state.currentAssistantBlock.contentEl.hidden = false;
  state.currentAssistantBlock.contentEl.textContent = content;
  scrollFeedToBottom();
}

function buildResultSummary(result) {
  if (!result) return "Task finished.";
  const lines = [result.message || result.error || "Task finished."];
  if (result.bills_created != null) {
    lines.push(`Bills extracted: ${result.bills_created}`);
    lines.push(`Needs review: ${result.bills_needing_review ?? 0}`);
    lines.push(`Duplicates: ${result.duplicates_detected ?? 0}`);
  }
  if (result.cancelled) lines.unshift("Run stopped.");
  return lines.filter(Boolean).join("\n");
}

function finalizeAssistantSummary(result) {
  if (!state.currentAssistantBlock) return;
  const block = state.currentAssistantBlock;
  const isError = result?.success === false || result?.cancelled;
  const summary = document.createElement("div");
  summary.className = `msg-summary${isError ? " error" : ""}`;
  summary.innerHTML = `
    <div class="msg-summary-title">${isError ? "Summary" : "Result"}</div>
    <div>${escapeHtml(buildResultSummary(result)).replaceAll("\n", "<br>")}</div>
  `;
  block.body = block.row.querySelector(".msg-body");
  block.body.appendChild(summary);
  block.summaryEl = summary;
  if (block.contentEl.textContent.trim()) {
    block.contentEl.hidden = false;
  } else {
    block.contentEl.remove();
  }
  scrollFeedToBottom();
}

function getActivityContainer() {
  if (state.currentAssistantBlock?.activityEl) {
    return state.currentAssistantBlock.activityEl;
  }
  ensureFeedReady();
  return agentFeed;
}

function getTurn(turnId) {
  const parent = getActivityContainer();
  if (!state.turns.has(turnId)) {
    const wrap = document.createElement("div");
    wrap.className = "agent-turn";
    wrap.dataset.turnId = String(turnId);

    const header = document.createElement("button");
    header.type = "button";
    header.className = "turn-header open";
    header.innerHTML = `<span class="turn-title">Step ${turnId}</span><span class="turn-chevron">▼</span>`;

    const body = document.createElement("div");
    body.className = "turn-body open";

    header.addEventListener("click", () => {
      header.classList.toggle("open");
      body.classList.toggle("open");
      header.querySelector(".turn-chevron").textContent = body.classList.contains("open") ? "▼" : "▶";
    });

    wrap.appendChild(header);
    wrap.appendChild(body);
    parent.appendChild(wrap);
    state.turns.set(turnId, { wrap, header, body, titleEl: header.querySelector(".turn-title") });
  }
  return state.turns.get(turnId);
}

function appendAgentStep(event) {
  if (event.type === "ping") return;

  if (event.type === "chat") {
    if (event.role === "user" && state.skipUserEcho) return;
    if (event.role === "assistant") {
      updateAssistantInterim(event.content);
      return;
    }
    appendMessageRow(event.role, event.content);
    return;
  }

  if (event.type === "turn_start") {
    ensureFeedReady();
    state.activeTurnId = event.turn_id;
    const turn = getTurn(event.turn_id);
    turn.titleEl.textContent = event.title || `Step ${event.turn_id}`;
    turn.header.classList.add("open");
    turn.body.classList.add("open");
    showAgentStatus("Working on your request…");
    scrollFeedToBottom();
    return;
  }

  if (event.type === "turn_end") {
    const turn = state.turns.get(event.turn_id);
    if (turn) {
      turn.titleEl.textContent = `${event.summary || turn.titleEl.textContent} · ${event.status}`;
      turn.header.classList.remove("open");
      turn.body.classList.remove("open");
      turn.header.querySelector(".turn-chevron").textContent = "▶";
    }
    return;
  }

  if (event.type === "done") {
    hideAgentStatus();
    setRunControls(false);
    setComposerEnabled(true);
    state.skipUserEcho = false;
    if (event.result?.session_id) {
      state.chatSessionId = event.result.session_id;
      localStorage.setItem("chatSessionId", state.chatSessionId);
    }
    finalizeAssistantSummary(event.result);
    appendAgentStep({
      type: "step",
      turn_id: state.activeTurnId || 0,
      kind: event.result?.success === false ? "error" : "success",
      title: event.result?.success === false ? "Run failed" : "Run complete",
      detail: event.result?.message || "",
    });
    state.currentAssistantBlock = null;
    return;
  }

  ensureFeedReady();
  const turnId = event.turn_id || state.activeTurnId || 1;
  const turn = getTurn(turnId);
  const el = document.createElement("div");
  el.className = `agent-step ${event.kind || "thinking"}`;
  const time = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "";
  el.innerHTML = `
    <div class="step-head">${iconForKind(event.kind)} ${labelForKind(event.kind)} · ${time}</div>
    <div class="step-title">${escapeHtml(event.title || "")}</div>
    ${event.detail ? `<div class="step-detail">${escapeHtml(event.detail)}</div>` : ""}
  `;
  turn.body.appendChild(el);
  scrollFeedToBottom();

  if (event.kind === "thinking") showAgentStatus("Thinking…");
  if (event.kind === "tool") showAgentStatus("Running tools…");
  if (event.kind === "permission") showAgentStatus("Waiting for your approval…");

  if (event.kind === "permission" && event.meta) {
    handlePermissionEvent(event);
  }
}

function isToolExecutionPermission(meta) {
  return meta.approval_type === "tool_execution" && meta.run_id;
}

function isPaymentPermission(meta) {
  return meta.task_id && meta.provider && meta.approval_type !== "tool_execution";
}

function handlePermissionEvent(event) {
  const meta = event.meta;
  if (isToolExecutionPermission(meta)) {
    showToolApprovalCard(event, meta);
    return;
  }
  if (isPaymentPermission(meta)) {
    showApprovalModal(meta);
  }
}

function formatToolLabel(tool) {
  return ({
    list_folder: "List folder",
    find_zip: "Find ZIP files",
    process_zip: "Process ZIP & extract bills",
    prepare_mock_payment: "Prepare mock payment",
  }[tool] || tool || "Tool");
}

function showToolApprovalCard(event, meta) {
  state.pendingToolApproval = { runId: meta.run_id, cardId: `approval-${meta.run_id}-${Date.now()}` };
  setRunControls(true);
  showAgentStatus("Waiting for your approval…");

  const turnId = event.turn_id || state.activeTurnId || 1;
  const turn = getTurn(turnId);
  const card = document.createElement("div");
  card.className = "approval-card";
  card.id = state.pendingToolApproval.cardId;
  card.dataset.runId = meta.run_id;

  const toolLabel = formatToolLabel(meta.tool);
  const detail = event.detail || meta.description || "";
  const argsPreview = meta.args ? JSON.stringify(meta.args, null, 2) : "";

  card.innerHTML = `
    <div class="approval-card-title">Approval required</div>
    <div class="approval-card-body">
      <strong>${escapeHtml(toolLabel)}</strong>
      ${detail ? `<div style="margin-top:6px">${escapeHtml(detail)}</div>` : ""}
      ${meta.thought ? `<div class="approval-card-thought">${escapeHtml(meta.thought)}</div>` : ""}
    </div>
    ${argsPreview ? `<pre class="approval-card-meta">${escapeHtml(argsPreview)}</pre>` : ""}
    <div class="approval-card-actions">
      <button class="btn btn-secondary tool-deny" type="button">Deny</button>
      <button class="btn btn-primary tool-approve" type="button">Approve & run</button>
    </div>
  `;

  card.querySelector(".tool-approve").addEventListener("click", () => respondToToolApproval(meta.run_id, true, card));
  card.querySelector(".tool-deny").addEventListener("click", () => respondToToolApproval(meta.run_id, false, card));

  turn.body.appendChild(card);
  scrollFeedToBottom();
}

async function respondToToolApproval(runId, approved, cardEl) {
  cardEl.querySelectorAll("button").forEach((btn) => { btn.disabled = true; });
  const status = document.createElement("div");
  status.className = "approval-card-status";
  status.textContent = approved ? "Approved — executing…" : "Denied — action cancelled";
  cardEl.querySelector(".approval-card-actions").replaceWith(status);
  showAgentStatus(approved ? "Running tools…" : "Stopping…");

  try {
    const res = await fetch(`/api/runs/${runId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved }),
    });
    if (!res.ok) {
      const data = await res.json();
      status.textContent = data.detail || "Approval request failed";
      status.classList.add("error");
    }
  } catch {
    status.textContent = "Could not reach server";
    status.classList.add("error");
  }

  if (state.pendingToolApproval?.runId === runId) {
    state.pendingToolApproval = null;
  }
}

function iconForKind(kind) {
  return ({ thinking: "💭", tool: "🔧", success: "✅", warning: "⚠️", error: "❌", permission: "🛡️" }[kind] || "•");
}

function labelForKind(kind) {
  return ({ thinking: "Thinking", tool: "Tool", success: "Success", warning: "Warning", error: "Error", permission: "Permission" }[kind] || "Step");
}

function escapeHtml(str) {
  return String(str).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
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

async function stopCurrentRun() {
  if (!state.currentRunId) return;
  chatStopBtn.disabled = true;
  showAgentStatus("Stopping…");
  try {
    await fetch(`/api/runs/${state.currentRunId}/stop`, { method: "POST" });
  } catch {
    showAgentStatus("Could not stop run");
  }
  if (state.activeEventSource) {
    state.activeEventSource.close();
    state.activeEventSource = null;
  }
}

async function listenToRun(runId, onDone) {
  state.currentRunId = runId;
  state.activeRunCount += 1;
  setRunControls(true);
  showAgentStatus("Thinking…");

  const source = new EventSource(`/api/runs/${runId}/events`);
  state.activeEventSource = source;

  source.onmessage = (message) => {
    const event = JSON.parse(message.data);
    appendAgentStep(event);
    if (event.type === "done") {
      source.close();
      state.activeEventSource = null;
      state.activeRunCount = Math.max(0, state.activeRunCount - 1);
      if (state.currentRunId === runId) state.currentRunId = null;
      if (state.activeRunCount === 0 && !state.pendingToolApproval) {
        setComposerEnabled(true);
        setRunControls(false);
        hideAgentStatus();
      }
      onDone?.(event.result);
    }
  };

  source.onerror = () => {
    source.close();
    state.activeEventSource = null;
    state.activeRunCount = Math.max(0, state.activeRunCount - 1);
    if (state.activeRunCount === 0 && !state.pendingToolApproval) {
      setComposerEnabled(true);
      setRunControls(false);
      hideAgentStatus();
    }
  };
}

async function sendChatMessage() {
  const message = chatInput.value.trim();
  if (!message || chatInput.disabled) return;
  chatInput.value = "";
  chatInput.style.height = "auto";

  appendMessageRow("user", message);
  beginAssistantResponse();
  state.skipUserEcho = true;
  setRunControls(true);

  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: state.chatSessionId }),
  });
  const data = await res.json();
  if (!res.ok) {
    hideAgentStatus();
    setRunControls(false);
    setComposerEnabled(true);
    state.skipUserEcho = false;
    appendMessageRow("assistant", data.detail || "Chat request failed.");
    return;
  }

  if (data.session_id) {
    state.chatSessionId = data.session_id;
    localStorage.setItem("chatSessionId", state.chatSessionId);
  }

  listenToRun(data.run_id, (result) => {
    if (result?.job_id || result?.success) {
      document.getElementById("upload-metrics").hidden = false;
      if (result.bills_created != null) {
        document.getElementById("metric-bills").textContent = result.bills_created;
        document.getElementById("metric-review").textContent = result.bills_needing_review ?? 0;
        document.getElementById("metric-dups").textContent = result.duplicates_detected ?? 0;
      }
    }
    loadBills();
    loadTasks();
    if (result?.success && result?.bills_created != null) setView("bills");
  });
}

async function startNewChat() {
  if (state.activeRunCount > 0) {
    await stopCurrentRun();
  }
  const res = await fetch("/api/chat/sessions", { method: "POST" });
  const data = await res.json();
  if (!res.ok) return;
  state.chatSessionId = data.session.session_id;
  localStorage.setItem("chatSessionId", state.chatSessionId);
  clearAgentFeed();
  hideHistoryPanel();
}

function hideHistoryPanel() {
  historyPanel.classList.add("hidden");
}

function toggleHistoryPanel() {
  historyPanel.classList.toggle("hidden");
  if (!historyPanel.classList.contains("hidden")) {
    loadChatHistory();
  }
}

async function loadChatHistory() {
  const res = await fetch("/api/chat/sessions");
  const data = await res.json();
  if (!res.ok) {
    historyList.innerHTML = `<p class="history-item-meta" style="padding:14px">Could not load history.</p>`;
    return;
  }
  historyList.innerHTML = data.sessions.map((session) => `
    <button class="history-item${session.session_id === state.chatSessionId ? " active" : ""}" type="button" data-session-id="${escapeHtml(session.session_id)}">
      <span class="history-item-title">${escapeHtml(session.title || "New chat")}</span>
      <span class="history-item-meta">${session.message_count} messages · ${new Date(session.updated_at).toLocaleString()}</span>
    </button>
  `).join("") || `<p class="history-item-meta" style="padding:14px">No chats yet.</p>`;

  historyList.querySelectorAll(".history-item[data-session-id]").forEach((btn) => {
    btn.addEventListener("click", () => loadChatSession(btn.dataset.sessionId));
  });
}

async function loadChatSession(sessionId) {
  if (state.activeRunCount > 0) return;
  const res = await fetch(`/api/chat/sessions/${sessionId}`);
  const data = await res.json();
  if (!res.ok) return;

  state.chatSessionId = sessionId;
  localStorage.setItem("chatSessionId", sessionId);
  state.turns.clear();
  state.activeTurnId = null;
  state.currentAssistantBlock = null;
  agentFeed.innerHTML = "";

  data.messages.forEach((message) => {
    const row = appendMessageRow(message.role, message.content);
    if (message.role === "assistant" && message.metadata && Object.keys(message.metadata).length) {
      const summary = document.createElement("div");
      summary.className = `msg-summary${message.metadata.success === false ? " error" : ""}`;
      summary.innerHTML = `
        <div class="msg-summary-title">Saved result</div>
        <div>${escapeHtml(buildResultSummary(message.metadata)).replaceAll("\n", "<br>")}</div>
      `;
      row.body.appendChild(summary);
    }
  });

  if (!agentFeed.children.length) {
    agentFeed.innerHTML = `<div class="agent-empty"><p>No messages in this chat yet.</p></div>`;
  }
  hideHistoryPanel();
  scrollFeedToBottom();
}

async function loadStatus() {
  const res = await fetch("/api/status");
  const data = await res.json();
  const card = document.getElementById("ollama-status");
  card.classList.toggle("online", data.ollama_available);
  card.classList.toggle("offline", !data.ollama_available);
  card.querySelector("p").textContent = data.ollama_available ? `Connected · ${data.model}` : `Unavailable · run ollama serve`;
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
      <td class="url-cell">${bill.pay_online_url ? `<a href="${escapeHtml(bill.pay_online_url)}" target="_blank" rel="noopener">${escapeHtml(bill.pay_online_url)}</a>` : "—"}</td>
      <td>${(bill.confidence * 100).toFixed(0)}%</td>
      <td><span class="status-pill status-${bill.status}">${escapeHtml(bill.status.replaceAll("_", " "))}</span></td>
      <td>${escapeHtml(bill.review_reason || "—")}</td>
    </tr>
  `).join("") || `<tr><td colspan="9">No bills yet. Ask the agent to find and process a ZIP.</td></tr>`;
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
      <button class="btn btn-primary prepare-btn" data-task-id="${task.task_id}" ${task.status === "completed" ? "disabled" : ""}>Prepare Mock Payment</button>
    </div>
  `).join("") || `<p style="color: var(--text-muted)">No payment tasks yet.</p>`;
  grid.querySelectorAll(".prepare-btn").forEach((btn) => btn.addEventListener("click", () => preparePayment(btn.dataset.taskId)));
}

async function preparePayment(taskId) {
  appendMessageRow("user", `Prepare mock payment for task ${taskId}`);
  beginAssistantResponse();
  setRunControls(true);
  const res = await fetch(`/api/tasks/${taskId}/prepare`, { method: "POST" });
  const data = await res.json();
  listenToRun(data.run_id, () => {
    loadTasks();
    loadBills();
  });
}

async function submitPayment(approved) {
  if (!state.pendingTaskId) return;
  hideApprovalModal();
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
    data.transactions.map((t) => `<tr><td>${escapeHtml(t.provider)}</td><td>$${Number(t.amount).toFixed(2)}</td><td>${escapeHtml(t.confirmation_number || "—")}</td><td>${escapeHtml(t.status || "—")}</td></tr>`).join("") ||
    `<tr><td colspan="4">No transactions yet.</td></tr>`;
  document.getElementById("audit-timeline").innerHTML = data.events.map((e) => `
    <div class="timeline-item"><strong>${escapeHtml(e.event_type.replaceAll("_", " "))}</strong><div>${escapeHtml(e.actor)} · job ${escapeHtml(e.job_id)}</div><small>${new Date(e.timestamp).toLocaleString()}</small></div>
  `).join("") || `<p style="color: var(--text-muted)">No audit events yet.</p>`;
}

async function processUpload() {
  if (!state.selectedFile) return;
  beginAssistantResponse();
  setRunControls(true);
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
    setView("bills");
  });
}

function setupUpload() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  dropzone.addEventListener("click", () => fileInput.click());
  document.getElementById("browse-btn").addEventListener("click", (e) => { e.stopPropagation(); fileInput.click(); });
  ["dragenter", "dragover"].forEach((evt) => dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((evt) => dropzone.addEventListener(evt, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); }));
  dropzone.addEventListener("drop", (e) => { const file = e.dataTransfer.files[0]; if (file) selectFile(file); });
  fileInput.addEventListener("change", (e) => { const file = e.target.files[0]; if (file) selectFile(file); });
  document.getElementById("process-btn").addEventListener("click", processUpload);
}

function selectFile(file) {
  if (!file.name.toLowerCase().endsWith(".zip")) return;
  state.selectedFile = file;
  document.getElementById("upload-meta").hidden = false;
  document.getElementById("selected-file").textContent = file.name;
}

async function clearTabData(scope, confirmMessage) {
  if (!window.confirm(confirmMessage)) return;
  const res = await fetch(`/api/clear/${scope}`, { method: "DELETE" });
  const data = await res.json();
  if (!res.ok || !data.success) {
    appendMessageRow("assistant", data.detail || `Failed to clear ${scope}.`);
    return;
  }

  appendMessageRow("assistant", `Cleared ${scope} data.`);

  if (scope === "workspace") {
    state.selectedFile = null;
    document.getElementById("upload-meta").hidden = true;
    document.getElementById("upload-metrics").hidden = true;
    document.getElementById("metric-bills").textContent = "0";
    document.getElementById("metric-review").textContent = "0";
    document.getElementById("metric-dups").textContent = "0";
    document.getElementById("selected-file").textContent = "";
  }

  loadBills();
  loadTasks();
  loadReport();
}

function setupPanelResize() {
  const resizer = document.getElementById("panel-resizer");
  const root = document.documentElement;
  const stored = localStorage.getItem("agentPanelWidth");
  if (stored) root.style.setProperty("--agent-panel-width", stored);

  let dragging = false;

  resizer.addEventListener("mousedown", (event) => {
    dragging = true;
    resizer.classList.add("dragging");
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    event.preventDefault();
  });

  window.addEventListener("mousemove", (event) => {
    if (!dragging) return;
    const min = 320;
    const max = Math.min(760, window.innerWidth - 420);
    const width = Math.min(Math.max(window.innerWidth - event.clientX, min), max);
    root.style.setProperty("--agent-panel-width", `${width}px`);
  });

  window.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false;
    resizer.classList.remove("dragging");
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    localStorage.setItem("agentPanelWidth", getComputedStyle(root).getPropertyValue("--agent-panel-width").trim());
  });
}

document.getElementById("clear-workspace").addEventListener("click", () =>
  clearTabData(
    "workspace",
    "Clear workspace? This removes all jobs, bills, payment tasks, audit history, and uploaded job files."
  )
);
document.getElementById("clear-bills").addEventListener("click", () =>
  clearTabData("bills", "Clear all extracted bills and their linked payment tasks?")
);
document.getElementById("clear-payments").addEventListener("click", () =>
  clearTabData("payments", "Clear the payment queue and transaction records?")
);
document.getElementById("clear-report").addEventListener("click", () =>
  clearTabData("report", "Clear audit timeline and confirmation report data?")
);

document.querySelectorAll(".nav-item").forEach((btn) => btn.addEventListener("click", () => setView(btn.dataset.view)));
document.getElementById("clear-agent").addEventListener("click", clearAgentFeed);
document.getElementById("new-chat").addEventListener("click", startNewChat);
document.getElementById("chat-history-btn").addEventListener("click", toggleHistoryPanel);
document.getElementById("history-close").addEventListener("click", hideHistoryPanel);
document.getElementById("refresh-bills").addEventListener("click", loadBills);
document.getElementById("refresh-tasks").addEventListener("click", loadTasks);
document.getElementById("approve-payment").addEventListener("click", () => submitPayment(true));
document.getElementById("cancel-payment").addEventListener("click", () => submitPayment(false));
document.getElementById("deny-payment").addEventListener("click", hideApprovalModal);
document.getElementById("chat-send").addEventListener("click", sendChatMessage);
document.getElementById("chat-stop").addEventListener("click", stopCurrentRun);
chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChatMessage();
  }
});
document.addEventListener("click", (event) => {
  if (!historyPanel.contains(event.target) && event.target.id !== "chat-history-btn") {
    hideHistoryPanel();
  }
});

setupUpload();
setupPanelResize();
loadStatus();
setView("workspace");

if (state.chatSessionId) {
  loadChatSession(state.chatSessionId).catch(() => {});
}
