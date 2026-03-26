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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { EnrollmentFunnel } from "@/components/admissions/enrollment-funnel";
import { TrendChart } from "@/components/admissions/trend-chart";
import { LeadSourceChart } from "@/components/admissions/lead-source-chart";
import { AttritionReport } from "@/components/admissions/attrition-report";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { TrendingUp, Users, Target, ArrowDownRight } from "lucide-react";
import {
  getAdmissionsFunnel,
  getEnrollmentTrends,
  getLeadSourceEffectiveness,
  getAttritionAnalysis,
  getEnrollmentVsCapacity,
  getReEnrollmentRates,
} from "@/actions/admissions.action";
import { getAdmissionPeriods } from "@/actions/admissions.action";
import { getAcademicYears } from "@/actions/academic.action";
import type { AcademicYear } from "@/types";
import type {
  FunnelResponse,
  TrendsResponse,
  SourceEffectivenessResponse,
  AttritionResponse,
  EnrollmentVsCapacityResponse,
  ReEnrollmentResponse,
  AdmissionPeriod,
} from "@/types/admissions.type";

export function AnalyticsDashboard() {
  const [loading, setLoading] = useState(true);

  // Filter state
  const [periods, setPeriods] = useState<AdmissionPeriod[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<string>("all");
  const [selectedYearId, setSelectedYearId] = useState<string>("");

  // Data state
  const [funnel, setFunnel] = useState<FunnelResponse | null>(null);
  const [trends, setTrends] = useState<TrendsResponse | null>(null);
  const [sources, setSources] = useState<SourceEffectivenessResponse | null>(
    null
  );
  const [attrition, setAttrition] = useState<AttritionResponse | null>(null);
  const [capacityComparison, setCapacityComparison] =
    useState<EnrollmentVsCapacityResponse | null>(null);
  const [reEnrollment, setReEnrollment] =
    useState<ReEnrollmentResponse | null>(null);

  // Load lookups
  useEffect(() => {
    async function loadLookups() {
      const [periodsResult, yearsResult] = await Promise.all([
        getAdmissionPeriods(),
        getAcademicYears(false),
      ]);

      if (periodsResult.success) {
        setPeriods(periodsResult.data.items);
      }
      if (yearsResult.success) {
        setAcademicYears(yearsResult.data);
        const current = yearsResult.data.find((y) => y.is_current);
        if (current) setSelectedYearId(current.id);
        else if (yearsResult.data.length > 0)
          setSelectedYearId(yearsResult.data[0].id);
      }
    }
    loadLookups();
  }, []);

  // Load analytics data
  const loadAnalytics = useCallback(async () => {
    if (!selectedYearId) return;
    setLoading(true);

    const periodId =
      selectedPeriod !== "all" ? selectedPeriod : undefined;

    const [
      funnelResult,
      trendsResult,
      sourcesResult,
      attritionResult,
      capacityResult,
      reEnrollResult,
    ] = await Promise.all([
      getAdmissionsFunnel(periodId),
      getEnrollmentTrends(5),
      getLeadSourceEffectiveness(periodId),
      getAttritionAnalysis(selectedYearId),
      getEnrollmentVsCapacity(selectedYearId),
      getReEnrollmentRates(5),
    ]);

    if (funnelResult.success) setFunnel(funnelResult.data);
    if (trendsResult.success) setTrends(trendsResult.data);
    if (sourcesResult.success) setSources(sourcesResult.data);
    if (attritionResult.success) setAttrition(attritionResult.data);
    if (capacityResult.success) setCapacityComparison(capacityResult.data);
    if (reEnrollResult.success) setReEnrollment(reEnrollResult.data);

    setLoading(false);
  }, [selectedPeriod, selectedYearId]);

  useEffect(() => {
    if (selectedYearId) {
      loadAnalytics();
    }
  }, [loadAnalytics, selectedYearId]);

  if (loading && !funnel) {
    return (
      <div className="space-y-6 p-4 md:p-6">
        <Skeleton className="h-8 w-48" />
        <div className="flex gap-4">
          <Skeleton className="h-10 w-[220px]" />
          <Skeleton className="h-10 w-[220px]" />
        </div>
        <Skeleton className="h-[350px]" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Skeleton className="h-[300px]" />
          <Skeleton className="h-[300px]" />
        </div>
      </div>
    );
  }

  const capacityData = capacityComparison?.classes.map((c) => ({
    name: c.class_name,
    target: c.target ?? 0,
    actual: c.actual_enrolled,
    capacity: c.capacity ?? 0,
    variance: c.variance ?? 0,
  }));

  return (
    <div className="space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Admissions Analytics</h1>
          <p className="text-sm text-muted-foreground">
            Enrollment funnel, trends, and insights
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
            <SelectTrigger className="w-full sm:w-[220px]">
              <SelectValue placeholder="Filter by period" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Periods</SelectItem>
              {periods.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={selectedYearId} onValueChange={setSelectedYearId}>
            <SelectTrigger className="w-full sm:w-[220px]">
              <SelectValue placeholder="Academic year" />
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
      </div>

      {/* Funnel */}
      {funnel && <EnrollmentFunnel stages={funnel.stages} />}

      {/* Row 2: Trends + Lead Sources */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {trends && <TrendChart years={trends.years} />}
        {sources && <LeadSourceChart sources={sources.sources} />}
      </div>

      {/* Row 3: Enrollment vs Capacity */}
      {capacityData && capacityData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Enrollment vs Capacity by Class
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[350px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={capacityData}
                  margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    className="stroke-muted"
                  />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 12 }}
                    className="fill-muted-foreground"
                  />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    className="fill-muted-foreground"
                  />
                  <Tooltip
                    content={({ active, payload, label }) => {
                      if (!active || !payload?.length) return null;
                      return (
                        <div className="rounded-lg border bg-background p-3 shadow-md">
                          <p className="mb-1 font-medium">{label}</p>
                          {payload.map((entry) => (
                            <p
                              key={entry.name}
                              className="text-sm"
                              style={{ color: entry.color }}
                            >
                              {entry.name}: {entry.value}
                            </p>
                          ))}
                        </div>
                      );
                    }}
                  />
                  <Legend />
                  <Bar
                    dataKey="capacity"
                    name="Capacity"
                    fill="hsl(var(--muted-foreground))"
                    opacity={0.3}
                    radius={[2, 2, 0, 0]}
                  />
                  <Bar
                    dataKey="target"
                    name="Target"
                    fill="hsl(var(--primary))"
                    opacity={0.6}
                    radius={[2, 2, 0, 0]}
                  />
                  <Bar dataKey="actual" name="Enrolled" radius={[2, 2, 0, 0]}>
                    {capacityData.map((entry, index) => {
                      const isOver = entry.variance > 0;
                      return (
                        <Cell
                          key={index}
                          fill={
                            isOver
                              ? "hsl(38, 92%, 50%)"
                              : "hsl(142, 71%, 45%)"
                          }
                        />
                      );
                    })}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Summary */}
            {capacityComparison && (
              <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
                <div className="rounded-lg border p-3">
                  <p className="text-lg font-bold">
                    {capacityComparison.total_target ?? "--"}
                  </p>
                  <p className="text-xs text-muted-foreground">Total Target</p>
                </div>
                <div className="rounded-lg border p-3">
                  <p className="text-lg font-bold">
                    {capacityComparison.total_enrolled}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Total Enrolled
                  </p>
                </div>
                <div className="rounded-lg border p-3">
                  <p className="text-lg font-bold">
                    {capacityComparison.total_capacity ?? "--"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Total Capacity
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Row 4: Attrition + Re-enrollment */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {attrition && <AttritionReport data={attrition} />}

        {/* Re-enrollment rates */}
        {reEnrollment && reEnrollment.years.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Re-enrollment Rates
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Academic Year</TableHead>
                      <TableHead className="text-right">Students</TableHead>
                      <TableHead className="text-right">Returning</TableHead>
                      <TableHead className="text-right">Rate</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {reEnrollment.years.map((year) => (
                      <TableRow key={year.academic_year_id}>
                        <TableCell className="font-medium">
                          {year.academic_year_name}
                        </TableCell>
                        <TableCell className="text-right">
                          {year.total_students}
                        </TableCell>
                        <TableCell className="text-right">
                          {year.returning_count}
                        </TableCell>
                        <TableCell className="text-right">
                          <span
                            className={
                              year.re_enrollment_rate >= 80
                                ? "text-green-600 font-medium"
                                : year.re_enrollment_rate >= 60
                                  ? "text-amber-600 font-medium"
                                  : "text-red-600 font-medium"
                            }
                          >
                            {year.re_enrollment_rate.toFixed(1)}%
                          </span>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
