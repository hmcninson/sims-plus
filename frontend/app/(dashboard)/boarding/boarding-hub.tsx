"use client";

import { useEffect, useState, useTransition } from "react";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Building2,
  BedDouble,
  Users,
  ClipboardCheck,
  ArrowRight,
  AlertTriangle,
  DoorOpen,
  UtensilsCrossed,
  AlertCircle,
  ShieldAlert,
} from "lucide-react";
import { getBoardingStats, getExeats } from "@/actions/boarding.action";
import type { BoardingStats, ExeatDetail } from "@/types";

function getExeatStatusBadge(status: string) {
  switch (status) {
    case "pending":
      return <Badge variant="secondary">Pending</Badge>;
    case "approved":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">Approved</Badge>;
    case "active":
      return <Badge>Active</Badge>;
    case "overdue":
      return <Badge variant="destructive">Overdue</Badge>;
    case "returned":
      return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Returned</Badge>;
    case "denied":
      return <Badge variant="outline">Denied</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

export function BoardingHub() {
  const [isPending, startTransition] = useTransition();
  const [stats, setStats] = useState<BoardingStats | null>(null);
  const [recentExeats, setRecentExeats] = useState<ExeatDetail[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    startTransition(async () => {
      const [statsResult, exeatsResult] = await Promise.all([
        getBoardingStats(),
        getExeats({ pageSize: 5 }),
      ]);

      if (statsResult.success && statsResult.data) {
        setStats(statsResult.data);
      } else {
        setError(statsResult.error || "Failed to load boarding stats");
      }

      if (exeatsResult.success && exeatsResult.data) {
        const data = exeatsResult.data;
        setRecentExeats(Array.isArray(data) ? data : (data.items ?? []));
      }
    });
  }, []);

  if (isPending && !stats) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-10 w-10 text-destructive" />
        <p className="text-muted-foreground">{error}</p>
      </div>
    );
  }

  const occupancyRate =
    stats && stats.total_beds > 0
      ? Math.round((stats.occupied_beds / stats.total_beds) * 100)
      : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Boarding Management</h1>
        <p className="text-muted-foreground">
          Manage boarding houses, dormitories, exeats, and dining
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Houses</CardTitle>
            <Building2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_houses ?? "--"}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.total_dormitories ?? 0} dormitories
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Beds</CardTitle>
            <BedDouble className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_beds ?? "--"}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.available_beds ?? 0} available
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Occupancy Rate</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{occupancyRate}%</div>
            <p className="text-xs text-muted-foreground">
              {stats?.total_boarders ?? 0} boarders
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Active Exeats</CardTitle>
            <DoorOpen className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.active_exeats ?? "--"}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.pending_exeats ?? 0} pending approval
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Alert banner for unresolved incidents */}
      {stats && stats.unresolved_incidents > 0 && (
        <Card className="border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950">
          <CardContent className="flex items-center gap-3 p-4">
            <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                {stats.unresolved_incidents} unresolved incident{stats.unresolved_incidents !== 1 ? "s" : ""}
              </p>
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Review and resolve outstanding boarding incidents
              </p>
            </div>
            <Button variant="outline" size="sm" asChild>
              <Link href="/boarding/incidents">View Incidents</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Quick Actions */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2">
            <Button variant="outline" className="justify-start" asChild>
              <Link href="/boarding/houses">
                <Building2 className="mr-2 h-4 w-4" />
                Manage Houses
              </Link>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <Link href="/boarding/assignments">
                <Users className="mr-2 h-4 w-4" />
                Manage Assignments
              </Link>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <Link href="/boarding/roll-call">
                <ClipboardCheck className="mr-2 h-4 w-4" />
                Roll Call
              </Link>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <Link href="/boarding/exeats">
                <DoorOpen className="mr-2 h-4 w-4" />
                Exeats
              </Link>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <Link href="/boarding/incidents">
                <ShieldAlert className="mr-2 h-4 w-4" />
                Incidents
              </Link>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <Link href="/boarding/dining">
                <UtensilsCrossed className="mr-2 h-4 w-4" />
                Dining
              </Link>
            </Button>
          </CardContent>
        </Card>

        {/* Recent Exeats */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent Exeats</CardTitle>
              <CardDescription>Latest exeat requests</CardDescription>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/boarding/exeats">
                View All <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {recentExeats.length > 0 ? (
              <div className="space-y-3">
                {recentExeats.map((exeat) => (
                  <div
                    key={exeat.id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="space-y-1">
                      <p className="text-sm font-medium">
                        {exeat.student_name || "Unknown Student"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {exeat.exeat_type} -- {exeat.start_date} to {exeat.end_date}
                      </p>
                    </div>
                    {getExeatStatusBadge(exeat.status)}
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex h-[150px] flex-col items-center justify-center gap-2 text-muted-foreground">
                <DoorOpen className="h-8 w-8" />
                <p className="text-sm">No recent exeats</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
