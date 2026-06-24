"use client";

import { useCallback, useEffect, useState } from "react";

type Theme = "dark" | "light" | "system";

const STORAGE_KEY = "resume-editor-theme";

function getStoredTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  return (localStorage.getItem(STORAGE_KEY) as Theme) || "dark";
}

function applyTheme(t: Theme) {
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const isDark = t === "dark" || (t === "system" && prefersDark);
  document.documentElement.classList.toggle("dark", isDark);
}

const THEME_CYCLE: Theme[] = ["dark", "light", "system"];

const THEME_META: Record<Theme, { icon: string; label: string }> = {
  dark: { icon: "🌙", label: "深色" },
  light: { icon: "☀️", label: "浅色" },
  system: { icon: "💻", label: "跟随系统" },
};

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");

  // Init from localStorage on mount
  useEffect(() => {
    const stored = getStoredTheme();
    setTheme(stored);
    applyTheme(stored);
  }, []);

  // Listen to system preference changes in "system" mode
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (theme === "system") applyTheme("system");
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  const cycle = useCallback(() => {
    setTheme((prev) => {
      const idx = THEME_CYCLE.indexOf(prev);
      const next = THEME_CYCLE[(idx + 1) % THEME_CYCLE.length];
      localStorage.setItem(STORAGE_KEY, next);
      applyTheme(next);
      return next;
    });
  }, []);

  const meta = THEME_META[theme];

  return (
    <button
      onClick={cycle}
      title={`主题：${meta.label}`}
      className="flex items-center gap-1.5 text-xs text-muted-foreground/60 hover:text-foreground/80 transition-colors px-1.5 py-1 rounded"
    >
      <span className="text-sm">{meta.icon}</span>
    </button>
  );
}
