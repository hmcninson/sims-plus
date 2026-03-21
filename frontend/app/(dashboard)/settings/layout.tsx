"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  User,
  Shield,
  Palette,
  Bell,
  School,
  GraduationCap,
  Users,
  CreditCard,
  Mail,
  Database,
  Baby,
  ScrollText,
  BookOpen,
} from "lucide-react";

const settingsNavItems = [
  {
    title: "Personal",
    items: [
      {
        title: "Profile",
        href: "/settings",
        icon: User,
        description: "Your personal information",
      },
      {
        title: "Account",
        href: "/settings/account",
        icon: Shield,
        description: "Security and password",
      },
      {
        title: "Appearance",
        href: "/settings/appearance",
        icon: Palette,
        description: "Theme and display",
      },
      {
        title: "Notifications",
        href: "/settings/notifications",
        icon: Bell,
        description: "Email and alerts",
      },
    ],
  },
  {
    title: "School",
    items: [
      {
        title: "School Profile",
        href: "/settings/school",
        icon: School,
        description: "School info and branding",
      },
      {
        title: "Academic",
        href: "/settings/academic",
        icon: GraduationCap,
        description: "Years, terms, grading",
      },
      {
        title: "Curriculum",
        href: "/settings/curriculum",
        icon: BookOpen,
        description: "Curriculum profiles, assessment",
      },
      {
        title: "Preschool",
        href: "/settings/preschool",
        icon: Baby,
        description: "Configuration, learning areas",
      },
      {
        title: "Users & Roles",
        href: "/settings/users",
        icon: Users,
        description: "Manage users and permissions",
      },
      {
        title: "Communication",
        href: "/settings/communication",
        icon: Mail,
        description: "SMS and email settings",
      },
    ],
  },
  {
    title: "System",
    items: [
      {
        title: "Subscription",
        href: "/settings/subscription",
        icon: CreditCard,
        description: "Plan, billing, and add-ons",
      },
      {
        title: "Data",
        href: "/settings/data",
        icon: Database,
        description: "Import, export, backup",
      },
      {
        title: "Audit Log",
        href: "/settings/audit-log",
        icon: ScrollText,
        description: "Security event history",
      },
    ],
  },
];

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account and school settings.
        </p>
      </div>

      <div className="flex flex-col gap-6 lg:flex-row lg:gap-10">
        {/* Settings sidebar navigation */}
        <aside className="lg:w-64 lg:shrink-0">
          <nav className="flex flex-col gap-6">
            {settingsNavItems.map((group) => (
              <div key={group.title}>
                <h4 className="mb-2 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {group.title}
                </h4>
                <ul className="space-y-1">
                  {group.items.map((item) => {
                    const isActive =
                      pathname === item.href ||
                      (item.href !== "/settings" &&
                        pathname.startsWith(item.href + "/"));
                    return (
                      <li key={item.href}>
                        <Link
                          href={item.href}
                          className={cn(
                            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                            isActive
                              ? "bg-primary text-primary-foreground"
                              : "text-muted-foreground hover:bg-muted hover:text-foreground"
                          )}
                        >
                          <item.icon className="h-4 w-4" />
                          <span>{item.title}</span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
        </aside>

        {/* Settings content */}
        <main className="flex-1 lg:max-w-3xl">{children}</main>
      </div>
    </div>
  );
}
