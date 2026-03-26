"use client";

import { useEffect, useState, useTransition } from "react";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Loader2, Briefcase, ChevronDown, ChevronUp } from "lucide-react";

import { getStaffWorkloadSummary, getStaffWorkload } from "@/actions/staff.action";
import { getDepartments } from "@/actions/staff.action";
import type { StaffWorkloadSummaryItem, StaffWorkloadResponse } from "@/types/leave.type";
import type { Department } from "@/actions/staff.action";

export default function WorkloadPage() {
  const [isPending, startTransition] = useTransition();
  const [workloadData, setWorkloadData] = useState<StaffWorkloadSummaryItem[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [filterDepartment, setFilterDepartment] = useState<string>("all");
  const [expandedStaffId, setExpandedStaffId] = useState<string | null>(null);
  const [staffDetail, setStaffDetail] = useState<StaffWorkloadResponse | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  useEffect(() => {
    startTransition(async () => {
      const [workloadResult, deptResult] = await Promise.all([
        getStaffWorkloadSummary(),
        getDepartments(),
      ]);
      if (workloadResult.success && workloadResult.data) {
        setWorkloadData(workloadResult.data);
      }
      if (deptResult.success && deptResult.data) {
        setDepartments(deptResult.data);
      }
    });
  }, []);

  const filteredData =
    filterDepartment === "all"
      ? workloadData
      : workloadData.filter(
          (s) =>
            s.department?.toLowerCase() === filterDepartment.toLowerCase()
        );

  // Chart data: top 15 by periods
  const chartData = [...filteredData]
    .sort((a, b) => b.total_periods_per_week - a.total_periods_per_week)
    .slice(0, 15)
    .map((s) => ({
      name: s.staff_name.length > 20 ? s.staff_name.substring(0, 18) + "..." : s.staff_name,
      periods: s.total_periods_per_week,
    }));

  const handleRowClick = async (staffId: string) => {
    if (expandedStaffId === staffId) {
      setExpandedStaffId(null);
      return;
    }
    setExpandedStaffId(staffId);
    setIsDetailLoading(true);
    setIsDetailOpen(true);
    const result = await getStaffWorkload(staffId);
    if (result.success && result.data) {
      setStaffDetail(result.data);
    }
    setIsDetailLoading(false);
  };

  const getWorkloadColor = (periods: number) => {
    if (periods >= 25) return "#EF4444"; // overloaded - red
    if (periods >= 20) return "#F59E0B"; // heavy - amber
    if (periods >= 10) return "#3B82F6"; // normal - blue
    return "#10B981"; // light - green
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Teaching Workload
          </h1>
          <p className="text-muted-foreground">
            Overview of teaching periods and class assignments per staff member
          </p>
        </div>
      </div>

      {/* Filter */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 sm:flex-row">
            <Select value={filterDepartment} onValueChange={setFilterDepartment}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue placeholder="Department" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Departments</SelectItem>
                {departments.map((dept) => (
                  <SelectItem key={dept.id} value={dept.name}>
                    {dept.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Chart */}
      {isPending ? (
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-40" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-[300px] w-full" />
          </CardContent>
        </Card>
      ) : chartData.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Periods per Week</CardTitle>
            <CardDescription>
              Top {chartData.length} staff by teaching periods (click a row below for details)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={chartData}
                  layout="vertical"
                  margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={140}
                    tick={{ fontSize: 12 }}
                  />
                  <Tooltip
                    content={({ payload }) => {
                      if (!payload?.[0]) return null;
                      const data = payload[0];
                      return (
                        <div className="rounded-lg border bg-background p-3 shadow-md">
                          <p className="font-medium">{data.payload.name}</p>
                          <p className="text-sm text-muted-foreground">
                            {data.value} periods/week
                          </p>
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="periods" radius={[0, 4, 4, 0]}>
                    {chartData.map((entry, index) => (
                      <Cell
                        key={index}
                        fill={getWorkloadColor(entry.periods)}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 flex flex-wrap gap-4 text-xs text-muted-foreground">
              <div className="flex items-center gap-1.5">
                <div className="h-3 w-3 rounded-sm bg-[#10B981]" />
                Light (&lt;10)
              </div>
              <div className="flex items-center gap-1.5">
                <div className="h-3 w-3 rounded-sm bg-[#3B82F6]" />
                Normal (10-19)
              </div>
              <div className="flex items-center gap-1.5">
                <div className="h-3 w-3 rounded-sm bg-[#F59E0B]" />
                Heavy (20-24)
              </div>
              <div className="flex items-center gap-1.5">
                <div className="h-3 w-3 rounded-sm bg-[#EF4444]" />
                Overloaded (25+)
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* Detail Table */}
      <Card>
        <CardHeader>
          <CardTitle>Staff Workload Details</CardTitle>
          <CardDescription>
            {filteredData.length} teaching staff member{filteredData.length !== 1 ? "s" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredData.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Staff Name</TableHead>
                  <TableHead className="hidden sm:table-cell">Department</TableHead>
                  <TableHead className="text-right">Sections</TableHead>
                  <TableHead className="text-right">Periods/Week</TableHead>
                  <TableHead className="hidden md:table-cell">Class Teacher?</TableHead>
                  <TableHead className="w-[50px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredData.map((staff) => (
                  <TableRow
                    key={staff.staff_id}
                    className="cursor-pointer"
                    onClick={() => handleRowClick(staff.staff_id)}
                  >
                    <TableCell className="font-medium">
                      {staff.staff_name}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">
                      {staff.department || "--"}
                    </TableCell>
                    <TableCell className="text-right">
                      {staff.total_sections}
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge
                        variant="secondary"
                        className={
                          staff.total_periods_per_week >= 25
                            ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                            : staff.total_periods_per_week >= 20
                              ? "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"
                              : ""
                        }
                      >
                        {staff.total_periods_per_week}
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden md:table-cell">
                      {staff.is_class_teacher ? (
                        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                          {staff.class_teacher_of || "Yes"}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">No</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {expandedStaffId === staff.staff_id ? (
                        <ChevronUp className="h-4 w-4 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-muted-foreground" />
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Briefcase className="h-12 w-12" />
              <p>No workload data available</p>
              <p className="text-sm text-center max-w-md">
                Assign teachers to classes and create timetables to see workload information.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail Dialog */}
      <Dialog open={isDetailOpen} onOpenChange={setIsDetailOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {staffDetail?.staff_name || "Staff"} - Workload Details
            </DialogTitle>
            <DialogDescription>
              Detailed section and period breakdown
            </DialogDescription>
          </DialogHeader>
          {isDetailLoading ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : staffDetail ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-muted-foreground">Total Periods/Week:</span>{" "}
                  <span className="font-medium">{staffDetail.total_periods_per_week}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Total Sections:</span>{" "}
                  <span className="font-medium">{staffDetail.total_sections}</span>
                </div>
                {staffDetail.class_teacher_of && (
                  <div>
                    <span className="text-muted-foreground">Class Teacher Of:</span>{" "}
                    <span className="font-medium">{staffDetail.class_teacher_of}</span>
                  </div>
                )}
                {staffDetail.subjects_taught.length > 0 && (
                  <div className="sm:col-span-2">
                    <span className="text-muted-foreground">Subjects:</span>{" "}
                    <span className="font-medium">
                      {staffDetail.subjects_taught.join(", ")}
                    </span>
                  </div>
                )}
              </div>

              {staffDetail.sections.length > 0 && (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Class</TableHead>
                      <TableHead>Section</TableHead>
                      <TableHead>Subject</TableHead>
                      <TableHead className="text-right">Periods</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {staffDetail.sections.map((section) => (
                      <TableRow key={section.section_id + (section.subject_name || "")}>
                        <TableCell>{section.class_name}</TableCell>
                        <TableCell>{section.section_name}</TableCell>
                        <TableCell>{section.subject_name || "--"}</TableCell>
                        <TableCell className="text-right">
                          {section.periods_per_week}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-8">
              No workload data found for this staff member.
            </p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
