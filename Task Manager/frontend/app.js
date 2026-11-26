const API_BASE = (window.TASK_MANAGER_API || "").replace(/\/+$/, "");
const KEY_STORAGE = "task-manager-access-key";
const accessForm = document.querySelector("#accessForm");
const taskForm = document.querySelector("#taskForm");
const keyInput = document.querySelector("#accessKey");
const titleInput = document.querySelector("#taskTitle");
const taskList = document.querySelector("#taskList");
const message = document.querySelector("#message");
const count = document.querySelector("#taskCount");
const logoutButton = document.querySelector("#logout");
let accessKey = localStorage.getItem(KEY_STORAGE) || "";

function showMessage(text) {
  message.textContent = text;
}

async function request(path, options = {}) {
  return fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Access-Key": accessKey,
      ...options.headers,
    },
  });
}

function showSignedIn(signedIn) {
  accessForm.hidden = signedIn;
  taskForm.hidden = !signedIn;
  logoutButton.hidden = !signedIn;
}

function renderTasks(tasks) {
  taskList.replaceChildren();
  count.textContent = tasks.length;
  if (!tasks.length) {
    showMessage("Hozircha vazifa yo‘q. Birinchi vazifangizni qo‘shing.");
    return;
  }
  showMessage("");

  for (const task of tasks) {
    const item = document.createElement("li");
    item.className = task.done ? "task done" : "task";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = task.done;
    checkbox.setAttribute("aria-label", "Bajarilgan deb belgilash");
    checkbox.addEventListener("change", () => updateTask(task.id, checkbox.checked));

    const title = document.createElement("span");
    title.className = "task-title";
    title.textContent = task.title;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "delete";
    remove.textContent = "×";
    remove.setAttribute("aria-label", "Vazifani o‘chirish");
    remove.addEventListener("click", () => deleteTask(task.id));
    item.append(checkbox, title, remove);
    taskList.append(item);
  }
}

async function loadTasks() {
  try {
    const response = await request("/api/tasks");
    if (response.status === 401) {
      localStorage.removeItem(KEY_STORAGE);
      accessKey = "";
      showSignedIn(false);
      showMessage("Kirish kaliti noto‘g‘ri. Render’da sozlangan kalitni kiriting.");
      return;
    }
    if (!response.ok) throw new Error("Vazifalarni olib bo‘lmadi.");
    showSignedIn(true);
    renderTasks(await response.json());
  } catch (error) {
    showMessage(`${error.message} Backend manzili va server holatini tekshiring.`);
  }
}

accessForm.addEventListener("submit", async event => {
  event.preventDefault();
  accessKey = keyInput.value.trim();
  localStorage.setItem(KEY_STORAGE, accessKey);
  await loadTasks();
});

taskForm.addEventListener("submit", async event => {
  event.preventDefault();
  const title = titleInput.value.trim();
  if (!title) return;
  const response = await request("/api/tasks", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    showMessage("Vazifani qo‘shib bo‘lmadi.");
    return;
  }
  titleInput.value = "";
  await loadTasks();
});

async function updateTask(id, done) {
  const response = await request(`/api/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ done }),
  });
  if (!response.ok) {
    showMessage("Vazifa holatini yangilab bo‘lmadi.");
    return;
  }
  await loadTasks();
}

async function deleteTask(id) {
  const response = await request(`/api/tasks/${id}`, { method: "DELETE" });
  if (!response.ok) {
    showMessage("Vazifani o‘chirib bo‘lmadi.");
    return;
  }
  await loadTasks();
}

logoutButton.addEventListener("click", () => {
  localStorage.removeItem(KEY_STORAGE);
  accessKey = "";
  keyInput.value = "";
  taskList.replaceChildren();
  count.textContent = "0";
  showSignedIn(false);
  showMessage("Kirish kalitini kiriting.");
});

if (accessKey) {
  keyInput.value = accessKey;
  loadTasks();
}
