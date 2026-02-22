"use client";

/**
 * SIMS Plus - Parent Portal Bottom Navigation
 *
 * Mobile-only bottom tab bar for quick navigation in the parent portal.
 * Visible on screens smaller than md breakpoint. Hidden on desktop where
 * the sidebar takes over.
 *
 * Uses the school's branding color for the active tab indicator.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, Users, CreditCard, Megaphone, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

interface NavTab {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

const tabs: NavTab[] = [
  { label: "Home", href: "/parent/dashboard", icon: Home },
  { label: "Children", href: "/parent/children", icon: Users },
  { label: "Payments", href: "/parent/payments", icon: CreditCard },
  { label: "News", href: "/parent/announcements", icon: Megaphone },
  { label: "Settings", href: "/parent/settings", icon: Settings },
];

export function ParentBottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-50 border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 md:hidden"
      role="navigation"
      aria-label="Parent portal navigation"
    >
      <div className="flex h-16 items-center justify-around px-2">
        {tabs.map((tab) => {
          const isActive =
            pathname === tab.href || pathname.startsWith(tab.href + "/");
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "flex flex-1 flex-col items-center justify-center gap-0.5 py-1 text-muted-foreground transition-colors",
                isActive && "text-primary"
              )}
              aria-current={isActive ? "page" : undefined}
            >
              <tab.icon
                className={cn("h-5 w-5", isActive && "text-primary")}
              />
              <span
                className={cn(
                  "text-[10px] leading-tight",
                  isActive ? "font-semibold text-primary" : "font-normal"
                )}
              >
                {tab.label}
              </span>
              {isActive && (
                <span className="absolute bottom-0 h-0.5 w-10 rounded-full bg-primary" />
              )}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
