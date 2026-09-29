const RATES = [
  { value: 88200, label: "88,2 кГц" },
  { value: 176400, label: "176,4 кГц" },
  { value: 352800, label: "352,8 кГц" },
];
const BITS = [
  { value: 24, label: "24 бит" },
  { value: 16, label: "16 бит" },
];
const LOWPASS = [
  { value: 30000, label: "30 кГц" },
  { value: 40000, label: "40 кГц" },
  { value: 50000, label: "50 кГц" },
  { value: 0, label: "Выкл" },
];
const STATUS = {
  pending: "Ждёт",
  extracting: "Извлечение",
  encoding: "Запись",
  done: "Готово",
  error: "Ошибка",
};

const state = {
  disc: null,
  mode: "stereo",
  selected: new Set(),
  rate: 176400,
  bits: 24,
  lowpass: 40000,
  jobId: null,
  source: null,
  busy: false,
};

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  restoreSettings();
  renderChoices();
  $("compression").addEventListener("input", () => {
    $("compression-label").textContent = $("compression").value;
    saveSettings();
    refreshEstimate();
  });
  $("pick-file").addEventListener("click", () => pick("iso"));
  $("pick-folder").addEventListener("click", () => pick("folder"));
  $("read-disc").addEventListener("click", readDisc);
  $("iso-path").addEventListener("keydown", (event) => {
    if (event.key === "Enter") readDisc();
  });
  $("out-path").addEventListener("input", () => {
    refreshPreview();
    refreshConvert();
  });
  $("convert").addEventListener("click", startConvert);
  $("cancel").addEventListener("click", cancelJob);
  $("reveal").addEventListener("click", revealFolder);
  $("select-all").addEventListener("change", toggleAll);
  loadHealth();
});

async function api(path, body) {
  const options = body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "Запрос не прошёл");
  return data;
}

async function loadHealth() {
  try {
    renderHealth(await api("/api/health"));
  } catch (error) {
    $("health").textContent = "Не удалось спросить инструменты";
    $("health").className = "health bad";
  }
}

function renderHealth(data) {
  const node = $("health");
  if (data.ffmpeg.ok && data.sacd_extract.ok) {
    node.textContent = data.soxr
      ? "ffmpeg с SoX и sacd_extract на месте"
      : "ffmpeg и sacd_extract на месте";
    node.className = "health ok";
    return;
  }
  const missing = [];
  if (!data.ffmpeg.ok) missing.push("ffmpeg");
  if (!data.sacd_extract.ok) missing.push("sacd_extract");
  node.textContent = `Нет ${missing.join(" и ")}. ${data.hint}`;
  node.className = "health bad";
}

function renderChoices() {
  fillSegment($("rate"), RATES, state.rate, (value) => {
    state.rate = value;
    if (state.lowpass && state.lowpass >= state.rate / 2) state.lowpass = 40000;
    renderChoices();
    saveSettings();
    refreshEstimate();
  });
  fillSegment($("bits"), BITS, state.bits, (value) => {
    state.bits = value;
    saveSettings();
    refreshEstimate();
  });
  fillSegment($("lowpass"), LOWPASS, state.lowpass, (value) => {
    state.lowpass = value;
    saveSettings();
  }, (item) => item.value !== 0 && item.value >= state.rate / 2);
}

function fillSegment(node, items, current, onPick, disabled) {
  node.replaceChildren();
  for (const item of items) {
    const blocked = disabled ? disabled(item) : false;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = item.label;
    button.setAttribute("aria-pressed", String(item.value === current));
    button.disabled = blocked;
    button.addEventListener("click", () => onPick(item.value));
    node.append(button);
  }
}

async function pick(kind) {
  try {
    const data = await api("/api/dialog", { kind });
    if (data.cancelled) return;
    if (data.unavailable) {
      notice(data.message);
      return;
    }
    if (kind === "iso") {
      $("iso-path").value = data.path;
      await readDisc();
    } else {
      $("out-path").value = data.path;
      refreshPreview();
      refreshConvert();
    }
  } catch (error) {
    notice(error.message);
  }
}

async function readDisc() {
  notice("");
  const path = $("iso-path").value.trim();
  if (!path) {
    notice("Вставьте путь к SACD ISO или DSF.");
    return;
  }
  $("read-disc").disabled = true;
  try {
    state.disc = await api("/api/probe", { path });
    const stereo = state.disc.areas.find((area) => area.mode === "stereo");
    state.mode = (stereo || state.disc.areas[0]).mode;
    selectAllCurrent();
    if (!$("out-path").value.trim() && state.disc.suggested_output) {
      $("out-path").value = state.disc.suggested_output;
    }
    renderDisc();
    renderTracks();
    refreshPreview();
    refreshEstimate();
    refreshConvert();
  } catch (error) {
    state.disc = null;
    renderDisc();
    renderTracks();
    notice(error.message);
  } finally {
    $("read-disc").disabled = state.busy;
  }
}

function renderDisc() {
  const node = $("disc");
  const areas = $("areas");
  node.classList.toggle("empty", !state.disc);
  if (!state.disc) {
    node.replaceChildren();
    node.append(line("p", "disc-kicker", "Оглавление"));
    node.append(line("p", "disc-title", "Диск ещё не прочитан"));
    node.append(line("p", "disc-copy", "Кедр снимет DST с образа, отфильтрует ультразвуковой шум DSD и запишет 24-битный FLAC."));
    areas.hidden = true;
    return;
  }
  const disc = state.disc;
  node.replaceChildren();
  node.append(line("p", "disc-kicker", disc.kind === "iso" ? "SACD ISO" : "DSF"));
  node.append(line("p", "disc-title", disc.title || "Без названия"));
  node.append(line("p", "disc-copy", disc.artist || "Исполнитель не указан"));
  const meta = [disc.date, disc.catalog, disc.genre].filter(Boolean).join(" · ");
  if (meta) node.append(line("p", "disc-meta", meta));

  areas.replaceChildren();
  areas.hidden = disc.areas.length < 2;
  for (const area of disc.areas) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `${area.label} · ${area.tracks.length}`;
    button.setAttribute("aria-pressed", String(area.mode === state.mode));
    button.addEventListener("click", () => {
      state.mode = area.mode;
      selectAllCurrent();
      renderDisc();
      renderTracks();
      refreshPreview();
      refreshEstimate();
    });
    areas.append(button);
  }
}

function renderTracks(job) {
  const list = $("track-list");
  const area = currentArea();
  const meta = $("tracks-meta");
  const wrap = $("select-all-wrap");
  list.replaceChildren();
  if (!area) {
    meta.textContent = "Появятся после чтения диска.";
    wrap.hidden = true;
    return;
  }
  const total = area.tracks.reduce((sum, track) => sum + track.duration_seconds, 0);
  meta.textContent = `${area.label} · ${area.tracks.length} дор. · ${formatDuration(total)}`;
  wrap.hidden = area.tracks.length < 2 || state.disc.kind !== "iso";
  const byNumber = new Map((job?.tracks || []).map((track) => [track.number, track]));
  for (const track of area.tracks) {
    const live = byNumber.get(track.number);
    const row = document.createElement("li");
    row.className = "track";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = state.selected.has(track.number);
    box.disabled = state.busy || state.disc.kind !== "iso";
    box.addEventListener("change", () => {
      if (box.checked) state.selected.add(track.number);
      else state.selected.delete(track.number);
      syncSelectAll();
      refreshEstimate();
      refreshConvert();
    });
    const number = document.createElement("b");
    number.textContent = String(track.number).padStart(2, "0");
    const title = document.createElement("span");
    title.className = "title";
    title.textContent = track.title || "Без названия";
    const time = document.createElement("span");
    time.className = "time";
    time.textContent = formatDuration(track.duration_seconds);
    const status = document.createElement("span");
    status.className = `state ${live?.status || ""}`;
    status.textContent = live ? STATUS[live.status] || live.status : "";
    row.append(box, number, title, time, status);
    list.append(row);
  }
  syncSelectAll();
}

function renderJob(job) {
  const progress = $("progress");
  const message = $("job-message");
  const done = $("done");
  state.busy = job.status === "running";
  progress.hidden = job.status !== "running";
  $("progress-bar").style.width = `${Math.max(0, Math.min(100, job.percent))}%`;
  message.hidden = !job.message;
  message.textContent = job.message || "";
  $("cancel").hidden = job.status !== "running";
  $("convert").disabled = state.busy || !canConvert();
  $("read-disc").disabled = state.busy;
  renderTracks(job);
  if (job.status === "done") {
    done.hidden = false;
    $("done-text").textContent = `Готово, ${filesLabel(job.files.length)}. ${job.output_dir}`;
    done.dataset.path = job.output_dir;
    notice("");
  } else if (job.status === "error") {
    done.hidden = true;
    notice(job.error || job.message);
  } else if (job.status === "cancelled") {
    done.hidden = true;
    notice("Остановлено. Уже записанные FLAC остались в папке.", "ok");
  } else {
    done.hidden = true;
  }
}

async function startConvert() {
  if (!canConvert()) return;
  notice("");
  $("done").hidden = true;
  state.busy = true;
  refreshConvert();
  const area = currentArea();
  const tracks = state.disc.kind === "iso" ? [...state.selected] : [];
  try {
    const job = await api("/api/convert", {
      path: $("iso-path").value.trim(),
      output_dir: $("out-path").value.trim(),
      mode: area.mode,
      tracks,
      rate: state.rate,
      bits: state.bits,
      lowpass: state.lowpass,
      compression: Number($("compression").value),
    });
    state.jobId = job.id;
    watch(job.id);
    renderJob(job);
  } catch (error) {
    state.busy = false;
    refreshConvert();
    notice(error.message);
  }
}

function watch(id) {
  if (state.source) state.source.close();
  const source = new EventSource(`/api/jobs/${id}/events`);
  state.source = source;
  source.onmessage = (event) => {
    const job = JSON.parse(event.data);
    renderJob(job);
    if (job.status !== "running") {
      source.close();
      state.busy = false;
      refreshConvert();
    }
  };
  source.onerror = () => {
    source.close();
    poll(id);
  };
}

async function poll(id) {
  try {
    const job = await api(`/api/jobs/${id}`);
    renderJob(job);
    if (job.status === "running") setTimeout(() => poll(id), 700);
  } catch (error) {
    notice(error.message);
    state.busy = false;
    refreshConvert();
  }
}

async function cancelJob() {
  if (!state.jobId) return;
  try {
    const job = await api(`/api/jobs/${state.jobId}/cancel`, {});
    renderJob(job);
  } catch (error) {
    notice(error.message);
  }
}

async function revealFolder() {
  const path = $("done").dataset.path;
  if (!path) return;
  try {
    await api("/api/reveal", { path });
  } catch (error) {
    notice(`${error.message} ${path}`);
  }
}

function currentArea() {
  if (!state.disc) return null;
  return state.disc.areas.find((area) => area.mode === state.mode) || state.disc.areas[0];
}

function selectAllCurrent() {
  const area = currentArea();
  state.selected = new Set(area ? area.tracks.map((track) => track.number) : []);
}

function toggleAll() {
  if ($("select-all").checked) selectAllCurrent();
  else state.selected.clear();
  renderTracks();
  refreshEstimate();
  refreshConvert();
}

function syncSelectAll() {
  const area = currentArea();
  if (!area) return;
  $("select-all").checked = area.tracks.every((track) => state.selected.has(track.number));
}

function canConvert() {
  return Boolean(state.disc && $("out-path").value.trim() && state.selected.size && !state.busy);
}

function refreshConvert() {
  $("convert").disabled = !canConvert();
}

function refreshPreview() {
  const area = currentArea();
  const output = $("out-path").value.trim().replace(/\/$/, "");
  $("preview").textContent = area && output ? `${output}/${area.dirname}` : "";
}

function refreshEstimate() {
  const area = currentArea();
  if (!area) {
    $("estimate").textContent = "";
    return;
  }
  const chosen = area.tracks.filter((track) => state.selected.has(track.number));
  const seconds = chosen.reduce((sum, track) => sum + track.duration_seconds, 0);
  const channels = area.channels || 2;
  const bytes = seconds * state.rate * (state.bits / 8) * channels * 0.62;
  $("estimate").textContent = seconds
    ? `Около ${formatBytes(bytes)} на ${chosen.length} дор. Оценка до сжатия FLAC, с запасом.`
    : "";
}

function filesLabel(count) {
  const mod100 = Math.abs(count) % 100;
  const mod10 = mod100 % 10;
  if (mod100 > 10 && mod100 < 20) return `${count} файлов`;
  if (mod10 === 1) return `${count} файл`;
  if (mod10 >= 2 && mod10 <= 4) return `${count} файла`;
  return `${count} файлов`;
}

function formatDuration(seconds) {
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours) return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

function formatBytes(size) {
  if (size < 1024 ** 2) return `${Math.round(size / 1024)} КБ`;
  if (size < 1024 ** 3) return `${Math.round(size / 1024 ** 2)} МБ`;
  return `${(size / 1024 ** 3).toFixed(1).replace(".", ",")} ГБ`;
}

function notice(text, kind) {
  const node = $("notice");
  node.hidden = !text;
  node.textContent = text || "";
  node.className = kind === "ok" ? "notice ok" : "notice";
}

function line(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

function restoreSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem("kedr-settings") || "{}");
    if (RATES.some((item) => item.value === saved.rate)) state.rate = saved.rate;
    if (BITS.some((item) => item.value === saved.bits)) state.bits = saved.bits;
    if (LOWPASS.some((item) => item.value === saved.lowpass)) state.lowpass = saved.lowpass;
    if (Number.isInteger(saved.compression)) {
      $("compression").value = String(saved.compression);
      $("compression-label").textContent = String(saved.compression);
    }
  } catch (_error) {
    /* пустые настройки */
  }
}

function saveSettings() {
  localStorage.setItem("kedr-settings", JSON.stringify({
    rate: state.rate,
    bits: state.bits,
    lowpass: state.lowpass,
    compression: Number($("compression").value),
  }));
}
