"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Plus,
  Loader2,
  Pencil,
  Trash2,
  Phone,
  User,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import {
  listAuthorizedPickups,
  addAuthorizedPickup,
  updateAuthorizedPickup,
  deleteAuthorizedPickup,
} from "@/actions/preschool.action";
import type { AuthorizedPickup } from "@/types";

interface AuthorizedPickupListProps {
  studentId: string;
}

const pickupFormSchema = z.object({
  full_name: z.string().min(1, "Full name is required"),
  phone: z
    .string()
    .min(1, "Phone number is required")
    .regex(/^\+?[\d\s-]+$/, "Enter a valid phone number"),
  relationship_to_student: z.string().optional(),
  notes: z.string().optional(),
  is_active: z.boolean(),
});

type PickupFormValues = z.infer<typeof pickupFormSchema>;

export function AuthorizedPickupList({ studentId }: AuthorizedPickupListProps) {
  const [pickups, setPickups] = useState<AuthorizedPickup[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPickup, setEditingPickup] = useState<AuthorizedPickup | null>(null);
  const [deletePickup, setDeletePickup] = useState<AuthorizedPickup | null>(null);
  const [deleting, setDeleting] = useState(false);

  const form = useForm<PickupFormValues>({
    resolver: zodResolver(pickupFormSchema),
    defaultValues: {
      full_name: "",
      phone: "",
      relationship_to_student: "",
      notes: "",
      is_active: true,
    },
  });

  const fetchPickups = useCallback(async () => {
    if (!studentId) return;
    setLoading(true);
    try {
      const result = await listAuthorizedPickups(studentId);
      if (result.success) {
        setPickups(result.data);
      } else {
        toast.error(result.error);
      }
    } catch {
      toast.error("Failed to load authorized pickups");
    } finally {
      setLoading(false);
    }
  }, [studentId]);

  useEffect(() => {
    fetchPickups();
  }, [fetchPickups]);

  function openAddDialog() {
    setEditingPickup(null);
    form.reset({
      full_name: "",
      phone: "",
      relationship_to_student: "",
      notes: "",
      is_active: true,
    });
    setDialogOpen(true);
  }

  function openEditDialog(pickup: AuthorizedPickup) {
    setEditingPickup(pickup);
    form.reset({
      full_name: pickup.full_name,
      phone: pickup.phone,
      relationship_to_student: pickup.relationship_to_student ?? "",
      notes: pickup.notes ?? "",
      is_active: pickup.is_active,
    });
    setDialogOpen(true);
  }

  async function onSubmit(values: PickupFormValues) {
    setSaving(true);
    try {
      if (editingPickup) {
        const result = await updateAuthorizedPickup(editingPickup.id, {
          full_name: values.full_name,
          phone: values.phone,
          relationship_to_student: values.relationship_to_student || undefined,
          notes: values.notes || undefined,
          is_active: values.is_active,
        });
        if (result.success) {
          toast.success("Authorized person updated");
          setDialogOpen(false);
          fetchPickups();
        } else {
          toast.error(result.error);
        }
      } else {
        const result = await addAuthorizedPickup(studentId, {
          full_name: values.full_name,
          phone: values.phone,
          relationship_to_student: values.relationship_to_student || undefined,
          notes: values.notes || undefined,
        });
        if (result.success) {
          toast.success("Authorized person added");
          setDialogOpen(false);
          fetchPickups();
        } else {
          toast.error(result.error);
        }
      }
    } catch {
      toast.error("Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deletePickup) return;
    setDeleting(true);
    try {
      const result = await deleteAuthorizedPickup(deletePickup.id);
      if (result.success) {
        toast.success("Authorized person removed");
        setDeletePickup(null);
        fetchPickups();
      } else {
        toast.error(result.error);
      }
    } catch {
      toast.error("Failed to delete");
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2].map((i) => (
          <Skeleton key={i} className="h-20 w-full rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {pickups.length} authorized person{pickups.length !== 1 ? "s" : ""}
        </p>
        <Button size="sm" onClick={openAddDialog}>
          <Plus className="mr-1 h-4 w-4" />
          Add Person
        </Button>
      </div>

      {pickups.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-8 text-center">
            <User className="h-10 w-10 text-muted-foreground/50" />
            <p className="mt-2 text-sm font-medium">No Authorized Persons</p>
            <p className="text-xs text-muted-foreground">
              Add people who are authorized to pick up this student.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {pickups.map((pickup) => (
            <Card key={pickup.id}>
              <CardContent className="flex items-center gap-3 py-3">
                <Avatar className="h-10 w-10">
                  <AvatarFallback className="bg-primary/10 text-primary text-sm">
                    {pickup.full_name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")
                      .slice(0, 2)
                      .toUpperCase()}
                  </AvatarFallback>
                </Avatar>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium truncate">
                      {pickup.full_name}
                    </p>
                    <Badge
                      variant={pickup.is_active ? "default" : "secondary"}
                      className="text-xs"
                    >
                      {pickup.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
                    <span className="flex items-center gap-1">
                      <Phone className="h-3 w-3" />
                      {pickup.phone}
                    </span>
                    {pickup.relationship_to_student && (
                      <span>{pickup.relationship_to_student}</span>
                    )}
                  </div>
                  {pickup.notes && (
                    <p className="text-xs text-muted-foreground mt-1 truncate">
                      {pickup.notes}
                    </p>
                  )}
                </div>

                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => openEditDialog(pickup)}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive"
                    onClick={() => setDeletePickup(pickup)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingPickup ? "Edit Authorized Person" : "Add Authorized Person"}
            </DialogTitle>
            <DialogDescription>
              {editingPickup
                ? "Update the details of this authorized pickup person."
                : "Add a new person authorized to pick up this student."}
            </DialogDescription>
          </DialogHeader>

          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="full_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Full Name</FormLabel>
                    <FormControl>
                      <Input placeholder="Full name" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="phone"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Phone Number</FormLabel>
                    <FormControl>
                      <Input placeholder="+233 XX XXX XXXX" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="relationship_to_student"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Relationship (optional)</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="e.g., Uncle, Family friend"
                        {...field}
                        value={field.value ?? ""}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes (optional)</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Any additional notes..."
                        rows={2}
                        {...field}
                        value={field.value ?? ""}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {editingPickup && (
                <FormField
                  control={form.control}
                  name="is_active"
                  render={({ field }) => (
                    <FormItem className="flex items-center justify-between rounded-lg border p-3">
                      <div>
                        <FormLabel>Active</FormLabel>
                        <p className="text-xs text-muted-foreground">
                          Inactive persons cannot pick up the student
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
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={saving}>
                  {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  {editingPickup ? "Update" : "Add Person"}
                </Button>
              </div>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deletePickup}
        onOpenChange={(open) => !open && setDeletePickup(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Authorized Person</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove{" "}
              <strong>{deletePickup?.full_name}</strong> from the authorized
              pickup list? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
