const $ = (id) => {
  const el = document.getElementById(id);
  if (!el && id !== "aiConfigBox" && id !== "aiPromptBox" && id !== "customBox") {
    console.warn(`Element with ID "${id}" not found.`);
  }
  return el;
};

console.log("app.js loading...");

const I18N = {
  id: {
    "top.tagline": "Scan Most Replayed, potong otomatis, subtitle rapi.",
    "label.url": "YouTube URL",
    "ph.url": "https://www.youtube.com/watch?v=...",
    "help.url": "Tempel link video/shorts. Nanti keluar preview.",
    "label.mode": "Mode",
    "opt.mode.heatmap": "Scan heatmap (Most Replayed)",
    "opt.mode.ai": "AI Analysis (Transcript)",
    "opt.mode.combined": "Combined (Heatmap + AI)",
    "opt.mode.custom": "Custom start/end (manual)",
    "help.mode": "Scan = cari momen paling rame. AI = analisis transkripsi. Combined = gabungan heatmap + AI. Custom = potong dari waktu yang kamu tentuin.",
    "label.ratio": "Ratio",
    "opt.ratio.9_16": "9:16 (Shorts)",
    "opt.ratio.original": "Original",
    "help.ratio": "Pilih bentuk output video. 9:16 buat Shorts/Reels/TikTok.",
    "label.crop": "Crop",
    "opt.crop.default": "Default",
    "opt.crop.face": "Face Tracking",
    "opt.crop.split_left": "Split Left",
    "opt.crop.split_right": "Split Right",
    "help.crop": "Face tracking = otomatis jaga wajah di tengah. Split itu buat gaming: atas gameplay, bawah facecam.",
    "label.padding": "Padding (detik)",
    "help.padding": "Nambah detik sebelum & sesudah momen biar nggak “kepotong nanggung”.",
    "label.max_clips": "Max clips",
    "help.max_clips": "Berapa potongan yang mau dihasilkan dari heatmap.",
    "label.subtitle": "Subtitle",
    "opt.no": "No",
    "opt.yes": "Yes",
    "help.subtitle": "Kalau Yes, audio ditranskrip jadi teks lalu dibakar ke video.",
    "label.whisper_model": "Model (Whisper)",
    "help.whisper_model": "Ini model AI buat transkripsi suara ke teks. Makin besar makin akurat, makin berat.",
    "label.subtitle_font": "Font Subtitle",
    "opt.custom": "Custom…",
    "ph.subtitle_font_custom": "Nama font custom (mis. Poppins)",
    "help.subtitle_font": "Kalau font-nya ada di folder fonts, isi Fonts dir = fonts.",
    "label.subtitle_location": "Subtitle Location",
    "opt.subtitle_location.bottom": "Bottom",
    "opt.subtitle_location.center": "Centered",
    "help.subtitle_location": "Bottom = lebih natural buat Shorts. Centered = lebih “in your face”.",
    "label.subtitle_fontsdir": "Fonts dir (opsional)",
    "help.subtitle_fontsdir": "Folder berisi file .ttf/.otf buat subtitle. Default: folder project <b>fonts</b>.",
    "label.start": "Start (detik atau mm:ss)",
    "ph.start": "689 atau 11:29",
    "label.end": "End (detik atau mm:ss)",
    "ph.end": "742 atau 12:22",
    "btn.scan": "Scan Heatmap",
    "btn.cancel_scan": "Cancel Scan",
    "btn.clip": "Buat Clip",
    "help.actions": "Scan Heatmap = ambil daftar momen “Most Replayed”. Buat Clip = download + crop + (opsional) subtitle.",
    "panel.segments": "Segments",
    "btn.select_all": "Select All",
    "btn.clear": "Clear",
    "btn.create_selected": "Create Selected Clip",
    "panel.progress": "Progress",
    "js.scan.progress": "{pct}% • {stage}",
    "js.modal.preview_segment": "Preview Segment",
    "js.modal.preview_clip": "Preview Clip",
    "js.segments.empty": "Belum ada segment. Klik Scan Heatmap dulu.",
    "js.preview.loading": "Loading preview…",
    "js.progress.count": "{done}/{total} selesai • {success} sukses",
    "js.selected.count": "{count} dipilih",
    "js.stage.download": "Download",
    "js.stage.crop": "Crop",
    "js.stage.subtitle": "Subtitle",
    "js.stage.subtitle_model_load": "Load model",
    "js.stage.subtitle_transcribe": "Transcribe",
    "js.stage.subtitle_write": "Tulis subtitle",
    "js.stage.burn_subtitle": "Burn subtitle",
    "js.stage.finalize": "Finalize",
    "js.stage.done_clip": "Selesai",
    "js.topprogress.processing": "Processing",
    "label.ai_api_url": "AI API URL",
    "ph.ai_api_url": "https://api.openai.com/v1/chat/completions",
    "help.ai_api_url": "URL untuk API AI (OpenAI-compatible)",
    "label.ai_model": "AI Model",
    "ph.ai_model": "gpt-4",
    "help.ai_model": "Nama model AI (mis. gpt-4, claude-3-opus)",
    "label.ai_api_key": "AI API Key",
    "ph.ai_api_key": "sk-...",
    "help.ai_api_key": "Kunci API untuk akses AI service"
    ,
    "label.ai_prompt": "AI Prompt (Segment/Timestamp)",
    "ph.ai_prompt": "Contoh: fokus ke momen lucu/reaksi penonton",
    "help.ai_prompt": "Instruksi tambahan untuk AI memilih timestamp/heatmap terbaik.",
    "label.ai_metadata_prompt": "AI Prompt (Publishing Metadata)",
    "ph.ai_metadata_prompt": "Contoh: buat title YouTube Shorts yang punchy",
    "help.ai_metadata_prompt": "Instruksi tambahan untuk AI membuat title, deskripsi, hashtags, dan notes.",
    "panel.metadata": "Publishing Metadata",
    "panel.gallery": "Clip Gallery",
    "btn.refresh_gallery": "Refresh",
    "btn.upload_youtube": "Upload ke YouTube",
    "js.gallery.empty": "Belum ada clip yang selesai. Buat clip dulu.",
    "js.uploading": "Sedang upload...",
    "js.upload_success": "Berhasil upload! Video ID: {id}",
    "js.upload_error": "Gagal upload: {err}",
    "label.cookies_browser": "Browser (Cookies)",
    "opt.cookies_browser.none": "None (Tanpa login)"
  },
  en: {
    "top.tagline": "Scan Most Replayed, auto cut, clean subtitles.",
    "label.url": "YouTube URL",
    "ph.url": "https://www.youtube.com/watch?v=...",
    "help.url": "Paste a video/shorts link. Preview will show up.",
    "label.mode": "Mode",
    "opt.mode.heatmap": "Scan heatmap (Most Replayed)",
    "opt.mode.ai": "AI Analysis (Transcript)",
    "opt.mode.combined": "Combined (Heatmap + AI)",
    "opt.mode.custom": "Custom start/end (manual)",
    "help.mode": "Scan = find the hottest moments. AI = transcript analysis. Combined = heatmap + AI. Custom = cut by your timestamps.",
    "label.ratio": "Ratio",
    "opt.ratio.9_16": "9:16 (Shorts)",
    "opt.ratio.original": "Original",
    "help.ratio": "Choose output aspect ratio. 9:16 is for Shorts/Reels/TikTok.",
    "label.crop": "Crop",
    "opt.crop.default": "Default",
    "opt.crop.face": "Face Tracking",
    "opt.crop.split_left": "Split Left",
    "opt.crop.split_right": "Split Right",
    "help.crop": "Face tracking keeps the face centered. Split is for gaming: gameplay on top, facecam below.",
    "label.padding": "Padding (seconds)",
    "help.padding": "Adds seconds before & after, so it doesn’t cut awkwardly.",
    "label.max_clips": "Max clips",
    "help.max_clips": "How many clips to generate from the heatmap.",
    "label.subtitle": "Subtitle",
    "opt.no": "No",
    "opt.yes": "Yes",
    "help.subtitle": "If Yes, audio is transcribed to text and burned into the video.",
    "label.whisper_model": "Model (Whisper)",
    "help.whisper_model": "AI model for speech-to-text. Bigger = more accurate, heavier.",
    "label.subtitle_font": "Subtitle Font",
    "opt.custom": "Custom…",
    "ph.subtitle_font_custom": "Custom font name (e.g. Poppins)",
    "help.subtitle_font": "If the font is in fonts folder, set Fonts dir = fonts.",
    "label.subtitle_location": "Subtitle Location",
    "opt.subtitle_location.bottom": "Bottom",
    "opt.subtitle_location.center": "Centered",
    "help.subtitle_location": "Bottom looks natural for Shorts. Centered is more “in your face”.",
    "label.subtitle_fontsdir": "Fonts dir (optional)",
    "help.subtitle_fontsdir": "Folder containing .ttf/.otf for subtitles. Default: project <b>fonts</b> folder.",
    "label.start": "Start (seconds or mm:ss)",
    "ph.start": "689 or 11:29",
    "label.end": "End (seconds or mm:ss)",
    "ph.end": "742 or 12:22",
    "btn.scan": "Scan Heatmap",
    "btn.cancel_scan": "Cancel Scan",
    "btn.clip": "Create Clip",
    "help.actions": "Scan Heatmap = fetch “Most Replayed” moments. Create Clip = download + crop + (optional) subtitles.",
    "panel.segments": "Segments",
    "btn.select_all": "Select All",
    "btn.clear": "Clear",
    "btn.create_selected": "Create Selected Clip",
    "panel.progress": "Progress",
    "js.scan.progress": "{pct}% • {stage}",
    "js.modal.preview_segment": "Preview Segment",
    "js.modal.preview_clip": "Preview Clip",
    "js.segments.empty": "No segments yet. Click Scan Heatmap first.",
    "js.preview.loading": "Loading preview…",
    "js.progress.count": "{done}/{total} done • {success} success",
    "js.selected.count": "{count} selected",
    "js.stage.download": "Download",
    "js.stage.crop": "Crop",
    "js.stage.subtitle": "Subtitle",
    "js.stage.subtitle_model_load": "Load model",
    "js.stage.subtitle_transcribe": "Transcribe",
    "js.stage.subtitle_write": "Write subtitles",
    "js.stage.burn_subtitle": "Burn subtitle",
    "js.stage.hook": "Hook Intro",
    "js.stage.finalize": "Finalize",
    "js.stage.done_clip": "Done",
    "js.topprogress.processing": "Processing",
    "label.ai_api_url": "AI API URL",
    "ph.ai_api_url": "https://api.openai.com/v1/chat/completions",
    "help.ai_api_url": "AI API URL (OpenAI-compatible)",
    "label.ai_model": "AI Model",
    "ph.ai_model": "gpt-4",
    "help.ai_model": "AI Model name (e.g. gpt-4, claude-3-opus)",
    "label.ai_api_key": "AI API Key",
    "ph.ai_api_key": "sk-...",
    "help.ai_api_key": "API key for AI service access"
    ,
    "label.ai_prompt": "AI Prompt (Segments/Timestamps)",
    "ph.ai_prompt": "Example: prioritize funny moments and crowd reactions",
    "help.ai_prompt": "Extra instructions to guide AI in picking timestamps/heatmap.",
    "label.ai_metadata_prompt": "AI Prompt (Publishing Metadata)",
    "ph.ai_metadata_prompt": "Example: write a punchy Shorts title",
    "help.ai_metadata_prompt": "Extra instructions to generate title, description, hashtags, and notes.",
    "panel.metadata": "Publishing Metadata",
    "panel.gallery": "Clip Gallery",
    "btn.refresh_gallery": "Refresh",
    "btn.upload_youtube": "Upload to YouTube",
    "js.gallery.empty": "No clips generated yet. Create clips first.",
    "js.uploading": "Uploading...",
    "js.upload_success": "Upload success! Video ID: {id}",
    "js.upload_error": "Upload failed: {err}",
    "label.cookies_browser": "Browser (Cookies)",
    "opt.cookies_browser.none": "None (No login)"
  },
};

let currentLang = "id";

function t(key, vars) {
  const base = I18N[currentLang] || I18N.id;
  const fallback = I18N.id || {};
  let s = base[key] ?? fallback[key] ?? key;
  if (vars && typeof s === "string") {
    Object.entries(vars).forEach(([k, v]) => {
      s = s.replaceAll(`{${k}}`, String(v));
    });
  }
  return s;
}

const TOP_PROGRESS = {
  pct: 0,
  titleBase: document.title || "MindCut",
  hideTimer: null,
};

function clamp(n, a, b) {
  return Math.min(b, Math.max(a, n));
}

function easeOutCubic(x) {
  const t = clamp(x, 0, 1);
  return 1 - Math.pow(1 - t, 3);
}

function stageLabel(stage) {
  const key = {
    download: "js.stage.download",
    crop: "js.stage.crop",
    subtitle: "js.stage.subtitle",
    subtitle_model_load: "js.stage.subtitle_model_load",
    subtitle_transcribe: "js.stage.subtitle_transcribe",
    subtitle_write: "js.stage.subtitle_write",
    burn_subtitle: "js.stage.burn_subtitle",
    hook: "js.stage.hook",
    finalize: "js.stage.finalize",
    done_clip: "js.stage.done_clip",
  }[stage];
  return key ? t(key) : stage || "";
}

function scanStageLabel(stage) {
  const map = {
    init: "Init",
    download: "Download",
    transcribe: "Transcribe",
    heatmap: "Heatmap",
    ai: "AI Scoring",
    metadata: "Metadata",
    done: "Done",
    error: "Error",
  };
  return map[stage] || stage || "";
}

function computeJobPct(job) {
  if (!job) return { pct: 0, text: "", active: false };
  const status = job.status || "";
  if (status !== "running" && status !== "queued") {
    const done = Number(job.done || 0);
    const total = Number(job.total || 0);
    const pct = total > 0 ? clamp((done / total) * 100, 0, 100) : 0;
    return { pct, text: "", active: false };
  }

  const total = Math.max(1, Number(job.total || 1));
  const done = clamp(Number(job.done || 0), 0, total);
  const subtitleEnabled = Boolean(job.subtitle_enabled);
  const stage = job.stage || "";
  const stageAt = job.stage_at ? Number(job.stage_at) : 0;
  const elapsed = stageAt ? Date.now() - stageAt : 0;
  const clipIndexRaw = Number(job.stage_clip || job.current || (done + 1) || 1);
  const clipIndex = clamp(clipIndexRaw, 1, total);

  const mapNoSub = {
    download: { a: 0.04, b: 0.62, d: 14000 },
    crop: { a: 0.62, b: 0.95, d: 9000 },
    hook: { a: 0.95, b: 0.985, d: 8000 },
    finalize: { a: 0.985, b: 0.995, d: 2500 },
    done_clip: { a: 1, b: 1, d: 0 },
  };
  const mapSub = {
    download: { a: 0.03, b: 0.55, d: 14000 },
    crop: { a: 0.55, b: 0.86, d: 9000 },
    subtitle: { a: 0.86, b: 0.87, d: 1200 },
    subtitle_model_load: { a: 0.87, b: 0.885, d: 2500 },
    subtitle_transcribe: { a: 0.885, b: 0.93, d: 20000 },
    subtitle_write: { a: 0.93, b: 0.94, d: 1800 },
    burn_subtitle: { a: 0.94, b: 0.97, d: 12000 },
    hook: { a: 0.97, b: 0.99, d: 8000 },
    finalize: { a: 0.99, b: 0.998, d: 1500 },
    done_clip: { a: 1, b: 1, d: 0 },
  };

  const table = subtitleEnabled ? mapSub : mapNoSub;
  const s = table[stage] || (subtitleEnabled ? mapSub.download : mapNoSub.download);
  let within = s.d > 0 ? s.a + (s.b - s.a) * easeOutCubic(clamp(elapsed / s.d, 0, 0.98)) : s.a;
  let sLabel = stageLabel(stage);

  if (stage === "download" && job.dl_pct !== undefined && job.dl_pct !== null && job.dl_pct > 0) {
    const dlFactor = clamp(Number(job.dl_pct) / 100, 0, 1);
    within = s.a + (s.b - s.a) * dlFactor;
    const spd = job.dl_speed ? ` (${job.dl_speed})` : "";
    sLabel = `${sLabel} ${job.dl_pct}%${spd}`;
  }

  const pctBase = ((clipIndex - 1) + within) / total * 100;
  const pctFloor = (done / total) * 100;
  const pct = clamp(Math.max(pctBase, pctFloor), 0, 99.5);

  const clipText = total > 0 ? `clip ${clipIndex}/${total}` : "";
  const text = [t("js.topprogress.processing"), clipText, sLabel].filter(Boolean).join(" • ");
  return { pct, text, active: true };
}

function renderTopProgress(job) {
  const wrap = $("topProgressWrap");
  const bar = $("topProgressBar");
  const textEl = $("topProgressText");
  if (!wrap || !bar || !textEl) return;

  const { pct, text, active } = computeJobPct(job);

  if (!active) {
    if (job && (job.status === "done" || job.status === "error")) {
      bar.style.width = "100%";
      textEl.textContent = job.status === "error" ? "Error" : "";
      wrap.classList.remove("hide");
      clearTimeout(TOP_PROGRESS.hideTimer);
      TOP_PROGRESS.hideTimer = setTimeout(() => {
        wrap.classList.add("hide");
        bar.style.width = "0%";
        textEl.textContent = "";
      }, 650);
      document.title = TOP_PROGRESS.titleBase;
      TOP_PROGRESS.pct = 0;
      return;
    }
    wrap.classList.add("hide");
    bar.style.width = "0%";
    textEl.textContent = "";
    document.title = TOP_PROGRESS.titleBase;
    TOP_PROGRESS.pct = 0;
    return;
  }

  clearTimeout(TOP_PROGRESS.hideTimer);
  wrap.classList.remove("hide");
  TOP_PROGRESS.pct = Math.max(TOP_PROGRESS.pct, pct);
  bar.style.width = `${TOP_PROGRESS.pct.toFixed(1)}%`;
  textEl.textContent = text;
  document.title = `${TOP_PROGRESS.titleBase} (${Math.round(TOP_PROGRESS.pct)}%)`;
}

function applyI18n() {
  document.documentElement.lang = currentLang;
  $("langId")?.classList.toggle("isActive", currentLang === "id");
  $("langEn")?.classList.toggle("isActive", currentLang === "en");

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.dataset.i18n;
    if (!key) return;
    el.innerHTML = t(key);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.dataset.i18nPlaceholder;
    if (!key) return;
    el.setAttribute("placeholder", t(key));
  });
}

function setLang(lang) {
  currentLang = lang === "en" ? "en" : "id";
  localStorage.setItem("lang", currentLang);
  applyI18n();
  renderSegments(lastScanSegments);
  updateSelectedUi();
}

function fmtTime(s) {
  const sec = Math.max(0, Math.floor(Number(s) || 0));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const r = sec % 60;
  if (h > 0) return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return data;
}

function openModal(title, bodyEl) {
  $("modalTitle").textContent = title || "";
  const root = $("modalBody");
  root.innerHTML = "";
  root.appendChild(bodyEl);
  $("modal").classList.remove("hide");
}

function closeModal() {
  $("modal").classList.add("hide");
  $("modalBody").innerHTML = "";
}

function debounce(fn, wait) {
  let t = null;
  return (...args) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

function readPayload() {
  const defaults = {
    ratio: "9:16", crop: "default", padding: 10, max_clips: 6,
    subtitle: "n", whisper_model: "small", subtitle_font_select: "Plus Jakarta Sans",
    subtitle_font_custom: "", subtitle_location: "bottom", subtitle_fontsdir: "fonts",
    ai_api_url: "", ai_model: "gpt-4o", ai_api_key: "", ai_prompt: "", ai_metadata_prompt: "",
    hook_enabled: "n", hook_voice: "en-US-GuyNeural", hook_voice_rate: "+15%", hook_voice_pitch: "+5Hz", hook_font_size: 72
  };
  
  const getVal = (id) => {
    const el = $(id);
    if (el) return el.value;
    const l = localStorage.getItem(`yt_config_${id}`);
    return l !== null ? l : defaults[id];
  };

  const fontSel = getVal("subtitle_font_select");
  const fontCustom = (getVal("subtitle_font_custom") || "").trim();
  const subtitleFont = fontSel === "custom" ? fontCustom : fontSel;
  
  return {
    url: $("url") ? $("url").value.trim() : "",
    mode: $("mode") ? $("mode").value : "heatmap",
    ratio: getVal("ratio"),
    crop: getVal("crop"),
    padding: Number(getVal("padding") || 0),
    max_clips: Number(getVal("max_clips") || 6),
    subtitle: getVal("subtitle") === "y",
    whisper_model: getVal("whisper_model"),
    subtitle_font: subtitleFont,
    subtitle_location: getVal("subtitle_location"),
    subtitle_fontsdir: getVal("subtitle_fontsdir") || "",
    start: $("start") ? $("start").value : "",
    end: $("end") ? $("end").value : "",
    ai_api_url: getVal("ai_api_url") || "",
    ai_model: getVal("ai_model") || "",
    ai_api_key: getVal("ai_api_key") || "",
    ai_prompt: getVal("ai_prompt") || "",
    ai_metadata_prompt: getVal("ai_metadata_prompt") || "",
    cookies_browser: $("cookies_browser")?.value || "",
    hook_enabled: getVal("hook_enabled") === "y",
    hook_voice: getVal("hook_voice"),
    hook_voice_rate: getVal("hook_voice_rate"),
    hook_voice_pitch: getVal("hook_voice_pitch"),
    hook_font_size: Number(getVal("hook_font_size") || 72),
    video_title: typeof currentPreview !== "undefined" && currentPreview ? currentPreview.title : ""
  };
}

function setBusy(busy) {
  console.log("setBusy:", busy);
  const ids = ["scanBtn", "clipBtn", "segSelectAllBtn", "segClearBtn", "segCreateBtn", "scanCancelBtn"];
  ids.forEach(id => {
    const el = $(id);
    if (el) el.disabled = busy;
  });
  if ($("scanCancelBtn")) $("scanCancelBtn").disabled = false;
}

function getVideoThumb(videoId, fallback) {
  if (!videoId) return fallback || "";
  return `https://i.ytimg.com/vi_webp/${videoId}/hqdefault.webp`;
}

function openYouTubePreview(videoId, startSec, endSec, title) {
  const start = Math.max(0, Math.floor(Number(startSec) || 0));
  const end = Math.max(0, Math.floor(Number(endSec) || 0));
  const url = `https://www.youtube.com/embed/${encodeURIComponent(videoId)}?start=${start}${end > start ? `&end=${end}` : ""}&autoplay=1&playsinline=1&rel=0`;
  const iframe = document.createElement("iframe");
  iframe.className = "embed";
  iframe.src = url;
  iframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
  iframe.allowFullscreen = true;
  openModal(title || t("js.modal.preview_segment"), iframe);
}

function openClipPreview(title, src) {
  const v = document.createElement("video");
  v.className = "video";
  v.controls = true;
  v.autoplay = true;
  v.muted = true;
  v.playsInline = true;
  v.src = src;
  openModal(title || t("js.modal.preview_clip"), v);
}

function segKey(seg) {
  const start = Math.round(Number(seg.start || 0) * 1000);
  const dur = Math.round(Number(seg.duration || 0) * 1000);
  return `${start}:${dur}`;
}

function setSegControlsVisible(visible) {
  $("segControls").classList.toggle("hide", !visible);
}

function updateSelectedUi() {
  const count = selectedKeys.size;
  $("segSelectedMeta").textContent = count > 0 ? t("js.selected.count", { count }) : "";
  $("segCreateBtn").disabled = count === 0 || $("scanBtn").disabled;
  setSegControlsVisible($("mode").value !== "custom" && lastScanSegments.length > 0);
}

function selectAllSegments() {
  selectedKeys = new Set(lastScanSegments.map(segKey));
  renderSegments(lastScanSegments);
  updateSelectedUi();
}

function clearSelectedSegments() {
  selectedKeys = new Set();
  renderSegments(lastScanSegments);
  updateSelectedUi();
}

async function clipSelected() {
  if ($("mode").value === "custom") return;
  if (selectedKeys.size === 0) return;
  setBusy(true);
  try {
    const payload = readPayload();
    const picked = lastScanSegments.filter((s) => selectedKeys.has(segKey(s)));
    const data = await postJson("/api/clip", { ...payload, segments: picked });
    const jobId = data.job_id;
    await pollJob(jobId);
  } catch (e) {
    renderProgress({ status: "error", error: e.message, total: 0, done: 0, id: "" });
  } finally {
    setBusy(false);
    updateSelectedUi();
  }
}

function renderSegments(segments) {
  const root = $("segments");
  root.innerHTML = "";
  if (!segments || segments.length === 0) {
    root.innerHTML = `<div class="small">${t("js.segments.empty")}</div>`;
    updateSelectedUi();
    return;
  }
  segments.forEach((s, idx) => {
    const start = Number(s.start || 0);
    const dur = Number(s.duration || 0);
    const end = start + dur;
    const score = Number(s.score || 0);
    const el = document.createElement("div");
    el.className = "seg";
    const key = segKey(s);
    if (selectedKeys.has(key)) el.classList.add("selected");
    const thumb = getVideoThumb(currentVideoId, currentPreview?.thumbnail);
    el.innerHTML = `
      <div class="segThumb">
        <img alt="" src="${thumb}" />
        <div class="segTime">${fmtTime(start)}</div>
      </div>
      <div class="segMain">
        <div class="t">#${idx + 1} ${fmtTime(start)} → ${fmtTime(end)}</div>
        <div class="m">durasi ${Math.round(dur)}s</div>
      </div>
      <div class="segSide">
        <div class="pill">${score.toFixed(2)}</div>
        <button class="btn ghost smallBtn" type="button" data-preview="1">Preview</button>
        <button class="btn ghost smallBtn" type="button" data-clip="1">Clip</button>
      </div>
    `;
    el.addEventListener("click", (ev) => {
      const target = ev.target;
      if (target && target.dataset && target.dataset.preview) {
        ev.preventDefault();
        ev.stopPropagation();
        if (currentVideoId) openYouTubePreview(currentVideoId, start, end, currentPreview?.title || "Preview Segment");
        return;
      }
      if (target && target.dataset && target.dataset.clip) {
        ev.preventDefault();
        ev.stopPropagation();
        clipSingle(s);
        return;
      }
      if ($("mode").value === "custom") {
        $("start").value = Math.floor(start);
        $("end").value = Math.floor(end);
        return;
      }
      if (selectedKeys.has(key)) selectedKeys.delete(key);
      else selectedKeys.add(key);
      el.classList.toggle("selected");
      updateSelectedUi();
    });
    root.appendChild(el);
  });
  updateSelectedUi();
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderMetadata(metadata) {
  const panel = $("metaPanel");
  const root = $("metaContent");
  if (!panel || !root) return;
  root.innerHTML = "";
  if (!metadata || Object.keys(metadata).length === 0) {
    panel.classList.add("hide");
    return;
  }
  panel.classList.remove("hide");

  const rows = [];
  const addRow = (label, value) => {
    if (value == null || value === "") return;
    const row = document.createElement("div");
    row.className = "metaRow";
    row.innerHTML = `<div class="metaLabel">${escapeHtml(label)}</div><div class="metaValue">${value}</div>`;
    rows.push(row);
  };

  addRow("Title", escapeHtml(metadata.title || ""));
  addRow("Description", escapeHtml(metadata.description || ""));

  if (Array.isArray(metadata.hashtags) && metadata.hashtags.length > 0) {
    const tags = metadata.hashtags.map((t) => `<span class="metaTag">#${escapeHtml(t)}</span>`).join(" ");
    addRow("Hashtags", `<div class="metaTags">${tags}</div>`);
  }

  if (Array.isArray(metadata.tags) && metadata.tags.length > 0) {
    const tags = metadata.tags.map((t) => `<span class="metaTag">${escapeHtml(t)}</span>`).join(" ");
    addRow("Tags", `<div class="metaTags">${tags}</div>`);
  }

  addRow("Hook", escapeHtml(metadata.hook || ""));
  addRow("Thumbnail Text", escapeHtml(metadata.thumbnail_text || ""));
  addRow("Category", escapeHtml(metadata.category || ""));

  if (Array.isArray(metadata.timestamps) && metadata.timestamps.length > 0) {
    const list = document.createElement("div");
    list.className = "metaList";
    metadata.timestamps.forEach((t) => {
      const start = t.start != null ? fmtTime(t.start) : "";
      const end = t.end != null ? fmtTime(t.end) : "";
      const reason = t.reason ? ` • ${escapeHtml(t.reason)}` : "";
      const item = document.createElement("div");
      item.className = "metaItem";
      item.innerHTML = `<span class="metaCode">${escapeHtml(start)} → ${escapeHtml(end)}</span>${reason}`;
      list.appendChild(item);
    });
    addRow("Timestamps", list.outerHTML);
  }

  addRow("Publish Notes", escapeHtml(metadata.publish_notes || ""));

  rows.forEach((row) => root.appendChild(row));
}

function renderProgress(job) {
  const root = $("progress");
  const meta = $("jobMeta");
  const out = $("outputs");
  root.innerHTML = "";
  out.innerHTML = "";
  meta.textContent = "";
  if (!job) return;
  renderTopProgress(job);
  const total = Number(job.total || 0);
  const done = Number(job.done || 0);

  const { pct: livePct, text: liveText, active } = computeJobPct(job);
  const barPct = active ? livePct : (total > 0 ? Math.round((done / total) * 100) : 0);

  const stage = stageLabel(job.stage || "");
  meta.textContent = `${job.status} • ${(job.status_text || "").trim()}${stage ? " • " + stage : ""}`.trim();

  const bar = document.createElement("div");
  bar.innerHTML = `<div class="bar"><div style="width:${barPct.toFixed(1)}%"></div></div>`;
  root.appendChild(bar);

  // Detail line: show stage + download progress when active
  if (active && liveText) {
    const detail = document.createElement("div");
    detail.className = "progressDetail";
    detail.textContent = liveText;
    root.appendChild(detail);
  }

  const line = document.createElement("div");
  line.className = "small";
  line.textContent =
    total > 0
      ? t("js.progress.count", { done, total, success: job.success || 0 })
      : "";
  root.appendChild(line);

  if (job.status === "error") {
    const err = document.createElement("div");
    err.className = "small";
    err.textContent = job.error || "error";
    root.appendChild(err);
  }

  if (Array.isArray(job.outputs) && job.outputs.length > 0) {
    job.outputs.forEach((f) => {
      const el = document.createElement("div");
      el.className = "out";
      const href = `/clips/${job.id}/${encodeURIComponent(f.name)}`;
      el.innerHTML = `
        <div class="outLeft">
          <a href="${href}" target="_blank" rel="noreferrer">${f.name}</a>
          <div class="small">${Math.round((f.size || 0) / 1024)} KB</div>
        </div>
        <div class="outRight">
          <button class="btn ghost smallBtn" type="button" data-play="1">Play</button>
          <a class="btn ghost smallBtn" href="${href}" download>Download</a>
        </div>
      `;
      el.querySelector("[data-play]")?.addEventListener("click", (ev) => {
        ev.preventDefault();
        openClipPreview(f.name, href);
      });
      out.appendChild(el);
    });
  }
}

let lastScanSegments = [];
let lastScanMetadata = null;
let lastPreviewUrl = "";
let currentPreview = null;
let currentVideoId = "";
let selectedKeys = new Set();
let currentScanJobId = "";

async function loadGallery() {
  const root = $("gallery");
  if (!root) return;
  try {
    const data = await fetch("/api/gallery").then(r => r.json());
    if (!data.ok || !data.items || data.items.length === 0) {
      root.innerHTML = `<div class="small">${t("js.gallery.empty")}</div>`;
      return;
    }
    root.innerHTML = "";
    data.items.forEach(item => {
      const el = document.createElement("div");
      el.className = "out";
      const href = `/clips/${item.job_id}/${encodeURIComponent(item.filename)}`;
      el.innerHTML = `
        <div class="outLeft">
          <a href="${href}" target="_blank" rel="noreferrer">${item.filename}</a>
          <div class="small">${Math.round(item.size / 1024)} KB</div>
        </div>
        <div class="outRight">
          <button class="btn ghost smallBtn" type="button" data-play="1">Play</button>
          <a class="btn ghost smallBtn" href="${href}" download>Download</a>
          <button class="btn ghost smallBtn" type="button" data-upload="1">${t("btn.upload_youtube")}</button>
        </div>
      `;
      el.querySelector("[data-play]")?.addEventListener("click", () => {
        openClipPreview(item.filename, href);
      });
      el.querySelector("[data-upload]")?.addEventListener("click", async (ev) => {
        const btn = ev.target;
        btn.disabled = true;
        btn.textContent = t("js.uploading");
        try {
          const m = lastScanMetadata || {};
          const upData = await postJson("/api/youtube/upload", {
            job_id: item.job_id,
            filename: item.filename,
            title: m.title || `Clip ${item.filename}`,
            description: m.description || "",
            tags: m.hashtags || []
          });
          alert(t("js.upload_success", {id: upData.youtube_id}));
          btn.textContent = "Uploaded";
        } catch (e) {
          alert(t("js.upload_error", {err: e.message}));
          btn.textContent = t("btn.upload_youtube");
          btn.disabled = false;
        }
      });
      root.appendChild(el);
    });
  } catch (e) {
    root.innerHTML = `<div class="small">Error: ${e.message}</div>`;
  }
}

function renderScanProgress(job) {
  const wrap = $("scanProgress");
  const bar = $("scanBarFill");
  const text = $("scanText");
  if (!wrap || !bar || !text) return;
  if (!job || !job.status) {
    wrap.classList.add("hide");
    bar.style.width = "0%";
    text.textContent = "";
    return;
  }
  const pct = Math.max(0, Math.min(100, Number(job.pct || 0)));
  let stage = scanStageLabel(job.stage);
  if (job.stage === "download" && job.dl_pct !== undefined && job.dl_pct !== null && job.dl_pct > 0) {
      const spd = job.dl_speed ? ` (${job.dl_speed})` : "";
      stage = `${stage} ${job.dl_pct}%${spd}`;
  }
  wrap.classList.remove("hide");
  bar.style.width = `${pct}%`;
  text.textContent = t("js.scan.progress", { pct: Math.round(pct), stage });
  if (job.status === "done" || job.status === "error" || job.status === "cancelled") {
    setTimeout(() => {
      wrap.classList.add("hide");
      bar.style.width = "0%";
      text.textContent = "";
    }, 1200);
  }
}

const STORE_KEY = "yt_heatmap_settings_v1";

function readSettingsFromUi() {
  return {
    mode: $("mode")?.value || "heatmap",
    ratio: $("ratio")?.value || "9:16",
    crop: $("crop")?.value || "default",
    padding: $("padding")?.value || "10",
    max_clips: $("max_clips")?.value || "6",
    subtitle: $("subtitle")?.value || "n",
    whisper_model: $("whisper_model")?.value || "small",
    subtitle_font_select: $("subtitle_font_select")?.value || "Plus Jakarta Sans",
    subtitle_font_custom: $("subtitle_font_custom")?.value || "",
    subtitle_location: $("subtitle_location")?.value || "bottom",
    subtitle_fontsdir: $("subtitle_fontsdir")?.value || "fonts",
    ai_api_url: $("ai_api_url")?.value || "",
    ai_model: $("ai_model")?.value || "",
    ai_api_key: $("ai_api_key")?.value || "",
    ai_prompt: $("ai_prompt")?.value || "",
    ai_metadata_prompt: $("ai_metadata_prompt")?.value || "",
    cookies_browser: $("cookies_browser")?.value || ""
  };
}

function applySettingsToUi(settings) {
  if (!settings || typeof settings !== "object") return;
  if ($("mode") && settings.mode) $("mode").value = settings.mode;
  if ($("ratio") && settings.ratio) $("ratio").value = settings.ratio;
  if ($("crop") && settings.crop) $("crop").value = settings.crop;
  if ($("padding") && settings.padding != null) $("padding").value = settings.padding;
  if ($("max_clips") && settings.max_clips != null) $("max_clips").value = settings.max_clips;
  if ($("subtitle") && settings.subtitle) $("subtitle").value = settings.subtitle;
  if ($("whisper_model") && settings.whisper_model) $("whisper_model").value = settings.whisper_model;
  if ($("subtitle_location") && settings.subtitle_location) $("subtitle_location").value = settings.subtitle_location;
  if ($("subtitle_fontsdir") && settings.subtitle_fontsdir != null) $("subtitle_fontsdir").value = settings.subtitle_fontsdir;
  if ($("ai_api_url") && settings.ai_api_url != null) $("ai_api_url").value = settings.ai_api_url;
  if ($("ai_model") && settings.ai_model != null) $("ai_model").value = settings.ai_model;
  if ($("ai_api_key") && settings.ai_api_key != null) $("ai_api_key").value = settings.ai_api_key;
  if ($("ai_prompt") && settings.ai_prompt != null) $("ai_prompt").value = settings.ai_prompt;
  if ($("ai_metadata_prompt") && settings.ai_metadata_prompt != null) $("ai_metadata_prompt").value = settings.ai_metadata_prompt;
  if ($("cookies_browser") && settings.cookies_browser != null) $("cookies_browser").value = settings.cookies_browser;

  if ($("subtitle_font_select") && settings.subtitle_font_select) {
    $("subtitle_font_select").value = settings.subtitle_font_select;
  }
  if ($("subtitle_font_custom") && settings.subtitle_font_custom != null) {
    $("subtitle_font_custom").value = settings.subtitle_font_custom;
  }
  toggleFont();
  toggleCustomStartEnd();
  toggleMode();
}

function saveSettings() {
  // Only save if elements are present (e.g. on settings page if we ever use app.js there)
  // But on index.html, we only have 'mode' and 'cookies_browser'
}

function loadSettings() {
  // Load mode from localStorage individual key if exists
  const m = localStorage.getItem("yt_config_mode");
  if (m && $("mode")) $("mode").value = m;
  
  const c = localStorage.getItem("yt_config_cookies_browser");
  if (c && $("cookies_browser")) $("cookies_browser").value = c;
}

function bindSettingsAutosave() {
  const ids = [
    "mode",
    "ratio",
    "crop",
    "padding",
    "max_clips",
    "subtitle",
    "whisper_model",
    "subtitle_font_select",
    "subtitle_font_custom",
    "subtitle_location",
    "subtitle_fontsdir",
    "ai_api_url",
    "ai_model",
    "ai_api_key",
    "ai_prompt",
    "ai_metadata_prompt",
  ];
  ids.forEach((id) => {
    const el = $(id);
    if (!el) return;
    el.addEventListener("change", saveSettings);
    el.addEventListener("input", saveSettings);
  });
}

async function scan() {
  console.log("scan() called");
  setBusy(true);
  try {
    const payload = readPayload();
    console.log("payload:", payload);
    const data = await postJson("/api/scan/start", payload);
    console.log("scan started:", data);
    currentScanJobId = data.job_id || "";
    if ($("scanCancelBtn")) $("scanCancelBtn").classList.toggle("hide", !currentScanJobId);
    await pollScan(currentScanJobId);
  } catch (e) {
    console.error("scan() failed:", e);
    if ($("segMeta")) $("segMeta").textContent = e.message;
    renderSegments([]);
    renderMetadata(null);
  } finally {
    setBusy(false);
    updateSelectedUi();
  }
}

async function preview() {
  const url = $("url").value.trim();
  if (!url || url === lastPreviewUrl) return;
  lastPreviewUrl = url;
  const box = $("preview");
  const title = $("pvTitle");
  const sub = $("pvSub");
  const img = $("thumbImg");
  try {
    title.textContent = t("js.preview.loading");
    sub.textContent = "";
    img.removeAttribute("src");
    box.classList.remove("hide");
    const data = await postJson("/api/preview", { url });
    const p = data.preview || {};
    currentPreview = p;
    if (p.id) currentVideoId = p.id;
    title.textContent = p.title || "Untitled";
    const dur = p.duration != null ? fmtTime(p.duration) : "";
    const uploader = p.uploader || "";
    sub.textContent = [uploader, dur].filter(Boolean).join(" • ");
    if (p.thumbnail) img.src = p.thumbnail;
  } catch (e) {
    box.classList.add("hide");
  }
}

async function clip() {
  setBusy(true);
  try {
    const payload = readPayload();
    const data = await postJson("/api/clip", payload);
    const jobId = data.job_id;
    await pollJob(jobId);
  } catch (e) {
    renderProgress({ status: "error", error: e.message, total: 0, done: 0, id: "" });
  } finally {
    setBusy(false);
  }
}

async function clipSingle(seg) {
  setBusy(true);
  try {
    const payload = readPayload();
    const data = await postJson("/api/clip", { ...payload, segments: [seg] });
    const jobId = data.job_id;
    await pollJob(jobId);
  } catch (e) {
    renderProgress({ status: "error", error: e.message, total: 0, done: 0, id: "" });
  } finally {
    setBusy(false);
    updateSelectedUi();
  }
}

async function pollJob(jobId) {
  const started = Date.now();
  while (true) {
    const res = await fetch(`/api/job/${jobId}`);
    const data = await res.json().catch(() => null);
    if (!data || !data.ok) throw new Error("Job not found");
    renderProgress(data.job);
    if (data.job.status === "done" || data.job.status === "error") return;
    if (Date.now() - started > 1000 * 60 * 30) throw new Error("Timeout");
    await new Promise((r) => setTimeout(r, 1000));
  }
}

async function pollScan(jobId) {
  const started = Date.now();
  while (true) {
    const res = await fetch(`/api/scan/job/${jobId}`);
    const data = await res.json().catch(() => null);
    if (!data || !data.ok) throw new Error("Scan job not found");
    const job = data.job || {};
    renderScanProgress(job);
    if (job.status === "done") {
      const result = job.result || {};
      lastScanSegments = result.segments || [];
      lastScanSegments.forEach((s, idx) => s.original_index = idx + 1);
      lastScanMetadata = result.metadata || null;
      selectedKeys = new Set();
      currentVideoId = result.video_id || currentVideoId;
      $("segMeta").textContent = `${lastScanSegments.length} segments • durasi ~${fmtTime(result.duration || 0)}`;
      renderSegments(lastScanSegments);
      renderMetadata(lastScanMetadata);
      if (result.warning) {
        const warn = document.createElement("div");
        warn.className = "small";
        warn.style.color = "rgba(250, 204, 21, .9)";
        warn.textContent = "⚠ " + result.warning;
        $("segments").prepend(warn);
      }
      $("scanCancelBtn").classList.add("hide");
      return;
    }
    if (job.status === "error") {
      $("segMeta").textContent = job.error || "error";
      renderSegments([]);
      renderMetadata(null);
      $("scanCancelBtn").classList.add("hide");
      return;
    }
    if (job.status === "cancelled") {
      $("segMeta").textContent = "Scan cancelled";
      renderSegments([]);
      renderMetadata(null);
      $("scanCancelBtn").classList.add("hide");
      return;
    }
    if (Date.now() - started > 1000 * 60 * 30) throw new Error("Timeout");
    await new Promise((r) => setTimeout(r, 800));
  }
}

async function cancelScan() {
  if (!currentScanJobId) return;
  try {
    await postJson(`/api/scan/cancel/${currentScanJobId}`, {});
  } catch (e) {
    // ignore
  }
}

function toggleMode() {
  const modeEl = $("mode");
  if (!modeEl) return;
  const mode = modeEl.value;
  const isCustom = mode === "custom";
  const isAiMode = mode === "ai" || mode === "combined";
  
  $("customBox")?.classList.toggle("hide", !isCustom);
  $("scanBtn")?.classList.toggle("hide", isCustom);
  $("aiConfigBox")?.classList.toggle("hide", !isAiMode);
  $("aiPromptBox")?.classList.toggle("hide", !isAiMode);
  
  if (isCustom) {
    setSegControlsVisible(false);
    if ($("segSelectedMeta")) $("segSelectedMeta").textContent = "";
  } else {
    setSegControlsVisible(lastScanSegments.length > 0);
    updateSelectedUi();
  }
  if (!isAiMode) {
    renderMetadata(null);
  }
}

function toggleFont() {
  const sel = $("subtitle_font_select");
  if (!sel) return;
  const isCustom = sel.value === "custom";
  $("subtitle_font_custom")?.classList.toggle("hide", !isCustom);
}

function toggleCustomStartEnd() {
  const modeEl = $("mode");
  if (!modeEl) return;
  const mode = modeEl.value;
  const isCustom = mode === "custom";
  $("customStart")?.classList.toggle("hide", !isCustom);
  $("customEnd")?.classList.toggle("hide", !isCustom);
}

$("mode")?.addEventListener("change", toggleMode);
$("subtitle_font_select")?.addEventListener("change", toggleFont);
$("url")?.addEventListener("input", debounce(preview, 500));
$("scanBtn")?.addEventListener("click", scan);
$("clipBtn")?.addEventListener("click", clip);
$("segSelectAllBtn")?.addEventListener("click", selectAllSegments);
$("segClearBtn")?.addEventListener("click", clearSelectedSegments);
$("segCreateBtn")?.addEventListener("click", clipSelected);
$("scanCancelBtn")?.addEventListener("click", cancelScan);
$("modalClose")?.addEventListener("click", closeModal);
$("modalBackdrop")?.addEventListener("click", closeModal);
$("langId")?.addEventListener("click", () => setLang("id"));
$("langEn")?.addEventListener("click", () => setLang("en"));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeModal();
});
$("url")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("scanBtn")?.click();
  });

  $("refreshGalleryBtn")?.addEventListener("click", () => {
    loadGallery();
  });


currentLang = localStorage.getItem("lang") || document.documentElement.lang || "id";
currentLang = currentLang === "en" ? "en" : "id";
applyI18n();
loadSettings();
loadGallery();
bindSettingsAutosave();
toggleMode();
toggleFont();
renderSegments([]);
