"use client";

import { useState, useTransition } from "react";
import {
  Shield,
  Plus,
  MoreHorizontal,
  Pencil,
  Trash2,
  Users,
  Loader2,
  Zap,
  ShieldAlert,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import { RoleDialog } from "@/components/roles/role-dialog";
import { listCustomRoles, deleteCustomRole } from "@/actions/custom-roles.action";
import type { CustomRole } from "@/types/custom-role.type";
import type { SubscriptionTier } from "@/types";

// Base role display config
const BASE_ROLE_CONFIG: Record<string, { label: string; color: string }> = {
  school_admin: { label: "School Admin", color: "bg-orange-500" },
  academic_head: { label: "Academic Head", color: "bg-blue-500" },
  finance_officer: { label: "Finance Officer", color: "bg-green-500" },
  hr_officer: { label: "HR Officer", color: "bg-teal-500" },
  teacher: { label: "Teacher", color: "bg-purple-500" },
  house_parent: { label: "House Parent", color: "bg-yellow-500" },
};

interface CustomRolesPageProps {
  roles: CustomRole[];
  subscriptionTier: string;
}

export function CustomRolesPage({ roles: initialRoles, subscriptionTier }: CustomRolesPageProps) {
  const [roles, setRoles] = useState<CustomRole[]>(initialRoles);
  const [isPending, startTransition] = useTransition();

  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedRole, setSelectedRole] = useState<CustomRole | null>(null);

  const isFeatureAvailable =
    subscriptionTier === "professional" || subscriptionTier === "enterprise";

  const refreshRoles = () => {
    startTransition(async () => {
      const result = await listCustomRoles();
      if (result.success) {
        setRoles(result.data.roles);
      }
    });
  };

  const handleDelete = () => {
    if (!selectedRole) return;

    startTransition(async () => {
      const result = await deleteCustomRole(selectedRole.id);
      if (result.success) {
        toast.success("Role deleted", {
          description: `"${selectedRole.name}" has been removed.`,
        });
        setDeleteDialogOpen(false);
        setSelectedRole(null);
        refreshRoles();
      } else {
        toast.error("Failed to delete role", {
          description: result.error,
        });
      }
    });
  };

  const openEditDialog = (role: CustomRole) => {
    setSelectedRole(role);
    setEditDialogOpen(true);
  };

  const openDeleteDialog = (role: CustomRole) => {
    setSelectedRole(role);
    setDeleteDialogOpen(true);
  };

  // Feature gate: show upgrade prompt for Starter/Trial tiers
  if (!isFeatureAvailable) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Custom Roles</h2>
          <p className="text-sm text-muted-foreground">
            Create roles with granular permissions for your staff.
          </p>
        </div>

        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
              <Zap className="h-6 w-6 text-primary" />
            </div>
            <h3 className="mt-4 text-lg font-semibold">
              Upgrade to Professional
            </h3>
            <p className="mt-2 max-w-sm text-sm text-muted-foreground">
              Custom roles with granular permissions are available on Professional
              and Enterprise plans. Upgrade to create roles tailored to your
              school&apos;s needs.
            </p>
            <Button asChild className="mt-6">
              <Link href="/settings/subscription">
                <Zap className="mr-2 h-4 w-4" />
                View Plans
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Custom Roles</h2>
          <p className="text-sm text-muted-foreground">
            Create roles with specific permission sets for your staff.
          </p>
        </div>
        <Button onClick={() => setCreateDialogOpen(true)} size="sm">
          <Plus className="mr-2 h-4 w-4" />
          Create Role
        </Button>
      </div>

      {/* Roles List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Shield className="h-5 w-5" />
            Roles ({roles.length})
          </CardTitle>
          <CardDescription>
            Custom roles extend base roles with specific permission subsets.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {roles.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-muted">
                <ShieldAlert className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="mt-4 text-sm font-semibold">No custom roles yet</h3>
              <p className="mt-2 max-w-sm text-sm text-muted-foreground">
                Create your first custom role to assign specific permissions to
                staff members. Custom roles are based on existing roles but with
                fine-grained control.
              </p>
              <Button
                variant="outline"
                className="mt-4"
                onClick={() => setCreateDialogOpen(true)}
              >
                <Plus className="mr-2 h-4 w-4" />
                Create Role
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {roles.map((role) => {
                const baseConfig = BASE_ROLE_CONFIG[role.base_role] ?? {
                  label: role.base_role,
                  color: "bg-gray-500",
                };
                return (
                  <div
                    key={role.id}
                    className="flex items-center justify-between rounded-lg border p-4"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{role.name}</p>
                        {role.is_system && (
                          <Badge variant="outline" className="text-xs">
                            System
                          </Badge>
                        )}
                      </div>
                      {role.description && (
                        <p className="mt-1 text-sm text-muted-foreground line-clamp-1">
                          {role.description}
                        </p>
                      )}
                      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1.5">
                          <div className={`h-2 w-2 rounded-full ${baseConfig.color}`} />
                          {baseConfig.label}
                        </span>
                        <span>{role.permissions.length} permissions</span>
                        <span className="flex items-center gap-1">
                          <Users className="h-3 w-3" />
                          {role.user_count ?? 0} users
                        </span>
                      </div>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="shrink-0">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuLabel>Actions</DropdownMenuLabel>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() => openEditDialog(role)}
                          disabled={role.is_system}
                        >
                          <Pencil className="mr-2 h-4 w-4" />
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() => openDeleteDialog(role)}
                          disabled={role.is_system}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Role Dialog */}
      <RoleDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onSuccess={refreshRoles}
      />

      {/* Edit Role Dialog */}
      {selectedRole && (
        <RoleDialog
          open={editDialogOpen}
          onOpenChange={(open) => {
            setEditDialogOpen(open);
            if (!open) setSelectedRole(null);
          }}
          role={selectedRole}
          onSuccess={refreshRoles}
        />
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Custom Role</AlertDialogTitle>
            <AlertDialogDescription>
              {selectedRole && (selectedRole.user_count ?? 0) > 0 ? (
                <>
                  This role cannot be deleted because{" "}
                  <strong>{selectedRole.user_count}</strong> user
                  {(selectedRole.user_count ?? 0) > 1 ? "s are" : " is"} still
                  assigned to it. Reassign those users to another role first.
                </>
              ) : (
                <>
                  Are you sure you want to delete &ldquo;{selectedRole?.name}
                  &rdquo;? This action cannot be undone.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            {selectedRole && (selectedRole.user_count ?? 0) === 0 && (
              <AlertDialogAction
                onClick={handleDelete}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                disabled={isPending}
              >
                {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Delete
              </AlertDialogAction>
            )}
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
