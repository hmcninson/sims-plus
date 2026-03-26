"use client";

import { useCallback, useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
import { Skeleton } from "@/components/ui/skeleton";
import { CollapsibleFilters } from "@/components/filters/collapsible-filters";
import { PromotionEntryTable } from "@/components/admissions/promotion-entry-table";
import {
  Plus,
  Loader2,
  TrendingUp,
  Eye,
  Play,
  RefreshCw,
  ArrowLeft,
  Users,
  Repeat,
  GraduationCap,
  UserMinus,
} from "lucide-react";
import {
  getPromotionBatches,
  createPromotionBatch,
  generatePromotionPreview,
  getPromotionEntries,
  updatePromotionEntry,
  executePromotionBatch,
} from "@/actions/admissions.action";
import { getAcademicYears, getClasses } from "@/actions/academic.action";
import type {
  ClassPromotion,
  ClassPromotionEntry,
  PromotionBatchStatus,
  PromotionAction,
} from "@/types/admissions.type";
import type { AcademicYear, Class } from "@/types";

const batchSchema = z.object({
  name: z.string().min(1, "Name is required"),
  source_academic_year_id: z.string().min(1, "Source year is required"),
  target_academic_year_id: z.string().min(1, "Target year is required"),
});

type BatchFormValues = z.infer<typeof batchSchema>;

const BATCH_STATUS_CONFIG: Record<
  PromotionBatchStatus,
  { label: string; className: string }
> = {
  draft: {
    label: "Draft",
    className:
      "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  },
  preview: {
    label: "Preview",
    className:
      "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  },
  in_progress: {
    label: "In Progress",
    className:
      "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300",
  },
  completed: {
    label: "Completed",
    className:
      "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  },
  failed: {
    label: "Failed",
    className: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  },
};

export function PromotionsManagement() {
  const [batches, setBatches] = useState<ClassPromotion[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);

  // Detail view state
  const [selectedBatch, setSelectedBatch] = useState<ClassPromotion | null>(
    null
  );
  const [entries, setEntries] = useState<ClassPromotionEntry[]>([]);
  const [entriesPage, setEntriesPage] = useState(1);
  const [entriesTotalPages, setEntriesTotalPages] = useState(1);
  const [loadingEntries, setLoadingEntries] = useState(false);
  const [selectedEntryIds, setSelectedEntryIds] = useState<string[]>([]);
  const [classFilterForEntries, setClassFilterForEntries] =
    useState<string>("all");
  const [actionFilterForEntries, setActionFilterForEntries] =
    useState<string>("all");
  const [generating, setGenerating] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [showExecuteDialog, setShowExecuteDialog] = useState(false);

  const form = useForm<BatchFormValues>({
    resolver: zodResolver(batchSchema),
    defaultValues: {
      name: "",
      source_academic_year_id: "",
      target_academic_year_id: "",
    },
  });

  const loadBatches = useCallback(async () => {
    const [batchesResult, yearsResult, classesResult] = await Promise.all([
      getPromotionBatches({ page_size: 50 }),
      getAcademicYears(),
      getClasses(),
    ]);

    if (batchesResult.success && batchesResult.data) {
      setBatches(batchesResult.data.items);
    }
    if (yearsResult.success && yearsResult.data) {
      setAcademicYears(yearsResult.data);
    }
    if (classesResult.success && classesResult.data) {
      setClasses(classesResult.data);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadBatches();
  }, [loadBatches]);

  const loadEntries = useCallback(
    async (batchId: string) => {
      setLoadingEntries(true);
      const result = await getPromotionEntries(batchId, {
        page: entriesPage,
        page_size: 50,
        source_class_id:
          classFilterForEntries !== "all"
            ? classFilterForEntries
            : undefined,
        action:
          actionFilterForEntries !== "all"
            ? actionFilterForEntries
            : undefined,
      });
      if (result.success && result.data) {
        setEntries(result.data.items);
        setEntriesTotalPages(result.data.pages);
      }
      setLoadingEntries(false);
    },
    [entriesPage, classFilterForEntries, actionFilterForEntries]
  );

  useEffect(() => {
    if (selectedBatch) {
      loadEntries(selectedBatch.id);
    }
  }, [selectedBatch, loadEntries]);

  async function handleCreate(values: BatchFormValues) {
    const result = await createPromotionBatch({
      name: values.name,
      source_academic_year_id: values.source_academic_year_id,
      target_academic_year_id: values.target_academic_year_id,
    });

    if (result.success) {
      toast.success("Promotion batch created");
      setShowCreateDialog(false);
      form.reset();
      loadBatches();
    } else {
      toast.error(result.error);
    }
  }

  async function handleGeneratePreview() {
    if (!selectedBatch) return;
    setGenerating(true);
    try {
      const result = await generatePromotionPreview(selectedBatch.id);
      if (result.success && result.data) {
        setSelectedBatch(result.data);
        toast.success("Preview generated");
        loadEntries(selectedBatch.id);
        loadBatches();
      } else {
        toast.error(result.error);
      }
    } finally {
      setGenerating(false);
    }
  }

  async function handleExecute() {
    if (!selectedBatch) return;
    setExecuting(true);
    try {
      const result = await executePromotionBatch(selectedBatch.id);
      if (result.success && result.data) {
        setSelectedBatch(result.data);
        toast.success("Promotion executed successfully");
        loadBatches();
      } else {
        toast.error(result.error);
      }
    } finally {
      setExecuting(false);
      setShowExecuteDialog(false);
    }
  }

  async function handleBulkAction(action: PromotionAction) {
    if (selectedEntryIds.length === 0) return;
    let successCount = 0;
    for (const entryId of selectedEntryIds) {
      const result = await updatePromotionEntry(entryId, { action });
      if (result.success) successCount++;
    }
    toast.success(`${successCount} entries updated to ${action}`);
    setSelectedEntryIds([]);
    if (selectedBatch) loadEntries(selectedBatch.id);
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

  if (loading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-[400px]" />
      </div>
    );
  }

  // Detail view
  if (selectedBatch) {
    const statusConfig = BATCH_STATUS_CONFIG[selectedBatch.status];
    const canEdit =
      selectedBatch.status === "draft" || selectedBatch.status === "preview";
    const canExecute = selectedBatch.status === "preview";

    return (
      <div className="p-4 md:p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSelectedBatch(null)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold">{selectedBatch.name}</h1>
              <Badge variant="outline" className={statusConfig.className}>
                {statusConfig.label}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              {selectedBatch.source_academic_year_name || "Source Year"} -&gt;{" "}
              {selectedBatch.target_academic_year_name || "Target Year"}
            </p>
          </div>
          <div className="flex gap-2">
            {selectedBatch.status === "draft" && (
              <Button onClick={handleGeneratePreview} disabled={generating}>
                {generating ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                Generate Preview
              </Button>
            )}
            {canExecute && (
              <Button
                variant="default"
                onClick={() => setShowExecuteDialog(true)}
              >
                <Play className="mr-2 h-4 w-4" />
                Execute Promotion
              </Button>
            )}
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          <Card>
            <CardContent className="pt-6 text-center">
              <Users className="h-5 w-5 mx-auto text-muted-foreground mb-1" />
              <p className="text-2xl font-bold">
                {selectedBatch.total_students}
              </p>
              <p className="text-xs text-muted-foreground">Total</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <TrendingUp className="h-5 w-5 mx-auto text-green-500 mb-1" />
              <p className="text-2xl font-bold">
                {selectedBatch.promoted_count}
              </p>
              <p className="text-xs text-muted-foreground">Promoted</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <Repeat className="h-5 w-5 mx-auto text-amber-500 mb-1" />
              <p className="text-2xl font-bold">
                {selectedBatch.repeated_count}
              </p>
              <p className="text-xs text-muted-foreground">Repeated</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <GraduationCap className="h-5 w-5 mx-auto text-blue-500 mb-1" />
              <p className="text-2xl font-bold">
                {selectedBatch.graduated_count}
              </p>
              <p className="text-xs text-muted-foreground">Graduated</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 text-center">
              <UserMinus className="h-5 w-5 mx-auto text-red-500 mb-1" />
              <p className="text-2xl font-bold">
                {selectedBatch.withdrawn_count}
              </p>
              <p className="text-xs text-muted-foreground">Withdrawn</p>
            </CardContent>
          </Card>
        </div>

        {/* Bulk Actions for Entries */}
        {canEdit && selectedEntryIds.length > 0 && (
          <div className="flex items-center gap-2 rounded-lg border bg-muted/80 px-4 py-3">
            <span className="text-sm font-medium">
              {selectedEntryIds.length} selected
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleBulkAction("repeat")}
            >
              Set to Repeat
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleBulkAction("withdraw")}
            >
              Set to Withdraw
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => handleBulkAction("promote")}
            >
              Set to Promote
            </Button>
          </div>
        )}

        {/* Filters for entries */}
        <CollapsibleFilters
          activeFilterCount={
            (classFilterForEntries !== "all" ? 1 : 0) +
            (actionFilterForEntries !== "all" ? 1 : 0)
          }
        >
          <Select
            value={classFilterForEntries}
            onValueChange={(v) => {
              setClassFilterForEntries(v);
              setEntriesPage(1);
            }}
          >
            <SelectTrigger className="w-full md:w-[180px]">
              <SelectValue placeholder="Source Class" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Classes</SelectItem>
              {classes.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={actionFilterForEntries}
            onValueChange={(v) => {
              setActionFilterForEntries(v);
              setEntriesPage(1);
            }}
          >
            <SelectTrigger className="w-full md:w-[160px]">
              <SelectValue placeholder="Action" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Actions</SelectItem>
              <SelectItem value="promote">Promote</SelectItem>
              <SelectItem value="repeat">Repeat</SelectItem>
              <SelectItem value="graduate">Graduate</SelectItem>
              <SelectItem value="withdraw">Withdraw</SelectItem>
            </SelectContent>
          </Select>
        </CollapsibleFilters>

        {/* Entries Table */}
        <Card>
          <CardContent className="pt-6">
            {loadingEntries ? (
              <Skeleton className="h-[300px]" />
            ) : (
              <PromotionEntryTable
                entries={entries}
                classes={classes}
                editable={canEdit}
                selectedIds={selectedEntryIds}
                onSelectionChange={setSelectedEntryIds}
                onEntryUpdated={() => {
                  if (selectedBatch) loadEntries(selectedBatch.id);
                  loadBatches();
                }}
                page={entriesPage}
                totalPages={entriesTotalPages}
                onPageChange={setEntriesPage}
              />
            )}
          </CardContent>
        </Card>

        {/* Execute Confirmation Dialog */}
        <AlertDialog
          open={showExecuteDialog}
          onOpenChange={setShowExecuteDialog}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Execute Promotion</AlertDialogTitle>
              <AlertDialogDescription>
                This will execute the class promotion batch. Students will be
                moved to their target classes according to the configured
                actions. This action cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="py-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <span>To be promoted:</span>
                <span className="font-medium">
                  {selectedBatch.promoted_count}
                </span>
              </div>
              <div className="flex justify-between">
                <span>To repeat:</span>
                <span className="font-medium">
                  {selectedBatch.repeated_count}
                </span>
              </div>
              <div className="flex justify-between">
                <span>To graduate:</span>
                <span className="font-medium">
                  {selectedBatch.graduated_count}
                </span>
              </div>
              <div className="flex justify-between">
                <span>To withdraw:</span>
                <span className="font-medium">
                  {selectedBatch.withdrawn_count}
                </span>
              </div>
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={executing}>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleExecute} disabled={executing}>
                {executing && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Execute
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    );
  }

  // List view
  return (
    <div className="p-4 md:p-6 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Class Promotions</h1>
          <p className="text-sm text-muted-foreground">
            Manage end-of-year class promotions
          </p>
        </div>
        <Button onClick={() => setShowCreateDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Create Batch
        </Button>
      </div>

      {/* Batches Table */}
      <Card>
        <CardContent className="p-0">
          {batches.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <TrendingUp className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm font-medium">No promotion batches</p>
              <p className="text-sm text-muted-foreground">
                Create a promotion batch to manage class promotions
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead className="hidden md:table-cell">
                      Academic Years
                    </TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="hidden sm:table-cell">
                      Students
                    </TableHead>
                    <TableHead className="w-[80px]">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {batches.map((batch) => {
                    const statusConfig = BATCH_STATUS_CONFIG[batch.status];
                    return (
                      <TableRow key={batch.id}>
                        <TableCell className="font-medium">
                          {batch.name}
                        </TableCell>
                        <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                          {batch.source_academic_year_name || "N/A"} -&gt;{" "}
                          {batch.target_academic_year_name || "N/A"}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={statusConfig.className}
                          >
                            {statusConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell text-sm">
                          {batch.total_students}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedBatch(batch)}
                          >
                            <Eye className="mr-1 h-4 w-4" />
                            View
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Batch Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Promotion Batch</DialogTitle>
            <DialogDescription>
              Create a new class promotion batch for the end-of-year transition.
            </DialogDescription>
          </DialogHeader>

          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(handleCreate)}
              className="space-y-4"
            >
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Batch Name</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="e.g., 2025/2026 Promotions"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="source_academic_year_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Source Academic Year</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select source year" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {academicYears.map((year) => (
                          <SelectItem key={year.id} value={year.id}>
                            {year.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="target_academic_year_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Target Academic Year</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select target year" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {academicYears.map((year) => (
                          <SelectItem key={year.id} value={year.id}>
                            {year.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowCreateDialog(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={form.formState.isSubmitting}
                >
                  {form.formState.isSubmitting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Create Batch
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
