const registeredBodies = new WeakSet();
let topicDragContext = null;

export function ensureTopicBody(bodyEl) {
  if (registeredBodies.has(bodyEl)) return;
  registeredBodies.add(bodyEl);
  bodyEl.addEventListener("dragover", onTopicDragOver);
  bodyEl.addEventListener("drop", onTopicDrop);
}

export function bindTopicHandle(handle, state) {
  handle.addEventListener("click", (event) => event.stopPropagation());
  handle.addEventListener("mousedown", (event) => event.stopPropagation());
  handle.addEventListener("dragstart", (event) => startTopicDrag(event, state));
  handle.addEventListener("dragend", () => finishTopicDrag(state));
}

function startTopicDrag(event, state) {
  state.row.classList.add("topic-row-dragging");
  state.detailRow.classList.add("topic-row-dragging");
  state.bodyEl.classList.add("topic-drop-active");
  topicDragContext = {
    state,
    dragImage: createDragImage(state.row),
  };
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", state.topic);
  const { dragImage } = topicDragContext;
  if (dragImage) {
    const rect = state.row.getBoundingClientRect();
    const offsetX = event.clientX - rect.left;
    const offsetY = event.clientY - rect.top;
    event.dataTransfer.setDragImage(dragImage, offsetX, offsetY);
  }
}

function finishTopicDrag(state) {
  const context = topicDragContext;
  if (!state) state = context?.state;
  if (!state) return;
  state.row.classList.remove("topic-row-dragging");
  state.detailRow.classList.remove("topic-row-dragging");
  state.bodyEl.classList.remove("topic-drop-active");
  if (context?.dragImage) {
    document.body.removeChild(context.dragImage);
  }
  topicDragContext = null;
}

function onTopicDragOver(event) {
  if (!topicDragContext) return;
  const { state } = topicDragContext;
  if (event.currentTarget !== state.bodyEl) return;
  event.preventDefault();
}

function onTopicDrop(event) {
  if (!topicDragContext) return;
  const { state } = topicDragContext;
  if (event.currentTarget !== state.bodyEl) return;
  event.preventDefault();

  const afterRow = getTopicAfterRow(state.bodyEl, event.clientY, state.row);
  if (!afterRow) {
    state.bodyEl.append(state.row, state.detailRow);
  } else {
    state.bodyEl.insertBefore(state.row, afterRow);
    state.bodyEl.insertBefore(state.detailRow, afterRow);
  }

  finishTopicDrag(state);
}

function getTopicAfterRow(bodyEl, y, draggedRow) {
  const rows = [...bodyEl.querySelectorAll("tr.topic-row")].filter((row) => row !== draggedRow);
  let closest = { offset: Number.NEGATIVE_INFINITY, element: null };
  rows.forEach((row) => {
    const box = row.getBoundingClientRect();
    const offset = y - box.top - box.height / 2;
    if (offset < 0 && offset > closest.offset) {
      closest = { offset, element: row };
    }
  });
  return closest.element;
}

function createDragImage(row) {
  const clone = row.cloneNode(true);
  clone.classList.add("topic-drag-image");
  clone.style.width = `${row.offsetWidth}px`;
  clone.style.position = "absolute";
  clone.style.top = "-9999px";
  clone.style.left = "-9999px";
  document.body.appendChild(clone);
  return clone;
}
