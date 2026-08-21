"use client";

import { MoonIcon, SunIcon } from "./icons";

type Theme = "light" | "dark";

export function ThemeToggle() {
  function toggleTheme() {
    const nextTheme: Theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = nextTheme;
    localStorage.setItem("literae-theme", nextTheme);
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="theme-toggle"
      aria-label="Toggle color theme"
      title="Toggle color theme"
    >
      <span className="theme-track" aria-hidden="true">
        <SunIcon className="theme-icon-sun" />
        <MoonIcon className="theme-icon-moon" />
        <i />
      </span>
    </button>
  );
}
