"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  UserCog,
  GraduationCap,
  ClipboardCheck,
  FileText,
  Wallet,
  Building2,
  Bus,
  MessageSquare,
  BarChart3,
  ChevronRight,
  School,
  LogOut,
  ChevronsUpDown,
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
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
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

interface User {
  first_name: string;
  last_name: string;
  email: string;
  role: string;
}

interface AppSidebarProps extends React.ComponentProps<typeof Sidebar> {
  user: User;
  schoolName?: string;
}

interface SubItem {
  title: string;
  url: string;
}

interface NavItem {
  title: string;
  url: string;
  icon: React.ComponentType<{ className?: string }>;
  subItems?: SubItem[];
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

// Navigation structure organized by modules
const navigationGroups: NavGroup[] = [
  {
    label: "Overview",
    items: [
      {
        title: "Dashboard",
        url: "/dashboard",
        icon: LayoutDashboard,
      },
    ],
  },
  {
    label: "People",
    items: [
      {
        title: "Students",
        url: "/students",
        icon: Users,
        subItems: [
          { title: "All Students", url: "/students" },
          { title: "Enrollments", url: "/students/enrollments" },
          { title: "Guardians", url: "/students/guardians" },
        ],
      },
      {
        title: "Staff",
        url: "/staff",
        icon: UserCog,
        subItems: [
          { title: "All Staff", url: "/staff" },
          { title: "Departments", url: "/staff/departments" },
        ],
      },
    ],
  },
  {
    label: "Academics",
    items: [
      {
        title: "Classes",
        url: "/classes",
        icon: GraduationCap,
        subItems: [
          { title: "All Classes", url: "/classes" },
          { title: "Subjects", url: "/classes/subjects" },
          { title: "Timetable", url: "/classes/timetable" },
        ],
      },
      {
        title: "Attendance",
        url: "/attendance",
        icon: ClipboardCheck,
        subItems: [
          { title: "Mark Attendance", url: "/attendance/mark" },
          { title: "Reports", url: "/attendance/reports" },
        ],
      },
      {
        title: "Examinations",
        url: "/exams",
        icon: FileText,
        subItems: [
          { title: "Exams", url: "/exams" },
          { title: "Score Entry", url: "/exams/scores" },
          { title: "Report Cards", url: "/exams/report-cards" },
          { title: "Grading", url: "/exams/grading" },
        ],
      },
    ],
  },
  {
    label: "Finance",
    items: [
      {
        title: "Finance",
        url: "/finance",
        icon: Wallet,
        subItems: [
          { title: "Overview", url: "/finance" },
          { title: "Fee Structure", url: "/finance/fees" },
          { title: "Invoices", url: "/finance/invoices" },
          { title: "Payments", url: "/finance/payments" },
          { title: "Reports", url: "/finance/reports" },
        ],
      },
    ],
  },
  {
    label: "Facilities",
    items: [
      {
        title: "Boarding",
        url: "/boarding",
        icon: Building2,
        subItems: [
          { title: "Dormitories", url: "/boarding/dormitories" },
          { title: "Exeats", url: "/boarding/exeats" },
          { title: "Roll Call", url: "/boarding/roll-call" },
        ],
      },
      {
        title: "Transport",
        url: "/transport",
        icon: Bus,
        subItems: [
          { title: "Routes", url: "/transport/routes" },
          { title: "Vehicles", url: "/transport/vehicles" },
          { title: "Assignments", url: "/transport/assignments" },
        ],
      },
    ],
  },
  {
    label: "Communication",
    items: [
      {
        title: "Messages",
        url: "/messages",
        icon: MessageSquare,
        subItems: [
          { title: "Announcements", url: "/messages/announcements" },
          { title: "SMS", url: "/messages/sms" },
          { title: "Email", url: "/messages/email" },
        ],
      },
    ],
  },
  {
    label: "Analytics",
    items: [
      {
        title: "Reports",
        url: "/reports",
        icon: BarChart3,
        subItems: [
          { title: "Overview", url: "/reports" },
          { title: "Academic", url: "/reports/academic" },
          { title: "Financial", url: "/reports/financial" },
          { title: "Attendance", url: "/reports/attendance" },
        ],
      },
    ],
  },
];

function NavItemComponent({
  item,
  pathname,
}: {
  item: NavItem;
  pathname: string;
}) {
  const isActive = pathname === item.url || pathname.startsWith(item.url + "/");
  const hasSubItems = item.subItems && item.subItems.length > 0;
  const { state } = useSidebar();
  const isCollapsed = state === "collapsed";

  if (!hasSubItems) {
    return (
      <SidebarMenuItem>
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
  }

  // When sidebar is collapsed, show dropdown menu for subitems
  if (isCollapsed) {
    return (
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton isActive={isActive} tooltip={item.title}>
              <item.icon className="size-4" />
              <span>{item.title}</span>
              <ChevronRight className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            side="right"
            align="start"
            sideOffset={8}
            className="min-w-48"
          >
            <DropdownMenuLabel>{item.title}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {item.subItems?.map((subItem) => (
              <DropdownMenuItem key={subItem.url} asChild>
                <Link
                  href={subItem.url}
                  className={pathname === subItem.url ? "bg-accent" : ""}
                >
                  {subItem.title}
                </Link>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    );
  }

  // When sidebar is expanded, use collapsible
  return (
    <Collapsible asChild defaultOpen={isActive} className="group/collapsible">
      <SidebarMenuItem>
        <CollapsibleTrigger asChild>
          <SidebarMenuButton tooltip={item.title} isActive={isActive}>
            <item.icon className="size-4" />
            <span>{item.title}</span>
            <ChevronRight className="ml-auto size-4 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
          </SidebarMenuButton>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <SidebarMenuSub>
            {item.subItems?.map((subItem) => (
              <SidebarMenuSubItem key={subItem.url}>
                <SidebarMenuSubButton
                  asChild
                  isActive={pathname === subItem.url}
                >
                  <Link href={subItem.url}>
                    <span>{subItem.title}</span>
                  </Link>
                </SidebarMenuSubButton>
              </SidebarMenuSubItem>
            ))}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  );
}

export function AppSidebar({ user, schoolName, ...props }: AppSidebarProps) {
  const pathname = usePathname();

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="h-14 border-b border-sidebar-border flex items-center px-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" className="h-10" asChild>
              <Link href="/dashboard">
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                  <School className="size-4" />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">
                    {schoolName || "SIMS Plus"}
                  </span>
                  <span className="truncate text-xs text-muted-foreground">
                    School Portal
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {navigationGroups.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {group.items.map((item) => (
                  <NavItemComponent key={item.url} item={item} pathname={pathname} />
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
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
                        {user.role.replace("_", " ")}
                      </span>
                    </div>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href="/settings">Profile</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link href="/settings/account">Account</Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <form action={logout} className="w-full">
                    <button
                      type="submit"
                      className="flex w-full items-center gap-2"
                    >
                      <LogOut className="size-4" />
                      Sign out
                    </button>
                  </form>
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
