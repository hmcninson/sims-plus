"use client";

import { useEffect, useState, useTransition } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
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
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Plus, Pencil, Trash2, Tags } from "lucide-react";

import {
  getLeaveTypes,
  createLeaveType,
  updateLeaveType,
  deleteLeaveType,
} from "@/actions/leave.action";
import type { LeaveType } from "@/types/leave.type";
import { useToast } from "@/hooks/use-toast";

const leaveTypeSchema = z.object({
  name: z.string().min(1, "Name is required").max(100),
  code: z.string().min(1, "Code is required").max(20),
  description: z.string().optional(),
  default_days_per_year: z.coerce
    .number()
    .min(0, "Must be 0 or more")
    .max(365, "Cannot exceed 365"),
  max_carryover_days: z.coerce.number().min(0, "Must be 0 or more"),
  is_paid: z.boolean(),
  requires_approval: z.boolean(),
  color: z.string().regex(/^#[0-9A-Fa-f]{6}$/, "Must be a valid hex color"),
});

type LeaveTypeFormValues = z.infer<typeof leaveTypeSchema>;

export default function LeaveTypesPage() {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [leaveTypes, setLeaveTypes] = useState<LeaveType[]>([]);

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingType, setEditingType] = useState<LeaveType | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<LeaveTypeFormValues>({
    resolver: zodResolver(leaveTypeSchema) as Resolver<LeaveTypeFormValues>,
    defaultValues: {
      name: "",
      code: "",
      description: "",
      default_days_per_year: 0,
      max_carryover_days: 0,
      is_paid: true,
      requires_approval: true,
      color: "#3B82F6",
    },
  });

  const loadTypes = () => {
    startTransition(async () => {
      const result = await getLeaveTypes(false);
      if (result.success && result.data) {
        setLeaveTypes(result.data);
      }
    });
  };

  useEffect(() => {
    loadTypes();
  }, []);

  const handleOpenDialog = (leaveType?: LeaveType) => {
    if (leaveType) {
      setEditingType(leaveType);
      form.reset({
        name: leaveType.name,
        code: leaveType.code,
        description: leaveType.description || "",
        default_days_per_year: leaveType.default_days_per_year,
        max_carryover_days: leaveType.max_carryover_days,
        is_paid: leaveType.is_paid,
        requires_approval: leaveType.requires_approval,
        color: leaveType.color || "#3B82F6",
      });
    } else {
      setEditingType(null);
      form.reset({
        name: "",
        code: "",
        description: "",
        default_days_per_year: 0,
        max_carryover_days: 0,
        is_paid: true,
        requires_approval: true,
        color: "#3B82F6",
      });
    }
    setIsDialogOpen(true);
  };

  const onSubmit = async (formData: LeaveTypeFormValues) => {
    setIsSubmitting(true);
    try {
      const data = {
        name: formData.name.trim(),
        code: formData.code.trim().toUpperCase(),
        description: formData.description?.trim() || undefined,
        default_days_per_year: formData.default_days_per_year,
        max_carryover_days: formData.max_carryover_days,
        is_paid: formData.is_paid,
        requires_approval: formData.requires_approval,
        color: formData.color,
      };

      if (editingType) {
        const result = await updateLeaveType(editingType.id, data);
        if (result.success) {
          toast({ title: "Leave type updated", description: `${formData.name} has been updated.` });
          setIsDialogOpen(false);
          loadTypes();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      } else {
        const result = await createLeaveType(data);
        if (result.success) {
          toast({ title: "Leave type created", description: `${formData.name} has been created.` });
          setIsDialogOpen(false);
          loadTypes();
        } else {
          toast({ title: "Error", description: result.error, variant: "destructive" });
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    setIsSubmitting(true);
    try {
      const result = await deleteLeaveType(deleteId);
      if (result.success) {
        toast({ title: "Leave type deleted" });
        loadTypes();
      } else {
        toast({ title: "Error", description: result.error, variant: "destructive" });
      }
    } finally {
      setIsSubmitting(false);
      setDeleteId(null);
    }
  };

  const handleToggleActive = async (leaveType: LeaveType) => {
    const result = await updateLeaveType(leaveType.id, {
      is_active: !leaveType.is_active,
    });
    if (result.success) {
      toast({
        title: leaveType.is_active ? "Leave type deactivated" : "Leave type activated",
      });
      loadTypes();
    } else {
      toast({ title: "Error", description: result.error, variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Leave Types</h1>
          <p className="text-muted-foreground">
            Configure leave categories available to staff
          </p>
        </div>
        <Button onClick={() => handleOpenDialog()}>
          <Plus className="mr-2 h-4 w-4" />
          Add Leave Type
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Leave Types</CardTitle>
          <CardDescription>
            {leaveTypes.length} leave type{leaveTypes.length !== 1 ? "s" : ""} configured
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : leaveTypes.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead className="hidden sm:table-cell">Code</TableHead>
                  <TableHead className="hidden md:table-cell text-right">Days/Year</TableHead>
                  <TableHead className="hidden md:table-cell text-right">Carryover</TableHead>
                  <TableHead className="hidden sm:table-cell">Paid</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leaveTypes.map((lt) => (
                  <TableRow key={lt.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {lt.color && (
                          <div
                            className="h-3 w-3 rounded-full shrink-0"
                            style={{ backgroundColor: lt.color }}
                          />
                        )}
                        <span className="font-medium">{lt.name}</span>
                      </div>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell font-mono text-sm">
                      {lt.code}
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-right">
                      {lt.default_days_per_year}
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-right">
                      {lt.max_carryover_days}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell">
                      {lt.is_paid ? (
                        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
                          Paid
                        </Badge>
                      ) : (
                        <Badge variant="secondary">Unpaid</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={lt.is_active ? "default" : "secondary"}
                        className="cursor-pointer"
                        onClick={() => handleToggleActive(lt)}
                      >
                        {lt.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleOpenDialog(lt)}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setDeleteId(lt.id)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Tags className="h-12 w-12" />
              <p>No leave types configured</p>
              <p className="text-sm text-center max-w-md">
                Create leave types to enable staff leave management.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingType ? "Edit Leave Type" : "Create Leave Type"}
            </DialogTitle>
            <DialogDescription>
              {editingType
                ? "Update leave type configuration."
                : "Add a new leave type for staff."}
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Name *</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., Annual Leave" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="code"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Code *</FormLabel>
                      <FormControl>
                        <Input
                          placeholder="e.g., ANNUAL"
                          {...field}
                          onChange={(e) =>
                            field.onChange(e.target.value.toUpperCase())
                          }
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Textarea rows={2} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="default_days_per_year"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Days per Year *</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} step={0.5} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="max_carryover_days"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Max Carryover Days</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} step={0.5} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="color"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Color *</FormLabel>
                      <FormControl>
                        <div className="flex items-center gap-2">
                          <input
                            type="color"
                            value={field.value}
                            onChange={field.onChange}
                            className="h-10 w-10 cursor-pointer rounded border"
                          />
                          <Input
                            {...field}
                            className="flex-1"
                            placeholder="#3B82F6"
                          />
                        </div>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="is_paid"
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between rounded-lg border p-3">
                      <div>
                        <FormLabel className="text-sm font-medium">Paid Leave</FormLabel>
                        <p className="text-xs text-muted-foreground">
                          Staff receive salary during this leave
                        </p>
                      </div>
                      <FormControl>
                        <Switch
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="requires_approval"
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between rounded-lg border p-3">
                      <div>
                        <FormLabel className="text-sm font-medium">
                          Requires Approval
                        </FormLabel>
                        <p className="text-xs text-muted-foreground">
                          Must be approved by admin/HR
                        </p>
                      </div>
                      <FormControl>
                        <Switch
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsDialogOpen(false)}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingType ? "Save Changes" : "Create Leave Type"}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Leave Type?</AlertDialogTitle>
            <AlertDialogDescription>
              This will deactivate this leave type. Active leave balances may be affected.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isSubmitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isSubmitting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
