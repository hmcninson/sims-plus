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
  Download,
  Upload,
  Pencil,
  Trash2,
  Eye,
  UserCheck,
  UserX,
  GraduationCap,
  Building2,
} from "lucide-react";
import { toast } from "sonner";

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

import { getStaff, deleteStaff, getStaffStats, exportStaff } from "@/actions/staff.action";
import { ImportStaffDialog } from "./import-staff-dialog";
import type {
  StaffListItem,
  StaffStats,
  PaginatedResponse,
  StaffStatus,
  StaffType,
} from "@/types";

// Status configuration
const STATUS_CONFIG: Record<StaffStatus, { label: string; color: string }> = {
  active: { label: "Active", color: "bg-green-500" },
  on_leave: { label: "On Leave", color: "bg-yellow-500" },
  suspended: { label: "Suspended", color: "bg-red-500" },
  terminated: { label: "Terminated", color: "bg-gray-500" },
  retired: { label: "Retired", color: "bg-blue-500" },
};

// Staff type configuration
const TYPE_CONFIG: Record<StaffType, { label: string; color: string }> = {
  teaching: { label: "Teaching", color: "bg-blue-500" },
  non_teaching: { label: "Non-Teaching", color: "bg-teal-500" },
  administrative: { label: "Administrative", color: "bg-indigo-500" },
};

interface StaffManagementProps {
  initialData: PaginatedResponse<StaffListItem>;
  stats: StaffStats;
}

export function StaffManagement({
  initialData,
  stats: initialStats,
}: StaffManagementProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [staffList, setStaffList] = useState<PaginatedResponse<StaffListItem>>(initialData);
  const [stats, setStats] = useState<StaffStats>(initialStats);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [deleteConfirm, setDeleteConfirm] = useState<StaffListItem | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);

  // Fetch staff with filters
  const fetchStaff = useCallback(async (overrides?: {
    search?: string;
    status?: string;
    staff_type?: string;
    currentPage?: number;
  }) => {
    const search = overrides?.search ?? searchQuery;
    const status = overrides?.status ?? statusFilter;
    const staffType = overrides?.staff_type ?? typeFilter;
    const currentPage = overrides?.currentPage ?? page;

    startTransition(async () => {
      const result = await getStaff({
        search: search || undefined,
        status: status !== "all" ? status : undefined,
        staff_type: staffType !== "all" ? staffType : undefined,
        page: currentPage,
        page_size: 20,
      });
      if (result.success && result.data) {
        setStaffList(result.data);
      }

      // Also refresh stats
      const statsResult = await getStaffStats();
      if (statsResult.success && statsResult.data) {
        setStats(statsResult.data);
      }
    });
  }, [searchQuery, statusFilter, typeFilter, page, startTransition]);

  // Debounced search
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchQuery !== "") {
        setPage(1);
        fetchStaff({ search: searchQuery, currentPage: 1 });
      }
    }, 400);

    return () => clearTimeout(timeoutId);
  }, [searchQuery]);

  // Handle search form submit
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchStaff({ currentPage: 1 });
  };

  // Handle status filter change
  const handleStatusChange = (value: string) => {
    setStatusFilter(value);
    setPage(1);
    fetchStaff({ status: value, currentPage: 1 });
  };

  // Handle type filter change
  const handleTypeChange = (value: string) => {
    setTypeFilter(value);
    setPage(1);
    fetchStaff({ staff_type: value, currentPage: 1 });
  };

  // Clear all filters
  const handleClearFilters = () => {
    setSearchQuery("");
    setStatusFilter("all");
    setTypeFilter("all");
    setPage(1);
    fetchStaff({ search: "", status: "all", staff_type: "all", currentPage: 1 });
  };

  // Handle delete
  const handleDelete = async () => {
    if (!deleteConfirm) return;

    startTransition(async () => {
      const result = await deleteStaff(deleteConfirm.id);
      if (result.success) {
        toast.success("Staff member deleted successfully");
        setDeleteConfirm(null);
        fetchStaff();
      } else {
        toast.error(result.error || "Failed to delete staff member");
      }
    });
  };

  // Get initials
  const getInitials = (firstName: string, lastName: string) => {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  };

  // Handle export
  const handleExport = async () => {
    setIsExporting(true);
    try {
      const result = await exportStaff({
        status: statusFilter !== "all" ? statusFilter : undefined,
        staff_type: typeFilter !== "all" ? typeFilter : undefined,
      });

      if (result.success && result.data) {
        const url = window.URL.createObjectURL(result.data);
        const a = document.createElement("a");
        a.href = url;
        a.download = `staff_export_${new Date().toISOString().split("T")[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        toast.success("Staff data exported successfully");
      } else {
        toast.error(result.error || "Failed to export staff");
      }
    } catch {
      toast.error("Failed to export staff");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Staff</h1>
          <p className="text-muted-foreground">
            Manage staff records, assignments, and profiles.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
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
          <Button
            variant="outline"
            onClick={() => setShowImportDialog(true)}
          >
            <Upload className="mr-2 h-4 w-4" />
            Import
          </Button>
          <Button variant="outline" asChild>
            <Link href="/staff/departments">
              <Building2 className="mr-2 h-4 w-4" />
              Departments
            </Link>
          </Button>
          <Button asChild>
            <Link href="/staff/new">
              <UserPlus className="mr-2 h-4 w-4" />
              Add Staff
            </Link>
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Staff</CardTitle>
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
            <p className="text-xs text-muted-foreground">Currently employed</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Teaching</CardTitle>
            <GraduationCap className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">{stats.teaching}</div>
            <p className="text-xs text-muted-foreground">
              {stats.non_teaching} non-teaching, {stats.administrative} admin
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">On Leave</CardTitle>
            <UserX className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-yellow-600">{stats.on_leave}</div>
            <p className="text-xs text-muted-foreground">
              {stats.suspended} suspended, {stats.retired} retired
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters and Search */}
      <Card>
        <CardHeader>
          <CardTitle>Staff Directory</CardTitle>
          <CardDescription>Search and filter staff members</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 md:flex-row md:items-center">
            <form onSubmit={handleSearch} className="flex flex-1 gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search by name, email, or staff ID..."
                  className="pl-8"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <Button type="submit" variant="secondary" disabled={isPending}>
                {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Search"}
              </Button>
            </form>

            <div className="flex gap-2">
              <Select
                value={statusFilter}
                onValueChange={handleStatusChange}
              >
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="on_leave">On Leave</SelectItem>
                  <SelectItem value="suspended">Suspended</SelectItem>
                  <SelectItem value="terminated">Terminated</SelectItem>
                  <SelectItem value="retired">Retired</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={typeFilter}
                onValueChange={handleTypeChange}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="teaching">Teaching</SelectItem>
                  <SelectItem value="non_teaching">Non-Teaching</SelectItem>
                  <SelectItem value="administrative">Administrative</SelectItem>
                </SelectContent>
              </Select>

              {/* Clear filters button */}
              {(searchQuery || statusFilter !== "all" || typeFilter !== "all") && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClearFilters}
                  className="h-10"
                >
                  Clear
                </Button>
              )}
            </div>
          </div>

          {/* Staff Table */}
          <div className="mt-6 rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Staff Member</TableHead>
                  <TableHead>Staff ID</TableHead>
                  <TableHead>Job Title</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Department</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {staffList.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="h-24 text-center">
                      <div className="flex flex-col items-center gap-2">
                        <Users className="h-8 w-8 text-muted-foreground" />
                        <p className="text-muted-foreground">No staff found</p>
                        <Button variant="outline" size="sm" asChild>
                          <Link href="/staff/new">
                            <UserPlus className="mr-2 h-4 w-4" />
                            Add First Staff Member
                          </Link>
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  staffList.items.map((staff) => (
                    <TableRow key={staff.id}>
                      <TableCell>
                        <Link
                          href={`/staff/${staff.id}`}
                          className="flex items-center gap-3 hover:underline"
                        >
                          <Avatar className="h-9 w-9">
                            <AvatarImage src={staff.photo_url || undefined} />
                            <AvatarFallback>
                              {getInitials(staff.first_name, staff.last_name)}
                            </AvatarFallback>
                          </Avatar>
                          <div>
                            <div className="font-medium">
                              {staff.first_name}{" "}
                              {staff.middle_name ? `${staff.middle_name} ` : ""}
                              {staff.last_name}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {staff.email}
                            </div>
                          </div>
                        </Link>
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {staff.staff_id}
                      </TableCell>
                      <TableCell>{staff.job_title}</TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`${TYPE_CONFIG[staff.staff_type]?.color || "bg-gray-500"} text-white border-0`}
                        >
                          {TYPE_CONFIG[staff.staff_type]?.label || staff.staff_type}
                        </Badge>
                      </TableCell>
                      <TableCell>{staff.department || "-"}</TableCell>
                      <TableCell>
                        <Badge
                          variant="secondary"
                          className={`${STATUS_CONFIG[staff.status]?.color || "bg-gray-500"} text-white`}
                        >
                          {STATUS_CONFIG[staff.status]?.label || staff.status}
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
                              <Link href={`/staff/${staff.id}`}>
                                <Eye className="mr-2 h-4 w-4" />
                                View Profile
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuItem asChild>
                              <Link href={`/staff/${staff.id}/edit`}>
                                <Pencil className="mr-2 h-4 w-4" />
                                Edit
                              </Link>
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="text-red-600"
                              onClick={() => setDeleteConfirm(staff)}
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
          {staffList.total_pages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Showing {(page - 1) * 20 + 1} to {Math.min(page * 20, staffList.total)} of{" "}
                {staffList.total} staff members
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!staffList.has_previous || isPending}
                  onClick={() => {
                    const newPage = page - 1;
                    setPage(newPage);
                    fetchStaff({ currentPage: newPage });
                  }}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!staffList.has_next || isPending}
                  onClick={() => {
                    const newPage = page + 1;
                    setPage(newPage);
                    fetchStaff({ currentPage: newPage });
                  }}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Staff Member</AlertDialogTitle>
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

      {/* Import Dialog */}
      <ImportStaffDialog
        open={showImportDialog}
        onOpenChange={setShowImportDialog}
        onSuccess={() => fetchStaff()}
      />
    </div>
  );
}
