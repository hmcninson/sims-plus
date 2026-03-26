"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { platformLogout } from "@/actions/platform.action";
import type { PlatformUser } from "@/types/platform.type";
import {
  Building2,
  BarChart3,
  ScrollText,
  ShieldCheck,
  LogOut,
  User,
  Menu,
  X,
} from "lucide-react";
import { useState, useCallback } from "react";

interface PlatformShellProps {
  user: PlatformUser;
  children: React.ReactNode;
}

const NAV_ITEMS = [
  { href: "/platform/tenants", label: "Tenants", icon: Building2 },
  { href: "/platform/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/platform/audit-log", label: "Audit Log", icon: ScrollText },
];

export function PlatformShell({ user, children }: PlatformShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const handleLogout = useCallback(async () => {
    await platformLogout();
    router.push("/platform-login");
  }, [router]);

  return (
    <div className="flex min-h-screen bg-zinc-950">
      {/* Desktop Sidebar */}
      <aside className="hidden w-64 flex-col border-r border-zinc-800 bg-zinc-900 md:flex">
        {/* Logo */}
        <div className="flex h-16 items-center gap-2 border-b border-zinc-800 px-6">
          <ShieldCheck className="h-6 w-6 text-indigo-500" />
          <div>
            <p className="text-sm font-semibold text-white">SIMS Plus</p>
            <p className="text-xs text-zinc-500">Platform Admin</p>
          </div>
        </div>

        {/* Nav links */}
        <nav className="flex-1 space-y-1 p-4">
          {NAV_ITEMS.map((item) => {
            const isActive =
              pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-indigo-600/10 text-indigo-400"
                    : "text-zinc-400 hover:bg-zinc-800 hover:text-white"
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* User footer */}
        <div className="border-t border-zinc-800 p-4">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-zinc-400 hover:bg-zinc-800 hover:text-white">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600 text-xs font-medium text-white">
                  {user.first_name[0]}
                  {user.last_name[0]}
                </div>
                <div className="flex-1 text-left">
                  <p className="text-sm font-medium text-white">
                    {user.first_name} {user.last_name}
                  </p>
                  <p className="text-xs text-zinc-500">{user.email}</p>
                </div>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuItem disabled>
                <User className="mr-2 h-4 w-4" />
                Profile
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout}>
                <LogOut className="mr-2 h-4 w-4" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* Mobile header + content */}
      <div className="flex flex-1 flex-col">
        {/* Mobile header */}
        <header className="flex h-16 items-center justify-between border-b border-zinc-800 bg-zinc-900 px-4 md:hidden">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-indigo-500" />
            <span className="text-sm font-semibold text-white">
              Platform Admin
            </span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="text-zinc-400"
            onClick={() => setMobileNavOpen(!mobileNavOpen)}
          >
            {mobileNavOpen ? (
              <X className="h-5 w-5" />
            ) : (
              <Menu className="h-5 w-5" />
            )}
          </Button>
        </header>

        {/* Mobile nav overlay */}
        {mobileNavOpen && (
          <div className="border-b border-zinc-800 bg-zinc-900 p-4 md:hidden">
            <nav className="space-y-1">
              {NAV_ITEMS.map((item) => {
                const isActive =
                  pathname === item.href ||
                  pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileNavOpen(false)}
                    className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                      isActive
                        ? "bg-indigo-600/10 text-indigo-400"
                        : "text-zinc-400 hover:bg-zinc-800 hover:text-white"
                    }`}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
            <div className="mt-4 border-t border-zinc-800 pt-4">
              <Button
                variant="ghost"
                className="w-full justify-start text-zinc-400 hover:text-white"
                onClick={handleLogout}
              >
                <LogOut className="mr-2 h-4 w-4" />
                Sign out
              </Button>
            </div>
          </div>
        )}

        {/* Desktop top bar */}
        <header className="hidden h-16 items-center justify-between border-b border-zinc-800 bg-zinc-900 px-6 md:flex">
          <div />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="gap-2 text-zinc-400 hover:text-white"
              >
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600 text-xs font-medium text-white">
                  {user.first_name[0]}
                  {user.last_name[0]}
                </div>
                <span className="text-sm">
                  {user.first_name} {user.last_name}
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuItem disabled>
                <User className="mr-2 h-4 w-4" />
                Profile
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout}>
                <LogOut className="mr-2 h-4 w-4" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>

        {/* Main content */}
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
