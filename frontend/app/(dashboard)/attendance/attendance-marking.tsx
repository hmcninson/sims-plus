"use client";

import { useState, useTransition, useCallback, useEffect } from "react";
import { format } from "date-fns";
import {
  Users,
  Calendar,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  Pill,
  Check,
  Save,
  Search,
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

import {
  getStudentsForAttendance,
  getSectionAttendanceSummary,
  bulkMarkStudentAttendance,
} from "@/actions/attendance.action";
import type { Class, StudentAttendanceListItem, SectionAttendanceSummary, AttendanceStatus } from "@/types";

const STATUS_OPTIONS: { value: AttendanceStatus; label: string; icon: React.ElementType; bgColor: string; selectedClass: string }[] = [
  { value: "present", label: "Present", icon: CheckCircle2, bgColor: "bg-green-500", selectedClass: "!bg-green-100 !text-green-700 dark:!bg-green-900 dark:!text-green-300 ring-1 ring-green-400" },
  { value: "absent", label: "Absent", icon: XCircle, bgColor: "bg-red-500", selectedClass: "!bg-red-100 !text-red-700 dark:!bg-red-900 dark:!text-red-300 ring-1 ring-red-400" },
  { value: "late", label: "Late", icon: Clock, bgColor: "bg-yellow-500", selectedClass: "!bg-yellow-100 !text-yellow-700 dark:!bg-yellow-900 dark:!text-yellow-300 ring-1 ring-yellow-400" },
  { value: "excused", label: "Excused", icon: AlertCircle, bgColor: "bg-blue-500", selectedClass: "!bg-blue-100 !text-blue-700 dark:!bg-blue-900 dark:!text-blue-300 ring-1 ring-blue-400" },
  { value: "sick", label: "Sick", icon: Pill, bgColor: "bg-purple-500", selectedClass: "!bg-purple-100 !text-purple-700 dark:!bg-purple-900 dark:!text-purple-300 ring-1 ring-purple-400" },
];

interface AttendanceMarkingProps {
  classes: Class[];
}

export function AttendanceMarking({ classes }: AttendanceMarkingProps) {
  const [isPending, startTransition] = useTransition();
  const [isSaving, setIsSaving] = useState(false);
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [selectedSectionId, setSelectedSectionId] = useState<string>("");
  const [selectedDate, setSelectedDate] = useState<string>(format(new Date(), "yyyy-MM-dd"));
  const [students, setStudents] = useState<StudentAttendanceListItem[]>([]);
  const [summary, setSummary] = useState<SectionAttendanceSummary | null>(null);
  const [attendanceData, setAttendanceData] = useState<Record<string, AttendanceStatus>>({});
  const [hasChanges, setHasChanges] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const selectedClass = classes.find((c) => c.id === selectedClassId);

  // Filter students based on search query
  const filteredStudents = students.filter((student) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    const fullName = `${student.first_name} ${student.middle_name || ""} ${student.last_name}`.toLowerCase();
    return (
      fullName.includes(query) ||
      student.student_number?.toLowerCase().includes(query)
    );
  });
  const sections = selectedClass?.sections || [];

  // Fetch students when section and date are selected
  const fetchStudents = useCallback(async () => {
    if (!selectedSectionId || !selectedDate) return;

    startTransition(async () => {
      const [studentsResult, summaryResult] = await Promise.all([
        getStudentsForAttendance(selectedSectionId, selectedDate),
        getSectionAttendanceSummary(selectedSectionId, selectedDate),
      ]);

      if (studentsResult.success && studentsResult.data) {
        setStudents(studentsResult.data);
        // Initialize attendance data from existing records
        const initialData: Record<string, AttendanceStatus> = {};
        studentsResult.data.forEach((student) => {
          if (student.status) {
            initialData[student.student_id] = student.status;
          }
        });
        setAttendanceData(initialData);
        setHasChanges(false);
      }

      if (summaryResult.success && summaryResult.data) {
        setSummary(summaryResult.data);
      }
    });
  }, [selectedSectionId, selectedDate]);

  // Fetch when section or date changes
  useEffect(() => {
    if (selectedSectionId && selectedDate) {
      fetchStudents();
    }
  }, [selectedSectionId, selectedDate, fetchStudents]);

  // Handle class change
  const handleClassChange = (classId: string) => {
    setSelectedClassId(classId);
    setSelectedSectionId("");
    setStudents([]);
    setSummary(null);
    setAttendanceData({});
    setHasChanges(false);
  };

  // Handle section change
  const handleSectionChange = (sectionId: string) => {
    setSelectedSectionId(sectionId);
  };

  // Handle individual attendance change
  const handleAttendanceChange = (studentId: string, status: AttendanceStatus) => {
    setAttendanceData((prev) => ({
      ...prev,
      [studentId]: status,
    }));
    setHasChanges(true);
  };

  // Mark all students with a status
  const handleMarkAll = (status: AttendanceStatus) => {
    const newData: Record<string, AttendanceStatus> = {};
    students.forEach((student) => {
      newData[student.student_id] = status;
    });
    setAttendanceData(newData);
    setHasChanges(true);
  };

  // Save attendance
  const handleSave = async () => {
    if (!selectedSectionId || !selectedDate || Object.keys(attendanceData).length === 0) {
      toast.error("Please mark attendance for at least one student");
      return;
    }

    setIsSaving(true);

    const records = Object.entries(attendanceData).map(([studentId, status]) => ({
      student_id: studentId,
      status,
    }));

    const result = await bulkMarkStudentAttendance({
      section_id: selectedSectionId,
      date: selectedDate,
      records,
    });

    if (result.success) {
      toast.success(
        `Attendance saved: ${result.data?.created || 0} created, ${result.data?.updated || 0} updated`
      );
      setHasChanges(false);
      // Refresh data
      fetchStudents();
    } else {
      toast.error(result.error || "Failed to save attendance");
    }

    setIsSaving(false);
  };

  // Get initials
  const getInitials = (firstName: string, lastName: string) => {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Attendance</h1>
          <p className="text-muted-foreground">
            Mark and manage student attendance records
          </p>
        </div>
        {hasChanges && (
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Save Changes
          </Button>
        )}
      </div>

      {/* Selection Controls */}
      <Card>
        <CardHeader>
          <CardTitle>Select Class & Date</CardTitle>
          <CardDescription>Choose a class section and date to mark attendance</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <div className="w-[280px]">
              <Label htmlFor="class">Class</Label>
              <Select value={selectedClassId} onValueChange={handleClassChange}>
                <SelectTrigger id="class" className="mt-1.5 w-full">
                  <SelectValue placeholder="Select class" />
                </SelectTrigger>
                <SelectContent>
                  {classes.map((cls) => (
                    <SelectItem key={cls.id} value={cls.id}>
                      {cls.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="w-[280px]">
              <Label htmlFor="section">Section</Label>
              <Select
                value={selectedSectionId}
                onValueChange={handleSectionChange}
                disabled={sections.length === 0}
              >
                <SelectTrigger id="section" className="mt-1.5 w-full">
                  <SelectValue placeholder={sections.length === 0 ? "Select class first" : "Select section"} />
                </SelectTrigger>
                <SelectContent>
                  {sections.map((section) => (
                    <SelectItem key={section.id} value={section.id}>
                      {section.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="w-[280px]">
              <Label htmlFor="date">Date</Label>
              <Input
                id="date"
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="mt-1.5"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Summary Stats */}
      {summary && (
        <div className="grid gap-4 md:grid-cols-5">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{summary.total_students}</div>
              <p className="text-xs text-muted-foreground">
                {summary.marked} marked, {summary.unmarked} unmarked
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
              <CardTitle className="text-sm font-medium">Rate</CardTitle>
              <Calendar className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{summary.attendance_rate}%</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Attendance Table */}
      {selectedSectionId && selectedDate && (
        <Card>
          <CardHeader>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle>Student Attendance</CardTitle>
                <CardDescription>
                  {selectedClass?.name} - {sections.find((s) => s.id === selectedSectionId)?.name} |{" "}
                  {format(new Date(selectedDate), "EEEE, MMMM d, yyyy")}
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleMarkAll("present")}
                >
                  <Check className="mr-1 h-4 w-4" />
                  Mark All Present
                </Button>
              </div>
            </div>
            {/* Search Input */}
            <div className="relative mt-2">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name or student ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          </CardHeader>
          <CardContent>
            {isPending ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : students.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Users className="h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground">No students found in this section</p>
              </div>
            ) : filteredStudents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Search className="h-12 w-12 text-muted-foreground mb-4" />
                <p className="text-muted-foreground">No students match &quot;{searchQuery}&quot;</p>
              </div>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Student</TableHead>
                      <TableHead>Student ID</TableHead>
                      <TableHead>Gender</TableHead>
                      <TableHead className="text-center">Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredStudents.map((student) => (
                      <TableRow key={student.student_id}>
                        <TableCell>
                          <div className="flex items-center gap-3">
                            <Avatar className="h-8 w-8">
                              <AvatarImage src={student.photo_url || undefined} />
                              <AvatarFallback className="text-xs">
                                {getInitials(student.first_name, student.last_name)}
                              </AvatarFallback>
                            </Avatar>
                            <div>
                              <div className="font-medium">
                                {student.first_name}{" "}
                                {student.middle_name ? `${student.middle_name} ` : ""}
                                {student.last_name}
                              </div>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {student.student_number}
                        </TableCell>
                        <TableCell className="capitalize">{student.gender}</TableCell>
                        <TableCell>
                          <ToggleGroup
                            type="single"
                            value={attendanceData[student.student_id] || ""}
                            onValueChange={(value) => {
                              if (value) {
                                handleAttendanceChange(student.student_id, value as AttendanceStatus);
                              }
                            }}
                            className="justify-center"
                          >
                            {STATUS_OPTIONS.map((option) => {
                              const Icon = option.icon;
                              const isSelected = attendanceData[student.student_id] === option.value;
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
                                  <Icon className={`h-4 w-4 ${isSelected ? "" : "text-muted-foreground"}`} />
                                </ToggleGroupItem>
                              );
                            })}
                          </ToggleGroup>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}

            {/* Legend */}
            {students.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-4 text-sm">
                {STATUS_OPTIONS.map((option) => {
                  const Icon = option.icon;
                  return (
                    <div key={option.value} className="flex items-center gap-1.5">
                      <div className={`rounded p-1 ${option.bgColor}`}>
                        <Icon className="h-3 w-3 text-white" />
                      </div>
                      <span className="text-muted-foreground">{option.label}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {!selectedSectionId && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Calendar className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium">Select a Class and Section</h3>
            <p className="text-sm text-muted-foreground text-center max-w-md mt-2">
              Choose a class section and date above to start marking attendance for students.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
