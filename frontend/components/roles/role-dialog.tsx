"use client";

import { useEffect, useState, useTransition, useCallback } from "react";
import { Loader2, Info } from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";

import {
  createCustomRole,
  updateCustomRole,
  getPermissionsCatalog,
} from "@/actions/custom-roles.action";
import type { CustomRole, PermissionModule } from "@/types/custom-role.type";

// Staff roles allowed as base role (exclude platform_admin, chain_admin, parent, student, applicant)
const ALLOWED_BASE_ROLES: { value: string; label: string }[] = [
  { value: "school_admin", label: "School Admin" },
  { value: "academic_head", label: "Academic Head" },
  { value: "finance_officer", label: "Finance Officer" },
  { value: "hr_officer", label: "HR Officer" },
  { value: "teacher", label: "Teacher" },
  { value: "house_parent", label: "House Parent" },
];

interface RoleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  role?: CustomRole;
  onSuccess: () => void;
}

export function RoleDialog({ open, onOpenChange, role, onSuccess }: RoleDialogProps) {
  const isEditing = !!role;
  const [isPending, startTransition] = useTransition();

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [baseRole, setBaseRole] = useState("teacher");
  const [selectedPermissions, setSelectedPermissions] = useState<Set<string>>(new Set());

  // Catalog state
  const [catalog, setCatalog] = useState<PermissionModule[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(false);

  // Load catalog when base role changes or dialog opens
  const loadCatalog = useCallback(async (role: string) => {
    setCatalogLoading(true);
    const result = await getPermissionsCatalog(role);
    if (result.success) {
      setCatalog(result.data.modules);
    } else {
      toast.error("Failed to load permissions", {
        description: result.error,
      });
      setCatalog([]);
    }
    setCatalogLoading(false);
  }, []);

  // Initialize form when dialog opens
  useEffect(() => {
    if (!open) return;

    if (isEditing && role) {
      setName(role.name);
      setDescription(role.description ?? "");
      setBaseRole(role.base_role);
      setSelectedPermissions(new Set(role.permissions));
      loadCatalog(role.base_role);
    } else {
      setName("");
      setDescription("");
      setBaseRole("teacher");
      setSelectedPermissions(new Set());
      loadCatalog("teacher");
    }
  }, [open, isEditing, role, loadCatalog]);

  const handleBaseRoleChange = (newBaseRole: string) => {
    setBaseRole(newBaseRole);
    // Clear permissions that might not be valid for the new base role
    setSelectedPermissions(new Set());
    loadCatalog(newBaseRole);
  };

  const togglePermission = (key: string) => {
    setSelectedPermissions((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const toggleModuleAll = (module: PermissionModule) => {
    const moduleKeys = module.permissions.map((p) => p.key);
    const allSelected = moduleKeys.every((k) => selectedPermissions.has(k));

    setSelectedPermissions((prev) => {
      const next = new Set(prev);
      if (allSelected) {
        moduleKeys.forEach((k) => next.delete(k));
      } else {
        moduleKeys.forEach((k) => next.add(k));
      }
      return next;
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      toast.error("Role name is required");
      return;
    }
    if (selectedPermissions.size === 0) {
      toast.error("Select at least one permission");
      return;
    }

    startTransition(async () => {
      const permissions = Array.from(selectedPermissions);

      if (isEditing && role) {
        const result = await updateCustomRole(role.id, {
          name: name.trim(),
          description: description.trim() || undefined,
          permissions,
        });
        if (result.success) {
          toast.success("Role updated", {
            description: `"${name}" has been updated.`,
          });
          onOpenChange(false);
          onSuccess();
        } else {
          toast.error("Failed to update role", {
            description: result.error,
          });
        }
      } else {
        const result = await createCustomRole({
          name: name.trim(),
          base_role: baseRole,
          description: description.trim() || undefined,
          permissions,
        });
        if (result.success) {
          toast.success("Role created", {
            description: `"${name}" has been created.`,
          });
          onOpenChange(false);
          onSuccess();
        } else {
          toast.error("Failed to create role", {
            description: result.error,
          });
        }
      }
    });
  };

  const totalAvailablePermissions = catalog.reduce(
    (sum, m) => sum + m.permissions.length,
    0
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] flex flex-col">
        <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0">
          <DialogHeader>
            <DialogTitle>
              {isEditing ? "Edit Custom Role" : "Create Custom Role"}
            </DialogTitle>
            <DialogDescription>
              {isEditing
                ? "Update the role name, description, and permissions."
                : "Define a new role with specific permissions based on an existing role."}
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 min-h-0 overflow-y-auto py-4 space-y-5">
            {/* Name */}
            <div className="space-y-2">
              <Label htmlFor="role_name">Role Name</Label>
              <Input
                id="role_name"
                placeholder="e.g., Head of Department"
                required
                maxLength={100}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            {/* Description */}
            <div className="space-y-2">
              <Label htmlFor="role_description">
                Description{" "}
                <span className="text-muted-foreground font-normal">(optional)</span>
              </Label>
              <Textarea
                id="role_description"
                placeholder="Brief description of this role's purpose..."
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            {/* Base Role */}
            <div className="space-y-2">
              <Label htmlFor="base_role">Base Role</Label>
              {isEditing ? (
                <div>
                  <Input
                    value={
                      ALLOWED_BASE_ROLES.find((r) => r.value === baseRole)?.label ??
                      baseRole
                    }
                    disabled
                    className="bg-muted"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Base role cannot be changed after creation. Create a new role instead.
                  </p>
                </div>
              ) : (
                <Select value={baseRole} onValueChange={handleBaseRoleChange}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select base role" />
                  </SelectTrigger>
                  <SelectContent>
                    {ALLOWED_BASE_ROLES.map((r) => (
                      <SelectItem key={r.value} value={r.value}>
                        {r.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <p className="text-xs text-muted-foreground">
                The base role defines the permission ceiling. Custom permissions
                cannot exceed the base role&apos;s access level.
              </p>
            </div>

            {/* Permissions Picker */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Permissions</Label>
                <span className="text-xs text-muted-foreground">
                  {selectedPermissions.size} of {totalAvailablePermissions} selected
                </span>
              </div>

              {catalogLoading ? (
                <div className="space-y-4 rounded-md border p-4">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div key={i} className="space-y-2">
                      <Skeleton className="h-4 w-24" />
                      <div className="space-y-1.5 pl-2">
                        <Skeleton className="h-4 w-48" />
                        <Skeleton className="h-4 w-40" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : catalog.length === 0 ? (
                <div className="rounded-md border p-6 text-center text-sm text-muted-foreground">
                  No permissions available for this base role.
                </div>
              ) : (
                <ScrollArea className="h-[300px] rounded-md border">
                  <div className="p-4 space-y-5">
                    {catalog.map((module) => {
                      const moduleKeys = module.permissions.map((p) => p.key);
                      const allSelected = moduleKeys.every((k) =>
                        selectedPermissions.has(k)
                      );
                      const someSelected =
                        !allSelected &&
                        moduleKeys.some((k) => selectedPermissions.has(k));

                      return (
                        <div key={module.module} className="space-y-2">
                          {/* Module header with select all */}
                          <div className="flex items-center gap-2">
                            <Checkbox
                              id={`module-${module.module}`}
                              checked={allSelected}
                              data-indeterminate={someSelected}
                              onCheckedChange={() => toggleModuleAll(module)}
                              className={someSelected ? "opacity-70" : undefined}
                            />
                            <label
                              htmlFor={`module-${module.module}`}
                              className="text-sm font-semibold cursor-pointer select-none"
                            >
                              {module.module}
                            </label>
                            <span className="text-xs text-muted-foreground">
                              ({moduleKeys.filter((k) => selectedPermissions.has(k)).length}
                              /{moduleKeys.length})
                            </span>
                          </div>

                          {/* Individual permissions */}
                          <div className="ml-6 space-y-1.5">
                            <TooltipProvider delayDuration={300}>
                              {module.permissions.map((perm) => (
                                <div
                                  key={perm.key}
                                  className="flex items-center gap-2"
                                >
                                  <Checkbox
                                    id={`perm-${perm.key}`}
                                    checked={selectedPermissions.has(perm.key)}
                                    onCheckedChange={() => togglePermission(perm.key)}
                                  />
                                  <label
                                    htmlFor={`perm-${perm.key}`}
                                    className="text-sm cursor-pointer select-none flex-1"
                                  >
                                    {perm.label}
                                  </label>
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <Info className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                                    </TooltipTrigger>
                                    <TooltipContent side="left" className="max-w-xs">
                                      <p className="text-xs">{perm.description}</p>
                                      <p className="mt-1 text-xs font-mono text-muted-foreground">
                                        {perm.key}
                                      </p>
                                    </TooltipContent>
                                  </Tooltip>
                                </div>
                              ))}
                            </TooltipProvider>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>
              )}
            </div>
          </div>

          <DialogFooter className="pt-4 border-t">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isPending || catalogLoading || selectedPermissions.size === 0}
            >
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isEditing ? "Save Changes" : "Create Role"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
