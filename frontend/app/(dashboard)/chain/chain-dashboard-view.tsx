"use client";

/**
 * Chain Dashboard View
 *
 * Displays aggregated metrics across all schools in the chain.
 * Shows KPI cards at the top and a per-school breakdown table.
 */

import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { School, Users, UserCog, TrendingUp, Wallet, AlertCircle } from "lucide-react";
import type { ChainDashboard } from "@/types/chain.type";
import { formatCurrency } from "@/lib/format";

interface ChainDashboardViewProps {
  dashboard: ChainDashboard;
  error?: string;
}

function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function ChainDashboardView({ dashboard, error }: ChainDashboardViewProps) {
  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold tracking-tight">Chain Dashboard</h1>
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Chain Dashboard</h1>
          <p className="text-muted-foreground">
            Overview of all {dashboard.total_schools} schools in your chain.
          </p>
        </div>
        <Button asChild>
          <Link href="/chain/schools/new">Add School</Link>
        </Button>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Schools</CardTitle>
            <School className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{dashboard.total_schools}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Students</CardTitle>
            <Users className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {dashboard.total_students.toLocaleString()}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Staff</CardTitle>
            <UserCog className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {dashboard.total_staff.toLocaleString()}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Attendance Rate</CardTitle>
            <TrendingUp className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatPercent(dashboard.overall_attendance_rate)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Financial Summary */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Revenue</CardTitle>
            <Wallet className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(dashboard.total_revenue)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Outstanding</CardTitle>
            <Wallet className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-destructive">
              {formatCurrency(dashboard.total_outstanding)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Per-School Breakdown Table */}
      <Card>
        <CardHeader>
          <CardTitle>School Breakdown</CardTitle>
          <CardDescription>
            Performance metrics for each school in the chain.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {dashboard.schools.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              <School className="mx-auto mb-2 size-8" />
              <p>No schools in this chain yet.</p>
              <Button asChild variant="outline" className="mt-4">
                <Link href="/chain/schools/new">Add Your First School</Link>
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>School</TableHead>
                    <TableHead className="hidden sm:table-cell text-right">Students</TableHead>
                    <TableHead className="hidden sm:table-cell text-right">Staff</TableHead>
                    <TableHead className="hidden md:table-cell text-right">Attendance</TableHead>
                    <TableHead className="hidden md:table-cell text-right">Collected</TableHead>
                    <TableHead className="text-right">Outstanding</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {dashboard.schools.map((school) => (
                    <TableRow key={school.school_id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="flex size-8 items-center justify-center rounded bg-muted">
                            <School className="size-4 text-muted-foreground" />
                          </div>
                          <div>
                            <div className="font-medium">{school.school_name}</div>
                            {school.school_code && (
                              <div className="text-xs text-muted-foreground">
                                {school.school_code}
                              </div>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell text-right">
                        {school.total_students.toLocaleString()}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell text-right">
                        {school.total_staff.toLocaleString()}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-right">
                        <Badge variant={school.attendance_rate >= 90 ? "default" : "secondary"}>
                          {formatPercent(school.attendance_rate)}
                        </Badge>
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-right">
                        {formatCurrency(school.total_collected)}
                      </TableCell>
                      <TableCell className="text-right">
                        <span className={school.outstanding > 0 ? "text-destructive" : ""}>
                          {formatCurrency(school.outstanding)}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
