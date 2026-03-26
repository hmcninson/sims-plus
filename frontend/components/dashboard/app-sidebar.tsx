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
  Baby,
  Star,
  BookOpen,
  CalendarDays,
  FileHeart,
  Calendar,
  Megaphone,
  StickyNote,
  Link2,
  UserPlus,
  AlertTriangle,
  UserCheck,
  Clock,
  GitBranch,
  TrendingUp,
  Target,
  Briefcase,
  Banknote,
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
import { formatRoleLabel } from "@/lib/utils";
import { logout } from "@/actions/auth.action";
import { clearOfflineData } from "@/lib/offline/db";
import { SchoolSwitcher } from "@/components/layout/school-switcher";
import { useSchool } from "@/contexts/school-context";

interface User {
  first_name: string;
  last_name: string;
  email: string;
  role: string;
  /** Per-school role overrides for chain tenants (school UUID -> role string). */
  school_roles?: Record<string, string>;
}

interface AppSidebarProps extends React.ComponentProps<typeof Sidebar> {
  user: User;
  schoolName?: string;
  /** Whether the tenant is a school chain with multiple schools. */
  isChain?: boolean;
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
      {
        title: "Calendar",
        url: "/calendar",
        icon: Calendar,
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
          { title: "Workload", url: "/staff/workload" },
        ],
      },
    ],
  },
  {
    label: "Enrollment",
    items: [
      {
        title: "Admissions",
        url: "/admissions",
        icon: UserPlus,
        subItems: [
          { title: "Dashboard", url: "/admissions" },
          { title: "Inquiries", url: "/admissions/inquiries" },
          { title: "Applications", url: "/admissions/applications" },
          { title: "Entrance Exams", url: "/admissions/exams" },
          { title: "Decisions", url: "/admissions/decisions" },
          { title: "Enrollment", url: "/admissions/enrollment" },
          { title: "Promotions", url: "/admissions/promotions" },
          { title: "Return Intents", url: "/admissions/return-intents" },
          { title: "CSSPS Import", url: "/admissions/cssps" },
          { title: "Capacity Planning", url: "/admissions/capacity" },
          { title: "Events & Tours", url: "/admissions/events" },
          { title: "Analytics", url: "/admissions/analytics" },
          { title: "Periods", url: "/admissions/periods" },
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
          { title: "Staff Attendance", url: "/attendance/staff" },
        ],
      },
      {
        title: "Examinations",
        url: "/exams",
        icon: FileText,
        subItems: [
          { title: "All Exams", url: "/exams" },
          { title: "Continuous Assessment", url: "/exams/ca" },
          { title: "Report Cards", url: "/exams/report-cards" },
          { title: "External Exams", url: "/exams/external" },
          { title: "Predicted Grades", url: "/exams/predicted-grades" },
        ],
      },
    ],
  },
  {
    label: "Preschool",
    items: [
      {
        title: "Preschool",
        url: "/preschool",
        icon: Baby,
        subItems: [
          { title: "Skill Assessment", url: "/preschool/assessment" },
          { title: "Observations", url: "/preschool/observations" },
          { title: "Daily Logs", url: "/preschool/daily-logs" },
          { title: "Incidents", url: "/preschool/incidents" },
          { title: "Pickups", url: "/preschool/pickups" },
          { title: "Portfolio", url: "/preschool/portfolio" },
          { title: "Extended Care", url: "/preschool/extended-care" },
          { title: "Timeline", url: "/preschool/timeline" },
          { title: "Reports", url: "/preschool/reports" },
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
          { title: "Fee Types", url: "/finance/fee-types" },
          { title: "Fee Structures", url: "/finance/fee-structures" },
          { title: "Invoices", url: "/finance/invoices" },
          { title: "Payments", url: "/finance/payments" },
          { title: "Scholarships", url: "/finance/scholarships" },
          { title: "Credit Notes", url: "/finance/credit-notes" },
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
          { title: "Overview", url: "/boarding" },
          { title: "Houses", url: "/boarding/houses" },
          { title: "Dormitories", url: "/boarding/dormitories" },
          { title: "Assignments", url: "/boarding/assignments" },
          { title: "Roll Call", url: "/boarding/roll-call" },
          { title: "Exeats", url: "/boarding/exeats" },
          { title: "Incidents", url: "/boarding/incidents" },
          { title: "Dining", url: "/boarding/dining" },
        ],
      },
      {
        title: "Transport",
        url: "/transport",
        icon: Bus,
        subItems: [
          { title: "Overview", url: "/transport" },
          { title: "Vehicles", url: "/transport/vehicles" },
          { title: "Drivers", url: "/transport/drivers" },
          { title: "Routes", url: "/transport/routes" },
          { title: "Assignments", url: "/transport/assignments" },
          { title: "Trips", url: "/transport/trips" },
        ],
      },
    ],
  },
  {
    label: "HR",
    items: [
      {
        title: "Leave Management",
        url: "/hr/leave",
        icon: Briefcase,
        subItems: [
          { title: "Leave Requests", url: "/hr/leave/requests" },
          { title: "Leave Calendar", url: "/hr/leave/calendar" },
          { title: "My Leave", url: "/hr/leave/my-requests" },
          { title: "Leave Types", url: "/hr/leave/types" },
          { title: "Leave Balances", url: "/hr/leave/balances" },
        ],
      },
      {
        title: "Payroll",
        url: "/payroll",
        icon: Banknote,
        subItems: [
          { title: "Dashboard", url: "/payroll" },
          { title: "Runs", url: "/payroll/runs" },
          { title: "Settings", url: "/payroll/settings" },
          { title: "Reports", url: "/payroll/reports" },
          { title: "Audit Log", url: "/payroll/audit" },
          { title: "Loans", url: "/payroll/loans" },
          { title: "Loan Portfolio", url: "/payroll/loans/portfolio" },
        ],
      },
    ],
  },
  {
    label: "Communication",
    items: [
      {
        title: "Announcements",
        url: "/announcements",
        icon: Megaphone,
      },
      {
        title: "Teacher Notes",
        url: "/teacher-notes",
        icon: StickyNote,
      },
      {
        title: "Messages",
        url: "/messages",
        icon: MessageSquare,
        subItems: [
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

// Chain management navigation -- only shown for chain tenants
const chainNavigationGroup: NavGroup = {
  label: "Chain Management",
  items: [
    {
      title: "Chain Overview",
      url: "/chain",
      icon: Link2,
      subItems: [
        { title: "Dashboard", url: "/chain" },
        { title: "Schools", url: "/chain/schools" },
        { title: "Users", url: "/chain/users" },
      ],
    },
  ],
};

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

export function AppSidebar({ user, schoolName, isChain = false, ...props }: AppSidebarProps) {
  const pathname = usePathname();
  const { activeSchoolId } = useSchool();

  // Derive the role to display: use the school-specific role when available,
  // falling back to the user's global role for single-school tenants or when
  // no per-school override exists.
  const displayRole = React.useMemo(() => {
    if (activeSchoolId && user.school_roles?.[activeSchoolId]) {
      return user.school_roles[activeSchoolId];
    }
    return user.role;
  }, [activeSchoolId, user.school_roles, user.role]);

  // Build navigation groups, appending chain management for chain tenants
  const allGroups = isChain
    ? [...navigationGroups, chainNavigationGroup]
    : navigationGroups;

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader
        className="border-b border-sidebar-border px-2 py-2"
        style={{
          borderTopWidth: "3px",
          borderTopStyle: "solid",
          /* Tenant primary color accent along the top of the sidebar header */
          borderTopColor: "var(--tenant-primary-color, #1B4F72)",
        }}
      >
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" className="h-10" asChild>
              <Link href="/dashboard">
                <div
                  className="flex aspect-square size-8 items-center justify-center rounded-lg text-white"
                  style={{
                    /* Use tenant branding color for the school icon background */
                    backgroundColor: "var(--tenant-primary-color, #1B4F72)",
                  }}
                >
                  <School className="size-4" />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">
                    {schoolName || "SIMS Plus"}
                  </span>
                  <span className="truncate text-xs text-muted-foreground">
                    {isChain ? "School Chain" : "School Portal"}
                  </span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
          {/* School switcher -- only visible for chain tenants */}
          {isChain && (
            <SidebarMenuItem>
              <SchoolSwitcher schoolRoles={user.school_roles} />
            </SidebarMenuItem>
          )}
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        {allGroups.map((group) => (
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
                        {formatRoleLabel(displayRole)}
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
                <DropdownMenuItem
                  onSelect={async () => {
                    try { await clearOfflineData(); } catch { /* ignore */ }
                    // Clear the active-school cookie so chain users don't have
                    // a stale school context carried into the next session.
                    document.cookie = "x-active-school=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
                    await logout();
                  }}
                >
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
