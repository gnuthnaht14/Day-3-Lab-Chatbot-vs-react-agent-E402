const messages = document.querySelector("#messages");
const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const traceList = document.querySelector("#traceList");
const traceSummary = document.querySelector("#traceSummary");
const clearButton = document.querySelector("#clearButton");
const providerStatus = document.querySelector("#providerStatus");
const statusDot = document.querySelector("#statusDot");
const workspace = document.querySelector(".workspace");
const workspaceTabs = document.querySelectorAll(".workspace-tab");
const traceCount = document.querySelector("#traceCount");
const capabilityCount = document.querySelector("#capabilityCount");
const guardrailList = document.querySelector("#guardrailList");
const toolList = document.querySelector("#toolList");
const guardrailCount = document.querySelector("#guardrailCount");
const toolCountLabel = document.querySelector("#toolCount");

let activeMode = "compare";
let activeToolPolicy = [];

const labels = {
  thought: "Thought",
  action: "Action",
  observation: "Observation",
  guardrail: "Guardrail",
  intent: "Intent & policy",
  complete: "Hoàn tất",
  step: "Bước xử lý",
  detail: "Chi tiết",
};

function setActivePanel(panel) {
  workspace.dataset.activePanel = panel;
  workspaceTabs.forEach((tab) => {
    const isActive = tab.dataset.panel === panel;
    tab.classList.toggle("active", isActive);
    tab.setAttribute("aria-selected", String(isActive));
  });
}

function highlightTools(policy = []) {
  activeToolPolicy = policy;
  document.querySelectorAll(".tool-card").forEach((card) => {
    card.classList.toggle("active", policy.includes(card.dataset.toolName));
  });
}

function renderCapabilities(data) {
  document.querySelector("#maxSteps").textContent = data.limits.max_business_steps;
  document.querySelector("#policyRetries").textContent = data.limits.max_policy_retries;
  document.querySelector("#toolTimeout").textContent = `${data.limits.tool_timeout_seconds}s`;
  document.querySelector("#returnWindow").textContent = data.limits.return_window_days;
  capabilityCount.textContent = String(data.tools.length);
  guardrailCount.textContent = `${data.guardrails.length} lớp`;
  toolCountLabel.textContent = `${data.tools.length} tools`;

  guardrailList.replaceChildren();
  for (const guardrail of data.guardrails) {
    const card = document.createElement("article");
    card.className = "guardrail-card";
    const title = document.createElement("strong");
    title.textContent = guardrail.name;
    const description = document.createElement("p");
    description.textContent = guardrail.description;
    card.append(title, description);
    guardrailList.append(card);
  }

  toolList.replaceChildren();
  for (const tool of data.tools) {
    const card = document.createElement("article");
    card.className = "tool-card";
    card.dataset.toolName = tool.name;
    const header = document.createElement("div");
    header.className = "tool-card-header";
    const signature = document.createElement("code");
    signature.textContent = tool.signature;
    const kind = document.createElement("span");
    kind.className = `tool-kind${tool.mutating ? " write" : ""}`;
    kind.textContent = tool.mutating ? "WRITE" : "READ";
    header.append(signature, kind);
    const description = document.createElement("p");
    description.textContent = tool.description;
    card.append(header, description);
    toolList.append(card);
  }
  highlightTools(activeToolPolicy);
}

function addMessage(role, text, result = null) {
  const article = document.createElement("article");
  article.className = `message ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "BẠN" : "OC";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  bubble.append(paragraph);

  if (result?.trace) {
    const traceButton = document.createElement("button");
    traceButton.className = "trace-link";
    traceButton.type = "button";
    traceButton.textContent = "Xem trace xử lý →";
    traceButton.addEventListener("click", () => {
      renderTrace(result);
      setActivePanel("trace");
    });
    bubble.append(traceButton);
  }

  article.append(avatar, bubble);
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
  return article;
}

function createResultCard(title, description, result, variant) {
  const card = document.createElement("section");
  card.className = `result-card ${variant}`;

  const header = document.createElement("div");
  header.className = "result-card-header";
  const titleGroup = document.createElement("div");
  const badge = document.createElement("span");
  badge.className = "result-badge";
  badge.textContent = title;
  const subtitle = document.createElement("small");
  subtitle.textContent = description;
  titleGroup.append(badge, subtitle);

  const toolCount = document.createElement("span");
  toolCount.className = "tool-count";
  toolCount.textContent = `${result.policy.length} tool`;
  header.append(titleGroup, toolCount);

  const answer = document.createElement("p");
  answer.className = "result-answer";
  answer.textContent = result.answer;

  const traceButton = document.createElement("button");
  traceButton.className = "trace-link";
  traceButton.type = "button";
  traceButton.textContent = variant === "agent-result" ? "Xem reasoning Agent →" : "Xem log Baseline →";
  traceButton.addEventListener("click", () => {
    renderTrace(result);
    setActivePanel("trace");
  });

  card.append(header, answer, traceButton);
  return card;
}

function addComparisonMessage(result) {
  const article = document.createElement("article");
  article.className = "message assistant comparison";

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = "VS";

  const bubble = document.createElement("div");
  bubble.className = "bubble comparison-bubble";
  const heading = document.createElement("div");
  heading.className = "comparison-heading";
  const title = document.createElement("strong");
  title.textContent = "Kết quả đối chiếu";
  const caption = document.createElement("span");
  caption.textContent = "Cùng một câu hỏi · Hai cách xử lý";
  heading.append(title, caption);

  const grid = document.createElement("div");
  grid.className = "comparison-grid";
  grid.append(
    createResultCard("BASELINE", "Trả lời không dùng công cụ", result.baseline, "baseline-result"),
    createResultCard("AGENT", result.agent.intent, result.agent, "agent-result"),
  );

  const insight = document.createElement("p");
  insight.className = "comparison-insight";
  const agentTools = result.agent.policy.length;
  insight.textContent = agentTools
    ? `Khác biệt chính: Agent đã dùng ${agentTools} tool (${result.agent.policy.join(" → ")}) để lấy dữ liệu thực tế; Baseline không gọi tool.`
    : "Cả hai luồng đều không cần gọi tool cho câu hỏi này; hãy so sánh độ chính xác và cách diễn đạt."

  bubble.append(heading, grid, insight);
  article.append(avatar, bubble);
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
}

function showTyping() {
  const article = document.createElement("article");
  article.className = "message assistant typing";
  article.id = "typingIndicator";
  article.innerHTML = '<div class="avatar">OC</div><div class="bubble"><i></i><i></i><i></i></div>';
  messages.append(article);
  messages.scrollTop = messages.scrollHeight;
}

function renderTrace(result) {
  const policy = result.policy?.length ? result.policy.join(" → ") : "Không gọi tool";
  traceSummary.replaceChildren();
  const badge = document.createElement("span");
  badge.className = "trace-badge";
  badge.textContent = result.intent || result.mode.toUpperCase();
  const summary = document.createElement("p");
  summary.textContent = `Policy: ${policy}`;
  traceSummary.append(badge, summary);

  traceList.replaceChildren();
  traceCount.textContent = String(result.trace.length);
  highlightTools(result.policy || []);
  for (const event of result.trace) {
    const item = document.createElement("div");
    item.className = `trace-event ${event.type}`;
    const label = document.createElement("div");
    label.className = "event-label";
    label.textContent = labels[event.type] || "Log";
    const content = document.createElement("p");
    content.className = "event-content";
    content.textContent = event.content;
    item.append(label, content);
    traceList.append(item);
  }
}

async function sendMessage(message) {
  addMessage("user", message);
  showTyping();
  sendButton.disabled = true;
  messageInput.disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, mode: activeMode }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Không thể xử lý yêu cầu.");
    document.querySelector("#typingIndicator")?.remove();
    if (result.mode === "compare") {
      addComparisonMessage(result);
      renderTrace(result.agent);
    } else {
      addMessage("assistant", result.answer, result);
      renderTrace(result);
    }
  } catch (error) {
    document.querySelector("#typingIndicator")?.remove();
    addMessage("assistant", `Đã xảy ra lỗi: ${error.message}`);
  } finally {
    sendButton.disabled = false;
    messageInput.disabled = false;
    messageInput.focus();
  }
}

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;
  messageInput.value = "";
  messageInput.style.height = "auto";
  sendMessage(message);
});

messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

messageInput.addEventListener("input", () => {
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 130)}px`;
});

document.querySelectorAll(".mode-button").forEach((button) => {
  button.addEventListener("click", () => {
    activeMode = button.dataset.mode;
    document.querySelectorAll(".mode-button").forEach((item) => item.classList.toggle("active", item === button));
  });
});

workspaceTabs.forEach((tab) => {
  tab.addEventListener("click", () => setActivePanel(tab.dataset.panel));
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    messageInput.value = button.dataset.prompt;
    messageInput.focus();
  });
});

clearButton.addEventListener("click", () => {
  messages.replaceChildren();
  addMessage("assistant", "Hội thoại đã được làm mới. Bạn cần hỗ trợ đơn hàng nào?");
  traceList.innerHTML = '<div class="empty-trace"><span>◎</span><p>Chưa có hoạt động</p><small>Gửi một câu hỏi để xem Agent chọn intent, tool và điểm dừng.</small></div>';
  traceSummary.innerHTML = '<span class="trace-badge">Sẵn sàng</span><p>Trace của câu hỏi gần nhất sẽ xuất hiện tại đây.</p>';
  traceCount.textContent = "0";
  highlightTools([]);
  setActivePanel("chat");
});

fetch("/api/health")
  .then((response) => response.json())
  .then((health) => {
    providerStatus.textContent = `${health.provider} · ${health.model}`;
    statusDot.classList.add("online");
  })
  .catch(() => {
    providerStatus.textContent = "Mất kết nối";
    statusDot.classList.add("error");
  });

fetch("/api/capabilities")
  .then((response) => {
    if (!response.ok) throw new Error("Không tải được capabilities");
    return response.json();
  })
  .then(renderCapabilities)
  .catch(() => {
    guardrailList.innerHTML = '<p class="capability-loading">Không tải được guardrail.</p>';
    toolList.innerHTML = '<p class="capability-loading">Không tải được danh sách tool.</p>';
  });
