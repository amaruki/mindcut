/* scheduled.js – Channel Videos page */
(function () {
  "use strict";

  /* ── State ─────────────────────────────────────────────────────── */
  let allVideos = [];
  let activeFilter = "all";
  let activeView = "grid"; // 'grid' or 'calendar'
  
  // Calendar state
  let currentMonth = new Date(); // Represents the month currently being viewed
  currentMonth.setDate(1);

  /* ── DOM refs ───────────────────────────────────────────────────── */
  const accountSelect = document.getElementById("accountSelect");
  const refreshBtn    = document.getElementById("refreshBtn");
  const schGrid       = document.getElementById("schGrid");
  const schCalendar   = document.getElementById("schCalendar");
  const schState      = document.getElementById("schState");
  const schStats      = document.getElementById("schStats");
  const filterTabs    = document.querySelectorAll(".filter-tab");
  const viewBtns      = document.querySelectorAll(".view-btn");
  
  // Calendar DOM refs
  const calDateGrid   = document.getElementById("calDateGrid");
  const calMonthYear  = document.getElementById("calMonthYear");
  const calPrevBtn    = document.getElementById("calPrevBtn");
  const calNextBtn    = document.getElementById("calNextBtn");
  const calTodayBtn   = document.getElementById("calTodayBtn");

  /* ── Init ───────────────────────────────────────────────────────── */
  loadAccounts().then(() => loadVideos());

  refreshBtn.addEventListener("click", () => loadVideos());
  accountSelect.addEventListener("change", () => loadVideos());

  filterTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      filterTabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      activeFilter = tab.dataset.filter;
      renderActiveView();
    });
  });

  viewBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      viewBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeView = btn.dataset.view;
      renderActiveView();
    });
  });

  // Calendar Controls
  calPrevBtn.addEventListener("click", () => {
    currentMonth.setMonth(currentMonth.getMonth() - 1);
    renderActiveView();
  });
  calNextBtn.addEventListener("click", () => {
    currentMonth.setMonth(currentMonth.getMonth() + 1);
    renderActiveView();
  });
  calTodayBtn.addEventListener("click", () => {
    currentMonth = new Date();
    currentMonth.setDate(1);
    renderActiveView();
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
    schGrid.style.display = "none";
    schCalendar.classList.remove("active");
    schState.classList.add("active");
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
      const res = await fetch(`/api/youtube/videos?account_id=${encodeURIComponent(accountId)}&max_results=200`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Unknown error");

      allVideos = data.videos || [];
      updateCounts();
      renderActiveView();
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
  function renderActiveView() {
    const filtered = activeFilter === "all"
      ? allVideos
      : allVideos.filter(v => resolvedStatus(v) === activeFilter);

    if (!filtered.length && activeView === "grid") {
      schGrid.style.display = "none";
      schCalendar.classList.remove("active");
      schState.classList.add("active");
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

    // Hide empty state if there is anything to render
    schState.classList.remove("active");

    if (activeView === "grid") {
      schCalendar.classList.remove("active");
      schGrid.style.display = "grid";
      schGrid.innerHTML = filtered.map(videoCard).join("");
    } else {
      schGrid.style.display = "none";
      schCalendar.classList.add("active");
      renderCalendar(filtered);
    }

    schStats.textContent = `${filtered.length} video${filtered.length !== 1 ? "s" : ""}${activeFilter !== "all" ? ` · ${activeFilter}` : ""}`;
    schStats.style.display = "block";
  }

  function renderCalendar(filteredVideos) {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    
    // Set Header
    calMonthYear.textContent = currentMonth.toLocaleString('default', { month: 'long', year: 'numeric' });

    // Calculate dates
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startingDay = firstDay.getDay(); // 0 = Sunday
    const totalDays = lastDay.getDate();

    // Group videos by date string "YYYY-MM-DD"
    const videosByDate = {};
    filteredVideos.forEach(v => {
      // Use publishAt if scheduled, else publishedAt
      const status = resolvedStatus(v);
      const targetDateStr = (status === "scheduled" && v.publishAt) ? v.publishAt : v.publishedAt;
      if (!targetDateStr) return;

      const dateObj = new Date(targetDateStr);
      if (isNaN(dateObj)) return;

      const y = dateObj.getFullYear();
      const m = String(dateObj.getMonth() + 1).padStart(2, '0');
      const d = String(dateObj.getDate()).padStart(2, '0');
      const dateKey = `${y}-${m}-${d}`;

      if (!videosByDate[dateKey]) videosByDate[dateKey] = [];
      videosByDate[dateKey].push(v);
    });

    // Build the grid HTML
    let cellsHtml = '';
    
    // Blank cells before start of month
    for (let i = 0; i < startingDay; i++) {
        cellsHtml += '<div class="cal-cell empty"></div>';
    }

    const today = new Date();
    
    // Cells for each day of month
    for (let i = 1; i <= totalDays; i++) {
        const dStr = String(i).padStart(2, '0');
        const mStr = String(month + 1).padStart(2, '0');
        const dateKey = `${year}-${mStr}-${dStr}`;
        
        const isToday = today.getDate() === i && today.getMonth() === month && today.getFullYear() === year;
        
        const dayVideos = videosByDate[dateKey] || [];
        // Sort day videos by time explicitly (earliest first)
        dayVideos.sort((a,b) => {
           const ta = new Date((resolvedStatus(a) === "scheduled" && a.publishAt) ? a.publishAt : a.publishedAt).getTime();
           const tb = new Date((resolvedStatus(b) === "scheduled" && b.publishAt) ? b.publishAt : b.publishedAt).getTime();
           return ta - tb;
        });

        const vidsHtml = dayVideos.map(v => {
            const status = resolvedStatus(v);
            const ytUrl = `https://www.youtube.com/watch?v=${v.id}`;
            return `
              <a href="${ytUrl}" target="_blank" rel="noreferrer" class="cal-video-item" title="${escHtml(v.title)}">
                <span class="status-dot ${status}"></span>
                ${v.thumbnail ? `<img src="${escHtml(v.thumbnail)}" class="cal-video-thumb" alt="">` : ''}
                <span class="cal-video-title">${escHtml(v.title)}</span>
              </a>
            `;
        }).join("");

        cellsHtml += `
            <div class="cal-cell ${isToday ? 'today' : ''}">
                <div class="cal-date-num">${i}</div>
                <div class="cal-videos custom-scrollbar">${vidsHtml}</div>
            </div>
        `;
    }

    calDateGrid.innerHTML = cellsHtml;
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
