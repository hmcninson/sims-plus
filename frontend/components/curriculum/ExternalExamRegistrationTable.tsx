"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  MoreHorizontal,
  Eye,
  Edit,
  Trash2,
  ArrowUpDown,
  CheckCircle2,
  Minus,
  Search,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import { deleteExternalExamRegistration } from "@/actions/curriculum.action";
import type { ExternalExamRegistration, ExternalExamBoard } from "@/types/curriculum.type";

const BOARD_BADGE_COLORS: Record<ExternalExamBoard, string> = {
  waec: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  cambridge_international: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  edexcel: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  college_board: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  ibo: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  other: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

const BOARD_LABELS: Record<ExternalExamBoard, string> = {
  waec: "WAEC",
  cambridge_international: "Cambridge",
  edexcel: "Edexcel",
  college_board: "College Board",
  ibo: "IBO",
  other: "Other",
};

const STATUS_BADGE_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
  registered: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  confirmed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
};

interface ExternalExamRegistrationTableProps {
  registrations: ExternalExamRegistration[];
  /** Map of student_id -> display name for student column rendering */
  studentNames?: Record<string, string>;
  onEdit: (registration: ExternalExamRegistration) => void;
  onRefresh: () => void;
  compact?: boolean;
}

export function ExternalExamRegistrationTable({
  registrations,
  studentNames = {},
  onEdit,
  onRefresh,
  compact = false,
}: ExternalExamRegistrationTableProps) {
  const getStudentDisplayName = (studentId: string): string =>
    studentNames[studentId] ?? studentId.slice(0, 8);
  const [searchQuery, setSearchQuery] = useState("");
  const [boardFilter, setBoardFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [sortField, setSortField] = useState<"student_id" | "exam_session">("student_id");
  const [sortAsc, setSortAsc] = useState(true);
  const [currentPage, setCurrentPage] = useState(0);
  const pageSize = compact ? 5 : 10;

  const filteredData = useMemo(() => {
    let data = registrations;
    if (boardFilter !== "all") {
      data = data.filter((r) => r.exam_board === boardFilter);
    }
    if (statusFilter !== "all") {
      data = data.filter((r) => r.registration_status === statusFilter);
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      data = data.filter(
        (r) =>
          getStudentDisplayName(r.student_id).toLowerCase().includes(q) ||
          (r.candidate_number ?? "").toLowerCase().includes(q) ||
          r.exam_session.toLowerCase().includes(q),
      );
    }
    // Sort
    data = [...data].sort((a, b) => {
      const aVal = sortField === "student_id"
        ? getStudentDisplayName(a.student_id).toLowerCase()
        : (a[sortField] ?? "").toLowerCase();
      const bVal = sortField === "student_id"
        ? getStudentDisplayName(b.student_id).toLowerCase()
        : (b[sortField] ?? "").toLowerCase();
      return sortAsc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    });
    return data;
  }, [registrations, boardFilter, statusFilter, searchQuery, sortField, sortAsc, studentNames]);

  const totalPages = Math.ceil(filteredData.length / pageSize);
  const paginatedData = filteredData.slice(currentPage * pageSize, (currentPage + 1) * pageSize);

  function toggleSort(field: "student_id" | "exam_session") {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  }

  async function handleDelete() {
    if (!deleteId) return;
    setIsDeleting(true);
    const result = await deleteExternalExamRegistration(deleteId);
    if (result.success) {
      toast.success("Registration deleted");
      onRefresh();
    } else {
      toast.error(result.error);
    }
    setIsDeleting(false);
    setDeleteId(null);
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search students..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(0);
            }}
            className="pl-9 w-full md:w-[300px]"
          />
        </div>
        <Select
          value={boardFilter}
          onValueChange={(v) => {
            setBoardFilter(v);
            setCurrentPage(0);
          }}
        >
          <SelectTrigger className="w-full md:w-[180px]">
            <SelectValue placeholder="Exam Board" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Boards</SelectItem>
            {Object.entries(BOARD_LABELS)
              .filter(([k]) => k !== "other")
              .map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
        <Select
          value={statusFilter}
          onValueChange={(v) => {
            setStatusFilter(v);
            setCurrentPage(0);
          }}
        >
          <SelectTrigger className="w-full md:w-[160px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="registered">Registered</SelectItem>
            <SelectItem value="confirmed">Confirmed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <Button
                  variant="ghost"
                  size="sm"
                  className="-ml-3 h-8"
                  onClick={() => toggleSort("student_id")}
                >
                  Student
                  <ArrowUpDown className="ml-1 size-3" />
                </Button>
              </TableHead>
              <TableHead>Exam Board</TableHead>
              <TableHead>
                <Button
                  variant="ghost"
                  size="sm"
                  className="-ml-3 h-8"
                  onClick={() => toggleSort("exam_session")}
                >
                  Session
                  <ArrowUpDown className="ml-1 size-3" />
                </Button>
              </TableHead>
              <TableHead className="hidden sm:table-cell">Candidate #</TableHead>
              <TableHead>Status</TableHead>
              {!compact && (
                <>
                  <TableHead className="hidden md:table-cell">Subjects</TableHead>
                  <TableHead className="hidden md:table-cell">Results</TableHead>
                </>
              )}
              <TableHead className="w-[50px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedData.length === 0 ? (
              <TableRow>
                <TableCell colSpan={compact ? 6 : 8} className="h-24 text-center">
                  <p className="text-muted-foreground">No registrations found.</p>
                </TableCell>
              </TableRow>
            ) : (
              paginatedData.map((reg) => (
                <TableRow key={reg.id}>
                  <TableCell>
                    <Link
                      href={`/students/${reg.student_id}`}
                      className="font-medium text-primary hover:underline"
                    >
                      {getStudentDisplayName(reg.student_id)}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className={BOARD_BADGE_COLORS[reg.exam_board]}>
                      {BOARD_LABELS[reg.exam_board]}
                    </Badge>
                  </TableCell>
                  <TableCell>{reg.exam_session}</TableCell>
                  <TableCell className="hidden sm:table-cell font-mono text-sm">
                    {reg.candidate_number || (
                      <span className="text-muted-foreground">&mdash;</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className={STATUS_BADGE_COLORS[reg.registration_status]}>
                      {reg.registration_status}
                    </Badge>
                  </TableCell>
                  {!compact && (
                    <>
                      <TableCell className="hidden md:table-cell">{reg.subjects.length}</TableCell>
                      <TableCell className="hidden md:table-cell">
                        {reg.results && reg.results.length > 0 ? (
                          <CheckCircle2 className="size-4 text-green-600" />
                        ) : (
                          <Minus className="size-4 text-muted-foreground" />
                        )}
                      </TableCell>
                    </>
                  )}
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="size-8">
                          <MoreHorizontal className="size-4" />
                          <span className="sr-only">Actions</span>
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem asChild>
                          <Link href={`/exams/external/${reg.id}`}>
                            <Eye className="mr-2 size-4" />
                            View Details
                          </Link>
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => onEdit(reg)}>
                          <Edit className="mr-2 size-4" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() => setDeleteId(reg.id)}
                        >
                          <Trash2 className="mr-2 size-4" />
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
      {!compact && totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {filteredData.length} registration(s)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.max(0, p - 1))}
              disabled={currentPage === 0}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={currentPage >= totalPages - 1}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Registration</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this registration? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} disabled={isDeleting}>
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
