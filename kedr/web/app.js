const FORMATS = [
  { value: "flac", label: "FLAC" },
  { value: "mp3", label: "MP3" },
];
const FLAC_RATES = [
  { value: 88200, label: "88,2 кГц" },
  { value: 176400, label: "176,4 кГц" },
  { value: 352800, label: "352,8 кГц" },
];
const MP3_RATES = [
  { value: 44100, label: "44,1 кГц" },
  { value: 48000, label: "48 кГц" },
];
const BITS = [
  { value: 24, label: "24 бит" },
  { value: 16, label: "16 бит" },
];
const BITRATES = [
  { value: 320, label: "320" },
  { value: 256, label: "256" },
  { value: 192, label: "192" },
  { value: 128, label: "128" },
];
const LOWPASS = [
  { value: 20000, label: "20 кГц" },
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
  format: "flac",
  rate: 176400,
  bits: 24,
  bitrate: 320,
  lowpass: 40000,
  mp3Encoder: true,
  jobId: null,
  source: null,
  busy: false,
};

const $ = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
  if (window.kedr) {
    document.body.classList.add("desktop");
    if (window.kedr.platform === "darwin") document.body.classList.add("darwin");
    const eyebrow = document.querySelector(".eyebrow");
    if (eyebrow) eyebrow.textContent = "Настольное приложение";
  }
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
  state.mp3Encoder = Boolean(data.mp3);
  const node = $("health");
  renderChoices();
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
  snapRate();
  fillSegment($("format"), FORMATS, state.format, (value) => {
    state.format = value;
    snapRate();
    renderChoices();
    saveSettings();
    refreshEstimate();
    refreshConvert();
  });
  fillSegment($("rate"), state.format === "mp3" ? MP3_RATES : FLAC_RATES, state.rate, (value) => {
    state.rate = value;
    snapLowpass();
    renderChoices();
    saveSettings();
    refreshEstimate();
  });
  fillSegment($("bits"), BITS, state.bits, (value) => {
    state.bits = value;
    saveSettings();
    refreshEstimate();
  });
  fillSegment($("bitrate"), BITRATES, state.bitrate, (value) => {
    state.bitrate = value;
    saveSettings();
    refreshEstimate();
  });
  fillSegment($("lowpass"), LOWPASS, state.lowpass, (value) => {
    state.lowpass = value;
    saveSettings();
  }, (item) => item.value !== 0 && item.value >= state.rate / 2);
  const mp3 = state.format === "mp3";
  $("bits-block").hidden = mp3;
  $("compression-block").hidden = mp3;
  $("bitrate-block").hidden = !mp3;
  $("pcm-title").textContent = mp3 ? "MP3" : "FLAC";
  $("pcm-lead").textContent = mp3
    ? "LAME, не выше 48 кГц."
    : "176,4 кГц и срез 40 кГц для DSD64.";
  const blocked = mp3Blocked();
  const hint = blocked
    ? "MP3 не вмещает 5.1. Выберите FLAC или стереозону."
    : (mp3 && !state.mp3Encoder ? "В ffmpeg нет LAME, MP3 записать не получится." : "");
  $("format-hint").textContent = hint;
  $("format-hint").hidden = !hint;
  refreshConvert();
}

function snapRate() {
  const allowed = state.format === "mp3" ? MP3_RATES : FLAC_RATES;
  if (!allowed.some((item) => item.value === state.rate)) {
    state.rate = state.format === "mp3" ? 44100 : 176400;
  }
  snapLowpass();
}

function snapLowpass() {
  if (!state.lowpass || state.lowpass < state.rate / 2) return;
  const fallback = state.format === "mp3" ? 20000 : 40000;
  state.lowpass = fallback < state.rate / 2 ? fallback : 0;
}

function mp3Blocked() {
  const area = currentArea();
  return state.format === "mp3" && Boolean(area && area.channels > 2);
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
    const data = window.kedr
      ? await window.kedr.pick(kind)
      : await api("/api/dialog", { kind });
    if (!data || data.cancelled) return;
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
    node.append(line("p", "disc-copy", "Выберите образ или уже извлечённый DSF."));
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
      renderChoices();
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
    notice("Остановлено. Уже записанные файлы остались в папке.", "ok");
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
      format: state.format,
      rate: state.rate,
      bits: state.bits,
      bitrate: state.bitrate,
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
    if (window.kedr) {
      await window.kedr.reveal(path);
      return;
    }
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
  if (!state.disc || !$("out-path").value.trim() || !state.selected.size || state.busy) return false;
  if (mp3Blocked()) return false;
  if (state.format === "mp3" && !state.mp3Encoder) return false;
  return true;
}

function refreshConvert() {
  const label = state.format === "mp3" ? "MP3" : "FLAC";
  $("convert").textContent = `Преобразовать в ${label}`;
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
  if (!seconds) {
    $("estimate").textContent = "";
    return;
  }
  if (state.format === "mp3") {
    const bytes = seconds * state.bitrate * 1000 / 8;
    $("estimate").textContent = `Около ${formatBytes(bytes)} на ${chosen.length} дор. Постоянный битрейт ${state.bitrate} кбит/с.`;
    return;
  }
  const channels = area.channels || 2;
  const bytes = seconds * state.rate * (state.bits / 8) * channels * 0.62;
  $("estimate").textContent = `Около ${formatBytes(bytes)} на ${chosen.length} дор. Оценка до сжатия FLAC, с запасом.`;
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
    if (saved.format === "flac" || saved.format === "mp3") state.format = saved.format;
    if (typeof saved.rate === "number") state.rate = saved.rate;
    if (BITS.some((item) => item.value === saved.bits)) state.bits = saved.bits;
    if (BITRATES.some((item) => item.value === saved.bitrate)) state.bitrate = saved.bitrate;
    if (LOWPASS.some((item) => item.value === saved.lowpass)) state.lowpass = saved.lowpass;
    if (Number.isInteger(saved.compression)) {
      $("compression").value = String(saved.compression);
      $("compression-label").textContent = String(saved.compression);
    }
  } catch (_error) {
    /* пустые настройки */
  }
  snapRate();
}

function saveSettings() {
  localStorage.setItem("kedr-settings", JSON.stringify({
    format: state.format,
    rate: state.rate,
    bits: state.bits,
    bitrate: state.bitrate,
    lowpass: state.lowpass,
    compression: Number($("compression").value),
  }));
}
