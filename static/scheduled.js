/* scheduled.js – Channel Videos page */
(function () {
  "use strict";

  /* ── State ─────────────────────────────────────────────────────── */
  let allVideos = [];
  let activeFilter = "all";

  /* ── DOM refs ───────────────────────────────────────────────────── */
  const accountSelect = document.getElementById("accountSelect");
  const refreshBtn    = document.getElementById("refreshBtn");
  const schGrid       = document.getElementById("schGrid");
  const schState      = document.getElementById("schState");
  const schStats      = document.getElementById("schStats");
  const filterTabs    = document.querySelectorAll(".filter-tab");

  /* ── Init ───────────────────────────────────────────────────────── */
  loadAccounts().then(() => loadVideos());

  refreshBtn.addEventListener("click", () => loadVideos());
  accountSelect.addEventListener("change", () => loadVideos());

  filterTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      filterTabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      activeFilter = tab.dataset.filter;
      renderGrid();
    });
  });

  /* ── Accounts ───────────────────────────────────────────────────── */
  async function loadAccounts() {
    try {
      const res = await fetch("/api/youtube/accounts");
      const data = await res.json();
      accountSelect.innerHTML = "";
      if (!data.ok || !data.accounts.length) {
        accountSelect.innerHTML = '<option value="">No channels linked</option>';
        return;
      }
      data.accounts.forEach((acc, i) => {
        const opt = document.createElement("option");
        opt.value = acc.id;
        opt.textContent = acc.title;
        if (i === 0) opt.selected = true;
        accountSelect.appendChild(opt);
      });
    } catch (e) {
      accountSelect.innerHTML = '<option value="">Error loading channels</option>';
    }
  }

  /* ── Load Videos ────────────────────────────────────────────────── */
  async function loadVideos() {
    schGrid.innerHTML = "";
    schGrid.style.display = "none";
    schState.style.display = "flex";
    schState.innerHTML = `<div class="spinner"></div><div class="state-title">Loading videos…</div>`;
    schStats.style.display = "none";

    const accountId = accountSelect.value;
    if (!accountId) {
      schState.innerHTML = `
        ${iconCamera()}
        <div class="state-title">No Channel Selected</div>
        <p>Please link a YouTube channel first via <a href="/settings" style="color:var(--accent)">Settings</a>.</p>`;
      return;
    }

    try {
      const res = await fetch(`/api/youtube/videos?account_id=${encodeURIComponent(accountId)}`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Unknown error");

      allVideos = data.videos || [];
      updateCounts();
      renderGrid();
    } catch (e) {
      schState.innerHTML = `
        ${iconWarn()}
        <div class="state-title">Error Loading Videos</div>
        <p>${escHtml(e.message)}</p>`;
    }
  }

  /* ── Counts ─────────────────────────────────────────────────────── */
  function updateCounts() {
    const counts = { all: allVideos.length, public: 0, private: 0, unlisted: 0, scheduled: 0 };
    allVideos.forEach(v => {
      const status = resolvedStatus(v);
      if (counts[status] !== undefined) counts[status]++;
    });
    document.getElementById("cnt-all").textContent      = `(${counts.all})`;
    document.getElementById("cnt-public").textContent   = `(${counts.public})`;
    document.getElementById("cnt-private").textContent  = `(${counts.private})`;
    document.getElementById("cnt-unlisted").textContent = `(${counts.unlisted})`;
    document.getElementById("cnt-scheduled").textContent= `(${counts.scheduled})`;
  }

  /**
   * A video is "scheduled" when it is private AND has a future publishAt date.
   */
  function resolvedStatus(v) {
    if (v.publishAt && v.privacyStatus === "private") {
      const t = new Date(v.publishAt);
      if (!isNaN(t) && t > new Date()) return "scheduled";
    }
    return v.privacyStatus || "private";
  }

  /* ── Render ─────────────────────────────────────────────────────── */
  function renderGrid() {
    const filtered = activeFilter === "all"
      ? allVideos
      : allVideos.filter(v => resolvedStatus(v) === activeFilter);

    if (!filtered.length) {
      schGrid.style.display = "none";
      schState.style.display = "flex";
      if (!allVideos.length) {
        schState.innerHTML = `
          ${iconCamera()}
          <div class="state-title">No Videos Found</div>
          <p>This channel has no uploaded videos yet.</p>`;
      } else {
        schState.innerHTML = `
          ${iconFilter()}
          <div class="state-title">No Videos Match Filter</div>
          <p>Try selecting a different status tab.</p>`;
      }
      schStats.style.display = "none";
      return;
    }

    schState.style.display = "none";
    schGrid.style.display  = "grid";
    schGrid.innerHTML = filtered.map(videoCard).join("");

    schStats.textContent = `${filtered.length} video${filtered.length !== 1 ? "s" : ""}${activeFilter !== "all" ? ` · ${activeFilter}` : ""}`;
    schStats.style.display = "block";
  }

  function videoCard(v) {
    const status   = resolvedStatus(v);
    const duration = fmtDuration(v.duration);
    const views    = fmtNum(v.viewCount);
    const pubDate  = v.publishedAt ? relativeTime(v.publishedAt) : "—";

    const scheduleRow = (status === "scheduled" && v.publishAt)
      ? `<div class="schedule-row">
           ${iconClock()}
           Scheduled: ${fmtDatetime(v.publishAt)}
         </div>`
      : "";

    const ytUrl = `https://www.youtube.com/watch?v=${v.id}`;

    return `
      <a class="video-card" href="${ytUrl}" target="_blank" rel="noreferrer" title="${escHtml(v.title)}">
        <div class="video-thumb">
          ${v.thumbnail ? `<img src="${escHtml(v.thumbnail)}" alt="" loading="lazy">` : ""}
          ${duration ? `<span class="thumb-duration">${duration}</span>` : ""}
          <span class="thumb-status"><span class="status-pill ${escHtml(status)}">${statusLabel(status)}</span></span>
        </div>
        <div class="video-body">
          <div class="video-title">${escHtml(v.title)}</div>
          <div class="video-meta">
            ${v.viewCount !== undefined ? `<span class="meta-item">${iconEye()} ${views} views</span>` : ""}
            <span class="meta-item">${iconCal()} ${pubDate}</span>
          </div>
          ${scheduleRow}
        </div>
      </a>`;
  }

  /* ── Formatting ─────────────────────────────────────────────────── */
  function statusLabel(s) {
    const map = { public: "Public", private: "Private", unlisted: "Unlisted", scheduled: "Scheduled" };
    return map[s] || s;
  }

  function fmtDuration(secs) {
    if (!secs) return "";
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    if (h > 0) return `${h}:${pad2(m)}:${pad2(s)}`;
    return `${m}:${pad2(s)}`;
  }

  function pad2(n) { return String(n).padStart(2, "0"); }

  function fmtNum(n) {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
    if (n >= 1_000)     return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
    return String(n);
  }

  function relativeTime(iso) {
    const now  = Date.now();
    const then = new Date(iso).getTime();
    const diff = Math.round((now - then) / 1000);
    if (diff < 60)   return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400)return `${Math.floor(diff / 3600)}h ago`;
    const days = Math.floor(diff / 86400);
    if (days < 30)   return `${days}d ago`;
    if (days < 365)  return `${Math.floor(days / 30)}mo ago`;
    return `${Math.floor(days / 365)}y ago`;
  }

  function fmtDatetime(iso) {
    try {
      return new Date(iso).toLocaleString(undefined, {
        month: "short", day: "numeric", year: "numeric",
        hour: "2-digit", minute: "2-digit"
      });
    } catch { return iso; }
  }

  function escHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  /* ── Icons ──────────────────────────────────────────────────────── */
  function iconClock() {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`;
  }
  function iconEye() {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
  }
  function iconCal() {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`;
  }
  function iconCamera() {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>`;
  }
  function iconWarn() {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><triangle points="12 2 22 20 2 20"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
  }
  function iconFilter() {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>`;
  }
})();
