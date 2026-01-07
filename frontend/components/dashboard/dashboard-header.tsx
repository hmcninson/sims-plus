"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, HelpCircle, Search, Settings } from "lucide-react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

interface User {
  first_name: string;
  last_name: string;
  email: string;
  role: string;
}

interface DashboardHeaderProps {
  user: User;
}

// Map paths to readable names
const pathNames: Record<string, string> = {
  dashboard: "Dashboard",
  students: "Students",
  staff: "Staff",
  classes: "Classes",
  attendance: "Attendance",
  exams: "Examinations",
  finance: "Finance",
  boarding: "Boarding",
  transport: "Transport",
  messages: "Messages",
  reports: "Reports",
  settings: "Settings",
  enrollments: "Enrollments",
  guardians: "Guardians",
  departments: "Departments",
  subjects: "Subjects",
  timetable: "Timetable",
  mark: "Mark Attendance",
  scores: "Score Entry",
  "report-cards": "Report Cards",
  grading: "Grading",
  fees: "Fee Structure",
  invoices: "Invoices",
  payments: "Payments",
  dormitories: "Dormitories",
  exeats: "Exeats",
  "roll-call": "Roll Call",
  routes: "Routes",
  vehicles: "Vehicles",
  assignments: "Assignments",
  announcements: "Announcements",
  sms: "SMS",
  email: "Email",
  academic: "Academic Reports",
  financial: "Financial Reports",
  profile: "Profile",
  account: "Account",
  appearance: "Appearance",
  notifications: "Notifications",
  billing: "Billing",
  users: "Users",
  school: "School",
  communication: "Communication",
  data: "Data Management",
};

// Map parent paths to detail page names (for dynamic routes like /students/[id])
const detailPageNames: Record<string, string> = {
  students: "Student Profile",
  staff: "Staff Profile",
  classes: "Class Details",
  guardians: "Guardian Details",
  invoices: "Invoice Details",
  payments: "Payment Details",
  exams: "Exam Details",
};

// Check if a string is a UUID
function isUUID(str: string): boolean {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  return uuidRegex.test(str);
}

function getBreadcrumbs(pathname: string) {
  const segments = pathname.split("/").filter(Boolean);
  const breadcrumbs = [];

  let currentPath = "";
  for (let i = 0; i < segments.length; i++) {
    currentPath += `/${segments[i]}`;
    const segment = segments[i];

    let name: string;
    if (isUUID(segment)) {
      // For UUIDs, use the parent segment to determine the detail page name
      const parentSegment = segments[i - 1];
      name = detailPageNames[parentSegment] || "Details";
    } else {
      name = pathNames[segment] || segment.charAt(0).toUpperCase() + segment.slice(1);
    }

    breadcrumbs.push({
      name,
      path: currentPath,
      isLast: i === segments.length - 1,
    });
  }

  return breadcrumbs;
}

export function DashboardHeader({ user }: DashboardHeaderProps) {
  const pathname = usePathname();
  const breadcrumbs = getBreadcrumbs(pathname);

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4">
      <SidebarTrigger className="-ml-1 h-8 w-8 border-none shadow-none [&>svg]:size-4" />

      {/* Breadcrumb */}
      <Breadcrumb className="hidden md:flex">
        <BreadcrumbList>
          {breadcrumbs.map((crumb, index) => (
            <React.Fragment key={crumb.path}>
              <BreadcrumbItem>
                {crumb.isLast ? (
                  <BreadcrumbPage>{crumb.name}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink href={crumb.path}>{crumb.name}</BreadcrumbLink>
                )}
              </BreadcrumbItem>
              {!crumb.isLast && <BreadcrumbSeparator />}
            </React.Fragment>
          ))}
        </BreadcrumbList>
      </Breadcrumb>

      {/* Mobile title */}
      <h1 className="font-semibold md:hidden">
        {breadcrumbs[breadcrumbs.length - 1]?.name || "Dashboard"}
      </h1>

      {/* Right side */}
      <div className="ml-auto flex items-center gap-2">
        {/* Search - hidden on mobile */}
        <div className="relative hidden lg:block">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search..."
            className="w-64 pl-8 h-9"
          />
        </div>

        {/* Search button - mobile */}
        <Button variant="ghost" size="icon" className="lg:hidden h-9 w-9">
          <Search className="h-4 w-4" />
          <span className="sr-only">Search</span>
        </Button>

        {/* Notifications */}
        <Button variant="ghost" size="icon" className="h-9 w-9 relative">
          <Bell className="h-4 w-4" />
          <span className="sr-only">Notifications</span>
          <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-medium text-primary-foreground">
            3
          </span>
        </Button>

        {/* Help */}
        <Button variant="ghost" size="icon" className="h-9 w-9">
          <HelpCircle className="h-4 w-4" />
          <span className="sr-only">Help</span>
        </Button>

        {/* Settings */}
        <Button variant="ghost" size="icon" className="h-9 w-9" asChild>
          <Link href="/settings">
            <Settings className="h-4 w-4" />
            <span className="sr-only">Settings</span>
          </Link>
        </Button>
      </div>
    </header>
  );
}
