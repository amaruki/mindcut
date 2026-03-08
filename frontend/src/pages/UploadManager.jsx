import React, { useState, useEffect, useRef } from 'react';

function formatBytes(bytes) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function getNextOptimalUSTime() {
  const pad = n => n.toString().padStart(2, '0');
  const EST_OFFSET = -5;
  const OPTIMAL_HOURS_EST = [9, 14, 17];
  const now = new Date();
  const nowUtc = now.getTime() + now.getTimezoneOffset() * 60000;

  for (const estHour of OPTIMAL_HOURS_EST) {
    const utcHour = estHour - EST_OFFSET;
    const candidate = new Date(nowUtc);
    candidate.setUTCHours(utcHour, 0, 0, 0);
    const local = new Date(candidate.getTime() - now.getTimezoneOffset() * 60000);
    if (local > now) {
      return `${local.getFullYear()}-${pad(local.getMonth()+1)}-${pad(local.getDate())}T${pad(local.getHours())}:${pad(local.getMinutes())}`;
    }
  }
  const tomorrow = new Date(nowUtc + 86400000);
  const utcHour = OPTIMAL_HOURS_EST[0] - EST_OFFSET;
  tomorrow.setUTCHours(utcHour, 0, 0, 0);
  const local = new Date(tomorrow.getTime() - now.getTimezoneOffset() * 60000);
  return `${local.getFullYear()}-${pad(local.getMonth()+1)}-${pad(local.getDate())}T${pad(local.getHours())}:${pad(local.getMinutes())}`;
}

export default function UploadManager() {
  const [clips, setClips] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [currentClip, setCurrentClip] = useState(null);
  
  const [status, setStatus] = useState("");
  const [statusType, setStatusType] = useState("info");

  const [loadingClips, setLoadingClips] = useState(true);
  const [formDisabled, setFormDisabled] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);

  // Form State
  const [metaAccount, setMetaAccount] = useState("");
  const [metaTitle, setMetaTitle] = useState("");
  const [metaDesc, setMetaDesc] = useState("");
  const [metaTags, setMetaTags] = useState("");
  const [metaPrivacy, setMetaPrivacy] = useState("private");
  const [metaDate, setMetaDate] = useState("");
  const [metaAiPrompt, setMetaAiPrompt] = useState("");
  const [collapsedGroups, setCollapsedGroups] = useState({});

  const videoRef = useRef(null);

  useEffect(() => {
    loadAccounts();
    loadClips();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (currentClip && videoRef.current) {
      videoRef.current.src = `/clips/${currentClip.job_id}/${currentClip.filename}`;
      videoRef.current.load();
    }
  }, [currentClip]);

  const showStatus = (text, type = "info") => {
    setStatus(text);
    setStatusType(type);
  };

  const loadAccounts = async () => {
    try {
      const res = await fetch("/api/youtube/accounts");
      const data = await res.json();
      if (data.ok && data.accounts) {
        setAccounts(data.accounts);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const loadClips = async () => {
    setLoadingClips(true);
    try {
      const res = await fetch("/api/gallery");
      const data = await res.json();
      if (data.ok) {
        setClips(data.groups || []);
        // Init collapsed state from localStorage
        const clps = {};
        (data.groups || []).forEach(g => {
          clps[g.job_id] = localStorage.getItem(`group_${g.job_id}_collapsed`) === "true";
        });
        setCollapsedGroups(clps);
      }
    } catch (err) {
      console.error(err);
      showStatus("Failed to load clips", "error");
    } finally {
      setLoadingClips(false);
    }
  };

  const toggleGroup = (jobId) => {
    setCollapsedGroups(prev => {
      const isCollapsed = !prev[jobId];
      localStorage.setItem(`group_${jobId}_collapsed`, isCollapsed);
      return { ...prev, [jobId]: isCollapsed };
    });
  };

  const deleteGroup = async (jobId, e) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete the ENTIRE folder: ${jobId}?\nThis will delete all clips within it.`)) return;
    try {
      showStatus("Deleting folder...");
      const res = await fetch("/api/gallery/delete-group", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId })
      });
      const data = await res.json();
      if (data.ok) {
        showStatus("Folder deleted", "success");
        if (currentClip && currentClip.job_id === jobId) setCurrentClip(null);
        await loadClips();
      } else {
        showStatus(`Failed to delete folder: ${data.error}`, "error");
      }
    } catch (err) {
      showStatus(`Error: ${err.message}`, "error");
    }
  };

  const deleteClip = async (jobId, filename, e) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete ${filename}?`)) return;
    try {
      showStatus("Deleting clip...");
      const res = await fetch("/api/gallery/delete", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId, filename })
      });
      const data = await res.json();
      if (data.ok) {
        showStatus("Clip deleted", "success");
        if (currentClip && currentClip.job_id === jobId && currentClip.filename === filename) setCurrentClip(null);
        await loadClips();
      } else {
        showStatus(`Failed to delete: ${data.error}`, "error");
      }
    } catch (err) {
      showStatus(`Error: ${err.message}`, "error");
    }
  };

  const selectClip = async (clip) => {
    setCurrentClip(clip);
    setMetaTitle("");
    setMetaDesc("");
    setMetaTags("");
    setMetaPrivacy("private");
    setMetaDate(getNextOptimalUSTime());
    setMetaAiPrompt("");
    
    showStatus("Loading metadata...");
    setFormDisabled(true);

    try {
      const res = await fetch(`/api/clips/metadata?job_id=${clip.job_id}&filename=${encodeURIComponent(clip.filename)}`);
      const data = await res.json();
      if (data.ok && data.metadata) {
        const pub = data.metadata.publishing || {};
        const m = data.metadata;

        const titleVariants = Array.isArray(pub.title_variants) ? pub.title_variants : [];
        const aiTitle = titleVariants.length > 0 ? titleVariants[0] : (pub.core_title || m.suggested_clip_title || "My Short Video");
        
        setMetaTitle(m.title || aiTitle);
        setMetaDesc(m.description || pub.core_description || "");
        
        let tags = m.tags || pub.tags || [];
        if (tags.length === 0 && pub.platforms?.youtube_shorts?.tags) {
            tags = pub.platforms.youtube_shorts.tags;
        }
        setMetaTags(Array.isArray(tags) ? tags.join(", ") : (tags || ""));
        setMetaPrivacy(m.privacy || "private");
        
        if (m.publish_at) {
          try {
            const dt = new Date(m.publish_at);
            const pad = n => n.toString().padStart(2, '0');
            setMetaDate(`${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`);
          } catch(e) {
            console.error(e);
          }
        }
        showStatus("Metadata loaded.", "success");
      } else {
        showStatus("No metadata found for this clip. Try auto-generating it.");
      }
    } catch (err) {
      showStatus(`Error loading metadata: ${err.message}`, "error");
    } finally {
      setFormDisabled(false);
    }
  };

  const linkAccount = async () => {
    setActionLoading("link");
    showStatus("Please check the opened browser to link your YouTube account...", "info");
    try {
      const res = await fetch("/api/youtube/accounts/link", { method: "POST" });
      const data = await res.json();
      if (data.ok) {
        showStatus(`Successfully linked channel: ${data.account.title}`, "success");
        await loadAccounts();
        setMetaAccount(data.account.id);
      } else {
        showStatus(`Failed to link account: ${data.error}`, "error");
      }
    } catch (err) {
      showStatus(`Error linking account: ${err.message}`, "error");
    } finally {
      setActionLoading(null);
    }
  };

  const saveMetadata = async () => {
    if (!currentClip) return;
    setActionLoading("save");
    showStatus("Saving...", "info");
    
    const tagsArr = metaTags.split(",").map(t => t.trim()).filter(t => t.length > 0);
    const payload = {
      job_id: currentClip.job_id,
      filename: currentClip.filename,
      metadata: {
        title: metaTitle,
        description: metaDesc,
        tags: tagsArr,
        privacy: metaPrivacy,
        publish_at: metaDate ? new Date(metaDate).toISOString() : null,
      }
    };
    
    try {
      const res = await fetch("/api/clips/metadata/save", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.ok) {
        showStatus("Saved successfully.", "success");
        setClips(prev => {
          const newClips = [...prev];
          for(const g of newClips) {
            if (g.job_id === currentClip.job_id) {
              const c = g.items.find(x => x.filename === currentClip.filename);
              if (c) c.has_metadata = true;
            }
          }
          return newClips;
        });
      } else {
        showStatus(`Failed to save: ${data.error}`, "error");
      }
    } catch (err) {
      showStatus(`Error saving: ${err.message}`, "error");
    } finally {
      setActionLoading(null);
    }
  };

  const generateMetadata = async () => {
    if (!currentClip) return;
    setActionLoading("generate");
    setFormDisabled(true);
    showStatus("Generating AI metadata...", "info");
    try {
      const res = await fetch("/api/clips/metadata/generate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: currentClip.job_id, filename: currentClip.filename, custom_prompt: metaAiPrompt })
      });
      const data = await res.json();
      if (data.ok && data.metadata) {
        const meta = data.metadata;
        const titleVariants = Array.isArray(meta.title_variants) ? meta.title_variants : [];
        const aiTitle = titleVariants.length > 0 ? titleVariants[0] : (meta.core_title || "My Short Video");
        
        setMetaTitle(meta.title || aiTitle);
        setMetaDesc(meta.description || meta.core_description || "");
        
        let tags = meta.tags || [];
        if (tags.length === 0 && meta.platforms?.youtube_shorts?.tags) {
            tags = meta.platforms.youtube_shorts.tags;
        }
        setMetaTags(Array.isArray(tags) ? tags.join(", ") : (tags || ""));
        showStatus("AI metadata generated successfully!", "success");
        
        setClips(prev => {
          const newClips = [...prev];
          for(const g of newClips) {
            if (g.job_id === currentClip.job_id) {
              const c = g.items.find(x => x.filename === currentClip.filename);
              if (c) c.has_metadata = true;
            }
          }
          return newClips;
        });
      } else {
        throw new Error(data.error);
      }
    } catch (err) {
      showStatus(`Failed to generate: ${err.message}`, "error");
    } finally {
      setFormDisabled(false);
      setActionLoading(null);
    }
  };

  const uploadToYouTube = async () => {
    if (!currentClip) return;
    await saveMetadata();
    setActionLoading("upload");
    setFormDisabled(true);
    showStatus("Uploading to YouTube...", "info");
    
    const tagsArr = metaTags.split(",").map(t => t.trim()).filter(t => t.length > 0);
    const pubDate = metaDate ? new Date(metaDate).toISOString() : null;
    
    const payload = {
      job_id: currentClip.job_id,
      filename: currentClip.filename,
      title: metaTitle || "My Short Video",
      description: metaDesc || "",
      tags: tagsArr,
      privacy: metaPrivacy || "private",
      publish_at: pubDate,
      account_id: metaAccount
    };
    
    try {
      const res = await fetch("/api/youtube/upload", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.ok) {
        showStatus(`Upload complete! YouTube Video ID: ${data.youtube_id}`, "success");
        setClips(prev => {
          const newClips = [...prev];
          for(const g of newClips) {
            if (g.job_id === currentClip.job_id) {
              const c = g.items.find(x => x.filename === currentClip.filename);
              if (c) c.is_uploaded = true;
            }
          }
          return newClips;
        });
        setCurrentClip(prev => ({...prev, is_uploaded: true}));
      } else {
        throw new Error(data.error || "Unknown upload error");
      }
    } catch (err) {
      showStatus(`Upload failed: ${err.message}`, "error");
    } finally {
      setFormDisabled(false);
      setActionLoading(null);
    }
  };

  const addHookIntro = async () => {
    if (!currentClip) return;
    setActionLoading("hook");
    showStatus("Generating hook intro (extracting face frame, TTS, etc)...", "info");

    try {
      const voice = localStorage.getItem('yt_config_hook_voice') || 'en-US-GuyNeural';
      const rate = localStorage.getItem('yt_config_hook_voice_rate') || '+15%';
      const pitch = localStorage.getItem('yt_config_hook_voice_pitch') || '+5Hz';
      const fontSize = localStorage.getItem('yt_config_hook_font_size') || '72';

      const res = await fetch('/api/clips/hook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: currentClip.job_id,
          filename: currentClip.filename,
          voice: voice,
          rate: rate,
          pitch: pitch,
          font_size: fontSize
        })
      });
      const data = await res.json();
      if (data.ok) {
        showStatus("Hook intro added successfully!", "success");
        // Reload video source to show new hook
        if (videoRef.current) {
          const t = new Date().getTime();
          videoRef.current.src = `/clips/${currentClip.job_id}/${currentClip.filename}?t=${t}`;
        }
      } else {
        throw new Error(data.error || "Unknown error");
      }
    } catch (e) {
      showStatus("Error: " + e.message, "error");
    } finally {
      setActionLoading(null);
    }
  };

  return (
    <main className="grid grid-cols-[350px_1fr] flex-1 overflow-hidden">
      
      {/* LEFT SIDEBAR: CLIP LIST */}
      <aside className="bg-bg-panel/40 backdrop-blur-md border-r border-border-main p-4 flex flex-col gap-4 overflow-y-auto custom-scrollbar">
        <div className="flex justify-between items-baseline mb-4">
          <div className="font-semibold text-[15px]">Clips Gallery</div>
          <button onClick={loadClips} className="bg-transparent text-fg border border-border-main rounded-lg py-1.5 px-3 font-semibold text-xs hover:bg-white/5 cursor-pointer transition-colors">Refresh</button>
        </div>

        <div className="flex flex-col gap-2">
          {loadingClips ? (
             <div className="text-xs text-center p-5 text-fg-muted">Loading clips...</div>
          ) : clips.length === 0 ? (
             <div className="text-xs text-center p-5 text-fg-muted">No clips found.</div>
          ) : (
            clips.map(group => (
              <div key={group.job_id} className={`bg-bg-panel rounded-lg border border-border-main overflow-hidden ${collapsedGroups[group.job_id] ? 'collapsed' : ''}`}>
                <div onClick={() => toggleGroup(group.job_id)} className={`p-2.5 bg-white/5 cursor-pointer flex justify-between items-center ${collapsedGroups[group.job_id] ? '' : 'border-b border-border-main'}`}>
                  <div className="flex gap-2 items-center">
                    <svg className={`w-3 h-3 transition-transform duration-200 ${collapsedGroups[group.job_id] ? '-rotate-90' : 'rotate-0'}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    <span className="font-semibold text-[13px]">{group.job_id}</span>
                  </div>
                  <div className="flex gap-3 items-center">
                    <span className="text-[11px] text-fg-muted opacity-60">{group.items.length} clips</span>
                    <button className="bg-transparent border-none text-fg-muted cursor-pointer text-base p-1 hover:text-white" title="Delete Folder" onClick={(e) => deleteGroup(group.job_id, e)}>
                       ✕
                    </button>
                  </div>
                </div>
                {!collapsedGroups[group.job_id] && (
                  <div className="p-2 flex flex-col gap-1">
                    {group.items.map(clip => {
                      const isActive = currentClip && currentClip.job_id === clip.job_id && currentClip.filename === clip.filename;
                      return (
                        <div 
                          key={clip.filename} 
                          className={`p-2.5 rounded-lg cursor-pointer flex justify-between items-center border ${isActive ? 'bg-accent/10 border-accent' : 'bg-white/5 border-border-main'}`}
                          onClick={() => selectClip(clip)}
                        >
                          <div>
                            <div className="font-semibold text-[13px] mb-0.5 max-w-[180px] whitespace-nowrap overflow-hidden text-ellipsis">{clip.filename}</div>
                            <div className="text-[11px] text-fg-muted flex gap-1.5">
                              <span>{formatBytes(clip.size)}</span>
                              <span>•</span>
                              <span>{new Date(clip.created * 1000).toLocaleDateString()}</span>
                            </div>
                          </div>
                          <div className="flex gap-2 items-center">
                            {clip.is_uploaded ? <span className="text-[10px] px-1.5 py-0.5 rounded border border-success text-success">Uploaded</span> :
                             clip.has_metadata ? <span className="text-[10px] px-1.5 py-0.5 rounded border border-accent text-accent">Ready</span> :
                             <span className="text-[10px] px-1.5 py-0.5 rounded border border-fg-muted text-fg-muted">New</span>}
                            <button className="bg-transparent border-none text-fg-muted cursor-pointer text-base p-1 hover:text-white" title="Delete Clip" onClick={(e) => deleteClip(clip.job_id, clip.filename, e)}>✕</button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </aside>

      {/* RIGHT WORKSPACE: EDITOR */}
      {currentClip ? (
        <section className="p-6 grid grid-cols-[minmax(300px,1fr)_380px] gap-6 items-start overflow-y-auto custom-scrollbar">
          
          <div className="bg-black rounded-xl overflow-hidden shadow-[0_10px_30px_rgba(0,0,0,0.5)] border border-border-main aspect-[9/16] max-h-[80vh] mx-auto w-full max-w-[450px]">
            <video ref={videoRef} controls playsInline className="w-full h-full object-contain"></video>
          </div>

          <div className="bg-bg-panel/65 border border-border-main rounded-2xl p-6 flex flex-col gap-4 backdrop-blur-md shadow-md">
            <div className="flex justify-between items-baseline m-0">
              <div className="font-semibold text-[15px]">Publishing Metadata</div>
            </div>

            <div className="flex flex-col gap-1.5 mt-2">
              <div className="flex justify-between items-center">
                <label className="text-fg-muted text-xs font-medium">YouTube Channel</label>
                <button onClick={linkAccount} disabled={formDisabled || actionLoading === 'link'} className="bg-transparent text-fg border border-border-main rounded-lg py-1.5 px-3 font-semibold text-xs hover:bg-white/5 cursor-pointer transition-colors disabled:opacity-50 inline-flex items-center justify-center">Link New Channel</button>
              </div>
              <select value={metaAccount} onChange={e => setMetaAccount(e.target.value)} disabled={formDisabled} className="mt-1 w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none">
                {accounts.length > 0 ? accounts.map(a => <option key={a.id} value={a.id}>{a.title}</option>) : <option value="">No channels linked</option>}
              </select>
            </div>

            <hr className="border-none border-t border-border-main my-1" />

            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between items-center">
                <label className="text-fg-muted text-xs font-medium">AI Auto-Generate</label>
                <button onClick={generateMetadata} disabled={formDisabled || actionLoading === 'generate'} className="bg-transparent text-fg border border-border-main rounded-lg py-1.5 px-3 font-semibold text-xs hover:bg-white/5 cursor-pointer transition-colors disabled:opacity-50 inline-flex items-center justify-center">Re-Generate with AI</button>
              </div>
              <input value={metaAiPrompt} onChange={e => setMetaAiPrompt(e.target.value)} disabled={formDisabled} className="mt-1 w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" placeholder="Custom AI instructions..." />
            </div>

            <hr className="border-none border-t border-border-main my-1" />

            <div className="flex flex-col gap-1.5">
              <label className="text-fg-muted text-xs font-medium">Title</label>
              <input value={metaTitle} onChange={e => setMetaTitle(e.target.value)} disabled={formDisabled} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" placeholder="Video Title" />
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-fg-muted text-xs font-medium">Description</label>
              <textarea value={metaDesc} onChange={e => setMetaDesc(e.target.value)} disabled={formDisabled} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25 min-h-[80px] resize-y" placeholder="Video Description..."></textarea>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-fg-muted text-xs font-medium">Tags (comma separated)</label>
              <input value={metaTags} onChange={e => setMetaTags(e.target.value)} disabled={formDisabled} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none placeholder:text-white/25" placeholder="Shorts, Gaming, Trending" />
              <div className="text-[11px] text-fg-muted mt-1 leading-relaxed">Tags will be added as #hashtags — first in title (if space), then in description.</div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-fg-muted text-xs font-medium">Privacy</label>
                <select value={metaPrivacy} onChange={e => setMetaPrivacy(e.target.value)} disabled={formDisabled} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none">
                  <option value="private">Private</option>
                  <option value="unlisted">Unlisted</option>
                  <option value="public">Public</option>
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-fg-muted text-xs font-medium">Schedule (Optional)</label>
                <input type="datetime-local" value={metaDate} onChange={e => setMetaDate(e.target.value)} disabled={formDisabled} className="w-full bg-white/5 border border-border-main text-fg rounded-lg py-2.5 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none" />
              </div>
            </div>

            <div className="flex flex-col gap-2 mt-4">
              <button onClick={saveMetadata} disabled={formDisabled || actionLoading === 'save'} className="bg-gradient-to-br from-violet-600 to-pink-600 text-white hover:from-violet-500 hover:to-rose-500 hover:-translate-y-0.5 hover:shadow-[0_6px_16px_rgba(139,92,246,0.4)] border-none rounded-lg py-2.5 px-4 font-semibold text-[13px] cursor-pointer transition-all duration-300 inline-flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed">
                {actionLoading === 'save' ? 'Saving...' : 'Save Metadata'}
              </button>
              <button onClick={addHookIntro} disabled={formDisabled || actionLoading === 'hook'} className="bg-transparent text-fg border border-border-main rounded-lg py-2.5 px-4 font-semibold text-[13px] hover:bg-white/5 cursor-pointer disabled:opacity-50 inline-flex items-center justify-center">
                {actionLoading === 'hook' ? 'Processing...' : 'Add Hook Intro'}
              </button>
              <button 
                onClick={uploadToYouTube} 
                disabled={formDisabled || actionLoading === 'upload' || currentClip?.is_uploaded} 
                className={`text-white border-none rounded-lg py-2.5 px-4 font-semibold text-[13px] transition-all inline-flex items-center justify-center ${currentClip?.is_uploaded ? 'bg-success opacity-50 cursor-not-allowed' : 'bg-red-500 hover:bg-red-400 cursor-pointer'}`}
              >
                {currentClip?.is_uploaded ? 'Already Uploaded ✓' : actionLoading === 'upload' ? 'Uploading...' : 'Upload to YouTube'}
              </button>
            </div>

            <div className={`text-[13px] text-center p-2 ${statusType === 'error' ? 'text-red-400' : statusType === 'success' ? 'text-success' : 'text-fg-muted'}`}>
              {status}
            </div>
          </div>
        </section>
      ) : (
        <section className="flex items-center justify-center text-fg-muted">
          Select a clip from the list to view and manage it.
        </section>
      )}
    </main>
  );
}
