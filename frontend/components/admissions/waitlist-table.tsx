"use client";

import { useCallback, useEffect, useState, useTransition } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  ListOrdered,
  Loader2,
  Save,
  UserCheck,
} from "lucide-react";
import {
  getWaitlist,
  reorderWaitlist,
  promoteFromWaitlist,
  getAdmissionPeriods,
} from "@/actions/admissions.action";
import { getClasses } from "@/actions/academic.action";
import type { WaitlistEntry } from "@/types/admissions.type";
import type { Class } from "@/types";

const promoteSchema = z.object({
  offered_class_id: z.string().min(1, "Class is required"),
  response_deadline: z.string().optional(),
  conditions: z.string().optional(),
});

type PromoteFormValues = z.infer<typeof promoteSchema>;

export function WaitlistTable() {
  const [entries, setEntries] = useState<WaitlistEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [isPending, startTransition] = useTransition();

  // Filters
  const [periodFilter, setPeriodFilter] = useState<string>("all");
  const [periods, setPeriods] = useState<Array<{ id: string; name: string }>>([]);

  // Reorder state
  const [localOrder, setLocalOrder] = useState<WaitlistEntry[]>([]);
  const [hasOrderChanges, setHasOrderChanges] = useState(false);
  const [savingOrder, setSavingOrder] = useState(false);

  // Promote dialog
  const [promoteEntry, setPromoteEntry] = useState<WaitlistEntry | null>(null);
  const [classes, setClasses] = useState<Class[]>([]);
  const [loadingClasses, setLoadingClasses] = useState(false);

  const promoteForm = useForm<PromoteFormValues>({
    resolver: zodResolver(promoteSchema),
    defaultValues: {
      offered_class_id: "",
      response_deadline: "",
      conditions: "",
    },
  });

  const loadWaitlist = useCallback(async () => {
    startTransition(async () => {
      const result = await getWaitlist({
        period_id: periodFilter !== "all" ? periodFilter : undefined,
        page,
        page_size: 50,
      });

      if (result.success && result.data) {
        setEntries(result.data.items);
        setLocalOrder(result.data.items);
        setTotal(result.data.total);
        setTotalPages(result.data.pages);
        setHasOrderChanges(false);
      }
      setLoading(false);
    });
  }, [page, periodFilter]);

  useEffect(() => {
    loadWaitlist();
  }, [loadWaitlist]);

  useEffect(() => {
    async function loadLookups() {
      const periodsResult = await getAdmissionPeriods({ page_size: 50 });
      if (periodsResult.success && periodsResult.data) {
        setPeriods(
          periodsResult.data.items.map((p) => ({ id: p.id, name: p.name }))
        );
      }
    }
    loadLookups();
  }, []);

  function moveUp(index: number) {
    if (index <= 0) return;
    const newOrder = [...localOrder];
    [newOrder[index - 1], newOrder[index]] = [
      newOrder[index],
      newOrder[index - 1],
    ];
    setLocalOrder(newOrder);
    setHasOrderChanges(true);
  }

  function moveDown(index: number) {
    if (index >= localOrder.length - 1) return;
    const newOrder = [...localOrder];
    [newOrder[index], newOrder[index + 1]] = [
      newOrder[index + 1],
      newOrder[index],
    ];
    setLocalOrder(newOrder);
    setHasOrderChanges(true);
  }

  async function handleSaveOrder() {
    if (periodFilter === "all") {
      toast.error("Please select a specific admission period before saving the order");
      return;
    }

    setSavingOrder(true);
    const result = await reorderWaitlist({
      period_id: periodFilter,
      ordered_decision_ids: localOrder.map((e) => e.decision_id),
    });

    if (result.success) {
      toast.success("Waitlist order saved");
      setHasOrderChanges(false);
      loadWaitlist();
    } else {
      toast.error(result.error);
    }
    setSavingOrder(false);
  }

  async function handlePromote(values: PromoteFormValues) {
    if (!promoteEntry) return;

    const result = await promoteFromWaitlist(promoteEntry.decision_id, {
      offered_class_id: values.offered_class_id,
      response_deadline: values.response_deadline || undefined,
      conditions: values.conditions || undefined,
    });

    if (result.success) {
      toast.success(
        `${promoteEntry.applicant_name} has been promoted from the waitlist`
      );
      setPromoteEntry(null);
      promoteForm.reset();
      loadWaitlist();
    } else {
      toast.error(result.error);
    }
  }

  function openPromoteDialog(entry: WaitlistEntry) {
    setPromoteEntry(entry);
    promoteForm.reset({
      offered_class_id: "",
      response_deadline: "",
      conditions: "",
    });
    if (classes.length === 0) {
      setLoadingClasses(true);
      getClasses()
        .then((res) => {
          if (res.success && res.data) setClasses(res.data);
        })
        .finally(() => setLoadingClasses(false));
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-[400px]" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header + Filters */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold">Waitlist</h2>
          <p className="text-sm text-muted-foreground">
            {total} waitlisted applicant{total !== 1 ? "s" : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Select
            value={periodFilter}
            onValueChange={(v) => {
              setPeriodFilter(v);
              setPage(1);
            }}
          >
            <SelectTrigger className="w-full sm:w-[200px]">
              <SelectValue placeholder="Filter by Period" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Periods</SelectItem>
              {periods.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {hasOrderChanges && (
            <Button onClick={handleSaveOrder} disabled={savingOrder}>
              {savingOrder ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              Save Order
            </Button>
          )}
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {localOrder.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <ListOrdered className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm font-medium">No waitlisted applicants</p>
              <p className="text-sm text-muted-foreground">
                Applicants placed on the waitlist will appear here
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[60px]">Rank</TableHead>
                    <TableHead className="w-[80px]">Order</TableHead>
                    <TableHead>Applicant</TableHead>
                    <TableHead className="hidden md:table-cell">
                      Class
                    </TableHead>
                    <TableHead className="hidden sm:table-cell">
                      Date
                    </TableHead>
                    <TableHead className="w-[100px]">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {localOrder.map((entry, index) => (
                    <TableRow key={entry.decision_id}>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className="font-mono text-xs"
                        >
                          {index + 1}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => moveUp(index)}
                            disabled={index === 0}
                          >
                            <ArrowUp className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => moveDown(index)}
                            disabled={index === localOrder.length - 1}
                          >
                            <ArrowDown className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <span className="font-medium">
                            {entry.applicant_name}
                          </span>
                          <span className="ml-2 text-xs text-muted-foreground font-mono">
                            {entry.tracking_code}
                          </span>
                        </div>
                        {entry.waitlist_notes && (
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {entry.waitlist_notes}
                          </p>
                        )}
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-sm text-muted-foreground">
                        {entry.target_class_name || "-"}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                        {new Date(entry.decision_date).toLocaleDateString(
                          "en-GB"
                        )}
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openPromoteDialog(entry)}
                        >
                          <UserCheck className="mr-1.5 h-3.5 w-3.5" />
                          Promote
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(page - 1)}
              disabled={page <= 1 || isPending}
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(page + 1)}
              disabled={page >= totalPages || isPending}
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Promote Dialog */}
      <Dialog
        open={promoteEntry !== null}
        onOpenChange={(open) => {
          if (!open) {
            setPromoteEntry(null);
            promoteForm.reset();
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Promote from Waitlist</DialogTitle>
            <DialogDescription>
              Promote {promoteEntry?.applicant_name} to an offered admission
              place.
            </DialogDescription>
          </DialogHeader>

          <Form {...promoteForm}>
            <form
              onSubmit={promoteForm.handleSubmit(handlePromote)}
              className="space-y-4"
            >
              <FormField
                control={promoteForm.control}
                name="offered_class_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Offered Class</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                      disabled={loadingClasses}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue
                            placeholder={
                              loadingClasses
                                ? "Loading classes..."
                                : "Select class"
                            }
                          />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {classes.map((cls) => (
                          <SelectItem key={cls.id} value={cls.id}>
                            {cls.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={promoteForm.control}
                name="response_deadline"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Response Deadline (Optional)</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={promoteForm.control}
                name="conditions"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Conditions (Optional)</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Any conditions for this offer..."
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setPromoteEntry(null);
                    promoteForm.reset();
                  }}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={promoteForm.formState.isSubmitting}
                >
                  {promoteForm.formState.isSubmitting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Promote to Offered
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
