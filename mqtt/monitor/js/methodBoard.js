import { currentTime } from "./utils.js";
let dragContext = null;
const make = (tag, cls, text) => {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  if (text !== undefined) el.textContent = text;
  return el;
};
export function createMethodBoard({ topic, container, emptyEl, list, isTopicExpanded }) {
  const state = { topic, container, emptyEl, list, isTopicExpanded, methods: new Map(), detailHeight: 220, hasDragHandlers: false };
  const record = (messageInfo) => {
    const method = (messageInfo.method || "未知方法").trim() || "未知方法";
    container.classList.remove("empty");
    emptyEl.hidden = true;
    ensureDragHandlers(state);
    let entry = state.methods.get(method);
    if (!entry) {
      entry = createEntry(state, method);
      state.methods.set(method, entry);
    }
    entry.count += 1;
    entry.payloadEl.textContent = messageInfo.formatted || "暂无数据";
    entry.countEl.textContent = `x${formatCount(entry.count)}`;
    entry.timeEl.textContent = currentTime();
    entry.snippetEl.textContent = buildSnippet(messageInfo);
    entry.summaryButton.classList.add("method-summary-updated");
    requestAnimationFrame(() => entry.summaryButton.classList.remove("method-summary-updated"));
    if (state.isTopicExpanded()) syncHeight(state);
    return method;
  };
  const handleTopicExpanded = () => {
    if (state.methods.size) syncHeight(state);
  };
  return { record, handleTopicExpanded };
}
function createEntry(state, method) {
  const section = make("div", "method-section");
  section.dataset.method = method;
  const header = make("div", "method-header");
  const dragHandle = make("span", "method-drag-handle", "⋮⋮");
  dragHandle.title = "拖动以调整顺序";
  dragHandle.draggable = true;
  dragHandle.addEventListener("mousedown", (evt) => evt.stopPropagation());
  dragHandle.addEventListener("dragstart", (evt) => startDrag(evt, state, method));
  dragHandle.addEventListener("dragend", (evt) => finishDrag(evt.currentTarget, state));
  const summaryButton = make("button", "method-summary");
  summaryButton.type = "button";
  summaryButton.dataset.method = method;
  summaryButton.setAttribute("aria-expanded", "false");
  summaryButton.addEventListener("click", (evt) => {
    evt.stopPropagation();
    toggleEntry(state, method);
  });
  const summaryMain = make("div", "method-summary-main");
  const nameEl = make("span", "method-name", method);
  const countEl = make("span", "method-count", "x1");
  const snippetEl = make("span", "method-snippet", "暂无内容");
  summaryMain.append(nameEl, countEl, snippetEl);
  const timeEl = make("span", "method-time", currentTime());
  const chevronEl = make("span", "method-chevron");
  summaryButton.append(summaryMain, timeEl, chevronEl);
  header.append(dragHandle, summaryButton);
  const detail = make("div", "method-detail");
  detail.hidden = true;
  const payloadEl = make("pre", "method-payload", "暂无数据");
  detail.append(payloadEl);
  section.append(header, detail);
  state.list.append(section);
  return { section, summaryButton, countEl, snippetEl, timeEl, detail, payloadEl, expanded: false, count: 0 };
}
function toggleEntry(state, method) {
  const entry = state.methods.get(method);
  if (!entry) return;
  entry.expanded = !entry.expanded;
  entry.section.classList.toggle("expanded", entry.expanded);
  entry.summaryButton.setAttribute("aria-expanded", String(entry.expanded));
  entry.detail.hidden = !entry.expanded;
  if (entry.expanded && state.isTopicExpanded()) syncHeight(state);
}
function ensureDragHandlers(state) {
  if (state.hasDragHandlers) return;
  state.hasDragHandlers = true;
  state.list.addEventListener("dragover", (evt) => dragOver(evt, state));
  state.list.addEventListener("drop", (evt) => drop(evt, state));
}
function startDrag(evt, state, method) {
  evt.currentTarget.classList.add("dragging");
  state.container.classList.add("drag-active");
  evt.dataTransfer.effectAllowed = "move";
  evt.dataTransfer.setData("text/plain", method);
  dragContext = { state, method };
}
function dragOver(evt, state) {
  if (!dragContext || dragContext.state !== state) return;
  evt.preventDefault();
}
function drop(evt, state) {
  if (!dragContext || dragContext.state !== state) return;
  evt.preventDefault();
  const method = dragContext.method;
  const list = state.list;
  const dragging = list.querySelector(`.method-section[data-method="${method}"]`);
  if (!dragging) {
    finishDrag(null, state);
    return;
  }
  const after = getDragAfterElement(list, evt.clientY, method);
  if (!after) list.append(dragging);
  else list.insertBefore(dragging, after);
  rebuildOrder(state);
  finishDrag(null, state);
  if (state.isTopicExpanded()) syncHeight(state);
}
function finishDrag(handle, state) {
  if (handle) handle.classList.remove("dragging");
  const ctx = dragContext;
  dragContext = null;
  const targetState = state || ctx?.state;
  if (!targetState) return;
  targetState.container.classList.remove("drag-active");
  targetState.list.querySelectorAll(".method-drag-handle.dragging").forEach((el) => el.classList.remove("dragging"));
}
function getDragAfterElement(list, y, method) {
  const sections = [...list.querySelectorAll(".method-section")].filter((sec) => sec.dataset.method !== method);
  let closest = { offset: Number.NEGATIVE_INFINITY, element: null };
  sections.forEach((sec) => {
    const box = sec.getBoundingClientRect();
    const offset = y - box.top - box.height / 2;
    if (offset < 0 && offset > closest.offset) closest = { offset, element: sec };
  });
  return closest.element;
}
function rebuildOrder(state) {
  const reordered = new Map();
  state.list.querySelectorAll(".method-section").forEach((sec) => {
    const method = sec.dataset.method;
    if (!method) return;
    const entry = state.methods.get(method);
    if (entry) reordered.set(method, entry);
  });
  state.methods = reordered;
}
function syncHeight(state) {
  requestAnimationFrame(() => {
    state.container.style.height = "auto";
    const measured = state.container.scrollHeight;
    state.detailHeight = Math.max(state.detailHeight, measured);
    state.container.style.height = `${state.detailHeight}px`;
  });
}
function buildSnippet(info) {
  if (!info) return "暂无内容";
  if (info.isJson && info.raw) {
    const data = info.raw.data ?? info.raw;
    if (typeof data === "object") return summarize(JSON.stringify(data));
  }
  return summarize(info.rawText || info.formatted);
}
function summarize(text, limit = 80) {
  if (!text) return "暂无内容";
  const single = text.replace(/\s+/g, " ").trim();
  if (!single) return "暂无内容";
  return single.length > limit ? `${single.slice(0, limit - 1)}…` : single;
}
function formatCount(count) {
  return count > 999 ? "999+" : count || 0;
}
