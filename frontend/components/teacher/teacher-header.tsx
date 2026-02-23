"use client";

/**
 * SIMS Plus - Teacher Portal Header
 *
 * Top bar for the teacher portal showing school identity, page title,
 * notification bell, and user avatar with dropdown menu.
 *
 * On mobile: shows school logo + name + actions.
 * On desktop: shows sidebar trigger + page title + actions.
 */

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { Bell, LogOut, User } from "lucide-react";

import { SidebarTrigger } from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { NotificationBell } from "@/components/notifications/notification-bell";
import { getInitials } from "@/lib/format";
import { logout } from "@/actions/auth.action";

interface TeacherHeaderUser {
  first_name: string;
  last_name: string;
  email: string;
  avatar_url?: string;
}

interface TeacherHeaderProps {
  user: TeacherHeaderUser;
  schoolName?: string;
  schoolLogo?: string | null;
}

/** Map route segments to readable page titles. */
const pageTitles: Record<string, string> = {
  dashboard: "Dashboard",
  schedule: "My Schedule",
  classes: "My Classes",
  attendance: "Attendance",
  grading: "Grading",
  notes: "Student Notes",
  reports: "Reports",
  "head-teacher": "School Overview",
  performance: "Class Performance",
  notifications: "Notifications",
  profile: "Profile",
  students: "Student Detail",
};

function getPageTitle(pathname: string): string {
  const segments = pathname.replace("/teacher/", "").split("/").filter(Boolean);
  if (segments.length === 0) return "Dashboard";

  // Check last non-UUID segment for a readable title
  for (let i = segments.length - 1; i >= 0; i--) {
    const segment = segments[i];
    // Skip UUID segments
    if (
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
        segment
      )
    ) {
      continue;
    }
    if (pageTitles[segment]) return pageTitles[segment];
    // Fallback: capitalize and replace hyphens
    return segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, " ");
  }

  return "Dashboard";
}

export function TeacherHeader({
  user,
  schoolName,
  schoolLogo,
}: TeacherHeaderProps) {
  const pathname = usePathname();
  const pageTitle = getPageTitle(pathname);

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4">
      {/* Sidebar trigger -- visible on desktop for collapsed sidebar */}
      <SidebarTrigger className="-ml-1 h-8 w-8 border-none shadow-none [&>svg]:size-4 hidden md:flex" />

      {/* School logo + name on mobile, page title on desktop */}
      <div className="flex items-center gap-2 md:hidden">
        {schoolLogo ? (
          <Image
            src={schoolLogo}
            alt={schoolName || "School logo"}
            width={28}
            height={28}
            className="rounded-md"
          />
        ) : (
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary">
            <span className="text-[10px] font-bold text-primary-foreground">
              {schoolName ? schoolName.charAt(0) : "S"}
            </span>
          </div>
        )}
        <span className="font-semibold text-sm truncate max-w-[140px]">
          {schoolName || "SIMS Plus"}
        </span>
      </div>

      {/* Desktop page title */}
      <h1 className="hidden md:block text-sm font-semibold">{pageTitle}</h1>

      {/* Right side actions */}
      <div className="ml-auto flex items-center gap-1">
        {/* Notification bell */}
        <NotificationBell />

        {/* User avatar dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9 rounded-full"
            >
              <Avatar className="h-7 w-7">
                {user.avatar_url && (
                  <AvatarImage
                    src={user.avatar_url}
                    alt={`${user.first_name} ${user.last_name}`}
                  />
                )}
                <AvatarFallback className="bg-primary/10 text-primary text-[10px]">
                  {getInitials(`${user.first_name} ${user.last_name}`)}
                </AvatarFallback>
              </Avatar>
              <span className="sr-only">User menu</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium leading-none">
                  {user.first_name} {user.last_name}
                </p>
                <p className="text-xs leading-none text-muted-foreground">
                  {user.email}
                </p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/teacher/profile">
                <User className="mr-2 h-4 w-4" />
                Profile
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/teacher/notifications">
                <Bell className="mr-2 h-4 w-4" />
                Notifications
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => logout()}>
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
