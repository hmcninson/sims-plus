"use client";

/**
 * SIMS Plus - Teacher Portal Sidebar
 *
 * Desktop sidebar navigation for the teacher portal.
 * Shows class management, attendance, grading, and reporting nav items.
 * Head teachers get an additional "Overview" section.
 * Hidden on mobile where the bottom nav takes over.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  Calendar,
  BookOpen,
  ClipboardCheck,
  PenLine,
  StickyNote,
  FileText,
  Shield,
  Bell,
  User,
  LogOut,
  School,
  ChevronsUpDown,
  NotebookPen,
  MessageSquare,
} from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import { SchoolSwitcher } from "@/components/layout/school-switcher";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { getInitials } from "@/lib/format";
import { logout } from "@/actions/auth.action";

interface TeacherUser {
  first_name: string;
  last_name: string;
  email: string;
  role: string;
}

interface TeacherSidebarProps {
  user: TeacherUser;
  schoolName?: string;
  schoolLogo?: string | null;
  /** Whether this tenant is a chain with multiple schools. */
  isChain?: boolean;
}

interface NavItem {
  title: string;
  url: string;
  icon: React.ComponentType<{ className?: string }>;
}

const mainNavItems: NavItem[] = [
  { title: "Dashboard", url: "/teacher/dashboard", icon: Home },
  { title: "Schedule", url: "/teacher/schedule", icon: Calendar },
  { title: "My Classes", url: "/teacher/classes", icon: BookOpen },
  { title: "Attendance", url: "/teacher/attendance", icon: ClipboardCheck },
  { title: "Grading", url: "/teacher/grading", icon: PenLine },
  { title: "Notes", url: "/teacher/notes", icon: StickyNote },
  { title: "Reports", url: "/teacher/reports", icon: FileText },
];

const managementNavItems: NavItem[] = [
  { title: "Lesson Plans", url: "/teacher/lessons", icon: NotebookPen },
  { title: "Communication", url: "/teacher/communication", icon: MessageSquare },
];

const secondaryNavItems: NavItem[] = [
  { title: "Notifications", url: "/teacher/notifications", icon: Bell },
  { title: "Profile", url: "/teacher/profile", icon: User },
];

const headTeacherNavItems: NavItem[] = [
  { title: "School Overview", url: "/teacher/head-teacher", icon: Shield },
];

export function TeacherSidebar({ user, schoolName, schoolLogo, isChain }: TeacherSidebarProps) {
  const pathname = usePathname();

  // Head teachers, academic heads, and school admins see additional navigation
  const isHeadTeacher = user.role === "academic_head" || user.role === "school_admin";

  return (
    <Sidebar collapsible="icon" className="hidden md:flex">
      <SidebarHeader className="h-14 border-b border-sidebar-border flex items-center px-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" className="h-10" asChild>
              <Link href="/teacher/dashboard">
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <School className="size-4" />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">
                    {schoolName || "SIMS Plus"}
                  </span>
                  <span className="truncate text-xs text-muted-foreground">
                    Teacher Portal
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
          {/* School switcher -- only visible for chain tenants */}
          {isChain && (
            <SidebarMenuItem>
              <SchoolSwitcher />
            </SidebarMenuItem>
          )}
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {/* Main navigation */}
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {mainNavItems.map((item) => {
                const isActive =
                  pathname === item.url || pathname.startsWith(item.url + "/");
                return (
                  <SidebarMenuItem key={item.url}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      tooltip={item.title}
                    >
                      <Link href={item.url}>
                        <item.icon className="size-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Management section */}
        <SidebarGroup>
          <SidebarGroupLabel>Management</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {managementNavItems.map((item) => {
                const isActive =
                  pathname === item.url || pathname.startsWith(item.url + "/");
                return (
                  <SidebarMenuItem key={item.url}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      tooltip={item.title}
                    >
                      <Link href={item.url}>
                        <item.icon className="size-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {/* Head Teacher section -- only visible for academic heads */}
        {isHeadTeacher && (
          <SidebarGroup>
            <SidebarGroupLabel>Administration</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {headTeacherNavItems.map((item) => {
                  const isActive =
                    pathname === item.url || pathname.startsWith(item.url + "/");
                  return (
                    <SidebarMenuItem key={item.url}>
                      <SidebarMenuButton
                        asChild
                        isActive={isActive}
                        tooltip={item.title}
                      >
                        <Link href={item.url}>
                          <item.icon className="size-4" />
                          <span>{item.title}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}

        {/* Secondary navigation */}
        <SidebarGroup>
          <SidebarGroupLabel>Account</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {secondaryNavItems.map((item) => {
                const isActive =
                  pathname === item.url || pathname.startsWith(item.url + "/");
                return (
                  <SidebarMenuItem key={item.url}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive}
                      tooltip={item.title}
                    >
                      <Link href={item.url}>
                        <item.icon className="size-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        <SidebarMenu>
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  size="lg"
                  className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                >
                  <Avatar className="size-8">
                    <AvatarFallback className="bg-primary/10 text-primary text-xs">
                      {getInitials(`${user.first_name} ${user.last_name}`)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-medium">
                      {user.first_name} {user.last_name}
                    </span>
                    <span className="truncate text-xs text-muted-foreground">
                      {user.email}
                    </span>
                  </div>
                  <ChevronsUpDown className="ml-auto size-4" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
                side="bottom"
                align="end"
                sideOffset={4}
              >
                <DropdownMenuLabel className="p-0 font-normal">
                  <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                    <Avatar className="size-8">
                      <AvatarFallback className="bg-primary/10 text-primary text-xs">
                        {getInitials(`${user.first_name} ${user.last_name}`)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="grid flex-1 text-left text-sm leading-tight">
                      <span className="truncate font-medium">
                        {user.first_name} {user.last_name}
                      </span>
                      <span className="truncate text-xs text-muted-foreground">
                        {user?.role === "school_admin"
                          ? "School Admin"
                          : user?.role === "academic_head"
                            ? "Academic Head"
                            : "Teacher"}
                      </span>
                    </div>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href="/teacher/profile">Profile</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link href="/teacher/notifications">Notifications</Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => logout()}>
                  <LogOut className="size-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  );
}
