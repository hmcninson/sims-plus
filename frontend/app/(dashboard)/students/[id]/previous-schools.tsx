"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Building2,
  Plus,
  Edit,
  Trash2,
  Loader2,
  MapPin,
  BookOpen,
  Calendar,
  ArrowRightLeft,
  FileText,
} from "lucide-react";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
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

import {
  getPreviousSchools,
  createPreviousSchool,
  updatePreviousSchool,
  deletePreviousSchool,
} from "@/actions/students.action";
import type { PreviousSchoolRecord } from "@/types";

const formSchema = z.object({
  school_name: z.string().min(1, "School name is required").max(200),
  school_address: z.string().max(500).optional().or(z.literal("")),
  last_class: z.string().max(100).optional().or(z.literal("")),
  years_attended: z.string().max(50).optional().or(z.literal("")),
  transfer_reason: z.string().max(500).optional().or(z.literal("")),
  leaving_certificate_ref: z.string().max(100).optional().or(z.literal("")),
});

type FormValues = z.infer<typeof formSchema>;

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

interface PreviousSchoolsProps {
  studentId: string;
}

export function PreviousSchools({ studentId }: PreviousSchoolsProps) {
  const [records, setRecords] = useState<PreviousSchoolRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState<PreviousSchoolRecord | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<PreviousSchoolRecord | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      school_name: "",
      school_address: "",
      last_class: "",
      years_attended: "",
      transfer_reason: "",
      leaving_certificate_ref: "",
    },
  });

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    const result = await getPreviousSchools(studentId);
    if (result.success && result.data) {
      setRecords(result.data);
    } else {
      toast.error(result.error || "Failed to load previous schools");
    }
    setLoading(false);
  }, [studentId]);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  const openCreate = () => {
    setEditingRecord(null);
    form.reset({
      school_name: "",
      school_address: "",
      last_class: "",
      years_attended: "",
      transfer_reason: "",
      leaving_certificate_ref: "",
    });
    setDialogOpen(true);
  };

  const openEdit = (record: PreviousSchoolRecord) => {
    setEditingRecord(record);
    form.reset({
      school_name: record.school_name,
      school_address: record.school_address || "",
      last_class: record.last_class || "",
      years_attended: record.years_attended || "",
      transfer_reason: record.transfer_reason || "",
      leaving_certificate_ref: record.leaving_certificate_ref || "",
    });
    setDialogOpen(true);
  };

  const handleSubmit = async (values: FormValues) => {
    // Clean empty strings to undefined
    const cleanData = {
      school_name: values.school_name,
      school_address: values.school_address || undefined,
      last_class: values.last_class || undefined,
      years_attended: values.years_attended || undefined,
      transfer_reason: values.transfer_reason || undefined,
      leaving_certificate_ref: values.leaving_certificate_ref || undefined,
    };

    if (editingRecord) {
      const result = await updatePreviousSchool(studentId, editingRecord.id, cleanData);
      if (result.success) {
        toast.success("Previous school updated");
        setDialogOpen(false);
        fetchRecords();
      } else {
        toast.error(result.error || "Failed to update");
      }
    } else {
      const result = await createPreviousSchool(studentId, cleanData);
      if (result.success) {
        toast.success("Previous school added");
        setDialogOpen(false);
        fetchRecords();
      } else {
        toast.error(result.error || "Failed to add");
      }
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    const result = await deletePreviousSchool(studentId, deleteTarget.id);
    if (result.success) {
      toast.success("Previous school removed");
      setDeleteTarget(null);
      fetchRecords();
    } else {
      toast.error(result.error || "Failed to delete");
    }
    setIsDeleting(false);
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between">
        <div>
          <CardTitle className="text-base flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            Previous Schools
          </CardTitle>
          <CardDescription>
            Schools the student previously attended
          </CardDescription>
        </div>
        <Button size="sm" onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" />
          Add
        </Button>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <Skeleton key={i} className="h-24 w-full rounded-lg" />
            ))}
          </div>
        ) : records.length === 0 ? (
          <div className="text-center py-12">
            <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
              <Building2 className="h-7 w-7 text-muted-foreground" />
            </div>
            <h3 className="font-semibold mb-1">No Previous Schools</h3>
            <p className="text-muted-foreground mb-4">
              Record the schools this student attended before enrolling here.
            </p>
            <Button variant="outline" onClick={openCreate}>
              <Plus className="h-4 w-4 mr-2" />
              Add Previous School
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {records.map((record) => (
              <div
                key={record.id}
                className="relative p-4 rounded-lg border hover:bg-accent/50 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="space-y-2 flex-1 min-w-0">
                    <h4 className="font-semibold">{record.school_name}</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                      {record.school_address && (
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <MapPin className="h-3.5 w-3.5 shrink-0" />
                          <span className="truncate">{record.school_address}</span>
                        </div>
                      )}
                      {record.last_class && (
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <BookOpen className="h-3.5 w-3.5 shrink-0" />
                          <span>Last Class: {record.last_class}</span>
                        </div>
                      )}
                      {record.years_attended && (
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <Calendar className="h-3.5 w-3.5 shrink-0" />
                          <span>Years: {record.years_attended}</span>
                        </div>
                      )}
                      {record.leaving_certificate_ref && (
                        <div className="flex items-center gap-1.5 text-muted-foreground">
                          <FileText className="h-3.5 w-3.5 shrink-0" />
                          <span>Cert Ref: {record.leaving_certificate_ref}</span>
                        </div>
                      )}
                    </div>
                    {record.transfer_reason && (
                      <div className="flex items-start gap-1.5 text-sm text-muted-foreground">
                        <ArrowRightLeft className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                        <span>Reason: {record.transfer_reason}</span>
                      </div>
                    )}
                    <p className="text-xs text-muted-foreground">
                      Added {formatDate(record.created_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0 ml-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => openEdit(record)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      onClick={() => setDeleteTarget(record)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>

      {/* Create/Edit Dialog */}
      <Dialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) {
            setEditingRecord(null);
            form.reset();
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingRecord ? "Edit Previous School" : "Add Previous School"}
            </DialogTitle>
            <DialogDescription>
              {editingRecord
                ? "Update the previous school record."
                : "Add a school this student previously attended."}
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="school_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>School Name</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. Achimota Primary" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="school_address"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Address (optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="School address" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="last_class"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Last Class (optional)</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. Primary 6" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="years_attended"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Years Attended (optional)</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g. 2020-2024" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="transfer_reason"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Transfer Reason (optional)</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Reason for leaving this school"
                        rows={2}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="leaving_certificate_ref"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Leaving Certificate Ref (optional)</FormLabel>
                    <FormControl>
                      <Input placeholder="Certificate reference number" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={form.formState.isSubmitting}>
                  {form.formState.isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      {editingRecord ? "Updating..." : "Adding..."}
                    </>
                  ) : editingRecord ? (
                    "Update"
                  ) : (
                    "Add School"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Previous School</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove <strong>{deleteTarget?.school_name}</strong>?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? "Removing..." : "Remove"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
