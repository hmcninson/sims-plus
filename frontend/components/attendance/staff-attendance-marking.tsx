"use client";

import { useState, useTransition, useCallback, useEffect, useMemo } from "react";
import Link from "next/link";
import { format } from "date-fns";
import {
  Users,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  Pill,
  Save,
  Search,
  ArrowLeft,
  UserCog,
} from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ToggleGroup,
  ToggleGroupItem,
} from "@/components/ui/toggle-group";
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";

import { getStaff, getDepartments } from "@/actions/staff.action";
import {
  listStaffAttendance,
  bulkMarkStaffAttendance,
} from "@/actions/attendance.action";
import type {
  StaffListItem,
  AttendanceStatus,
  StaffAttendance,
  StaffType,
} from "@/types";

// ==========================================
// Constants
// ==========================================

const STATUS_OPTIONS: {
  value: AttendanceStatus;
  label: string;
  icon: React.ElementType;
  selectedClass: string;
}[] = [
  {
    value: "present",
    label: "Present",
    icon: CheckCircle2,
    selectedClass:
      "!bg-green-100 !text-green-700 dark:!bg-green-900 dark:!text-green-300 ring-1 ring-green-400",
  },
  {
    value: "absent",
    label: "Absent",
    icon: XCircle,
    selectedClass:
      "!bg-red-100 !text-red-700 dark:!bg-red-900 dark:!text-red-300 ring-1 ring-red-400",
  },
  {
    value: "late",
    label: "Late",
    icon: Clock,
    selectedClass:
      "!bg-yellow-100 !text-yellow-700 dark:!bg-yellow-900 dark:!text-yellow-300 ring-1 ring-yellow-400",
  },
  {
    value: "excused",
    label: "Excused",
    icon: AlertCircle,
    selectedClass:
      "!bg-blue-100 !text-blue-700 dark:!bg-blue-900 dark:!text-blue-300 ring-1 ring-blue-400",
  },
  {
    value: "sick",
    label: "Sick",
    icon: Pill,
    selectedClass:
      "!bg-purple-100 !text-purple-700 dark:!bg-purple-900 dark:!text-purple-300 ring-1 ring-purple-400",
  },
];

const STAFF_TYPE_LABELS: Record<StaffType, string> = {
  teaching: "Teaching",
  non_teaching: "Non-Teaching",
  administrative: "Administrative",
};

// ==========================================
// Types
// ==========================================

interface StaffEntry {
  staff_id: string;
  first_name: string;
  last_name: string;
  staff_code: string;
  department?: string;
  staff_type: StaffType;
  photo_url?: string;
  status: AttendanceStatus | "";
  remarks: string;
}

interface DepartmentOption {
  id: string;
  name: string;
}

// ==========================================
// Component
// ==========================================

export function StaffAttendanceMarking() {
  const [isPending, startTransition] = useTransition();
  const [isSaving, setIsSaving] = useState(false);
  const [selectedDate, setSelectedDate] = useState<string>(format(new Date(), "yyyy-MM-dd"));

  // Staff data
  const [staffEntries, setStaffEntries] = useState<StaffEntry[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState<string>("all");
  const [staffTypeFilter, setStaffTypeFilter] = useState<string>("all");
  const [departments, setDepartments] = useState<DepartmentOption[]>([]);

  const [hasChanges, setHasChanges] = useState(false);

  // Load departments on mount
  useEffect(() => {
    const loadDepartments = async () => {
      const result = await getDepartments();
      if (result.success && result.data) {
        setDepartments(result.data.map((d) => ({ id: d.id, name: d.name })));
      }
    };
    loadDepartments();
  }, []);

  // Fetch staff and existing attendance when date changes
  const fetchStaffAndAttendance = useCallback(
    async (date: string) => {
      startTransition(async () => {
        // Fetch all active staff
        const staffResult = await getStaff({
          status: "active",
          page_size: 500,
        });

        if (!staffResult.success || !staffResult.data) {
          toast.error(staffResult.error || "Failed to load staff");
          return;
        }

        const staffList: StaffListItem[] = staffResult.data.items;

        // Fetch existing attendance for this date
        const attendanceResult = await listStaffAttendance({
          start_date: date,
          end_date: date,
          page_size: 500,
        });

        const existingRecords: StaffAttendance[] =
          attendanceResult.success && attendanceResult.data
            ? attendanceResult.data.items
            : [];

        // Build a map of staff_id -> existing record
        const existingMap = new Map<string, StaffAttendance>();
        existingRecords.forEach((r) => {
          existingMap.set(r.staff_id, r);
        });

        // Build entries
        const entries: StaffEntry[] = staffList.map((staff) => {
          const existing = existingMap.get(staff.id);
          return {
            staff_id: staff.id,
            first_name: staff.first_name,
            last_name: staff.last_name,
            staff_code: staff.staff_id,
            department: staff.department,
            staff_type: staff.staff_type,
            photo_url: staff.photo_url,
            status: existing ? existing.status : "",
            remarks: existing?.remarks || "",
          };
        });

        setStaffEntries(entries);
        setIsLoaded(true);
        setHasChanges(false);
      });
    },
    []
  );

  useEffect(() => {
    fetchStaffAndAttendance(selectedDate);
  }, [selectedDate, fetchStaffAndAttendance]);

  // Filter staff
  const filteredStaff = useMemo(() => {
    return staffEntries.filter((entry) => {
      // Search filter
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const fullName = `${entry.first_name} ${entry.last_name}`.toLowerCase();
        if (!fullName.includes(query) && !entry.staff_code.toLowerCase().includes(query)) {
          return false;
        }
      }

      // Department filter
      if (departmentFilter !== "all" && entry.department !== departmentFilter) {
        return false;
      }

      // Staff type filter
      if (staffTypeFilter !== "all" && entry.staff_type !== staffTypeFilter) {
        return false;
      }

      return true;
    });
  }, [staffEntries, searchQuery, departmentFilter, staffTypeFilter]);

  // Count active filters
  const activeFilterCount = [
    departmentFilter !== "all" ? 1 : 0,
    staffTypeFilter !== "all" ? 1 : 0,
  ].reduce((a, b) => a + b, 0);

  // Summary stats (from current state, not filtered)
  const summary = useMemo(() => {
    const marked = staffEntries.filter((e) => e.status !== "");
    return {
      total: staffEntries.length,
      marked: marked.length,
      present: marked.filter((e) => e.status === "present").length,
      absent: marked.filter((e) => e.status === "absent").length,
      late: marked.filter((e) => e.status === "late").length,
      excused: marked.filter((e) => e.status === "excused").length,
      sick: marked.filter((e) => e.status === "sick").length,
    };
  }, [staffEntries]);

  // Handlers
  const handleStatusChange = (staffId: string, status: AttendanceStatus) => {
    setStaffEntries((prev) =>
      prev.map((entry) =>
        entry.staff_id === staffId ? { ...entry, status } : entry
      )
    );
    setHasChanges(true);
  };

  const handleRemarksChange = (staffId: string, remarks: string) => {
    setStaffEntries((prev) =>
      prev.map((entry) =>
        entry.staff_id === staffId ? { ...entry, remarks } : entry
      )
    );
    setHasChanges(true);
  };

  const handleMarkAll = (status: AttendanceStatus) => {
    setStaffEntries((prev) =>
      prev.map((entry) => ({ ...entry, status }))
    );
    setHasChanges(true);
  };

  const handleSave = async () => {
    const toSave = staffEntries.filter((e) => e.status !== "");
    if (toSave.length === 0) {
      toast.error("Please mark attendance for at least one staff member");
      return;
    }

    setIsSaving(true);

    const result = await bulkMarkStaffAttendance({
      date: selectedDate,
      records: toSave.map((entry) => ({
        staff_id: entry.staff_id,
        status: entry.status as AttendanceStatus,
        remarks: entry.remarks || undefined,
      })),
    });

    if (result.success) {
      toast.success(
        `Attendance saved: ${result.data?.created || 0} created, ${result.data?.updated || 0} updated`
      );
      setHasChanges(false);
      // Refresh to reflect saved state
      fetchStaffAndAttendance(selectedDate);
    } else {
      toast.error(result.error || "Failed to save attendance");
    }

    setIsSaving(false);
  };

  const getInitials = (firstName: string, lastName: string) => {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/attendance/staff">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Mark Staff Attendance</h1>
            <p className="text-muted-foreground">
              Record daily attendance for all staff members
            </p>
          </div>
        </div>
        {hasChanges && (
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Save Attendance
          </Button>
        )}
      </div>

      {/* Date & Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Select Date & Filters</CardTitle>
          <CardDescription>Choose a date and filter staff to mark attendance</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4 items-end">
            <div className="w-full sm:w-[200px]">
              <Label htmlFor="date">Date</Label>
              <Input
                id="date"
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                max={format(new Date(), "yyyy-MM-dd")}
                className="mt-1.5"
              />
            </div>

            {/* Search always visible */}
            <div className="w-full sm:w-[250px]">
              <Label htmlFor="search">Search</Label>
              <div className="relative mt-1.5">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="search"
                  placeholder="Search by name or ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>

            {/* Collapsible filters for mobile */}
            <CollapsibleFilters activeFilterCount={activeFilterCount}>
              <div className="w-full md:w-auto">
                <Label className="md:sr-only">Department</Label>
                <Select value={departmentFilter} onValueChange={setDepartmentFilter}>
                  <SelectTrigger className="w-full md:w-[180px] mt-1.5 md:mt-0">
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

              <div className="w-full md:w-auto">
                <Label className="md:sr-only">Staff Type</Label>
                <Select value={staffTypeFilter} onValueChange={setStaffTypeFilter}>
                  <SelectTrigger className="w-full md:w-[180px] mt-1.5 md:mt-0">
                    <SelectValue placeholder="Staff Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="teaching">Teaching</SelectItem>
                    <SelectItem value="non_teaching">Non-Teaching</SelectItem>
                    <SelectItem value="administrative">Administrative</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CollapsibleFilters>
          </div>
        </CardContent>
      </Card>

      {/* Summary Stats */}
      {isLoaded && summary.marked > 0 && (
        <div className="grid gap-4 grid-cols-2 md:grid-cols-5">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total</CardTitle>
              <UserCog className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{summary.total}</div>
              <p className="text-xs text-muted-foreground">
                {summary.marked} marked
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Present</CardTitle>
              <CheckCircle2 className="h-4 w-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{summary.present}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Absent</CardTitle>
              <XCircle className="h-4 w-4 text-red-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{summary.absent}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Late</CardTitle>
              <Clock className="h-4 w-4 text-yellow-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">{summary.late}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Excused/Sick</CardTitle>
              <AlertCircle className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">
                {summary.excused + summary.sick}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Staff Attendance Table / Cards */}
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>Staff List</CardTitle>
              <CardDescription>
                {format(new Date(selectedDate), "EEEE, MMMM d, yyyy")} &mdash;{" "}
                {filteredStaff.length} of {staffEntries.length} staff shown
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleMarkAll("present")}
              >
                <CheckCircle2 className="mr-1 h-4 w-4 text-green-500" />
                Mark All Present
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleMarkAll("absent")}
              >
                <XCircle className="mr-1 h-4 w-4 text-red-500" />
                Mark All Absent
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : staffEntries.length === 0 && isLoaded ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Users className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No active staff found</p>
            </div>
          ) : filteredStaff.length === 0 && isLoaded ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Search className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">
                No staff match your search or filters
              </p>
            </div>
          ) : (
            <>
              {/* Desktop: Table View */}
              <div className="hidden sm:block rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Staff Member</TableHead>
                      <TableHead className="hidden md:table-cell">Staff ID</TableHead>
                      <TableHead className="hidden lg:table-cell">Department</TableHead>
                      <TableHead className="hidden lg:table-cell">Type</TableHead>
                      <TableHead className="text-center">Status</TableHead>
                      <TableHead className="hidden md:table-cell">Remarks</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredStaff.map((entry) => (
                      <TableRow key={entry.staff_id}>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <Avatar className="h-8 w-8">
                              <AvatarImage src={entry.photo_url || undefined} />
                              <AvatarFallback className="text-xs">
                                {getInitials(entry.first_name, entry.last_name)}
                              </AvatarFallback>
                            </Avatar>
                            <div>
                              <div className="font-medium">
                                {entry.first_name} {entry.last_name}
                              </div>
                              <div className="text-xs text-muted-foreground md:hidden">
                                {entry.staff_code}
                              </div>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="hidden md:table-cell font-mono text-sm">
                          {entry.staff_code}
                        </TableCell>
                        <TableCell className="hidden lg:table-cell text-sm">
                          {entry.department || "--"}
                        </TableCell>
                        <TableCell className="hidden lg:table-cell text-sm capitalize">
                          {STAFF_TYPE_LABELS[entry.staff_type] || entry.staff_type}
                        </TableCell>
                        <TableCell>
                          <ToggleGroup
                            type="single"
                            value={entry.status}
                            onValueChange={(value) => {
                              if (value) {
                                handleStatusChange(entry.staff_id, value as AttendanceStatus);
                              }
                            }}
                            className="justify-center"
                          >
                            {STATUS_OPTIONS.map((option) => {
                              const Icon = option.icon;
                              const isSelected = entry.status === option.value;
                              return (
                                <ToggleGroupItem
                                  key={option.value}
                                  value={option.value}
                                  aria-label={option.label}
                                  className={`h-8 w-8 p-0 rounded-md ${
                                    isSelected
                                      ? option.selectedClass
                                      : "hover:bg-muted"
                                  }`}
                                  title={option.label}
                                >
                                  <Icon
                                    className={`h-4 w-4 ${
                                      isSelected ? "" : "text-muted-foreground"
                                    }`}
                                  />
                                </ToggleGroupItem>
                              );
                            })}
                          </ToggleGroup>
                        </TableCell>
                        <TableCell className="hidden md:table-cell">
                          <Input
                            placeholder="Optional remarks..."
                            value={entry.remarks}
                            onChange={(e) =>
                              handleRemarksChange(entry.staff_id, e.target.value)
                            }
                            className="h-8 text-sm"
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Mobile: Card View */}
              <div className="sm:hidden space-y-3">
                {filteredStaff.map((entry) => (
                  <div
                    key={entry.staff_id}
                    className="rounded-lg border p-4 space-y-3"
                  >
                    <div className="flex items-center gap-3">
                      <Avatar className="h-10 w-10">
                        <AvatarImage src={entry.photo_url || undefined} />
                        <AvatarFallback className="text-xs">
                          {getInitials(entry.first_name, entry.last_name)}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">
                          {entry.first_name} {entry.last_name}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {entry.staff_code}
                          {entry.department ? ` / ${entry.department}` : ""}
                        </div>
                      </div>
                      {entry.status && (
                        <Badge
                          variant="secondary"
                          className={
                            entry.status === "present"
                              ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                              : entry.status === "absent"
                              ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                              : entry.status === "late"
                              ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
                              : entry.status === "excused"
                              ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                              : "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300"
                          }
                        >
                          {entry.status.charAt(0).toUpperCase() + entry.status.slice(1)}
                        </Badge>
                      )}
                    </div>

                    {/* Status Toggle */}
                    <ToggleGroup
                      type="single"
                      value={entry.status}
                      onValueChange={(value) => {
                        if (value) {
                          handleStatusChange(entry.staff_id, value as AttendanceStatus);
                        }
                      }}
                      className="justify-start"
                    >
                      {STATUS_OPTIONS.map((option) => {
                        const Icon = option.icon;
                        const isSelected = entry.status === option.value;
                        return (
                          <ToggleGroupItem
                            key={option.value}
                            value={option.value}
                            aria-label={option.label}
                            className={`h-9 w-9 p-0 rounded-md ${
                              isSelected
                                ? option.selectedClass
                                : "hover:bg-muted"
                            }`}
                            title={option.label}
                          >
                            <Icon
                              className={`h-4 w-4 ${
                                isSelected ? "" : "text-muted-foreground"
                              }`}
                            />
                          </ToggleGroupItem>
                        );
                      })}
                    </ToggleGroup>

                    {/* Remarks */}
                    <Input
                      placeholder="Remarks (optional)..."
                      value={entry.remarks}
                      onChange={(e) =>
                        handleRemarksChange(entry.staff_id, e.target.value)
                      }
                      className="h-8 text-sm"
                    />
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Legend */}
          {isLoaded && staffEntries.length > 0 && (
            <div className="mt-4 flex flex-wrap gap-4 text-sm">
              {STATUS_OPTIONS.map((option) => {
                const Icon = option.icon;
                return (
                  <div key={option.value} className="flex items-center gap-1.5">
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">{option.label}</span>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Sticky Save Bar on Mobile */}
      {hasChanges && (
        <div className="fixed bottom-0 left-0 right-0 z-50 border-t bg-background p-4 sm:hidden">
          <Button
            className="w-full"
            onClick={handleSave}
            disabled={isSaving}
          >
            {isSaving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Save Attendance ({summary.marked} staff)
          </Button>
        </div>
      )}
    </div>
  );
}
