const gameList = document.getElementById("game-list");
const template = document.getElementById("game-card-template");
const addForm = document.getElementById("add-form");
const nameInput = document.getElementById("game-name");
const modeSelect = document.getElementById("game-mode");
const targetInput = document.getElementById("game-target");
const statusEl = document.getElementById("status");
const confirmOverlay = document.getElementById("confirm-overlay");
const confirmMessage = document.getElementById("confirm-message");
const confirmCancelBtn = document.getElementById("confirm-cancel");
const confirmAcceptBtn = document.getElementById("confirm-accept");
let resolveConfirm = null;

function showConfirm(message) {
  confirmMessage.textContent = message;
  confirmOverlay.hidden = false;
  confirmAcceptBtn.focus();
  return new Promise((resolve) => {
    resolveConfirm = resolve;
  });
}

function closeConfirm(result) {
  confirmOverlay.hidden = true;
  if (resolveConfirm) {
    resolveConfirm(result);
    resolveConfirm = null;
  }
}

confirmCancelBtn.addEventListener("click", () => closeConfirm(false));
confirmAcceptBtn.addEventListener("click", () => closeConfirm(true));
confirmOverlay.addEventListener("click", (event) => {
  if (event.target === confirmOverlay) closeConfirm(false);
});
document.addEventListener("keydown", (event) => {
  if (!confirmOverlay.hidden && event.key === "Escape") closeConfirm(false);
});

let socket;
let reconnectDelay = 1000;
let isReordering = false;
let draggingCard = null;
let previousWinsById = new Map();

function connect() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${window.location.host}/ws`);

  socket.addEventListener("open", () => {
    reconnectDelay = 1000;
    setStatus("Verbunden", false);
  });

  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "state") {
      renderGames(payload.games);
    }
  });

  socket.addEventListener("close", () => {
    setStatus("Verbindung verloren – verbinde erneut …", true);
    setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 1.5, 10000);
  });

  socket.addEventListener("error", () => {
    socket.close();
  });
}

function setStatus(text, isWarning) {
  statusEl.textContent = text;
  statusEl.classList.toggle("status--warning", Boolean(isWarning));
}

function send(action) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(action));
  }
}

function renderGames(games) {
  if (isReordering) return;
  const resetIds = games
    .filter((game) => game.mode === "streak" && game.current_wins === 0 && previousWinsById.get(game.id) > 0)
    .map((game) => game.id);

  gameList.innerHTML = "";
  for (const game of games) {
    gameList.appendChild(buildCard(game));
  }

  for (const id of resetIds) {
    const card = gameList.querySelector(`[data-id="${id}"]`);
    if (!card) continue;
    card.classList.add("card--reset-flash");
    setTimeout(() => card.classList.remove("card--reset-flash"), 600);
  }

  previousWinsById = new Map(games.map((game) => [game.id, game.current_wins]));
}

// Verhindert, dass Mausrad-Scrollen über dem Feld dessen Zahlenwert ändert
function preventWheelChange(input) {
  input.addEventListener(
    "wheel",
    (event) => {
      if (document.activeElement === input) {
        event.preventDefault();
      }
    },
    { passive: false }
  );
}

preventWheelChange(targetInput);

function buildCard(game) {
  const node = template.content.firstElementChild.cloneNode(true);
  node.dataset.id = game.id;
  node.classList.toggle("card--completed", game.completed);

  const nameEl = node.querySelector(".card__name");
  const targetEl = node.querySelector(".card__target");
  nameEl.value = game.name;
  targetEl.value = game.target_wins;
  preventWheelChange(targetEl);

  const commitUpdate = () => {
    send({ action: "update", id: game.id, name: nameEl.value, target: targetEl.value });
  };
  nameEl.addEventListener("change", commitUpdate);
  targetEl.addEventListener("change", commitUpdate);

  const progressBar = node.querySelector(".card__progress-bar");
  const percent = Math.min(100, (game.current_wins / game.target_wins) * 100);
  progressBar.style.width = `${percent}%`;

  node.querySelector(".card__count").textContent = game.current_wins;

  const badge = node.querySelector(".card__badge");
  const modeLabel = node.querySelector(".card__mode-label");
  const isStreak = game.mode === "streak";
  badge.style.display = isStreak ? "inline-block" : "none";
  badge.textContent = isStreak ? `B${game.target_wins}B` : "";
  modeLabel.textContent = isStreak ? "am Stück" : "";

  node.querySelector('[data-action="increment"]').addEventListener("click", () => {
    send({ action: "increment", id: game.id });
  });
  const decrementBtn = node.querySelector('[data-action="decrement"]');
  decrementBtn.textContent = isStreak ? "✕" : "−";
  decrementBtn.title = isStreak ? "Niederlage – Serie zurücksetzen" : "-1 Sieg";
  decrementBtn.addEventListener("click", async () => {
    if (isStreak && game.current_wins > 0 && !(await showConfirm(`Serie bei "${game.name}" zurücksetzen?`))) {
      return;
    }
    send({ action: "decrement", id: game.id });
  });
  node.querySelector('[data-action="delete"]').addEventListener("click", async () => {
    if (await showConfirm(`"${game.name}" wirklich löschen?`)) {
      send({ action: "delete", id: game.id });
    }
  });

  const dragHandle = node.querySelector(".card__drag");
  dragHandle.addEventListener("dragstart", (event) => {
    draggingCard = node;
    isReordering = true;
    node.classList.add("card--dragging");
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", String(game.id));
  });
  dragHandle.addEventListener("dragend", () => {
    node.classList.remove("card--dragging");
    draggingCard = null;
    isReordering = false;
    commitOrder();
  });

  return node;
}

// Ermittelt die Karte, vor der die gezogene Karte anhand der Mausposition eingefügt werden soll
function getDragAfterElement(container, y) {
  const cards = [...container.querySelectorAll(".card:not(.card--dragging)")];
  return cards.reduce(
    (closest, child) => {
      const box = child.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) {
        return { offset, element: child };
      }
      return closest;
    },
    { offset: Number.NEGATIVE_INFINITY, element: null }
  ).element;
}

function commitOrder() {
  const order = [...gameList.querySelectorAll(".card")].map((card) => Number(card.dataset.id));
  send({ action: "reorder", order });
}

gameList.addEventListener("dragover", (event) => {
  if (!draggingCard) return;
  event.preventDefault();
  const afterElement = getDragAfterElement(gameList, event.clientY);
  if (afterElement == null) {
    gameList.appendChild(draggingCard);
  } else {
    gameList.insertBefore(draggingCard, afterElement);
  }
});

addForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const name = nameInput.value.trim();
  const target = parseInt(targetInput.value, 10);
  const mode = modeSelect.value;
  if (!name || !target || target < 1) return;
  send({ action: "add", name, target, mode });
  nameInput.value = "";
  targetInput.value = "";
  nameInput.focus();
});

renderGames(window.__INITIAL_GAMES__ || []);
connect();
