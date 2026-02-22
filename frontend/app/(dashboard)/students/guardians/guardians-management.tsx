"use client";

import { useState, useTransition, useCallback, useEffect } from "react";
import Link from "next/link";
import {
  Users,
  UserPlus,
  Search,
  MoreHorizontal,
  Loader2,
  Phone,
  Mail,
  Briefcase,
  Pencil,
  Trash2,
  Eye,
  GraduationCap,
  AlertTriangle,
  X,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import { getGuardians, deleteGuardian } from "@/actions/students.action";
import type { Guardian, PaginatedResponse } from "@/types";
import { AddGuardianDialog } from "./add-guardian-dialog";
import { ViewGuardianDialog } from "./view-guardian-dialog";
import { LinkToStudentDialog } from "./link-to-student-dialog";

interface GuardiansManagementProps {
  initialData: PaginatedResponse<Guardian>;
}

export function GuardiansManagement({ initialData }: GuardiansManagementProps) {
  const [isPending, startTransition] = useTransition();
  const [guardians, setGuardians] = useState<PaginatedResponse<Guardian>>(initialData);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(1);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [editGuardian, setEditGuardian] = useState<Guardian | null>(null);
  const [viewGuardian, setViewGuardian] = useState<Guardian | null>(null);
  const [linkGuardian, setLinkGuardian] = useState<Guardian | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<Guardian | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Calculate stats
  const totalGuardians = guardians.total;
  const guardiansWithStudents = guardians.items.filter((g) => (g.student_count || 0) > 0).length;

  // Fetch guardians with filters
  const fetchGuardians = useCallback(
    async (overrides?: { search?: string; currentPage?: number }) => {
      const search = overrides?.search ?? debouncedSearch;
      const currentPage = overrides?.currentPage ?? page;

      startTransition(async () => {
        const result = await getGuardians(search || undefined, currentPage, 20);
        if (result.success && result.data) {
          setGuardians(result.data);
        }
      });
    },
    [debouncedSearch, page]
  );

  // Debounced search effect
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery !== debouncedSearch) {
        setDebouncedSearch(searchQuery);
        setPage(1);
        fetchGuardians({ search: searchQuery, currentPage: 1 });
      }
    }, 400);

    return () => clearTimeout(timer);
  }, [searchQuery, debouncedSearch, fetchGuardians]);

  // Handle search form submit
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchGuardians({ search: searchQuery, currentPage: 1 });
  };

  // Clear search
  const handleClearSearch = () => {
    setSearchQuery("");
    setDebouncedSearch("");
    setPage(1);
    fetchGuardians({ search: "", currentPage: 1 });
  };

  // Handle pagination
  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    fetchGuardians({ currentPage: newPage });
  };

  // Handle delete
  const handleDelete = async () => {
    if (!deleteConfirm) return;

    // Check if guardian has linked students
    if ((deleteConfirm.student_count || 0) > 0) {
      toast.error(
        `Cannot delete guardian with ${deleteConfirm.student_count} linked student(s). Please unlink all students first.`
      );
      setDeleteConfirm(null);
      return;
    }

    setIsDeleting(true);
    const result = await deleteGuardian(deleteConfirm.id);

    if (result.success) {
      toast.success("Guardian deleted successfully");
      setDeleteConfirm(null);
      fetchGuardians();
    } else {
      toast.error(result.error || "Failed to delete guardian");
    }
    setIsDeleting(false);
  };

  // Handle guardian added/updated
  const handleGuardianChanged = () => {
    fetchGuardians();
  };

  // Get initials
  const getInitials = (firstName: string, lastName: string) => {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Guardians</h1>
          <p className="text-muted-foreground">
            Manage guardian and parent records linked to students.
          </p>
        </div>
        <Button onClick={() => setIsAddDialogOpen(true)}>
          <UserPlus className="mr-2 h-4 w-4" />
          Add Guardian
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Guardians</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalGuardians}</div>
            <p className="text-xs text-muted-foreground">
              Registered in the system
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">With Students</CardTitle>
            <GraduationCap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{guardiansWithStudents}</div>
            <p className="text-xs text-muted-foreground">
              Linked to one or more students
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Without Students</CardTitle>
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {totalGuardians - guardiansWithStudents}
            </div>
            <p className="text-xs text-muted-foreground">
              Not linked to any student
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Search and Table */}
      <Card>
        <CardHeader>
          <CardTitle>Guardian Directory</CardTitle>
          <CardDescription>Search and manage guardian records</CardDescription>
        </CardHeader>
        <CardContent>
          {/* Search */}
          <form onSubmit={handleSearch} className="mb-6 flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by name, phone, or email..."
                className="pl-8 pr-8"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={handleClearSearch}
                  className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
            <Button type="submit" variant="secondary" disabled={isPending}>
              {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Search"}
            </Button>
          </form>

          {/* Guardians Table */}
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Guardian</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead className="hidden md:table-cell">Occupation</TableHead>
                  <TableHead className="hidden lg:table-cell">Location</TableHead>
                  <TableHead className="hidden sm:table-cell text-center">Students</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {guardians.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="h-24 text-center">
                      <div className="flex flex-col items-center gap-2">
                        <Users className="h-8 w-8 text-muted-foreground" />
                        <p className="text-muted-foreground">
                          {searchQuery ? "No guardians match your search" : "No guardians found"}
                        </p>
                        {!searchQuery && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setIsAddDialogOpen(true)}
                          >
                            <UserPlus className="mr-2 h-4 w-4" />
                            Add First Guardian
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ) : (
                  guardians.items.map((guardian) => (
                    <TableRow key={guardian.id} className="group">
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className="h-10 w-10">
                            <AvatarImage src={guardian.photo_url || undefined} />
                            <AvatarFallback className="text-sm">
                              {getInitials(guardian.first_name, guardian.last_name)}
                            </AvatarFallback>
                          </Avatar>
                          <div>
                            <div className="font-medium">
                              {guardian.first_name} {guardian.last_name}
                            </div>
                            {guardian.ghana_card_number && (
                              <div className="text-xs text-muted-foreground font-mono">
                                {guardian.ghana_card_number}
                              </div>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="flex items-center gap-1.5 text-sm">
                            <Phone className="h-3.5 w-3.5 text-muted-foreground" />
                            <span>{guardian.phone}</span>
                          </div>
                          {guardian.email && (
                            <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                              <Mail className="h-3.5 w-3.5" />
                              <span className="max-w-[180px] truncate">{guardian.email}</span>
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="hidden md:table-cell">
                        {guardian.occupation ? (
                          <div className="flex items-center gap-1.5 text-sm">
                            <Briefcase className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="max-w-[150px] truncate">{guardian.occupation}</span>
                          </div>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell className="hidden lg:table-cell">
                        {guardian.city || guardian.region ? (
                          <span className="text-sm">
                            {guardian.city}
                            {guardian.city && guardian.region && ", "}
                            {guardian.region}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">-</span>
                        )}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell text-center">
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Badge
                                variant={(guardian.student_count || 0) > 0 ? "default" : "secondary"}
                                className="cursor-default"
                              >
                                {guardian.student_count || 0}
                              </Badge>
                            </TooltipTrigger>
                            <TooltipContent>
                              {(guardian.student_count || 0) === 0
                                ? "Not linked to any students"
                                : `Linked to ${guardian.student_count} student(s)`}
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
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
                            <DropdownMenuItem onClick={() => setViewGuardian(guardian)}>
                              <Eye className="mr-2 h-4 w-4" />
                              View Details
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => setEditGuardian(guardian)}>
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => setLinkGuardian(guardian)}>
                              <GraduationCap className="mr-2 h-4 w-4" />
                              Link to Student
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className={
                                (guardian.student_count || 0) > 0
                                  ? "text-muted-foreground cursor-not-allowed"
                                  : "text-red-600"
                              }
                              onClick={() => {
                                if ((guardian.student_count || 0) > 0) {
                                  toast.error(
                                    `Cannot delete guardian with ${guardian.student_count} linked student(s). Unlink all students first.`
                                  );
                                } else {
                                  setDeleteConfirm(guardian);
                                }
                              }}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                              {(guardian.student_count || 0) > 0 && (
                                <span className="ml-auto text-xs">({guardian.student_count} linked)</span>
                              )}
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
          {guardians.total_pages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Showing {(page - 1) * 20 + 1} to {Math.min(page * 20, guardians.total)} of{" "}
                {guardians.total} guardians
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!guardians.has_previous || isPending}
                  onClick={() => handlePageChange(page - 1)}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground px-2">
                  Page {page} of {guardians.total_pages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!guardians.has_next || isPending}
                  onClick={() => handlePageChange(page + 1)}
                >
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Guardian Dialog */}
      <AddGuardianDialog
        open={isAddDialogOpen}
        onOpenChange={setIsAddDialogOpen}
        onSuccess={handleGuardianChanged}
      />

      {/* Edit Guardian Dialog */}
      <AddGuardianDialog
        open={!!editGuardian}
        onOpenChange={(open) => !open && setEditGuardian(null)}
        guardian={editGuardian || undefined}
        onSuccess={handleGuardianChanged}
      />

      {/* View Guardian Dialog */}
      <ViewGuardianDialog
        open={!!viewGuardian}
        onOpenChange={(open) => !open && setViewGuardian(null)}
        guardian={viewGuardian || undefined}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteConfirm} onOpenChange={() => setDeleteConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Guardian</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete{" "}
              <strong>
                {deleteConfirm?.first_name} {deleteConfirm?.last_name}
              </strong>
              ? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Link to Student Dialog */}
      {linkGuardian && (
        <LinkToStudentDialog
          guardian={linkGuardian}
          open={!!linkGuardian}
          onOpenChange={(open) => !open && setLinkGuardian(null)}
          onSuccess={handleGuardianChanged}
        />
      )}
    </div>
  );
}
