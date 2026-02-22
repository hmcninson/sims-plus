"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Users,
  CreditCard,
  GraduationCap,
  CalendarCheck,
  TrendingUp,
  ChevronRight,
  Megaphone,
  Clock,
  AlertCircle,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { formatGHS, formatRelativeTime, getInitials } from "@/lib/format";
import type {
  ParentDashboardData,
  ChildSummary,
  UpcomingItem,
  Announcement,
  ActivityItem,
} from "@/types/parent.type";

interface ParentDashboardViewProps {
  userName: string;
  dashboard: ParentDashboardData | null;
}

export function ParentDashboardView({
  userName,
  dashboard,
}: ParentDashboardViewProps) {
  const children = dashboard?.children || [];
  const [selectedChild, setSelectedChild] = useState<ChildSummary | null>(
    children[0] || null
  );
  const overview = dashboard?.overview || null;
  const announcements = dashboard?.announcements || [];
  const upcoming = dashboard?.upcoming || [];

  return (
    <div className="space-y-6">
      {/* Welcome message */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Welcome back, {userName}
        </h1>
        <p className="text-sm text-muted-foreground">
          Here is an overview of your children&apos;s school activity.
        </p>
      </div>

      {/* Children selector -- horizontal scroll on mobile */}
      {children.length > 0 && (
        <div className="flex gap-3 overflow-x-auto pb-2 -mx-4 px-4 md:mx-0 md:px-0">
          {children.map((child) => (
            <button
              key={child.id}
              onClick={() => setSelectedChild(child)}
              className={cn(
                "flex shrink-0 items-center gap-3 rounded-lg border p-3 text-left transition-colors",
                selectedChild?.id === child.id
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50"
              )}
            >
              <Avatar className="h-10 w-10">
                <AvatarFallback className="bg-primary/10 text-primary text-sm">
                  {getInitials(`${child.first_name} ${child.last_name}`)}
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="text-sm font-medium">
                  {child.first_name} {child.last_name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {child.class_name}
                  {child.section_name ? ` ${child.section_name}` : ""}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Empty state for no children */}
      {children.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <Users className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No children linked yet</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-sm">
              Your children will appear here once the school administrator links
              them to your account.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Quick stats for selected child */}
      {selectedChild && overview && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            title="Attendance"
            value={`${overview.stats.attendance_rate}%`}
            icon={CalendarCheck}
            href={`/parent/children/${selectedChild.id}?tab=attendance`}
            color="text-green-600"
          />
          <StatCard
            title="Average Score"
            value={
              overview.stats.average_score !== null
                ? `${overview.stats.average_score.toFixed(1)}%`
                : "--"
            }
            icon={GraduationCap}
            href={`/parent/children/${selectedChild.id}?tab=grades`}
            color="text-blue-600"
          />
          <StatCard
            title="Class Position"
            value={
              overview.stats.class_position !== null
                ? `${overview.stats.class_position}/${overview.stats.class_size || "--"}`
                : "--"
            }
            icon={TrendingUp}
            href={`/parent/children/${selectedChild.id}?tab=grades`}
            color="text-purple-600"
          />
          <StatCard
            title="Balance Due"
            value={formatGHS(overview.stats.outstanding_balance)}
            icon={CreditCard}
            href="/parent/payments"
            color={
              overview.stats.outstanding_balance > 0
                ? "text-amber-600"
                : "text-green-600"
            }
          />
        </div>
      )}

      {/* Content grid: Activity + Announcements */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Recent Activity */}
        {overview && overview.child && (
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base">Recent Activity</CardTitle>
              <Link
                href={`/parent/children/${selectedChild?.id}`}
                className="text-xs text-primary hover:underline"
              >
                View all
              </Link>
            </CardHeader>
            <CardContent>
              {overview.recent_activity.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  No recent activity to show.
                </p>
              ) : (
                <div className="space-y-4">
                  {overview.recent_activity.slice(0, 5).map((activity) => (
                    <ActivityRow key={activity.id} activity={activity} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Announcements */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base">Announcements</CardTitle>
            <Link
              href="/parent/announcements"
              className="text-xs text-primary hover:underline"
            >
              View all
            </Link>
          </CardHeader>
          <CardContent>
            {announcements.length === 0 ? (
              <div className="flex flex-col items-center py-6 text-center">
                <Megaphone className="h-8 w-8 text-muted-foreground mb-2" />
                <p className="text-sm text-muted-foreground">
                  No announcements at this time.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                {announcements.slice(0, 4).map((ann) => (
                  <AnnouncementRow key={ann.id} announcement={ann} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Upcoming Events */}
      {upcoming.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Upcoming</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {upcoming.map((item, idx) => (
                <UpcomingRow key={idx} item={item} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quick action buttons on mobile */}
      <div className="grid grid-cols-2 gap-3 md:hidden">
        <Button
          variant="outline"
          className="h-auto py-4 flex flex-col items-center gap-2"
          asChild
        >
          <Link href="/parent/payments">
            <CreditCard className="h-5 w-5 text-primary" />
            <span className="text-xs">Pay Fees</span>
          </Link>
        </Button>
        <Button
          variant="outline"
          className="h-auto py-4 flex flex-col items-center gap-2"
          asChild
        >
          <Link href="/parent/children">
            <Users className="h-5 w-5 text-primary" />
            <span className="text-xs">View Children</span>
          </Link>
        </Button>
      </div>
    </div>
  );
}

// =========================
// Sub-components
// =========================

function StatCard({
  title,
  value,
  icon: Icon,
  href,
  color,
}: {
  title: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  href: string;
  color?: string;
}) {
  return (
    <Link href={href}>
      <Card className="hover:shadow-md transition-shadow cursor-pointer">
        <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
          <CardTitle className="text-xs font-medium text-muted-foreground">
            {title}
          </CardTitle>
          <Icon className={cn("h-4 w-4", color || "text-muted-foreground")} />
        </CardHeader>
        <CardContent>
          <div className={cn("text-xl font-bold", color)}>{value}</div>
        </CardContent>
      </Card>
    </Link>
  );
}

const activityTypeIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  grade: GraduationCap,
  attendance: CalendarCheck,
  finance: CreditCard,
  announcement: Megaphone,
  note: AlertCircle,
};

const activityTypeColors: Record<string, string> = {
  grade: "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300",
  attendance: "bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300",
  finance: "bg-amber-100 text-amber-600 dark:bg-amber-900 dark:text-amber-300",
  announcement: "bg-purple-100 text-purple-600 dark:bg-purple-900 dark:text-purple-300",
  note: "bg-red-100 text-red-600 dark:bg-red-900 dark:text-red-300",
};

function ActivityRow({ activity }: { activity: ActivityItem }) {
  const Icon = activityTypeIcons[activity.type] || AlertCircle;
  const colorClass =
    activityTypeColors[activity.type] ||
    "bg-muted text-muted-foreground";

  return (
    <div className="flex items-start gap-3">
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          colorClass
        )}
      >
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{activity.title}</p>
        <p className="text-xs text-muted-foreground truncate">
          {activity.description}
        </p>
      </div>
      <span className="text-xs text-muted-foreground whitespace-nowrap">
        {formatRelativeTime(activity.date)}
      </span>
    </div>
  );
}

const priorityStyles: Record<string, string> = {
  urgent: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  important: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  normal: "",
};

function AnnouncementRow({ announcement }: { announcement: Announcement }) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium truncate">{announcement.title}</p>
          {announcement.priority !== "normal" && (
            <Badge
              variant="secondary"
              className={cn(
                "text-[10px] h-5",
                priorityStyles[announcement.priority]
              )}
            >
              {announcement.priority}
            </Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground line-clamp-2 mt-0.5">
          {announcement.content}
        </p>
        <p className="text-[10px] text-muted-foreground mt-1">
          {announcement.author_name} &middot;{" "}
          {announcement.published_at
            ? formatRelativeTime(announcement.published_at)
            : "Draft"}
        </p>
      </div>
      <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
    </div>
  );
}

const upcomingTypeColors: Record<string, string> = {
  exam: "bg-red-100 text-red-600 dark:bg-red-900 dark:text-red-300",
  payment_due: "bg-amber-100 text-amber-600 dark:bg-amber-900 dark:text-amber-300",
  term_start: "bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300",
  term_end: "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300",
  holiday: "bg-purple-100 text-purple-600 dark:bg-purple-900 dark:text-purple-300",
};

function UpcomingRow({ item }: { item: UpcomingItem }) {
  const colorClass =
    upcomingTypeColors[item.type] || "bg-muted text-muted-foreground";

  return (
    <div className="flex items-center gap-3">
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          colorClass
        )}
      >
        <Clock className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{item.title}</p>
        {item.description && (
          <p className="text-xs text-muted-foreground truncate">
            {item.description}
          </p>
        )}
      </div>
      <div className="text-right shrink-0">
        <p className="text-xs font-medium">{item.date}</p>
        {item.is_overdue && (
          <Badge variant="destructive" className="text-[10px] h-5">
            Overdue
          </Badge>
        )}
      </div>
    </div>
  );
}
