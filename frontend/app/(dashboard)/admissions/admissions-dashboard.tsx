"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PipelineChart } from "@/components/admissions/pipeline-chart";
import { ApplicationStatusBadge } from "@/components/admissions/application-status-badge";
import {
  Users,
  CheckCircle,
  Clock,
  TrendingUp,
  ArrowRight,
  FileText,
  GraduationCap,
  ClipboardList,
} from "lucide-react";
import {
  getAdmissionsDashboard,
  getAdmissionsDemographics,
} from "@/actions/admissions.action";
import type {
  AdmissionsDashboardStats,
  AdmissionsDemographicsData,
} from "@/types/admissions.type";

export function AdmissionsDashboardContent() {
  const [stats, setStats] = useState<AdmissionsDashboardStats | null>(null);
  const [demographics, setDemographics] =
    useState<AdmissionsDemographicsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      const [dashResult, demoResult] = await Promise.all([
        getAdmissionsDashboard(),
        getAdmissionsDemographics(),
      ]);

      if (dashResult.success && dashResult.data) {
        setStats(dashResult.data);
      }
      if (demoResult.success && demoResult.data) {
        setDemographics(demoResult.data);
      }
      setLoading(false);
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[100px]" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-[380px]" />
          <Skeleton className="h-[380px]" />
        </div>
        <Skeleton className="h-[300px]" />
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4 p-6">
        <FileText className="h-10 w-10 text-muted-foreground" />
        <p className="text-muted-foreground">
          Failed to load admissions dashboard
        </p>
        <Button variant="outline" onClick={() => window.location.reload()}>
          Try Again
        </Button>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Admissions Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Overview of the admissions pipeline
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild>
            <Link href="/admissions/applications">
              <ClipboardList className="mr-2 h-4 w-4" />
              View Applications
            </Link>
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Total Applications
            </CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.total_applications}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Pending Decisions
            </CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.pending_decisions}</div>
            {stats.pending_decisions > 0 && (
              <Link
                href="/admissions/decisions"
                className="text-xs text-primary hover:underline"
              >
                Review now
              </Link>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Awaiting Enrollment
            </CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.pending_enrollment}</div>
            {stats.pending_enrollment > 0 && (
              <Link
                href="/admissions/enrollment"
                className="text-xs text-primary hover:underline"
              >
                Enroll now
              </Link>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              Conversion Rate
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.conversion_rate != null
                ? `${(Number(stats.conversion_rate) * 100).toFixed(1)}%`
                : "--"}
            </div>
            <p className="text-xs text-muted-foreground">
              Enrolled / Total
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Button variant="outline" className="h-auto py-3" asChild>
          <Link href="/admissions/periods">
            <div className="flex flex-col items-center gap-1 text-center">
              <FileText className="h-5 w-5" />
              <span className="text-xs">Manage Periods</span>
            </div>
          </Link>
        </Button>
        <Button variant="outline" className="h-auto py-3" asChild>
          <Link href="/admissions/exams">
            <div className="flex flex-col items-center gap-1 text-center">
              <GraduationCap className="h-5 w-5" />
              <span className="text-xs">Entrance Exams</span>
            </div>
          </Link>
        </Button>
        <Button variant="outline" className="h-auto py-3" asChild>
          <Link href="/admissions/promotions">
            <div className="flex flex-col items-center gap-1 text-center">
              <TrendingUp className="h-5 w-5" />
              <span className="text-xs">Promotions</span>
            </div>
          </Link>
        </Button>
        <Button variant="outline" className="h-auto py-3" asChild>
          <Link href="/admissions/return-intents">
            <div className="flex flex-col items-center gap-1 text-center">
              <ClipboardList className="h-5 w-5" />
              <span className="text-xs">Return Intents</span>
            </div>
          </Link>
        </Button>
      </div>

      {/* Pipeline + By Class */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Application Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <PipelineChart data={stats.by_status} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>By Target Class</CardTitle>
          </CardHeader>
          <CardContent>
            {stats.by_class.length === 0 ? (
              <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
                No class data available
              </div>
            ) : (
              <div className="space-y-3">
                {stats.by_class.map((item) => {
                  const maxCount = Math.max(
                    ...stats.by_class.map((c) => c.count)
                  );
                  const width =
                    maxCount > 0
                      ? Math.max((item.count / maxCount) * 100, 5)
                      : 0;
                  return (
                    <div key={item.class_name} className="space-y-1">
                      <div className="flex justify-between text-sm">
                        <span>{item.class_name}</span>
                        <span className="font-medium">{item.count}</span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-muted">
                        <div
                          className="h-2 rounded-full bg-primary transition-all"
                          style={{ width: `${width}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Demographics */}
      {demographics && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Gender Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-6">
                {Object.entries(demographics.by_gender).map(
                  ([gender, count]) => (
                    <div key={gender} className="text-center">
                      <p className="text-2xl font-bold">{count}</p>
                      <p className="text-sm text-muted-foreground capitalize">
                        {gender}
                      </p>
                    </div>
                  )
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">By Period</CardTitle>
            </CardHeader>
            <CardContent>
              {stats.by_period.length === 0 ? (
                <p className="text-sm text-muted-foreground">No period data</p>
              ) : (
                <div className="space-y-2">
                  {stats.by_period.map((item) => (
                    <div
                      key={item.period_name}
                      className="flex justify-between items-center"
                    >
                      <span className="text-sm">{item.period_name}</span>
                      <span className="font-medium">{item.count}</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Recent Applications */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Recent Applications</CardTitle>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/admissions/applications">
              View All
              <ArrowRight className="ml-1 h-4 w-4" />
            </Link>
          </Button>
        </CardHeader>
        <CardContent>
          {stats.recent_applications.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No applications yet
            </p>
          ) : (
            <div className="space-y-2">
              {stats.recent_applications.map((app) => (
                <Link
                  key={app.id}
                  href={`/admissions/applications/${app.id}`}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-lg p-3 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div>
                      <span className="font-medium">
                        {app.applicant_first_name} {app.applicant_last_name}
                      </span>
                      {app.target_class_name && (
                        <span className="ml-2 text-sm text-muted-foreground">
                          {app.target_class_name}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <ApplicationStatusBadge status={app.status} />
                    <span className="text-xs text-muted-foreground">
                      {new Date(app.created_at).toLocaleDateString("en-GB")}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
