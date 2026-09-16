"use client";

import { AppLink } from "./app-link";
import { ClipboardCheck, FlaskConical, Globe, Info, Moon, Sun } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

const THEME_STORAGE_KEY = "greenlight-theme";

const nav = [
  { to: "/queue", label: "Queue", icon: ClipboardCheck },
  { to: "/about", label: "How it works", icon: Info },
  { to: "/evals", label: "Evals", icon: FlaskConical },
];
export function AppShell({ children }: { children: ReactNode }) {
  const [dark, setDark] = useState(() => {
    if (typeof window === "undefined") return false;
    const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    return savedTheme ? savedTheme === "dark" : prefersDark;
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    window.localStorage.setItem(THEME_STORAGE_KEY, dark ? "dark" : "light");
  }, [dark]);
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <AppLink to="/queue" className="brand">
          <span className="brand-mark">G</span>
          <span>Greenlight</span>
        </AppLink>
        <nav>
          {nav.map(({ to, label, icon: Icon }) => (
            <AppLink key={to} to={to} className="nav-link" activeProps={{ className: "active" }}>
              <Icon size={17} />
              <span>{label}</span>
            </AppLink>
          ))}
          <AppLink to="/" className="nav-link sidebar-portal">
            <Globe size={17} />
            <span>Applicant site</span>
          </AppLink>
        </nav>
        <div className="sidebar-foot">
          <button
            className="icon-button"
            onClick={() => setDark((v) => !v)}
            aria-label="Toggle color theme"
            title="Toggle color theme"
          >
            {dark ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <span>
            Human authority
            <br />
            Code-bounded AI
          </span>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
