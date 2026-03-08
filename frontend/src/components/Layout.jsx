import React from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { Github } from 'lucide-react';

export default function Layout() {
  const location = useLocation();

  const getLinkStyle = (path) => {
    return location.pathname === path
      ? { fontWeight: 'bold', color: 'var(--fg)' }
      : { fontWeight: 500 };
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg-app text-fg font-sans w-full">
      {/* 1. Header */}
      <header className="h-16 flex justify-between items-center px-6 bg-bg-header/75 backdrop-blur-md border-b border-border-main z-10 shrink-0">
        <div className="flex flex-row items-center">
          <div className="text-lg font-bold tracking-tight">Mind<span className="text-accent">Cut</span></div>
          <div className="ml-6 flex items-center gap-4">
            <Link to="/" className="text-[13px] flex items-center gap-1.5 no-underline transition-colors hover:text-fg text-fg-muted" style={getLinkStyle('/')}>Editor Studio</Link>
            <span className="text-border-main">|</span>
            <Link to="/upload-manager" className="text-[13px] flex items-center gap-1.5 no-underline transition-colors hover:text-fg text-fg-muted" style={getLinkStyle('/upload-manager')}>Upload Manager</Link>
            <span className="text-border-main">|</span>
            <Link to="/scheduled" className="text-[13px] flex items-center gap-1.5 no-underline transition-colors hover:text-fg text-fg-muted" style={getLinkStyle('/scheduled')}>Channel Videos</Link>
            <span className="text-border-main">|</span>
            <Link to="/settings" className="text-[13px] flex items-center gap-1.5 no-underline transition-colors hover:text-fg text-fg-muted" style={getLinkStyle('/settings')}>Settings</Link>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex" role="group" aria-label="Language">
            <button id="langId" className="bg-accent/10 border border-accent text-accent px-2 py-1 rounded-md cursor-pointer text-xs font-semibold mr-1" type="button" aria-label="Bahasa Indonesia" title="Bahasa Indonesia">
              <span>ID</span>
            </button>
            <button id="langEn" className="bg-transparent border border-border-main text-fg-muted px-2 py-1 rounded-md cursor-pointer text-xs font-semibold hover:bg-white/5 transition-colors" type="button" aria-label="English" title="English">
              <span>EN</span>
            </button>
          </div>
          <a className="text-[13px] flex items-center gap-1.5 no-underline text-fg-muted transition-colors hover:text-fg" href="https://github.com/amaruki" target="_blank" rel="noreferrer">
            <Github className="w-3.5 h-3.5 fill-current" size={16} />
            <span>amaruki</span>
          </a>
        </div>
      </header>
      
      {/* 2. Main Work Area (Pages inserted here) */}
      <Outlet />
    </div>
  );
}
