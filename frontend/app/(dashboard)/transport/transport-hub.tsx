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
  Bus,
  Users,
  Route,
  MapPin,
  ArrowRight,
  AlertCircle,
  Wrench,
  Navigation,
  ClipboardList,
} from "lucide-react";
import { getTransportStats, getTrips } from "@/actions/transport.action";
import type { TransportStats, TripLogDetail } from "@/types";

function getTripStatusBadge(status: string) {
  switch (status) {
    case "scheduled":
      return <Badge variant="secondary">Scheduled</Badge>;
    case "in_progress":
      return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">In Progress</Badge>;
    case "completed":
      return <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">Completed</Badge>;
    case "cancelled":
      return <Badge variant="destructive">Cancelled</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

export function TransportHub() {
  const [isPending, startTransition] = useTransition();
  const [stats, setStats] = useState<TransportStats | null>(null);
  const [recentTrips, setRecentTrips] = useState<TripLogDetail[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    startTransition(async () => {
      const [statsResult, tripsResult] = await Promise.all([
        getTransportStats(),
        getTrips({ pageSize: 5 }),
      ]);

      if (statsResult.success && statsResult.data) {
        setStats(statsResult.data);
      } else {
        setError(statsResult.error || "Failed to load transport stats");
      }

      if (tripsResult.success && tripsResult.data) {
        const data = tripsResult.data;
        setRecentTrips(Array.isArray(data) ? data : (data.items ?? []));
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Transport Management</h1>
        <p className="text-muted-foreground">
          Manage vehicles, drivers, routes, and student transport
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Vehicles</CardTitle>
            <Bus className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_vehicles ?? "--"}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.active_vehicles ?? 0} active, {stats?.maintenance_vehicles ?? 0} in maintenance
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Drivers</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_drivers ?? "--"}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.active_drivers ?? 0} active
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Routes</CardTitle>
            <Route className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_routes ?? "--"}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.active_routes ?? 0} active
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Students Assigned</CardTitle>
            <MapPin className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_students_assigned ?? "--"}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.trips_today ?? 0} trips today
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Maintenance Alert */}
      {stats && stats.maintenance_vehicles > 0 && (
        <Card className="border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950">
          <CardContent className="flex items-center gap-3 p-4">
            <Wrench className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                {stats.maintenance_vehicles} vehicle{stats.maintenance_vehicles !== 1 ? "s" : ""} in maintenance
              </p>
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Review vehicle status and schedule repairs
              </p>
            </div>
            <Button variant="outline" size="sm" asChild>
              <Link href="/transport/vehicles">View Vehicles</Link>
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
              <Link href="/transport/vehicles">
                <Bus className="mr-2 h-4 w-4" />
                Manage Vehicles
              </Link>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <Link href="/transport/drivers">
                <Users className="mr-2 h-4 w-4" />
                Manage Drivers
              </Link>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <Link href="/transport/routes">
                <Route className="mr-2 h-4 w-4" />
                Manage Routes
              </Link>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <Link href="/transport/assignments">
                <MapPin className="mr-2 h-4 w-4" />
                Student Assignments
              </Link>
            </Button>
            <Button variant="outline" className="justify-start" asChild>
              <Link href="/transport/trips">
                <Navigation className="mr-2 h-4 w-4" />
                Trip Logs
              </Link>
            </Button>
          </CardContent>
        </Card>

        {/* Recent Trips */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent Trips</CardTitle>
              <CardDescription>Latest trip logs</CardDescription>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/transport/trips">
                View All <ArrowRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {recentTrips.length > 0 ? (
              <div className="space-y-3">
                {recentTrips.map((trip) => (
                  <div
                    key={trip.id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="space-y-1">
                      <p className="text-sm font-medium">
                        {trip.route_name || "Unknown Route"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {trip.vehicle_registration || "--"} -- {trip.driver_name || "--"} --{" "}
                        {new Date(trip.trip_date + "T00:00:00").toLocaleDateString("en-GB")}
                      </p>
                    </div>
                    {getTripStatusBadge(trip.status)}
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex h-[150px] flex-col items-center justify-center gap-2 text-muted-foreground">
                <ClipboardList className="h-8 w-8" />
                <p className="text-sm">No recent trips</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
