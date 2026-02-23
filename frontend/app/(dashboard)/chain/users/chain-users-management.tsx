"use client";

/**
 * Chain Users Management
 *
 * Lists all users in the chain tenant with their school assignments.
 * Allows assigning/removing users from schools.
 */

import { useState, useCallback } from "react";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { toast } from "sonner";
import {
  Users,
  Search,
  Plus,
  School,
  X,
  AlertCircle,
  Loader2,
} from "lucide-react";
import {
  getChainUsers,
  assignUserToSchool,
  removeUserFromSchool,
} from "@/actions/chain.action";
import type { ChainUser, ChainUserListResponse, ChainSchool } from "@/types/chain.type";

interface ChainUsersManagementProps {
  initialData: ChainUserListResponse;
  schools: ChainSchool[];
  error?: string;
}

const ROLES = [
  { value: "school_admin", label: "School Admin" },
  { value: "academic_head", label: "Academic Head" },
  { value: "finance_officer", label: "Finance Officer" },
  { value: "teacher", label: "Teacher" },
  { value: "house_parent", label: "House Parent" },
];

export function ChainUsersManagement({
  initialData,
  schools,
  error,
}: ChainUsersManagementProps) {
  const [data, setData] = useState(initialData);
  const [search, setSearch] = useState("");
  const [schoolFilter, setSchoolFilter] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);

  // Assign dialog state
  const [assignDialogOpen, setAssignDialogOpen] = useState(false);
  const [assignUserId, setAssignUserId] = useState<string>("");
  const [assignSchoolId, setAssignSchoolId] = useState<string>("");
  const [assignRole, setAssignRole] = useState<string>("");
  const [isAssigning, setIsAssigning] = useState(false);

  const fetchUsers = useCallback(
    async (page: number, searchTerm: string, schoolId: string) => {
      setIsLoading(true);
      try {
        const result = await getChainUsers(
          page,
          20,
          searchTerm || undefined,
          schoolId || undefined
        );
        if (result.success && result.data) {
          setData(result.data);
        }
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  const handleSearch = useCallback(() => {
    fetchUsers(1, search, schoolFilter);
  }, [search, schoolFilter, fetchUsers]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        handleSearch();
      }
    },
    [handleSearch]
  );

  const handleSchoolFilterChange = useCallback(
    (value: string) => {
      const newValue = value === "all" ? "" : value;
      setSchoolFilter(newValue);
      fetchUsers(1, search, newValue);
    },
    [search, fetchUsers]
  );

  const openAssignDialog = useCallback((userId: string) => {
    setAssignUserId(userId);
    setAssignSchoolId("");
    setAssignRole("");
    setAssignDialogOpen(true);
  }, []);

  const handleAssign = useCallback(async () => {
    if (!assignUserId || !assignSchoolId || !assignRole) {
      toast.error("Please select a school and role");
      return;
    }

    setIsAssigning(true);
    try {
      const result = await assignUserToSchool({
        user_id: assignUserId,
        school_id: assignSchoolId,
        role_at_school: assignRole,
      });

      if (result.success) {
        toast.success("User assigned to school");
        setAssignDialogOpen(false);
        fetchUsers(data.page, search, schoolFilter);
      } else {
        toast.error(result.error);
      }
    } finally {
      setIsAssigning(false);
    }
  }, [assignUserId, assignSchoolId, assignRole, data.page, search, schoolFilter, fetchUsers]);

  const handleRemoveAccess = useCallback(
    async (userId: string, schoolId: string, schoolName: string) => {
      if (!confirm(`Remove this user's access to ${schoolName}?`)) return;

      const result = await removeUserFromSchool({
        user_id: userId,
        school_id: schoolId,
      });

      if (result.success) {
        toast.success("Access removed");
        fetchUsers(data.page, search, schoolFilter);
      } else {
        toast.error(result.error);
      }
    },
    [data.page, search, schoolFilter, fetchUsers]
  );

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold tracking-tight">Chain Users</h1>
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Chain Users</h1>
        <p className="text-muted-foreground">
          Manage user access across schools in your chain ({data.total} users).
        </p>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search users by name or email..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={handleKeyDown}
                className="pl-9"
              />
            </div>
            <Select value={schoolFilter || "all"} onValueChange={handleSchoolFilterChange}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue placeholder="Filter by school" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Schools</SelectItem>
                {schools.map((school) => (
                  <SelectItem key={school.id} value={school.id}>
                    {school.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="secondary" onClick={handleSearch} disabled={isLoading}>
              Search
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Users Table */}
      <Card>
        <CardHeader>
          <CardTitle>Users</CardTitle>
          <CardDescription>
            View and manage user school assignments.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {data.items.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              <Users className="mx-auto mb-2 size-8" />
              <p>No users found.</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User</TableHead>
                      <TableHead className="hidden sm:table-cell">Role</TableHead>
                      <TableHead>School Access</TableHead>
                      <TableHead className="w-[100px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.items.map((user) => (
                      <TableRow key={user.id}>
                        <TableCell>
                          <div>
                            <div className="font-medium">
                              {user.first_name} {user.last_name}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {user.email}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          <Badge variant="outline">
                            {user.role.replace(/_/g, " ")}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {user.school_accesses.length === 0 ? (
                              <span className="text-xs text-muted-foreground">
                                No schools assigned
                              </span>
                            ) : (
                              user.school_accesses.map((access) => (
                                <Badge
                                  key={access.id}
                                  variant="secondary"
                                  className="flex items-center gap-1"
                                >
                                  <School className="size-3" />
                                  <span className="max-w-[120px] truncate">
                                    {access.school_name}
                                  </span>
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleRemoveAccess(
                                        user.id,
                                        access.school_id,
                                        access.school_name
                                      );
                                    }}
                                    className="ml-0.5 rounded-full p-0.5 hover:bg-muted-foreground/20"
                                    title={`Remove access to ${access.school_name}`}
                                  >
                                    <X className="size-3" />
                                  </button>
                                </Badge>
                              ))
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openAssignDialog(user.id)}
                          >
                            <Plus className="mr-1 size-3" />
                            Assign
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Pagination */}
              {data.total_pages > 1 && (
                <div className="flex items-center justify-between pt-4">
                  <p className="text-sm text-muted-foreground">
                    Page {data.page} of {data.total_pages}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={data.page <= 1 || isLoading}
                      onClick={() => fetchUsers(data.page - 1, search, schoolFilter)}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={data.page >= data.total_pages || isLoading}
                      onClick={() => fetchUsers(data.page + 1, search, schoolFilter)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Assign Dialog */}
      <Dialog open={assignDialogOpen} onOpenChange={setAssignDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Assign User to School</DialogTitle>
            <DialogDescription>
              Select a school and role for this user.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="assign-school">School</Label>
              <Select value={assignSchoolId} onValueChange={setAssignSchoolId}>
                <SelectTrigger id="assign-school">
                  <SelectValue placeholder="Select a school" />
                </SelectTrigger>
                <SelectContent>
                  {schools.map((school) => (
                    <SelectItem key={school.id} value={school.id}>
                      {school.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="assign-role">Role at School</Label>
              <Select value={assignRole} onValueChange={setAssignRole}>
                <SelectTrigger id="assign-role">
                  <SelectValue placeholder="Select a role" />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((role) => (
                    <SelectItem key={role.value} value={role.value}>
                      {role.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setAssignDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAssign}
              disabled={!assignSchoolId || !assignRole || isAssigning}
            >
              {isAssigning && <Loader2 className="mr-2 size-4 animate-spin" />}
              Assign
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
