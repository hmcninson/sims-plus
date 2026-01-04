"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

const themes = [
  {
    value: "light",
    label: "Light",
    icon: Sun,
  },
  {
    value: "dark",
    label: "Dark",
    icon: Moon,
  },
  {
    value: "system",
    label: "System",
    icon: Monitor,
  },
] as const;

interface ThemeToggleProps {
  className?: string;
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Avoid hydration mismatch
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className={cn("flex gap-1 rounded-lg bg-muted p-1", className)}>
        {themes.map((t) => (
          <div
            key={t.value}
            className="flex h-9 w-24 items-center justify-center gap-2 rounded-md px-3"
          >
            <t.icon className="h-4 w-4" />
            <span className="text-sm">{t.label}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className={cn("flex gap-1 rounded-lg bg-muted p-1", className)}>
      {themes.map((t) => {
        const isActive = theme === t.value;
        return (
          <button
            key={t.value}
            onClick={() => setTheme(t.value)}
            className={cn(
              "flex h-9 items-center justify-center gap-2 rounded-md px-3 text-sm font-medium transition-colors",
              isActive
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:bg-background/50 hover:text-foreground"
            )}
          >
            <t.icon className="h-4 w-4" />
            <span>{t.label}</span>
          </button>
        );
      })}
    </div>
  );
}

// Compact version for header/quick access
export function ThemeToggleCompact({ className }: ThemeToggleProps) {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <button className={cn("h-9 w-9 rounded-md", className)}>
        <Sun className="h-4 w-4" />
      </button>
    );
  }

  const cycleTheme = () => {
    if (theme === "light") setTheme("dark");
    else if (theme === "dark") setTheme("system");
    else setTheme("light");
  };

  const Icon = resolvedTheme === "dark" ? Moon : Sun;

  return (
    <button
      onClick={cycleTheme}
      className={cn(
        "flex h-9 w-9 items-center justify-center rounded-md border border-input bg-background transition-colors hover:bg-accent hover:text-accent-foreground",
        className
      )}
      title={`Current: ${theme}. Click to cycle themes.`}
    >
      <Icon className="h-4 w-4" />
      <span className="sr-only">Toggle theme</span>
    </button>
  );
}
