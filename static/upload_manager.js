// Upload Manager Frontend Logic

document.addEventListener("DOMContentLoaded", () => {
  const clipList = document.getElementById("clipList");
  const refreshBtn = document.getElementById("refreshBtn");
  const emptyWorkspace = document.getElementById("emptyWorkspace");
  const editorSection = document.getElementById("editorSection");
  
  // Video Elements
  const videoPlayer = document.getElementById("videoPlayer");
  
  // Metadata Form Elements
  const metaTitle = document.getElementById("metaTitle");
  const metaDesc = document.getElementById("metaDesc");
  const metaTags = document.getElementById("metaTags");
  const metaPrivacy = document.getElementById("metaPrivacy");
  const metaDate = document.getElementById("metaDate");
  const metaAiPrompt = document.getElementById("metaAiPrompt");
  const metaAccount = document.getElementById("metaAccount");
  
  // Buttons
  const metaGenerateBtn = document.getElementById("metaGenerateBtn");
  const saveBtn = document.getElementById("saveBtn");
  const uploadBtn = document.getElementById("uploadBtn");
  const linkAccountBtn = document.getElementById("linkAccountBtn");
  
  // Status Bar
  const statusBar = document.getElementById("statusBar");

  let clips = [];
  let currentClip = null;

  async function postJson(url, data) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });
    return res.json();
  }

  function showStatus(text, type = "info") {
    statusBar.textContent = text;
    statusBar.style.color = type === "error" ? "var(--error)" : 
                            type === "success" ? "var(--success)" : "var(--fg-muted)";
  }

  function formatBytes(bytes) {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }

  async function loadClips() {
    clipList.innerHTML = `<div class="small" style="text-align: center; padding: 20px;">Loading clips...</div>`;
    try {
      const res = await fetch("/api/gallery");
      const data = await res.json();
      if (!data.ok) throw new Error(data.error);
      
      clips = data.groups || [];
      renderClipList();
    } catch (err) {
      clipList.innerHTML = `<div class="small" style="color: var(--error); padding: 20px;">Failed to load clips: ${err.message}</div>`;
    }
  }

  async function loadAccounts() {
    try {
      metaAccount.innerHTML = '<option value="" disabled selected>Loading channels...</option>';
      const res = await fetch("/api/youtube/accounts");
      const data = await res.json();
      if (data.ok) {
        if (data.accounts && data.accounts.length > 0) {
          metaAccount.innerHTML = data.accounts.map(acc => 
            `<option value="${acc.id}">${acc.title}</option>`
          ).join("");
        } else {
          metaAccount.innerHTML = '<option value="" disabled selected>No channels linked</option>';
        }
      } else {
          metaAccount.innerHTML = '<option value="" disabled selected>Error loading channels</option>';
      }
    } catch (err) {
      metaAccount.innerHTML = '<option value="" disabled selected>Error loading channels</option>';
    }
  }

  async function linkAccount() {
    showStatus("Please check the opened browser to link your YouTube account...", "info");
    linkAccountBtn.disabled = true;
    try {
      const res = await postJson("/api/youtube/accounts/link", {});
      if (res.ok) {
        showStatus(`Successfully linked channel: ${res.account.title}`, "success");
        await loadAccounts();
        metaAccount.value = res.account.id;
      } else {
        showStatus(`Failed to link account: ${res.error}`, "error");
      }
    } catch (err) {
      showStatus(`Error linking account: ${err.message}`, "error");
    } finally {
      linkAccountBtn.disabled = false;
    }
  }

  function renderClipList() {
    clipList.innerHTML = "";
    if (clips.length === 0) {
      clipList.innerHTML = `<div class="small" style="text-align: center; padding: 20px; color: var(--fg-muted);">No clips found.</div>`;
      return;
    }

    clips.forEach(group => {
      const groupEl = document.createElement("div");
      groupEl.className = "clip-group";
      // Restore collapsed state from local storage or default to expanded
      const isCollapsed = localStorage.getItem(`group_${group.job_id}_collapsed`) === "true";
      if (isCollapsed) groupEl.classList.add("collapsed");
      
      const header = document.createElement("div");
      header.className = "clip-group-header";
      header.onclick = () => toggleGroup(group.job_id, groupEl);

      header.innerHTML = `
        <div class="flex-row">
          <svg class="group-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
          <span style="letter-spacing: 0.5px;">${group.job_id}</span>
        </div>
        <div class="flex-row" style="gap: 12px;">
          <span class="small" style="opacity: 0.6;">${group.items.length} clips</span>
          <div class="header-actions">
            <button class="remove-group-btn" title="Delete Entire Folder" onclick="event.stopPropagation(); deleteGroup('${group.job_id}')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
          </div>
        </div>
      `;
      groupEl.appendChild(header);

      const itemsContainer = document.createElement("div");
      itemsContainer.className = "clip-group-items";

      group.items.forEach(clip => {
        const el = document.createElement("div");
        el.className = "clip-item";
        if (currentClip && currentClip.job_id === clip.job_id && currentClip.filename === clip.filename) {
          el.classList.add("active");
        }
        if (clip.is_uploaded) {
          el.classList.add("uploaded");
        }
        
        let statusHtml = clip.is_uploaded ? `<span class="status-badge">Uploaded</span>` : 
                         clip.has_metadata ? `<span class="status-badge" style="color: var(--accent); border-color: var(--accent);">Ready</span>` : 
                         `<span class="status-badge">New</span>`;

        el.innerHTML = `
          <div class="clip-info">
            <div class="filename" title="${clip.filename}">${clip.filename}</div>
            <div class="size flex-row" style="gap: 6px;">
              <span>${formatBytes(clip.size)}</span>
              <span>•</span>
              <span>${new Date(clip.created * 1000).toLocaleDateString()}</span>
            </div>
          </div>
          <div class="flex-row" style="gap: 8px;">
            ${statusHtml}
            <button class="remove-btn" title="Delete Clip" onclick="event.stopPropagation(); deleteClip('${clip.job_id}', '${clip.filename}')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
            </button>
          </div>
        `;
        
        el.onclick = () => selectClip(clip);
        itemsContainer.appendChild(el);
      });
      
      groupEl.appendChild(itemsContainer);
      clipList.appendChild(groupEl);
    });
  }

  function toggleGroup(jobId, element) {
    element.classList.toggle("collapsed");
    const isCollapsed = element.classList.contains("collapsed");
    localStorage.setItem(`group_${jobId}_collapsed`, isCollapsed);
  }

  async function deleteGroup(jobId) {
    if (!confirm(`Are you sure you want to delete the ENTIRE folder: ${jobId}?\nThis will delete all clips within it.`)) return;
    
    try {
      showStatus("Deleting folder...");
      const res = await postJson("/api/gallery/delete-group", { job_id: jobId });
      if (res.ok) {
        showStatus("Folder deleted", "success");
        // If current clip was in this group, clear editor
        if (currentClip && currentClip.job_id === jobId) {
          currentClip = null;
          editorSection.classList.add("hide");
          emptyWorkspace.classList.remove("hide");
          videoPlayer.src = "";
        }
        await loadClips();
      } else {
        showStatus(`Failed to delete folder: ${res.error}`, "error");
      }
    } catch (err) {
      showStatus(`Error deleting folder: ${err.message}`, "error");
    }
  }

  async function deleteClip(jobId, filename) {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;
    
    try {
      showStatus("Deleting clip...");
      const res = await postJson("/api/gallery/delete", { job_id: jobId, filename: filename });
      if (res.ok) {
        showStatus("Clip deleted", "success");
        if (currentClip && currentClip.job_id === jobId && currentClip.filename === filename) {
          currentClip = null;
          editorSection.classList.add("hide");
          emptyWorkspace.classList.remove("hide");
          videoPlayer.src = "";
        }
        await loadClips();
      } else {
        showStatus(`Failed to delete: ${res.error}`, "error");
      }
    } catch (err) {
      showStatus(`Error deleting: ${err.message}`, "error");
    }
  }

  // Expose to window so it can be called from onclick
  window.deleteClip = deleteClip;
  window.deleteGroup = deleteGroup;
  window.toggleGroup = toggleGroup;

  async function selectClip(clip) {
    currentClip = clip;
    renderClipList(); // update active state in list
    
    emptyWorkspace.classList.add("hide");
    editorSection.classList.remove("hide");
    
    // Load video
    videoPlayer.src = `/clips/${clip.job_id}/${clip.filename}`;
    
    // Reset form
    metaTitle.value = "";
    metaDesc.value = "";
    metaTags.value = "";
    metaPrivacy.value = "private";
    metaDate.value = "";
    metaAiPrompt.value = "";
    showStatus("Loading metadata...");
    
    // Disable inputs while loading
    setFormDisabled(true);
    
    // Fetch Metadata
    try {
      const res = await fetch(`/api/clips/metadata?job_id=${clip.job_id}&filename=${encodeURIComponent(clip.filename)}`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error);
      
      if (data.metadata) {
        // Publishing metadata is nested under "publishing" key from clip generation
        const pub = data.metadata.publishing || {};
        const m = data.metadata;  // top-level (manually saved fields)

        const titleVariants = Array.isArray(pub.title_variants) ? pub.title_variants : [];
        const aiTitle = titleVariants.length > 0 ? titleVariants[0] : (pub.core_title || m.suggested_clip_title || "My Short Video");
        
        metaTitle.value = m.title || aiTitle;
        metaDesc.value = m.description || pub.core_description || "";
        
        let tags = m.tags || pub.tags || [];
        // If empty tags, try platform-specific tags
        if (tags.length === 0 && pub.platforms?.youtube_shorts?.tags) {
            tags = pub.platforms.youtube_shorts.tags;
        }
        metaTags.value = Array.isArray(tags) ? tags.join(", ") : (tags || "");
        
        metaPrivacy.value = m.privacy || "private";
        if (m.publish_at) {
          // Format for datetime-local
          try {
            const dt = new Date(m.publish_at);
            const pad = n => n.toString().padStart(2, '0');
            metaDate.value = `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
          } catch(e) {}
        }
        showStatus("Metadata loaded.", "success");
      } else {
        showStatus("No metadata found for this clip. Try auto-generating it.");
      }
    } catch (err) {
      showStatus(`Error loading metadata: ${err.message}`, "error");
    } finally {
      setFormDisabled(false);
      updateUploadButtonState();
    }
  }

  function setFormDisabled(disabled) {
    metaTitle.disabled = disabled;
    metaDesc.disabled = disabled;
    metaTags.disabled = disabled;
    metaPrivacy.disabled = disabled;
    metaDate.disabled = disabled;
    metaAiPrompt.disabled = disabled;
    metaAccount.disabled = disabled;
    linkAccountBtn.disabled = disabled;
    saveBtn.disabled = disabled;
    metaGenerateBtn.disabled = disabled;
  }
  
  function updateUploadButtonState() {
    if (!currentClip) return;
    if (currentClip.is_uploaded) {
      uploadBtn.textContent = "Already Uploaded ✓";
      uploadBtn.disabled = true;
      uploadBtn.style.opacity = "0.5";
      uploadBtn.style.background = "var(--success)";
    } else {
      uploadBtn.textContent = "Upload to YouTube";
      uploadBtn.disabled = false;
      uploadBtn.style.opacity = "1";
      uploadBtn.style.background = "#ef4444";
    }
  }

  async function saveMetadata() {
    if (!currentClip) return;
    showStatus("Saving...", "info");
    saveBtn.disabled = true;
    
    // Prepare tags
    const tagsArr = metaTags.value.split(",").map(t => t.trim()).filter(t => t.length > 0);
    
    const payload = {
      job_id: currentClip.job_id,
      filename: currentClip.filename,
      metadata: {
        title: metaTitle.value,
        description: metaDesc.value,
        tags: tagsArr,
        privacy: metaPrivacy.value,
        publish_at: metaDate.value ? new Date(metaDate.value).toISOString() : null,
      }
    };
    
    try {
      const res = await postJson("/api/clips/metadata/save", payload);
      if (res.ok) {
        showStatus("Saved successfully.", "success");
        // Update local state so it shows as "ready"
        const idx = clips.findIndex(c => c.job_id === currentClip.job_id && c.filename === currentClip.filename);
        if (idx >= 0 && !clips[idx].has_metadata) {
            clips[idx].has_metadata = true;
            renderClipList();
        }
      } else {
        showStatus(`Failed to save: ${res.error}`, "error");
      }
    } catch (err) {
      showStatus(`Error saving: ${err.message}`, "error");
    } finally {
      saveBtn.disabled = false;
    }
  }

  async function generateMetadata() {
    if (!currentClip) return;
    showStatus("Generating AI metadata...", "info");
    setFormDisabled(true);
    uploadBtn.disabled = true;
    
    try {
      const res = await postJson("/api/clips/metadata/generate", {
        job_id: currentClip.job_id,
        filename: currentClip.filename,
        custom_prompt: metaAiPrompt.value
      });
      
      if (!res.ok) throw new Error(res.error);
      
      const meta = res.metadata;
      if (meta) {
        const titleVariants = Array.isArray(meta.title_variants) ? meta.title_variants : [];
        const aiTitle = titleVariants.length > 0 ? titleVariants[0] : (meta.core_title || "My Short Video");
        
        metaTitle.value = meta.title || aiTitle;
        metaDesc.value = meta.description || meta.core_description || "";
        
        let tags = meta.tags || [];
        if (tags.length === 0 && meta.platforms?.youtube_shorts?.tags) {
            tags = meta.platforms.youtube_shorts.tags;
        }
        metaTags.value = Array.isArray(tags) ? tags.join(", ") : (tags || "");
        
        showStatus("AI metadata generated successfully!", "success");
        
        // Mark as having metadata
        const idx = clips.findIndex(c => c.job_id === currentClip.job_id && c.filename === currentClip.filename);
        if (idx >= 0 && !clips[idx].has_metadata) {
            clips[idx].has_metadata = true;
            renderClipList();
        }
      }
    } catch (err) {
      showStatus(`Failed to generate: ${err.message}`, "error");
    } finally {
      setFormDisabled(false);
      updateUploadButtonState();
    }
  }

  async function uploadToYouTube() {
    if (!currentClip) return;
    
    // Auto-save first
    await saveMetadata();
    
    showStatus("Uploading to YouTube...", "info");
    setFormDisabled(true);
    uploadBtn.disabled = true;
    uploadBtn.textContent = "Uploading...";
    
    const tagsArr = metaTags.value.split(",").map(t => t.trim()).filter(t => t.length > 0);
    const pubDate = metaDate.value ? new Date(metaDate.value).toISOString() : null;
    
    const payload = {
      job_id: currentClip.job_id,
      filename: currentClip.filename,
      title: metaTitle.value || "My Short Video",
      description: metaDesc.value || "",
      tags: tagsArr,
      privacy: metaPrivacy.value || "private",
      publish_at: pubDate,
      account_id: metaAccount.value
    };
    
    try {
      const res = await postJson("/api/youtube/upload", payload);
      if (res.ok) {
        showStatus(`Upload complete! YouTube Video ID: ${res.youtube_id}`, "success");
        
        // Update local state
        const idx = clips.findIndex(c => c.job_id === currentClip.job_id && c.filename === currentClip.filename);
        if (idx >= 0) {
            clips[idx].is_uploaded = true;
            if (currentClip) currentClip.is_uploaded = true;
            renderClipList();
            updateUploadButtonState();
        }
      } else {
        throw new Error(res.error || "Unknown upload error");
      }
    } catch (err) {
      showStatus(`Upload failed: ${err.message}`, "error");
      updateUploadButtonState(); // reset button
    } finally {
      setFormDisabled(false);
    }
  }

  // Event Listeners
  refreshBtn.addEventListener("click", loadClips);
  saveBtn.addEventListener("click", saveMetadata);
  metaGenerateBtn.addEventListener("click", generateMetadata);
  uploadBtn.addEventListener("click", uploadToYouTube);
  linkAccountBtn.addEventListener("click", linkAccount);
  document.getElementById('addHookBtn').addEventListener('click', addHookIntro);

  async function addHookIntro() {
    if (!currentClip) return;
    const btn = document.getElementById('addHookBtn');
    const oldText = btn.textContent;
    btn.disabled = true;
    btn.textContent = "Processing...";
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
      } else {
        throw new Error(data.error || "Unknown error");
      }
    } catch (e) {
      showStatus("Error: " + e.message, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = oldText;
    }
  }

  // Initial load
  loadAccounts();
  loadClips();
});
