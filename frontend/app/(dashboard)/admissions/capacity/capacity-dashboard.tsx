"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { CapacityChart } from "@/components/admissions/capacity-chart";
import { CapacityTable } from "@/components/admissions/capacity-table";
import { Target, Users, TrendingUp, AlertTriangle } from "lucide-react";
import { getCapacityDashboard } from "@/actions/capacity.action";
import { getAcademicYears } from "@/actions/academic.action";
import type { AcademicYear } from "@/types";
import type { CapacityDashboardResponse } from "@/types/admissions.type";

export function CapacityDashboard() {
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [selectedYearId, setSelectedYearId] = useState<string>("");
  const [dashboard, setDashboard] = useState<CapacityDashboardResponse | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [loadingDashboard, setLoadingDashboard] = useState(false);

  // Load academic years
  useEffect(() => {
    async function loadYears() {
      const result = await getAcademicYears(false);
      if (result.success) {
        setAcademicYears(result.data);
        const currentYear = result.data.find((y) => y.is_current);
        if (currentYear) {
          setSelectedYearId(currentYear.id);
        } else if (result.data.length > 0) {
          setSelectedYearId(result.data[0].id);
        }
      } else {
        toast.error(result.error);
      }
      setLoading(false);
    }
    loadYears();
  }, []);

  // Load dashboard data when year changes
  const loadDashboard = useCallback(async () => {
    if (!selectedYearId) return;
    setLoadingDashboard(true);
    const result = await getCapacityDashboard(selectedYearId);
    if (result.success) {
      setDashboard(result.data);
    } else {
      toast.error(result.error);
    }
    setLoadingDashboard(false);
  }, [selectedYearId]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  if (loading) {
    return (
      <div className="space-y-6 p-4 md:p-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-[350px]" />
      </div>
    );
  }

  const fillRate =
    dashboard?.total_capacity && dashboard.total_capacity > 0
      ? ((dashboard.total_enrolled / dashboard.total_capacity) * 100).toFixed(1)
      : null;

  return (
    <div className="space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Capacity Planning</h1>
          <p className="text-sm text-muted-foreground">
            Track enrollment targets and class capacity
          </p>
        </div>
        <Select value={selectedYearId} onValueChange={setSelectedYearId}>
          <SelectTrigger className="w-full sm:w-[220px]">
            <SelectValue placeholder="Select academic year" />
          </SelectTrigger>
          <SelectContent>
            {academicYears.map((year) => (
              <SelectItem key={year.id} value={year.id}>
                {year.name}
                {year.is_current ? " (Current)" : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {loadingDashboard ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
          <Skeleton className="h-[350px]" />
        </div>
      ) : dashboard ? (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Total Capacity
                </CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {dashboard.total_capacity ?? "--"}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Total Target
                </CardTitle>
                <Target className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {dashboard.total_target ?? "--"}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Total Enrolled
                </CardTitle>
                <TrendingUp className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {dashboard.total_enrolled}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  Fill Rate
                </CardTitle>
                <AlertTriangle className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {fillRate ? `${fillRate}%` : "--"}
                </div>
                <p className="text-xs text-muted-foreground">
                  Pipeline: {dashboard.total_pipeline}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Target vs Enrolled by Class
              </CardTitle>
            </CardHeader>
            <CardContent>
              <CapacityChart classes={dashboard.classes} />
            </CardContent>
          </Card>

          {/* Table */}
          <CapacityTable
            classes={dashboard.classes}
            academicYearId={selectedYearId}
            onRefresh={loadDashboard}
          />
        </>
      ) : (
        <Card>
          <CardContent className="flex h-[200px] items-center justify-center text-muted-foreground">
            Select an academic year to view capacity data.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
