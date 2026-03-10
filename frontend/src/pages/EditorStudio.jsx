import React, { useState, useEffect, useRef } from 'react';

// Helpers
function formatTime(s) {
  const sec = Math.max(0, Math.floor(Number(s) || 0));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const r = sec % 60;
  if (h > 0) return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

function clamp(n, a, b) {
  return Math.min(b, Math.max(a, n));
}

function easeOutCubic(x) {
  const t = clamp(x, 0, 1);
  return 1 - Math.pow(1 - t, 3);
}

function stageLabel(stage) {
  const map = {
    download: "Download",
    crop: "Crop",
    subtitle: "Subtitle",
    subtitle_model_load: "Load model",
    subtitle_transcribe: "Transcribe",
    subtitle_write: "Write subtitles",
    burn_subtitle: "Burn subtitle",
    hook: "Hook Intro",
    finalize: "Finalize",
    done_clip: "Done",
  };
  return map[stage] || stage || "";
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

export default function EditorStudio() {
  const [url, setUrl] = useState(() => sessionStorage.getItem('es_url') || "");
  const [mode, setMode] = useState(localStorage.getItem("yt_config_mode") || "heatmap");
  const [cookiesBrowser, setCookiesBrowser] = useState(localStorage.getItem("yt_config_cookies_browser") || "");
  const [customStart, setCustomStart] = useState(() => sessionStorage.getItem('es_customStart') || "");
  const [customEnd, setCustomEnd] = useState(() => sessionStorage.getItem('es_customEnd') || "");
  
  const [preview, setPreview] = useState(() => {
    const v = sessionStorage.getItem('es_preview');
    return v && v !== "undefined" ? JSON.parse(v) : null;
  });
  const [busy, setBusy] = useState(false);
  
  // Scan State
  const [scanJobId, setScanJobId] = useState(() => sessionStorage.getItem('es_scanJobId') || "");
  const [scanProgress, setScanProgress] = useState(null); // { pct, text }
  const [segments, setSegments] = useState(() => {
    const v = sessionStorage.getItem('es_segments');
    return v && v !== "undefined" ? JSON.parse(v) : [];
  });
  const [selectedSegments, setSelectedSegments] = useState(() => {
    const v = sessionStorage.getItem('es_selectedSegments');
    return v && v !== "undefined" ? new Set(JSON.parse(v)) : new Set();
  });
  const [metadata, setMetadata] = useState(() => {
    const v = sessionStorage.getItem('es_metadata');
    return v && v !== "undefined" ? JSON.parse(v) : null;
  });
  const [scanWarning, setScanWarning] = useState(() => sessionStorage.getItem('es_scanWarning') || "");
  
  // Clip Job State
  const [clipJob, setClipJob] = useState(null);
  const [gallery, setGallery] = useState([]);

  // Modal State
  const [modalContent, setModalContent] = useState(null); // { title, element }

  // Persist State to Session Storage
  useEffect(() => {
    sessionStorage.setItem('es_url', url);
    sessionStorage.setItem('es_customStart', customStart);
    sessionStorage.setItem('es_customEnd', customEnd);
    sessionStorage.setItem('es_preview', JSON.stringify(preview));
    sessionStorage.setItem('es_scanJobId', scanJobId);
    sessionStorage.setItem('es_segments', JSON.stringify(segments));
    sessionStorage.setItem('es_selectedSegments', JSON.stringify(Array.from(selectedSegments)));
    sessionStorage.setItem('es_metadata', JSON.stringify(metadata));
    sessionStorage.setItem('es_scanWarning', scanWarning);
  }, [url, customStart, customEnd, preview, scanJobId, segments, selectedSegments, metadata, scanWarning]);

  useEffect(() => {
    localStorage.setItem("yt_config_mode", mode);
  }, [mode]);

  useEffect(() => {
    localStorage.setItem("yt_config_cookies_browser", cookiesBrowser);
  }, [cookiesBrowser]);

  const debounceTimer = useRef(null);
  useEffect(() => {
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    if (!url) {
      setPreview(null);
      return;
    }
    debounceTimer.current = setTimeout(() => {
      fetchPreview(url);
    }, 500);
  }, [url]);

  useEffect(() => {
    loadGallery();
  }, []);

  const fetchPreview = async (videoUrl) => {
    try {
      setPreview((prev) => ({ ...prev, loading: true, title: "Loading preview..." }));
      const res = await fetch("/api/preview", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: videoUrl })
      });
      const data = await res.json();
      if (data.ok && data.preview) {
        setPreview(data.preview);
      } else {
        setPreview(null);
      }
    } catch {
      setPreview(null);
    }
  };

  const loadGallery = async () => {
    try {
      const res = await fetch("/api/gallery");
      const data = await res.json();
      if (data.ok && data.items) {
        setGallery(data.items);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const readPayload = () => {
    const defaults = {
      ratio: "9:16", crop: "default", padding: 10, max_clips: 6,
      subtitle: "y", whisper_model: "small", subtitle_font_select: "Plus Jakarta Sans",
      subtitle_font_custom: "", subtitle_location: "bottom", subtitle_fontsdir: "fonts",
      ai_api_url: "", ai_model: "gpt-4o", ai_api_key: "", ai_prompt: "", ai_metadata_prompt: "",
      hook_enabled: "y", hook_voice: "en-US-GuyNeural", hook_voice_rate: "+15%", hook_voice_pitch: "+5Hz", hook_font_size: 72
    };
    const getVal = (id) => {
      const l = localStorage.getItem(`yt_config_${id}`);
      return l !== null ? l : defaults[id];
    };
    
    const fontSel = getVal("subtitle_font_select");
    const fontCustom = (getVal("subtitle_font_custom") || "").trim();
    const subtitleFont = fontSel === "custom" ? fontCustom : fontSel;
    
    return {
      url: url.trim(),
      mode,
      ratio: getVal("ratio"),
      crop: getVal("crop"),
      padding: Number(getVal("padding") || 0),
      max_clips: Number(getVal("max_clips") || 6),
      subtitle: getVal("subtitle") === "y",
      whisper_model: getVal("whisper_model"),
      subtitle_font: subtitleFont,
      subtitle_location: getVal("subtitle_location"),
      subtitle_fontsdir: getVal("subtitle_fontsdir") || "",
      start: customStart,
      end: customEnd,
      ai_api_url: getVal("ai_api_url") || "",
      ai_model: getVal("ai_model") || "",
      ai_api_key: getVal("ai_api_key") || "",
      ai_prompt: getVal("ai_prompt") || "",
      ai_metadata_prompt: getVal("ai_metadata_prompt") || "",
      cookies_browser: cookiesBrowser,
      hook_enabled: getVal("hook_enabled") === "y",
      hook_voice: getVal("hook_voice"),
      hook_voice_rate: getVal("hook_voice_rate"),
      hook_voice_pitch: getVal("hook_voice_pitch"),
      hook_font_size: Number(getVal("hook_font_size") || 72),
      video_title: preview ? preview.title : ""
    };
  };

  // --- Scan Flow ---
  const startScan = async () => {
    if (!url) return;
    setBusy(true);
    setSegments([]);
    setMetadata(null);
    setScanWarning("");
    setSelectedSegments(new Set());
    
    try {
      const payload = readPayload();
      const res = await fetch("/api/scan/start", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error);
      
      setScanJobId(data.job_id);
      pollScan(data.job_id);
    } catch (e) {
      alert(e.message);
      setBusy(false);
    }
  };

  const cancelScan = async () => {
    if (!scanJobId) return;
    try {
      await fetch(`/api/scan/cancel/${scanJobId}`, { method: "POST" });
    } catch (e) { console.error(e); }
  };

  const pollScan = async (jobId) => {
    const started = Date.now();
    let isDone = false;
    
    while (!isDone) {
      try {
        const res = await fetch(`/api/scan/job/${jobId}`);
        const data = await res.json();
        if (!data || !data.ok) throw new Error("Job not found");
        
        const job = data.job || {};
        const pct = Math.max(0, Math.min(100, Number(job.pct || 0)));
        let stage = scanStageLabel(job.stage);
        if (job.stage === "download" && job.dl_pct > 0) {
            stage += ` ${job.dl_pct}% ${job.dl_speed ? `(${job.dl_speed})` : ''}`;
        }
        
        setScanProgress({ pct, text: `${Math.round(pct)}% • ${stage}` });
        
        if (job.status === "done") {
          const result = job.result || {};
          const segs = result.segments || [];
          segs.forEach((s, idx) => s.original_index = idx + 1);
          setSegments(segs);
          setMetadata(result.metadata || null);
          setScanWarning(result.warning || "");
          setBusy(false);
          setScanJobId("");
          setTimeout(() => setScanProgress(null), 1200);
          isDone = true;
          return;
        }
        
        if (job.status === "error" || job.status === "cancelled") {
          setScanWarning(job.status === "error" ? (job.error || "Error") : "Scan cancelled");
          setBusy(false);
          setScanJobId("");
          setTimeout(() => setScanProgress(null), 1200);
          isDone = true;
          return;
        }
        
        if (Date.now() - started > 1000 * 60 * 30) throw new Error("Timeout");
        await new Promise(r => setTimeout(r, 800));
      } catch (e) {
        setScanWarning(`Error polling scan: ${e.message}`);
        setBusy(false);
        setScanJobId("");
        setTimeout(() => setScanProgress(null), 1200);
        isDone = true;
      }
    }
  };

  // --- Clip Flow ---
  const extractCookies = async () => {
    if (!cookiesBrowser || cookiesBrowser === "none") {
      alert("Please select a browser to extract cookies from first.");
      return;
    }
    setBusy(true);
    try {
      const res = await fetch("/api/settings/extract-cookies", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ browser: cookiesBrowser })
      });
      const data = await res.json();
      alert(data.message || "Cookies extracted successfully.");
    } catch (e) {
      alert("Error extracting cookies: " + e.message);
    } finally {
      setBusy(false);
    }
  };

  const startClip = async (isManual = false) => {
    if (!url) return;
    if (!isManual && segments.length > 0 && selectedSegments.size === 0 && mode !== "custom") return;
    
    setBusy(true);
    setClipJob({ status: "queued", total: 0, done: 0 }); // Initial render
    
    try {
      const payload = readPayload();
      const body = { ...payload };
      if (!isManual && mode !== "custom") {
        body.segments = segments.filter(s => selectedSegments.has(`${s.start}:${s.duration}`));
      }
      
      const res = await fetch("/api/clip", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error);
      
      pollClipJob(data.job_id);
    } catch (e) {
      setClipJob({ status: "error", error: e.message });
      setBusy(false);
    }
  };

  const startSingleClip = async (seg) => {
    setBusy(true);
    setClipJob({ status: "queued", total: 0, done: 0 });
    try {
      const payload = readPayload();
      const res = await fetch("/api/clip", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, segments: [seg] })
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error);
      pollClipJob(data.job_id);
    } catch (e) {
      setClipJob({ status: "error", error: e.message });
      setBusy(false);
    }
  };

  const pollClipJob = async (jobId) => {
    const started = Date.now();
    let isDone = false;
    
    while (!isDone) {
      try {
        const res = await fetch(`/api/job/${jobId}`);
        const data = await res.json();
        if (!data || !data.ok) throw new Error("Job not found");
        
        setClipJob(data.job);
        
        if (data.job.status === "done" || data.job.status === "error") {
          if (data.job.status === "done") loadGallery();
          setBusy(false);
          isDone = true;
          return;
        }
        
        if (Date.now() - started > 1000 * 60 * 30) throw new Error("Timeout");
        await new Promise(r => setTimeout(r, 1000));
      } catch (e) {
         setClipJob({ status: "error", error: e.message });
         setBusy(false);
         isDone = true;
      }
    }
  };

  const segKey = (s) => `${s.start}:${s.duration}`;
  const toggleSegment = (s) => {
    const k = segKey(s);
    setSelectedSegments(prev => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });
  };

  const selectAll = () => setSelectedSegments(new Set(segments.map(segKey)));
  const clearAll = () => setSelectedSegments(new Set());

  // --- Progress Bar Math (Matching App.js computeJobPct) ---
  const getJobProgress = (job) => {
    if (!job) return { pct: 0, active: false, text: "" };
    if (job.status !== "running" && job.status !== "queued") {
      const d = Number(job.done || 0);
      const t = Number(job.total || 0);
      return { pct: t > 0 ? clamp((d / t) * 100, 0, 100) : 0, active: false, text: "" };
    }
    
    const total = Math.max(1, Number(job.total || 1));
    const done = clamp(Number(job.done || 0), 0, total);
    const subtitleEnabled = Boolean(job.subtitle_enabled);
    const stage = job.stage || "";
    const stageAt = job.stage_at ? Number(job.stage_at) : 0;
    const elapsed = stageAt ? Date.now() - stageAt : 0;
    const clipIndex = clamp(Number(job.stage_clip || job.current || (done + 1) || 1), 1, total);
    
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
    const s = table[stage] || table.download;
    let within = s.d > 0 ? s.a + (s.b - s.a) * easeOutCubic(clamp(elapsed / s.d, 0, 0.98)) : s.a;
    let sLabel = stageLabel(stage);
    
    if (stage === "download" && job.dl_pct > 0) {
      within = s.a + (s.b - s.a) * (Number(job.dl_pct) / 100);
      sLabel += ` ${job.dl_pct}% ${job.dl_speed ? `(${job.dl_speed})` : ''}`;
    }
    
    const pctBase = ((clipIndex - 1) + within) / total * 100;
    const pctFloor = (done / total) * 100;
    const pct = clamp(Math.max(pctBase, pctFloor), 0, 99.5);
    
    return { pct, active: true, text: `Processing • clip ${clipIndex}/${total} • ${sLabel}` };
  };

  const topProg = getJobProgress(clipJob);

  // --- Modals ---
  const openPreview = (title, src, isYoutube = false, start = 0, end = 0) => {
    let content;
    if (isYoutube) {
      const u = `https://www.youtube.com/embed/${encodeURIComponent(src)}?start=${start}${end > start ? `&end=${end}` : ""}&autoplay=1&playsinline=1&rel=0`;
      content = <iframe src={u} className="w-full aspect-video border-none" allow="autoplay; encrypted-media; fullscreen" allowFullScreen></iframe>;
    } else {
      content = <video className="w-auto max-w-full max-h-[80vh] object-contain shadow-2xl" src={src} controls autoPlay muted playsInline></video>;
    }
    setModalContent({ title, element: content });
  };

  return (
    <>
      {/* Top Progress Injection */}
      <style dangerouslySetInnerHTML={{__html: `
        .topProgressWrap { display: ${topProg.active || (clipJob && clipJob.status === 'done') ? 'block' : 'none'}; }
        .topProgressFill { width: ${(topProg.active ? topProg.pct : (clipJob && clipJob.status === 'done' ? 100 : 0))}%; }
        .topProgressText { content: "${topProg.text}"; }
      `}} />

      <main className="flex flex-1 overflow-hidden grid-cols-[minmax(300px,340px)_1fr] md:grid">
        
        {/* LEFT SIDEBAR */}
        <aside className="bg-bg-panel/40 backdrop-blur-md border-r border-border-main p-6 flex flex-col gap-6 overflow-y-auto custom-scrollbar">
          
          <div className="bg-bg-panel border border-border-main rounded-xl p-5">
            <div className="text-base font-semibold text-fg mb-4">Project Source</div>
            
            <div className="flex flex-col gap-2 mb-4">
              <label className="text-xs font-semibold text-fg-muted uppercase tracking-wider">YouTube URL</label>
              <input className="bg-white/5 border border-border-main rounded-lg py-2 px-3 text-[13px] text-fg transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none" placeholder="https://www.youtube.com/watch?v=..." value={url} onChange={e => setUrl(e.target.value)} disabled={busy} />
            </div>

            {preview && (
              <div className="flex gap-3 items-center bg-white/5 p-3 rounded-lg mb-4">
                {preview.loading ? (
                  <div className="text-xs text-fg-muted">Mencari video...</div>
                ) : (
                  <>
                   <div className="w-20 h-11 rounded bg-black shrink-0 overflow-hidden">
                     <img src={preview.thumbnail} alt="" className="w-full h-full object-cover" />
                   </div>
                   <div className="flex-1 min-w-0">
                     <div className="text-[13px] font-semibold whitespace-nowrap text-ellipsis overflow-hidden">{preview.title}</div>
                     <div className="text-[11px] text-fg-muted mt-1">{preview.uploader} • {preview.duration !== undefined ? formatTime(preview.duration) : ''}</div>
                   </div>
                  </>
                )}
              </div>
            )}

            <div className="flex flex-col gap-2 mb-4">
              <label className="text-xs font-semibold text-fg-muted uppercase tracking-wider">Browser (Cookies)</label>
              <div className="flex gap-2">
                <select className="bg-white/5 border border-border-main rounded-lg py-2 px-3 text-[13px] text-fg transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none flex-1" value={cookiesBrowser} onChange={e => setCookiesBrowser(e.target.value)} disabled={busy}>
                  <option value="">None (Tanpa login)</option>
                  <option value="chrome">Chrome</option>
                  <option value="edge">Edge</option>
                  <option value="firefox">Firefox</option>
                  <option value="brave">Brave</option>
                  <option value="opera">Opera</option>
                </select>
                <button onClick={extractCookies} disabled={busy} className="bg-white/5 border border-border-main text-fg rounded-lg px-3 h-[38px] hover:bg-white/10 transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed" type="button" title="Save Cookies to file">💾</button>
              </div>
            </div>

            <div className="flex flex-col gap-2 mb-4">
              <label className="text-xs font-semibold text-fg-muted uppercase tracking-wider">Mode</label>
              <select className="bg-white/5 border border-border-main rounded-lg py-2 px-3 text-[13px] text-fg transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none" value={mode} onChange={e => setMode(e.target.value)} disabled={busy}>
                <option value="heatmap">Scan heatmap (Most Replayed)</option>
                <option value="ai">AI Analysis (Transcript)</option>
                <option value="combined">Combined (Heatmap + AI)</option>
                <option value="custom">Custom start/end (manual)</option>
              </select>
            </div>

            {mode === 'custom' && (
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <label className="text-xs font-semibold text-fg-muted uppercase tracking-wider">Start</label>
                  <input className="bg-white/5 border border-border-main rounded-lg py-2 px-3 text-[13px] text-fg transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none" placeholder="00:00" value={customStart} onChange={e => setCustomStart(e.target.value)} disabled={busy} />
                </div>
                <div className="flex flex-col gap-2">
                  <label className="text-xs font-semibold text-fg-muted uppercase tracking-wider">End</label>
                  <input className="bg-white/5 border border-border-main rounded-lg py-2 px-3 text-[13px] text-fg transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none" placeholder="01:00" value={customEnd} onChange={e => setCustomEnd(e.target.value)} disabled={busy} />
                </div>
              </div>
            )}
          </div>

          <div className="bg-bg-panel border border-border-main rounded-xl p-5">
            <div className="text-base font-semibold text-accent mb-4">Controls</div>
            <div className="flex flex-col gap-2">
              {mode !== 'custom' && (
                <>
                  <button onClick={startScan} disabled={busy || !url} className="h-[42px] bg-gradient-to-r from-accent to-accent-hover text-white rounded-lg font-semibold text-sm border-none cursor-pointer transition-all hover:shadow-[0_4px_15px_rgba(139,92,246,0.3)] hover:-translate-y-px disabled:opacity-50 disabled:cursor-not-allowed">Scan Heatmap</button>
                  {scanJobId && <button onClick={cancelScan} className="h-[42px] bg-white/5 border border-border-main text-fg rounded-lg font-semibold text-sm cursor-pointer transition-colors hover:bg-white/10">Cancel Scan</button>}
                </>
              )}
              <button onClick={() => startClip(true)} disabled={busy || !url} className="h-[42px] bg-bg-panel text-accent border border-accent rounded-lg font-semibold text-sm cursor-pointer transition-all hover:bg-accent/10 hover:-translate-y-px hover:shadow-[0_4px_15px_rgba(139,92,246,0.15)] disabled:opacity-50 disabled:cursor-not-allowed disabled:border-border-main disabled:text-fg-muted">Buat Clip (Manual)</button>
            </div>
          </div>
        </aside>

        {/* CENTER WORKSPACE */}
        <section className="flex-1 p-6 overflow-y-auto flex flex-col gap-6 custom-scrollbar">
          
          {scanProgress && (
            <div className="bg-accent/10 border border-accent rounded-lg p-4">
              <div className="h-1.5 bg-white/10 rounded-full overflow-hidden mb-2">
                <div className="h-full bg-accent transition-[width] duration-300 ease-in-out" style={{ width: `${scanProgress.pct}%` }}></div>
              </div>
              <div className="text-xs text-fg text-right">{scanProgress.text}</div>
            </div>
          )}

          {scanWarning && (
            <div className="p-3 bg-red-500/10 border border-error text-error rounded-lg text-[13px]">
              {scanWarning}
            </div>
          )}

          {/* Segments Panel */}
          {mode !== 'custom' && segments.length > 0 && (
            <div className="bg-bg-panel border border-border-main rounded-xl p-6">
              <div className="flex justify-between items-center mb-4 pb-4 border-b border-border-main">
                <div className="text-lg font-semibold">Segments</div>
                <div className="flex gap-4 items-center">
                  <div className="text-xs text-fg-muted">
                    {selectedSegments.size > 0 && <span className="text-accent mr-3">{selectedSegments.size} dipilih</span>}
                    {segments.length} segments found
                  </div>
                  <div className="flex gap-2">
                    <button onClick={selectAll} disabled={busy} className="bg-white/5 border border-border-main text-fg rounded-lg py-1 px-2.5 font-semibold text-[11px] cursor-pointer transition-colors hover:bg-white/10">Select All</button>
                    <button onClick={clearAll} disabled={busy} className="bg-white/5 border border-border-main text-fg rounded-lg py-1 px-2.5 font-semibold text-[11px] cursor-pointer transition-colors hover:bg-white/10">Clear</button>
                    <button onClick={() => startClip(false)} disabled={busy || selectedSegments.size === 0} className="bg-accent text-white border-none rounded-lg py-1 px-2.5 font-semibold text-[11px] cursor-pointer transition-colors hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed">Create Selected</button>
                  </div>
                </div>
              </div>
              
              <div className="flex flex-col gap-2">
                {segments.map((seg, idx) => {
                  const s = seg.start;
                  const e = s + seg.duration;
                  const isSel = selectedSegments.has(segKey(seg));
                  const tmb = preview ? preview.thumbnail : "";
                  
                  return (
                    <div key={idx} className={`flex items-center gap-4 p-3 rounded-lg cursor-pointer transition-all duration-200 ${isSel ? 'bg-accent/15 border-accent' : 'bg-white/5 border-border-main'}`} style={{ border: `1px solid ${isSel ? 'var(--accent)' : 'var(--border)'}` }} onClick={(ev) => { if (ev.target.tagName !== 'BUTTON') toggleSegment(seg); }}>
                      <div className="w-[100px] h-[56px] bg-black rounded shrink-0 relative overflow-hidden">
                        <img src={tmb} alt="" className="w-full h-full object-cover" />
                        <div className="absolute bottom-1 right-1 bg-black/80 text-[10px] py-[2px] px-1 rounded text-white font-medium">{formatTime(s)}</div>
                      </div>
                      <div className="flex-1">
                        <div className="text-sm font-semibold">#{seg.original_index} {formatTime(s)} → {formatTime(e)}</div>
                        <div className="text-xs text-fg-muted mt-1">durasi {Math.round(seg.duration)}s</div>
                      </div>
                      <div className="flex gap-2 items-center">
                        <div className="bg-white/10 py-1 px-2.5 rounded-full text-[11px] font-semibold">{Number(seg.score || 0).toFixed(2)}</div>
                        <button className="bg-transparent text-fg border border-border-main rounded-lg py-1 px-2.5 font-semibold text-[11px] cursor-pointer transition-colors hover:bg-white/5" onClick={(ev) => { ev.stopPropagation(); openPreview(`Segment #${idx+1}`, preview?.id || url, true, Math.floor(s), Math.floor(e)); }}>Preview</button>
                        <button className="bg-transparent text-fg border border-border-main rounded-lg py-1 px-2.5 font-semibold text-[11px] cursor-pointer transition-colors hover:bg-white/5" disabled={busy} onClick={(ev) => { ev.stopPropagation(); startSingleClip(seg); }}>Clip</button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="grid grid-cols-[minmax(300px,1fr)_300px] gap-6">
            {/* Job Tracker Panel */}
            <div className="bg-bg-panel border border-border-main rounded-xl p-6">
              <div className="flex justify-between mb-4">
                <div className="text-base font-semibold">Progress Tracker</div>
                <div className="text-xs text-accent">
                  {clipJob ? `${clipJob.status} ${clipJob.status_text || ''} ${clipJob.stage ? ' • ' + stageLabel(clipJob.stage) : ''}` : ''}
                </div>
              </div>
              
              <div className="flex flex-col">
                {clipJob && (
                  <>
                    <div className="h-1.5 bg-white/10 rounded-full overflow-hidden mb-2">
                      <div className="h-full bg-accent transition-[width] duration-300 ease-in-out" style={{ width: `${getJobProgress(clipJob).active ? getJobProgress(clipJob).pct : (clipJob.total > 0 ? (clipJob.done / clipJob.total) * 100 : 0)}%` }}></div>
                    </div>
                    {getJobProgress(clipJob).active && <div className="text-xs text-fg-muted text-right mb-2">{getJobProgress(clipJob).text}</div>}
                    <div className="text-[11px] text-fg-muted">
                      {clipJob.total > 0 && `${clipJob.done}/${clipJob.total} done • ${clipJob.success || 0} success`}
                    </div>
                    {clipJob.status === "error" && <div className="text-xs text-error mt-2">{clipJob.error}</div>}
                  </>
                )}
              </div>

              {clipJob && clipJob.outputs && clipJob.outputs.length > 0 && (
                <div className="flex flex-col gap-2 mt-4">
                  {clipJob.outputs.map((out, i) => {
                    const href = `/clips/${clipJob.id}/${encodeURIComponent(out.name)}`;
                    return (
                      <div key={i} className="flex justify-between items-center bg-white/5 p-3 rounded-lg">
                         <div>
                           <a href={href} target="_blank" rel="noreferrer" className="text-[13px] font-medium text-fg no-underline hover:text-accent">{out.name}</a>
                           <div className="text-[11px] text-fg-muted mt-1">{Math.round(out.size / 1024)} KB</div>
                         </div>
                         <div className="flex gap-2">
                           <button onClick={() => openPreview(out.name, href)} className="bg-transparent text-fg border border-border-main rounded-lg py-1 px-2.5 font-semibold text-[11px] cursor-pointer transition-colors hover:bg-white/5">Play</button>
                           <a href={href} download className="bg-transparent text-fg border border-border-main rounded-lg py-1 px-2.5 font-semibold text-[11px] cursor-pointer transition-colors hover:bg-white/5 flex items-center justify-center no-underline">↓</a>
                         </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Metadata Panel */}
            {metadata && Object.keys(metadata).length > 0 && (
              <div className="bg-bg-panel border border-border-main rounded-xl p-6">
                <div className="text-base font-semibold mb-4">Publishing Metadata</div>
                <div className="max-h-[400px] overflow-y-auto flex flex-col gap-3 custom-scrollbar pr-2">
                  {metadata.title && <div><div className="text-[11px] text-fg-muted mb-1">Title</div><div className="text-[13px] bg-white/5 p-2 rounded">{metadata.title}</div></div>}
                  {metadata.description && <div><div className="text-[11px] text-fg-muted mb-1">Description</div><div className="text-[13px] bg-white/5 p-2 rounded whitespace-pre-wrap">{metadata.description}</div></div>}
                  {metadata.hashtags && metadata.hashtags.length > 0 && <div><div className="text-[11px] text-fg-muted mb-1">Hashtags</div><div className="text-[13px] text-accent">{metadata.hashtags.map(h => `#${h}`).join(' ')}</div></div>}
                  {metadata.hook && <div><div className="text-[11px] text-fg-muted mb-1">Hook</div><div className="text-[13px] bg-white/5 p-2 rounded">{metadata.hook}</div></div>}
                </div>
              </div>
            )}
          </div>

          {/* Gallery Preview / Fast Reference */}
          <div className="bg-bg-panel border border-border-main rounded-xl p-6">
            <div className="flex justify-between items-center mb-4">
              <div className="text-base font-semibold">Recent Clips</div>
              <button onClick={loadGallery} className="bg-transparent text-fg border border-border-main rounded-lg py-1 px-2.5 font-semibold text-[11px] cursor-pointer transition-colors hover:bg-white/5">Refresh</button>
            </div>
            {gallery.length === 0 ? (
              <div className="text-center p-5 text-[13px] text-fg-muted">No clips generated yet.</div>
            ) : (
              <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
                 {gallery.slice(0, 10).map((item, i) => { // show only last 10
                   const href = `/clips/${item.job_id}/${encodeURIComponent(item.filename)}`;
                   return (
                     <div key={i} className="flex justify-between items-center p-3 bg-white/5 rounded-lg border border-border-main hover:bg-white/10 transition-colors">
                       <div className="overflow-hidden whitespace-nowrap text-ellipsis pr-2.5">
                         <a href={href} target="_blank" rel="noreferrer" className="text-[13px] font-medium text-fg no-underline hover:text-accent">{item.filename}</a>
                         <div className="text-[11px] text-fg-muted mt-1">{Math.round(item.size / 1024)} KB</div>
                       </div>
                       <div className="flex gap-1.5 shrink-0">
                         <button onClick={() => openPreview(item.filename, href)} className="bg-accent text-white border-none rounded py-1 px-2.5 text-[11px] font-semibold cursor-pointer hover:bg-accent-hover transition-colors">Play</button>
                         <a href={href} download className="bg-transparent text-fg border border-border-main rounded py-1 px-2.5 text-[11px] font-semibold cursor-pointer flex items-center justify-center no-underline hover:bg-white/5 transition-colors">↓</a>
                       </div>
                     </div>
                   );
                 })}
              </div>
            )}
            <div className="text-center mt-4">
              <a href="#/upload-manager" className="bg-transparent text-fg font-semibold cursor-pointer border-none text-xs hover:text-accent no-underline transition-colors p-2 inline-block">Open Full Upload Manager →</a>
            </div>
          </div>

        </section>
      </main>

      {/* Modal */}
      {modalContent && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm z-[101]" onClick={() => setModalContent(null)}></div>
          <div className="relative z-[102] w-full max-w-[800px] bg-bg-panel border border-border-main rounded-xl shadow-2xl overflow-hidden flex flex-col translate-y-0 transition-transform duration-300">
            <div className="flex justify-between items-center p-4 border-b border-border-main bg-bg-panel/40">
              <div className="text-[15px] font-semibold text-fg tracking-wide">{modalContent.title}</div>
              <button className="w-8 h-8 rounded-lg flex items-center justify-center text-fg-muted bg-transparent border-none cursor-pointer transition-colors hover:bg-white/10 hover:text-fg text-lg" onClick={() => setModalContent(null)}>✕</button>
            </div>
            <div className="p-0 bg-black overflow-y-auto max-h-[85vh] custom-scrollbar flex items-center justify-center">
              {modalContent.element}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
