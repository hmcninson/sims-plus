"use client";

import { useState, useTransition, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Users,
  UserPlus,
  Search,
  MoreHorizontal,
  Loader2,
  GraduationCap,
  Filter,
  Download,
  Upload,
  Pencil,
  Trash2,
  Eye,
  UserCheck,
  UserX,
} from "lucide-react";
import { toast } from "sonner";
import { format } from "date-fns";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import { getStudents, deleteStudent, getStudentStats, exportStudents } from "@/actions/students.action";
import type {
  StudentListItem,
  StudentStats,
  PaginatedResponse,
  Class,
  StudentStatus,
} from "@/types";
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";
import { ImportStudentsDialog } from "./import-students-dialog";

// Status configuration
const STATUS_CONFIG: Record<StudentStatus, { label: string; color: string }> = {
  active: { label: "Active", color: "bg-green-500" },
  inactive: { label: "Inactive", color: "bg-gray-500" },
  graduated: { label: "Graduated", color: "bg-blue-500" },
  transferred: { label: "Transferred", color: "bg-yellow-500" },
  withdrawn: { label: "Withdrawn", color: "bg-orange-500" },
  suspended: { label: "Suspended", color: "bg-red-500" },
};

interface StudentsManagementProps {
  initialData: PaginatedResponse<StudentListItem>;
  stats: StudentStats;
  classes: Class[];
  initialClassFilter?: string;
}

export function StudentsManagement({
  initialData,
  stats: initialStats,
  classes,
  initialClassFilter,
}: StudentsManagementProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [students, setStudents] = useState<PaginatedResponse<StudentListItem>>(initialData);
  const [stats, setStats] = useState<StudentStats>(initialStats);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [classFilter, setClassFilter] = useState<string>(initialClassFilter || "all");
  const [page, setPage] = useState(1);
  const [isImportDialogOpen, setIsImportDialogOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<StudentListItem | null>(null);

  // Fetch students with filters - accepts overrides to avoid stale state issues
  const fetchStudents = useCallback(async (overrides?: {
    search?: string;
    status?: string;
    class_id?: string;
    currentPage?: number;
  }) => {
    const search = overrides?.search ?? searchQuery;
    const status = overrides?.status ?? statusFilter;
    const classId = overrides?.class_id ?? classFilter;
    const currentPage = overrides?.currentPage ?? page;

    startTransition(async () => {
      const result = await getStudents({
        search: search || undefined,
        status: status !== "all" ? status : undefined,
        class_id: classId !== "all" ? classId : undefined,
        page: currentPage,
        page_size: 20,
      });
      if (result.success && result.data) {
        setStudents(result.data);
      }

      // Also refresh stats
      const statsResult = await getStudentStats();
      if (statsResult.success && statsResult.data) {
        setStats(statsResult.data);
      }
    });
  }, [searchQuery, statusFilter, classFilter, page, startTransition]);

  // Debounced search - triggers after user stops typing
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchQuery !== "") {
        setPage(1);
        fetchStudents({ search: searchQuery, currentPage: 1 });
      }
    }, 400); // 400ms debounce

    return () => clearTimeout(timeoutId);
  }, [searchQuery]);

  // Handle search form submit (for Enter key or button click)
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchStudents({ currentPage: 1 });
  };

  // Handle status filter change
  const handleStatusChange = (value: string) => {
    setStatusFilter(value);
    setPage(1);
    fetchStudents({ status: value, currentPage: 1 });
  };

  // Handle class filter change
  const handleClassChange = (value: string) => {
    setClassFilter(value);
    setPage(1);
    fetchStudents({ class_id: value, currentPage: 1 });
    // Update URL to reflect filter (without full page reload)
    if (value !== "all") {
      router.replace(`/students?class_id=${value}`, { scroll: false });
    } else {
      router.replace("/students", { scroll: false });
    }
  };

  // Clear all filters
  const handleClearFilters = () => {
    setSearchQuery("");
    setStatusFilter("all");
    setClassFilter("all");
    setPage(1);
    fetchStudents({ search: "", status: "all", class_id: "all", currentPage: 1 });
    // Clear URL params
    router.replace("/students", { scroll: false });
  };

  // Handle delete
  const handleDelete = async () => {
    if (!deleteConfirm) return;

    startTransition(async () => {
      const result = await deleteStudent(deleteConfirm.id);
      if (result.success) {
        toast.success("Student deleted successfully");
        setDeleteConfirm(null);
        fetchStudents();
      } else {
        toast.error(result.error || "Failed to delete student");
      }
    });
  };

  // Handle student added
  const handleStudentAdded = () => {
    fetchStudents();
  };

  // Handle export
  const handleExport = async () => {
    setIsExporting(true);
    try {
      const result = await exportStudents({
        search: searchQuery || undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
        class_id: classFilter !== "all" ? classFilter : undefined,
      });

      console.log("Export result:", JSON.stringify(result, null, 2));

      if (result.success && result.data) {
        // Handle empty data
        if (result.data.length === 0) {
          toast.info("No students to export");
          return;
        }

        // Convert to CSV
        const headers = [
          "Student ID",
          "First Name",
          "Middle Name",
          "Last Name",
          "Gender",
          "Date of Birth",
          "Class",
          "Section",
          "Status",
        ];

        const rows = result.data.map((s) => [
          s.student_id,
          s.first_name,
          s.middle_name || "",
          s.last_name,
          s.gender,
          s.date_of_birth,
          s.class_name || "",
          s.section_name || "",
          s.status,
        ]);

        const csvContent = [
          headers.join(","),
          ...rows.map((row) =>
            row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")
          ),
        ].join("\n");

        // Download
        const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `students_export_${new Date().toISOString().split("T")[0]}.csv`;
        link.click();
        URL.revokeObjectURL(url);

        toast.success(`Exported ${result.data.length} students`);
      } else {
        console.log("Export failed, error:", result.error, typeof result.error);
        let errorMsg = "Export failed";
        if (typeof result.error === 'string') {
          errorMsg = result.error;
        } else if (result.error && typeof result.error === 'object') {
          errorMsg = JSON.stringify(result.error);
        }
        toast.error(errorMsg);
      }
    } catch (error) {
      console.log("Export exception:", error);
      let errorMsg = "Export failed";
      if (error instanceof Error) {
        errorMsg = error.message;
      } else if (typeof error === 'string') {
        errorMsg = error;
      }
      toast.error(errorMsg);
    } finally {
      setIsExporting(false);
    }
  };

  // Get initials
  const getInitials = (firstName: string, lastName: string) => {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  };

  // Calculate age
  const calculateAge = (dob: string) => {
    const today = new Date();
    const birthDate = new Date(dob);
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
      age--;
    }
    return age;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Students</h1>
          <p className="text-muted-foreground">
            Manage student records, enrollments, and profiles.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsImportDialogOpen(true)}
          >
            <Upload className="mr-2 h-4 w-4" />
            Import
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExport}
            disabled={isExporting}
          >
            {isExporting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-2 h-4 w-4" />
            )}
            Export
          </Button>
          <Button asChild>
            <Link href="/students/new">
              <UserPlus className="mr-2 h-4 w-4" />
              Add Student
            </Link>
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Students</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">
              {stats.male} male, {stats.female} female
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active</CardTitle>
            <UserCheck className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{stats.active}</div>
            <p className="text-xs text-muted-foreground">Currently enrolled</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Boarders</CardTitle>
            <GraduationCap className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">{stats.boarders}</div>
            <p className="text-xs text-muted-foreground">
              {stats.day_students} day students
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Inactive</CardTitle>
            <UserX className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {stats.graduated + stats.transferred + stats.withdrawn + stats.suspended}
            </div>
            <p className="text-xs text-muted-foreground">
              {stats.graduated} graduated, {stats.transferred} transferred
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Active Class Filter Banner */}
      {classFilter !== "all" && (
        <div className="flex items-center justify-between rounded-lg border bg-muted/50 px-4 py-3">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm">
              Showing students in{" "}
              <strong>{classes.find(c => c.id === classFilter)?.name || "selected class"}</strong>
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClearFilters}
          >
            Clear filter
          </Button>
        </div>
      )}

      {/* Filters and Search */}
      <Card>
        <CardHeader>
          <CardTitle>Student Directory</CardTitle>
          <CardDescription>Search and filter students</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 md:flex-row md:items-center">
            <form onSubmit={handleSearch} className="flex flex-1 gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by name or student ID..."
                  className="pl-8"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <Button type="submit" variant="secondary" disabled={isPending}>
                {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Search"}
              </Button>
            </form>

            <CollapsibleFilters
              activeFilterCount={
                (statusFilter !== "all" ? 1 : 0) +
                (classFilter !== "all" ? 1 : 0)
              }
            >
              <Select
                value={statusFilter}
                onValueChange={handleStatusChange}
              >
                <SelectTrigger className="w-full md:w-[150px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                  <SelectItem value="graduated">Graduated</SelectItem>
                  <SelectItem value="transferred">Transferred</SelectItem>
                  <SelectItem value="withdrawn">Withdrawn</SelectItem>
                  <SelectItem value="suspended">Suspended</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={classFilter}
                onValueChange={handleClassChange}
              >
                <SelectTrigger className="w-full md:w-[180px]">
                  <SelectValue placeholder="Class" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Classes</SelectItem>
                  {classes.map((cls) => (
                    <SelectItem key={cls.id} value={cls.id}>
                      {cls.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Clear filters button - show only when filters are active */}
              {(searchQuery || statusFilter !== "all" || classFilter !== "all") && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClearFilters}
                  className="h-10"
                >
                  Clear
                </Button>
              )}
            </CollapsibleFilters>
          </div>

          {/* Students Table */}
          <div className="mt-6 rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead className="hidden sm:table-cell">Student ID</TableHead>
                  <TableHead className="hidden md:table-cell">Class</TableHead>
                  <TableHead className="hidden lg:table-cell">Gender</TableHead>
                  <TableHead className="hidden lg:table-cell">Age</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {students.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="h-24 text-center">
                      <div className="flex flex-col items-center gap-2">
                        <Users className="h-8 w-8 text-muted-foreground" />
                        <p className="text-muted-foreground">No students found</p>
                        <Button variant="outline" size="sm" asChild>
                          <Link href="/students/new">
                            <UserPlus className="mr-2 h-4 w-4" />
                            Add First Student
                          </Link>
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  students.items.map((student) => (
                    <TableRow key={student.id}>
                      <TableCell>
                        <Link
                          href={`/students/${student.id}`}
                          className="flex items-center gap-3 hover:underline"
                        >
                          <Avatar className="h-9 w-9">
                            <AvatarImage src={student.photo_url || undefined} />
                            <AvatarFallback>
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
                        </Link>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell font-mono text-sm">
                        {student.student_id}
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {student.class_name || "-"}
                        {student.section_name && (
                          <span className="text-muted-foreground">
                            {" "}
                            ({student.section_name})
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell capitalize">{student.gender}</TableCell>
                      <TableCell className="hidden lg:table-cell">{calculateAge(student.date_of_birth)} yrs</TableCell>
                      <TableCell>
                        <Badge
                          variant="secondary"
                          className={`${STATUS_CONFIG[student.status]?.color || "bg-gray-500"} text-white`}
                        >
                          {STATUS_CONFIG[student.status]?.label || student.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuLabel>Actions</DropdownMenuLabel>
                            <DropdownMenuItem asChild>
                              <Link href={`/students/${student.id}`}>
                                <Eye className="mr-2 h-4 w-4" />
                                View Profile
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link href={`/students/${student.id}/edit`}>
                                <Pencil className="mr-2 h-4 w-4" />
                                Edit
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="text-red-600"
                              onClick={() => setDeleteConfirm(student)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          {students.total_pages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Showing {(page - 1) * 20 + 1} to {Math.min(page * 20, students.total)} of{" "}
                {students.total} students
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!students.has_previous || isPending}
                  onClick={() => {
                    const newPage = page - 1;
                    setPage(newPage);
                    fetchStudents({ currentPage: newPage });
                  }}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!students.has_next || isPending}
                  onClick={() => {
                    const newPage = page + 1;
                    setPage(newPage);
                    fetchStudents({ currentPage: newPage });
                  }}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Import Students Dialog */}
      <ImportStudentsDialog
        open={isImportDialogOpen}
        onOpenChange={setIsImportDialogOpen}
        onSuccess={handleStudentAdded}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Student</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete{" "}
              <strong>
                {deleteConfirm?.first_name} {deleteConfirm?.last_name}
              </strong>
              ? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleDelete}
              disabled={isPending}
            >
              {isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
