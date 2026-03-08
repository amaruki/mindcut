import React, { useState, useEffect, useMemo } from 'react';

// Icons
const IconCamera = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>;
const IconWarn = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polygon points="12 2 22 20 2 20"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>;
const IconFilter = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>;
const IconClock = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>;
const IconEye = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>;
const IconCal = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>;

// Helpers
function fmtDuration(secs) {
  if (!secs) return "";
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  const pad2 = n => String(n).padStart(2, "0");
  if (h > 0) return `${h}:${pad2(m)}:${pad2(s)}`;
  return `${m}:${pad2(s)}`;
}

function fmtNum(n) {
  if (n === undefined) return "";
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

function resolvedStatus(v) {
  if (v.publishAt && v.privacyStatus === "private") {
    const t = new Date(v.publishAt);
    if (!isNaN(t) && t > new Date()) return "scheduled";
  }
  return v.privacyStatus || "private";
}

function statusLabel(s) {
  const map = { public: "Public", private: "Private", unlisted: "Unlisted", scheduled: "Scheduled" };
  return map[s] || s;
}

export default function ChannelVideos() {
  const [accounts, setAccounts] = useState([]);
  const [selectedAccount, setSelectedAccount] = useState("");
  const [allVideos, setAllVideos] = useState([]);
  const [activeFilter, setActiveFilter] = useState("all");
  const [activeView, setActiveView] = useState("grid");
  const [currentMonth, setCurrentMonth] = useState(() => {
    const d = new Date();
    d.setDate(1);
    return d;
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccount) {
      loadVideos(selectedAccount);
    }
  }, [selectedAccount]);

  const loadAccounts = async () => {
    try {
      const res = await fetch("/api/youtube/accounts");
      const data = await res.json();
      if (data.ok && data.accounts.length > 0) {
        setAccounts(data.accounts);
        setSelectedAccount(data.accounts[0].id);
      } else {
        setLoading(false);
      }
    } catch (e) {
      console.error(e);
      setLoading(false);
    }
  };

  const loadVideos = async (accountId) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/youtube/videos?account_id=${encodeURIComponent(accountId)}&max_results=200`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Unknown error");
      setAllVideos(data.videos || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const counts = useMemo(() => {
    const c = { all: allVideos.length, public: 0, private: 0, unlisted: 0, scheduled: 0 };
    allVideos.forEach(v => {
      const s = resolvedStatus(v);
      if (c[s] !== undefined) c[s]++;
    });
    return c;
  }, [allVideos]);

  const filteredVideos = useMemo(() => {
    if (activeFilter === "all") return allVideos;
    return allVideos.filter(v => resolvedStatus(v) === activeFilter);
  }, [allVideos, activeFilter]);

  // Calendar Navigation
  const changeMonth = (offset) => {
    const d = new Date(currentMonth);
    d.setMonth(d.getMonth() + offset);
    setCurrentMonth(d);
  };
  const goToday = () => {
    const d = new Date();
    d.setDate(1);
    setCurrentMonth(d);
  };

  // Render Calendar Grid
  const renderCalendarDates = () => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startingDay = firstDay.getDay();
    const totalDays = lastDay.getDate();

    const videosByDate = {};
    filteredVideos.forEach(v => {
      const s = resolvedStatus(v);
      const targetDateStr = (s === "scheduled" && v.publishAt) ? v.publishAt : v.publishedAt;
      if (!targetDateStr) return;
      const dateObj = new Date(targetDateStr);
      if (isNaN(dateObj.getTime())) return;
      
      const y = dateObj.getFullYear();
      const m = String(dateObj.getMonth() + 1).padStart(2, '0');
      const d = String(dateObj.getDate()).padStart(2, '0');
      const dateKey = `${y}-${m}-${d}`;
      
      if (!videosByDate[dateKey]) videosByDate[dateKey] = [];
      videosByDate[dateKey].push({ ...v, status: s });
    });

    const cells = [];
    for (let i = 0; i < startingDay; i++) {
        cells.push(<div key={`empty-${i}`} className="min-h-[100px] border border-border-main bg-bg-panel/20 opacity-30 rounded-lg"></div>);
    }

    const today = new Date();
    
    for (let i = 1; i <= totalDays; i++) {
        const dStr = String(i).padStart(2, '0');
        const mStr = String(month + 1).padStart(2, '0');
        const dateKey = `${year}-${mStr}-${dStr}`;
        const isToday = today.getDate() === i && today.getMonth() === month && today.getFullYear() === year;
        
        const dayVideos = videosByDate[dateKey] || [];
        dayVideos.sort((a,b) => {
           const ta = new Date((a.status === "scheduled" && a.publishAt) ? a.publishAt : a.publishedAt).getTime();
           const tb = new Date((b.status === "scheduled" && b.publishAt) ? b.publishAt : b.publishedAt).getTime();
           return ta - tb;
        });

        cells.push(
          <div key={`day-${i}`} className={`min-h-[100px] border rounded-lg p-2.5 flex flex-col gap-2 transition-colors duration-200 group hover:border-accent hover:bg-accent/5 ${isToday ? 'border-accent bg-accent/10 shadow-[inset_0_0_20px_rgba(139,92,246,0.1)]' : 'border-border-main bg-bg-panel/40'}`}>
              <div className={`font-semibold text-right ${isToday ? 'text-accent text-[15px]' : 'text-fg-muted text-[13px] group-hover:text-fg'}`}>{i}</div>
              <div className="flex flex-col gap-1.5 overflow-y-auto max-h-[250px] custom-scrollbar">
                {dayVideos.map((v, idx) => (
                  <a key={idx} href={`https://www.youtube.com/watch?v=${v.id}`} target="_blank" rel="noreferrer" className="flex items-center gap-2 p-1.5 rounded bg-white/5 border border-transparent cursor-pointer no-underline text-fg transition-all hover:bg-white/10 hover:border-border-main hover:-translate-y-px" title={v.title}>
                    <span className={`w-2 h-2 rounded-full shrink-0 ${v.status === 'scheduled' ? 'bg-warning' : v.status === 'public' ? 'bg-success' : v.status === 'unlisted' ? 'bg-info' : 'bg-error'}`}></span>
                    {v.thumbnail && <img src={v.thumbnail} className="w-8 h-8 object-cover rounded shadow-sm shrink-0 bg-black/50" alt="" />}
                    <span className="text-[11px] font-medium whitespace-nowrap overflow-hidden text-ellipsis">{v.title}</span>
                  </a>
                ))}
              </div>
          </div>
        );
    }
    return cells;
  };

  return (
    <main className="flex flex-col flex-1 overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-4 py-3 px-6 bg-bg-panel/40 border-b border-border-main backdrop-blur-md sticky top-0 z-10">
        <select className="bg-white/5 border border-border-main text-fg rounded-lg py-2 px-3 text-[13px] transition-all focus:border-accent focus:bg-white/10 focus:ring-2 focus:ring-accent/20 focus:outline-none min-w-[200px]" value={selectedAccount} onChange={e => setSelectedAccount(e.target.value)} disabled={loading}>
          {accounts.length ? accounts.map(a => <option key={a.id} value={a.id}>{a.title}</option>) : <option value="">No channels linked</option>}
        </select>
        <button onClick={() => selectedAccount && loadVideos(selectedAccount)} className="bg-transparent text-fg border border-border-main rounded-lg py-1.5 px-3 font-semibold text-xs hover:bg-white/5 cursor-pointer transition-colors whitespace-nowrap">Refresh</button>
        
        <div className="flex bg-bg-app border border-border-main rounded-lg p-0.5 ml-4">
          <button className={`flex items-center gap-1.5 py-1.5 px-3 text-xs font-semibold rounded-md transition-all cursor-pointer border-none leading-[0] ${activeView === 'grid' ? 'bg-bg-panel text-fg shadow-sm' : 'bg-transparent text-fg-muted hover:text-fg'}`} onClick={() => setActiveView("grid")} title="Grid View">
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
            Grid
          </button>
          <button className={`flex items-center gap-1.5 py-1.5 px-3 text-xs font-semibold rounded-md transition-all cursor-pointer border-none leading-[0] ${activeView === 'calendar' ? 'bg-bg-panel text-fg shadow-sm' : 'bg-transparent text-fg-muted hover:text-fg'}`} onClick={() => setActiveView("calendar")} title="Calendar View">
             <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
             Calendar
          </button>
        </div>

        <a className="bg-transparent text-fg border border-border-main rounded-lg py-1.5 px-3 font-semibold text-xs hover:bg-white/5 cursor-pointer transition-colors inline-flex items-center gap-1.5 no-underline ml-auto whitespace-nowrap" href="https://studio.youtube.com" target="_blank" rel="noreferrer">
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M19 19H5V5h7V3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/></svg>
          YouTube Studio
        </a>
        <span className="text-[13px] text-fg-muted font-medium whitespace-nowrap ml-3">
          {!loading && `${filteredVideos.length} video${filteredVideos.length !== 1 ? "s" : ""}${activeFilter !== 'all' ? ` · ${activeFilter}` : ''}`}
        </span>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-4 px-6 border-b border-border-main bg-bg-app overflow-x-auto no-scrollbar pt-2">
        {['all', 'public', 'unlisted', 'private', 'scheduled'].map(filter => (
          <button key={filter} className={`px-2 py-3 bg-transparent border-none text-[13px] font-semibold cursor-pointer relative uppercase tracking-wider whitespace-nowrap transition-colors ${activeFilter === filter ? 'text-accent' : 'text-fg-muted hover:text-fg'}`} onClick={() => setActiveFilter(filter)}>
            {filter.charAt(0).toUpperCase() + filter.slice(1)} <span className={`ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-white/5 ${activeFilter === filter ? 'text-accent border border-accent/30' : 'text-fg-muted'}`}>({counts[filter]})</span>
            {activeFilter === filter && <div className="absolute bottom-0 left-0 w-full h-[2px] bg-accent rounded-t-sm shadow-[0_-2px_8px_rgba(139,92,246,0.5)]"></div>}
          </button>
        ))}
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-5 custom-scrollbar">
        
        {loading && (
          <div className="flex flex-col items-center justify-center p-12 text-fg-muted animate-fadeIn">
            <div className="w-8 h-8 rounded-full border-2 border-accent border-t-transparent animate-spin mb-4 shadow-[0_0_15px_var(--accent)]"></div>
            <div className="text-sm font-semibold text-fg tracking-wide">Loading videos...</div>
          </div>
        )}

        {!loading && error && (
          <div className="flex flex-col items-center justify-center p-12 text-fg-muted animate-fadeIn">
             <div className="w-12 h-12 opacity-50 mb-3"><IconWarn /></div>
             <div className="text-sm font-semibold text-fg tracking-wide mb-1">Error Loading Videos</div>
             <p className="max-w-[400px] text-center text-sm leading-relaxed m-0">{error}</p>
          </div>
        )}

        {!loading && !error && accounts.length === 0 && (
          <div className="flex flex-col items-center justify-center p-12 text-fg-muted animate-fadeIn">
            <div className="w-12 h-12 opacity-50 mb-3"><IconCamera /></div>
            <div className="text-sm font-semibold text-fg tracking-wide mb-1">No Channel Selected</div>
            <p className="max-w-[400px] text-center text-sm leading-relaxed m-0">Please link a YouTube channel first via <a href="#/settings" className="text-accent no-underline font-semibold hover:underline">Settings</a>.</p>
          </div>
        )}

        {!loading && !error && accounts.length > 0 && filteredVideos.length === 0 && (
           <div className="flex flex-col items-center justify-center p-12 text-fg-muted animate-fadeIn">
             <div className="w-12 h-12 opacity-50 mb-3">{activeFilter === 'all' ? <IconCamera /> : <IconFilter />}</div>
             <div className="text-sm font-semibold text-fg tracking-wide mb-1">{activeFilter === 'all' ? 'No Videos Found' : 'No Videos Match Filter'}</div>
             <p className="max-w-[400px] text-center text-sm leading-relaxed m-0">{activeFilter === 'all' ? 'This channel has no uploaded videos yet.' : 'Try selecting a different status tab.'}</p>
           </div>
        )}

        {!loading && !error && filteredVideos.length > 0 && (
          <>
            {activeView === 'grid' && (
               <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-5 animate-fadeIn">
                 {filteredVideos.map(v => {
                   const status = resolvedStatus(v);
                   const duration = fmtDuration(v.duration);
                   const views = fmtNum(v.viewCount);
                   const pubDate = v.publishedAt ? relativeTime(v.publishedAt) : "—";
                   const scheduleRow = (status === "scheduled" && v.publishAt) 
                     ? <div className="text-[11px] text-warning flex items-center gap-1.5 mt-2 pt-2 border-t border-border-main"><div className="w-[11px] h-[11px]"><IconClock /></div> Scheduled: {fmtDatetime(v.publishAt)}</div>
                     : null;

                   return (
                     <a key={v.id} className="bg-bg-panel/40 border border-border-main rounded-xl overflow-hidden cursor-pointer no-underline text-fg transition-all duration-300 flex flex-col hover:-translate-y-1 hover:border-accent hover:shadow-[0_10px_20px_rgba(0,0,0,0.4),0_0_15px_rgba(139,92,246,0.1)] group backdrop-blur-sm" href={`https://www.youtube.com/watch?v=${v.id}`} target="_blank" rel="noreferrer" title={v.title}>
                       <div className="w-full aspect-video bg-black relative overflow-hidden border-b border-border-main">
                         {v.thumbnail && <img src={v.thumbnail} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" alt="" loading="lazy" />}
                         {duration && <span className="absolute bottom-1.5 right-1.5 bg-black/80 text-white text-[10px] font-semibold px-1 rounded backdrop-blur-sm shadow-sm z-10">{duration}</span>}
                         <span className="absolute top-2 left-2 z-10"><span className={`inline-flex px-1.5 py-[1px] text-[10px] uppercase tracking-wider font-bold rounded shadow-sm border ${status === 'public' ? 'bg-success/20 text-success border-success/30' : status === 'unlisted' ? 'bg-info/20 text-info border-info/30' : status === 'scheduled' ? 'bg-warning/20 text-warning border-warning/30' : 'bg-error/20 text-error border-error/30'}`}>{statusLabel(status)}</span></span>
                       </div>
                       <div className="p-3.5 flex flex-col flex-1">
                         <div className="font-semibold text-[13px] leading-tight mb-2 line-clamp-2 text-fg group-hover:text-accent transition-colors">{v.title}</div>
                         <div className="flex items-center gap-3 text-[11px] text-fg-muted mt-auto">
                           {v.viewCount !== undefined && <span className="flex items-center gap-1 font-medium"><div className="w-3 h-3"><IconEye /></div> {views} views</span>}
                           <span className="flex items-center gap-1 font-medium"><div className="w-3 h-3"><IconCal /></div> {pubDate}</span>
                         </div>
                         {scheduleRow}
                       </div>
                     </a>
                   );
                 })}
               </div>
            )}
            
            {activeView === 'calendar' && (
              <div className="bg-bg-panel/40 border border-border-main rounded-xl p-5 shadow-lg animate-fadeIn flex flex-col gap-4 backdrop-blur-md">
                <div className="flex justify-between items-center mb-1 border-b border-border-main pb-4">
                  <div className="text-xl font-bold text-fg tracking-tight">{currentMonth.toLocaleString('default', { month: 'long', year: 'numeric' })}</div>
                  <div className="flex gap-2">
                    <button onClick={() => changeMonth(-1)} className="bg-transparent text-fg border border-border-main rounded-lg py-1.5 px-3 font-semibold text-[13px] hover:bg-white/5 cursor-pointer transition-colors">&lt; Prev</button>
                    <button onClick={goToday} className="bg-transparent text-fg border border-border-main rounded-lg py-1.5 px-3 font-semibold text-[13px] hover:bg-white/5 cursor-pointer transition-colors">Today</button>
                    <button onClick={() => changeMonth(1)} className="bg-transparent text-fg border border-border-main rounded-lg py-1.5 px-3 font-semibold text-[13px] hover:bg-white/5 cursor-pointer transition-colors">Next &gt;</button>
                  </div>
                </div>
                <div className="grid grid-cols-7 gap-3 mb-2">
                  <div className="text-center text-xs font-semibold text-fg-muted uppercase tracking-wider py-1 border-b border-border-main">Sun</div>
                  <div className="text-center text-xs font-semibold text-fg-muted uppercase tracking-wider py-1 border-b border-border-main">Mon</div>
                  <div className="text-center text-xs font-semibold text-fg-muted uppercase tracking-wider py-1 border-b border-border-main">Tue</div>
                  <div className="text-center text-xs font-semibold text-fg-muted uppercase tracking-wider py-1 border-b border-border-main">Wed</div>
                  <div className="text-center text-xs font-semibold text-fg-muted uppercase tracking-wider py-1 border-b border-border-main">Thu</div>
                  <div className="text-center text-xs font-semibold text-fg-muted uppercase tracking-wider py-1 border-b border-border-main">Fri</div>
                  <div className="text-center text-xs font-semibold text-fg-muted uppercase tracking-wider py-1 border-b border-border-main">Sat</div>
                </div>
                <div className="grid grid-cols-7 gap-3">
                   {renderCalendarDates()}
                </div>
              </div>
            )}
          </>
        )}

      </div>
    </main>
  );
}
