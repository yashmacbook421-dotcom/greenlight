"use client";

import { AppLink } from "./app-link";
import { ClipboardCheck, FlaskConical, Info, Moon, Plus, Sun } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
const nav = [
  { to: "/queue", label: "Queue", icon: ClipboardCheck },
  { to: "/about", label: "How it works", icon: Info },
  { to: "/evals", label: "Evals", icon: FlaskConical },
  { to: "/new", label: "New application", icon: Plus },
];
export function AppShell({ children }: { children: ReactNode }) {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
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
