const state = {
  generations: [],
  search: "",
  pollTimer: null,
  renameId: null,
  ready: false,
};

const $ = (selector, root = document) => root.querySelector(selector);
const list = $("#generation-list");
const emptyState = $("#empty-state");
const form = $("#generation-form");
const promptInput = $("#prompt");
const durationInput = $("#duration");

const promptIdeas = [
  "A widescreen 1960s science-fiction orchestral score, eerie strings, bold brass swells, theremin-like electronics, slow and ominous, instrumental",
  "1980s action movie chase score, pulsing analog synth bass, gated drums, distorted electric guitar, urgent and heroic, instrumental",
  "Nocturnal darkwave, icy drum machine, chorus-soaked bass guitar, haunted analog pads, hypnotic 105 BPM, instrumental",
  "Dusty spiritual jazz at midnight, modal upright bass, brushed drums, warm tenor saxophone, shimmering vibraphone, spacious tape sound, instrumental",
  "Minimalist chamber ensemble slowly building, interlocking marimba and piano patterns, low strings, tense but luminous, cinematic instrumental",
  "Retro-futurist documentary score, modular synthesizer sequences, gentle woodwinds, tape loops, curious and optimistic, instrumental",
];

async function api(path, options = {}) {
  const headers = { ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers };
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      message = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch (_) {}
    throw new Error(message);
  }
  return response.status === 204 ? null : response.json();
}

async function loadSystem() {
  const pill = $("#system-pill");
  try {
    const system = await api("/api/system");
    state.ready = system.ready;
    pill.className = `system-pill ${system.ready ? "ready" : "error"}`;
    $("#system-label").textContent = system.ready
      ? `Medium ready · ${formatBytes(system.free_disk_bytes)} free`
      : system.runtime_installed
        ? "Model weights missing · run setup"
        : "Runtime missing · run setup";
    pill.title = `Data: ${system.data_directory}`;
  } catch (error) {
    pill.classList.add("error");
    $("#system-label").textContent = "Local service unavailable";
  }
}

async function loadGenerations({ quiet = false } = {}) {
  try {
    state.generations = await api("/api/generations?limit=200");
    renderGenerations();
    schedulePolling();
  } catch (error) {
    if (!quiet) toast(error.message, true);
  }
}

function renderGenerations() {
  const filtered = state.generations.filter((generation) => {
    const haystack = `${generation.name} ${generation.prompt}`.toLowerCase();
    return haystack.includes(state.search.toLowerCase());
  });
  emptyState.hidden = filtered.length > 0;

  const wantedIds = new Set(filtered.map((item) => item.id));
  [...list.children].forEach((card) => {
    if (!wantedIds.has(card.dataset.id)) card.remove();
  });

  filtered.forEach((generation, index) => {
    const version = [
      generation.status,
      generation.name,
      Math.floor(generation.progress || 0),
      generation.stage,
      generation.error,
      generation.file_size,
    ].join("|");
    let card = list.querySelector(`[data-id="${generation.id}"]`);
    if (!card || card.dataset.version !== version) {
      const fresh = generationCard(generation);
      if (card) card.replaceWith(fresh);
      card = fresh;
    }
    const atIndex = list.children[index];
    if (atIndex !== card) list.insertBefore(card, atIndex || null);
  });
}

function generationCard(generation) {
  const card = document.createElement("article");
  card.className = "generation-card";
  card.dataset.id = generation.id;
  card.dataset.version = [
    generation.status,
    generation.name,
    Math.floor(generation.progress || 0),
    generation.stage,
    generation.error,
    generation.file_size,
  ].join("|");

  const cover = document.createElement("div");
  cover.className = "cover";
  cover.innerHTML = '<span class="wave"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></span>';

  const main = document.createElement("div");
  main.className = "generation-main";
  const titleRow = document.createElement("div");
  titleRow.className = "title-row";
  const title = document.createElement("h3");
  title.className = "generation-title";
  title.textContent = generation.name;
  title.title = generation.prompt;
  const badge = document.createElement("span");
  badge.className = `status-badge ${generation.status}`;
  badge.textContent = generation.status;
  titleRow.append(title, badge);

  const meta = document.createElement("p");
  meta.className = "generation-meta";
  const bits = [formatDuration(generation.duration_seconds), `seed ${generation.seed}`, `${generation.steps} steps`];
  if (generation.elapsed_seconds) bits.push(`${formatDuration(generation.elapsed_seconds)} render`);
  if (generation.file_size) bits.push(formatBytes(generation.file_size));
  bits.push(formatDate(generation.created_at));
  meta.textContent = bits.join("  ·  ");
  main.append(titleRow, meta);

  if (generation.status === "completed") {
    const audioRow = document.createElement("div");
    audioRow.className = "audio-row";
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.preload = "metadata";
    audio.src = `/api/generations/${generation.id}/audio`;
    audioRow.append(audio);
    main.append(audioRow);
  } else if (["queued", "running"].includes(generation.status)) {
    const progress = document.createElement("div");
    progress.className = "progress-wrap";
    const queueLabel = generation.status === "queued" ? queuedLabel(generation) : generation.stage;
    progress.innerHTML = `
      <div class="progress-label"><span></span><b>${Math.round(generation.progress || 0)}%</b></div>
      <div class="progress-track"><div class="progress-fill" style="width:${generation.progress || 0}%"></div></div>`;
    progress.querySelector("span").textContent = queueLabel;
    main.append(progress);
  }

  if (generation.error) {
    const error = document.createElement("p");
    error.className = "generation-error";
    error.textContent = generation.error;
    main.append(error);
  }

  const actions = document.createElement("div");
  actions.className = "card-actions";
  addAction(actions, "Prompt", "reuse", generation.id, "Load these settings into the composer");
  if (generation.status === "completed") {
    addLink(actions, "Download", `/api/generations/${generation.id}/download`);
    addAction(actions, "Finder", "reveal", generation.id, "Reveal WAV in Finder");
  }
  if (["queued", "running"].includes(generation.status)) {
    addAction(actions, "Cancel", "cancel", generation.id);
  } else {
    addAction(actions, "Retry", "retry", generation.id, "Generate again with the same seed");
  }
  addAction(actions, "Rename", "rename", generation.id);
  addAction(actions, "Log", "log", generation.id);
  if (generation.status !== "running") addAction(actions, "Delete", "delete", generation.id, "", "danger");

  card.append(cover, main, actions);
  return card;
}

function addAction(root, label, action, id, title = "", className = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.dataset.action = action;
  button.dataset.id = id;
  button.textContent = label;
  button.title = title;
  button.className = className;
  root.append(button);
}

function addLink(root, label, href) {
  const link = document.createElement("a");
  link.href = href;
  link.textContent = label;
  link.setAttribute("download", "");
  root.append(link);
}

function queuedLabel(generation) {
  const queued = state.generations
    .filter((item) => item.status === "queued")
    .sort((a, b) => a.created_at.localeCompare(b.created_at));
  const position = queued.findIndex((item) => item.id === generation.id) + 1;
  return position > 1 ? `Queued · ${position - 1} ahead` : "Queued · next up";
}

function schedulePolling() {
  clearTimeout(state.pollTimer);
  const hasActive = state.generations.some((item) => ["queued", "running"].includes(item.status));
  if (hasActive) state.pollTimer = setTimeout(() => loadGenerations({ quiet: true }), 800);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.ready) {
    toast("Stable Audio 3 is not ready yet. Run ./scripts/setup.sh in Terminal first.", true);
    return;
  }
  const button = $("#generate-button");
  button.disabled = true;
  button.querySelector("span").textContent = "Adding to queue…";
  try {
    const seedValue = $("#seed").value.trim();
    const generation = await api("/api/generations", {
      method: "POST",
      body: JSON.stringify({
        prompt: promptInput.value,
        negative_prompt: $("#negative-prompt").value,
        duration_seconds: Number(durationInput.value),
        seed: seedValue ? Number(seedValue) : null,
        steps: Number($("#steps").value),
        cfg_scale: Number($("#guidance").value),
      }),
    });
    state.generations.unshift(generation);
    renderGenerations();
    schedulePolling();
    toast("Generation queued on this Mac.");
    $("#library-title").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
    button.querySelector("span").textContent = "Generate music";
  }
});

list.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const generation = state.generations.find((item) => item.id === button.dataset.id);
  if (!generation) return;
  const action = button.dataset.action;
  button.disabled = true;
  try {
    if (action === "reuse") {
      promptInput.value = generation.prompt;
      $("#negative-prompt").value = generation.negative_prompt;
      durationInput.value = generation.duration_seconds;
      $("#seed").value = generation.seed;
      $("#steps").value = generation.steps;
      $("#guidance").value = generation.cfg_scale;
      updateControls();
      form.scrollIntoView({ behavior: "smooth", block: "center" });
      promptInput.focus();
    } else if (action === "reveal") {
      await api(`/api/generations/${generation.id}/reveal`, { method: "POST" });
    } else if (action === "cancel") {
      await api(`/api/generations/${generation.id}/cancel`, { method: "POST" });
      await loadGenerations();
    } else if (action === "retry") {
      const created = await api(`/api/generations/${generation.id}/retry`, { method: "POST" });
      state.generations.unshift(created);
      renderGenerations();
      schedulePolling();
      toast("Retry queued with the same seed.");
    } else if (action === "rename") {
      state.renameId = generation.id;
      $("#rename-input").value = generation.name;
      $("#rename-dialog").showModal();
      $("#rename-input").select();
    } else if (action === "log") {
      const data = await api(`/api/generations/${generation.id}/log`);
      $("#log-output").textContent = data.log;
      $("#log-dialog").showModal();
    } else if (action === "delete") {
      if (!confirm(`Delete “${generation.name}” and its WAV file? This cannot be undone.`)) return;
      await api(`/api/generations/${generation.id}`, { method: "DELETE" });
      state.generations = state.generations.filter((item) => item.id !== generation.id);
      renderGenerations();
      toast("Generation deleted.");
    }
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
});

$("#rename-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api(`/api/generations/${state.renameId}`, {
      method: "PATCH",
      body: JSON.stringify({ name: $("#rename-input").value }),
    });
    $("#rename-dialog").close();
    await loadGenerations();
  } catch (error) {
    toast(error.message, true);
  }
});

document.addEventListener("click", (event) => {
  const close = event.target.closest("[data-close-dialog]");
  if (close) close.closest("dialog").close();
});

promptInput.addEventListener("input", updateControls);
durationInput.addEventListener("input", updateControls);
$("#guidance").addEventListener("input", updateControls);
$("#steps").addEventListener("input", updateControls);
$("#search").addEventListener("input", (event) => {
  state.search = event.target.value;
  renderGenerations();
});
$("#refresh-button").addEventListener("click", () => loadGenerations());
$("#surprise-button").addEventListener("click", () => {
  promptInput.value = promptIdeas[Math.floor(Math.random() * promptIdeas.length)];
  updateControls();
  promptInput.focus();
});
$("#random-seed").addEventListener("click", () => {
  $("#seed").value = Math.floor(Math.random() * 4294967296);
});
document.querySelectorAll("[data-duration]").forEach((button) => {
  button.addEventListener("click", () => {
    durationInput.value = button.dataset.duration;
    updateControls();
  });
});

function updateControls() {
  $("#char-count").textContent = promptInput.value.length;
  $("#duration-output").textContent = formatDuration(Number(durationInput.value));
  $("#guidance-output").textContent = Number($("#guidance").value).toFixed(1);
  $("#steps-output").textContent = $("#steps").value;
  document.querySelectorAll("[data-duration]").forEach((button) => {
    button.classList.toggle("active", button.dataset.duration === durationInput.value);
  });
}

function formatDuration(seconds) {
  const value = Math.max(0, Math.round(seconds));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, "0")}`;
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index > 2 ? 1 : 0)} ${units[index]}`;
}

function formatDate(value) {
  const date = new Date(value);
  const now = new Date();
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function toast(message, error = false) {
  const element = document.createElement("div");
  element.className = `toast ${error ? "error" : ""}`;
  element.textContent = message;
  $("#toast-region").append(element);
  setTimeout(() => element.remove(), 4500);
}

updateControls();
Promise.all([loadSystem(), loadGenerations()]);
