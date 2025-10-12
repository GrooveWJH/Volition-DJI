import { currentTime } from "./utils.js";
import { createMethodBoard } from "./methodBoard.js";
import { ensureTopicBody, bindTopicHandle } from "./topicDrag.js";

const topicState = new Map();
let rcBodyEl = null;
let droneBodyEl = null;

export function initTopicTable(rcBody, droneBody) {
  rcBodyEl = rcBody;
  droneBodyEl = droneBody;
}

export function resetTopicTable() {
  if (rcBodyEl) rcBodyEl.innerHTML = "";
  if (droneBodyEl) droneBodyEl.innerHTML = "";
  topicState.clear();
}

export function populateTopicTable(rcTopics, droneTopics) {
  resetTopicTable();
  createRows(rcBodyEl, rcTopics);
  createRows(droneBodyEl, droneTopics);
}

function createRows(bodyEl, topics) {
  if (!bodyEl) return;
  ensureTopicBody(bodyEl);
  topics.forEach((info) => topicState.set(info.topic, createRow(bodyEl, info)));
}

function createRow(bodyEl, { topic, direction }) {
  const row = document.createElement("tr");
  row.className = "topic-row";
  row.dataset.topic = topic;

  const topicCell = document.createElement("td");
  topicCell.className = "topic";

  const handle = document.createElement("span");
  handle.className = "topic-handle";
  handle.title = "拖动以调整顺序";
  handle.textContent = "⋮⋮";
  handle.draggable = true;

  const topicText = document.createElement("span");
  topicText.className = "topic-text";
  topicText.textContent = topic;

  const badgeEl = document.createElement("span");
  badgeEl.className = "unread-badge hidden";

  topicCell.append(handle, topicText, badgeEl);

  const directionCell = buildDirectionCell(direction);

  const timeCell = document.createElement("td");
  timeCell.className = "last-time";
  timeCell.textContent = "--:--:--";

  row.append(topicCell, directionCell, timeCell);

  const detailRow = document.createElement("tr");
  detailRow.className = "detail-row";
  detailRow.dataset.topic = topic;
  const detailCell = document.createElement("td");
  detailCell.colSpan = 3;

  const detailContainer = document.createElement("div");
  detailContainer.className = "payload-detail empty";
  detailContainer.dataset.topic = topic;

  const emptyEl = document.createElement("div");
  emptyEl.className = "method-empty";
  emptyEl.textContent = "暂无数据";

  const methodList = document.createElement("div");
  methodList.className = "method-list";

  detailContainer.append(emptyEl, methodList);
  detailCell.append(detailContainer);
  detailRow.append(detailCell);

  row.addEventListener("click", () => toggleTopic(topic));
  row.addEventListener("animationend", (event) => {
    if (event.animationName === "flash-green") row.classList.remove("flash-once");
  });

  bodyEl.append(row, detailRow);

  const state = {
    topic,
    row,
    detailRow,
    bodyEl,
    timeCell,
    badgeEl,
    expanded: false,
    unreadCount: 0,
    latestMethod: "未知",
    board: null,
  };

  bindTopicHandle(handle, state);

  state.board = createMethodBoard({
    topic,
    container: detailContainer,
    emptyEl,
    list: methodList,
    isTopicExpanded: () => state.expanded,
  });

  return state;
}

function toggleTopic(topic) {
  const state = topicState.get(topic);
  if (!state) return;
  const willExpand = !state.expanded;
  state.expanded = willExpand;
  state.row.classList.toggle("expanded", willExpand);
  state.detailRow.classList.toggle("show", willExpand);
  if (willExpand) {
    state.board.handleTopicExpanded();
    clearUnread(state);
  }
}

export function applyTopicMessage(topic, messageInfo) {
  const state = topicState.get(topic);
  if (!state) return;

  state.timeCell.textContent = currentTime();
  state.latestMethod = state.board.record(messageInfo) || state.latestMethod;
  flashRow(state.row);

  if (state.expanded) {
    state.board.handleTopicExpanded();
    clearUnread(state);
  } else {
    state.unreadCount += 1;
    updateBadge(state);
  }
}

function clearUnread(state) {
  state.unreadCount = 0;
  updateBadge(state);
}

function updateBadge(state) {
  if (!state.badgeEl) return;
  const count = formatCount(state.unreadCount);
  if (state.unreadCount > 0) {
    state.badgeEl.textContent = count;
    state.badgeEl.classList.remove("hidden");
  } else {
    state.badgeEl.textContent = "";
    state.badgeEl.classList.add("hidden");
  }
}

function flashRow(row) {
  row.classList.remove("flash-once");
  void row.offsetWidth;
  row.classList.add("flash-once");
}

function formatCount(count) {
  return count > 999 ? "999+" : count || 0;
}

function buildDirectionCell(directionKey) {
  const cell = document.createElement("td");
  cell.className = "direction-cell";

  const iconRow = document.createElement("span");
  iconRow.className = "direction-icons";

  const { icons, description } = mapDirection(directionKey);
  icons.forEach(({ name, className }) => {
    const iconSpan = document.createElement("span");
    iconSpan.className = `material-symbols-rounded direction-icon ${className || ""}`.trim();
    iconSpan.textContent = name;
    iconRow.append(iconSpan);
  });

  const srOnly = document.createElement("span");
  srOnly.className = "sr-only";
  srOnly.textContent = description;

  cell.title = description;
  cell.setAttribute("aria-label", description);
  cell.append(iconRow, srOnly);
  return cell;
}

function mapDirection(directionKey) {
  switch (directionKey) {
    case "cloud-to-device":
      return {
        icons: [
          { name: "cloud", className: "direction-node direction-node-cloud" },
          { name: "arrow_forward", className: "direction-icon-arrow" },
          { name: "devices", className: "direction-node direction-node-device" },
        ],
        description: "云平台发送到设备",
      };
    case "device-to-cloud":
      return {
        icons: [
          { name: "devices", className: "direction-node direction-node-device" },
          { name: "arrow_forward", className: "direction-icon-arrow" },
          { name: "cloud", className: "direction-node direction-node-cloud" },
        ],
        description: "设备发送到云平台",
      };
    default:
      return {
        icons: [
          { name: "sync_alt", className: "direction-node direction-node-unknown" },
        ],
        description: "未识别的消息方向",
      };
  }
}
