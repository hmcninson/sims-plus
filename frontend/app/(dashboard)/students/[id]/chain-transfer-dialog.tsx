"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
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
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";

import {
  checkOutstandingFees,
  chainTransfer,
} from "@/actions/students.action";
import { getAccessibleSchools } from "@/actions/chain.action";
import { getClasses } from "@/actions/academic.action";
import type { OutstandingFeeCheckResponse, Class } from "@/types";
import type { SwitcherSchool } from "@/types/chain.type";

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

const chainTransferSchema = z.object({
  to_school_id: z.string().min(1, "Destination school is required"),
  to_class_id: z.string().min(1, "Destination class is required"),
  to_section_id: z.string(),
  reason: z.string().min(5, "Reason must be at least 5 characters"),
  effective_date: z.string().min(1, "Effective date is required"),
  fee_override: z.boolean(),
});

type ChainTransferFormData = z.infer<typeof chainTransferSchema>;

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ChainTransferDialogProps {
  studentId: string;
  studentName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ChainTransferDialog({
  studentId,
  studentName,
  open,
  onOpenChange,
  onSuccess,
}: ChainTransferDialogProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [feeCheck, setFeeCheck] = useState<OutstandingFeeCheckResponse | null>(
    null
  );
  const [schools, setSchools] = useState<SwitcherSchool[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [loadingClasses, setLoadingClasses] = useState(false);

  const form = useForm<ChainTransferFormData>({
    resolver: zodResolver(chainTransferSchema),
    defaultValues: {
      to_school_id: "",
      to_class_id: "",
      to_section_id: "",
      reason: "",
      effective_date: "",
      fee_override: false,
    },
  });

  const selectedSchoolId = form.watch("to_school_id");
  const selectedClassId = form.watch("to_class_id");

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setIsComplete(false);
      setFeeCheck(null);
      setSchools([]);
      setClasses([]);
      form.reset();
      loadInitialData();
    }
  }, [open]);

  // Load classes when school changes
  useEffect(() => {
    if (selectedSchoolId) {
      loadClasses();
      form.setValue("to_class_id", "");
      form.setValue("to_section_id", "");
    }
  }, [selectedSchoolId]);

  // Reset section when class changes
  useEffect(() => {
    if (selectedClassId) {
      form.setValue("to_section_id", "");
    }
  }, [selectedClassId]);

  async function loadInitialData() {
    const [feesResult, schoolsResult] = await Promise.all([
      checkOutstandingFees(studentId),
      getAccessibleSchools(),
    ]);

    if (feesResult.success) {
      setFeeCheck(feesResult.data);
    }
    if (schoolsResult.success) {
      setSchools(schoolsResult.data);
    }
  }

  async function loadClasses() {
    setLoadingClasses(true);
    // Note: getClasses fetches classes for the active school context.
    // For chain transfers, the backend should filter by the target school.
    // Here we fetch with sections included.
    const result = await getClasses(true);
    if (result.success) {
      setClasses(result.data);
    }
    setLoadingClasses(false);
  }

  async function onSubmit(values: ChainTransferFormData) {
    setIsLoading(true);
    const result = await chainTransfer(studentId, {
      to_school_id: values.to_school_id,
      to_class_id: values.to_class_id,
      to_section_id: values.to_section_id || undefined, // empty string -> undefined for API
      reason: values.reason,
      effective_date: values.effective_date,
      fee_override: values.fee_override,
    });

    if (result.success) {
      setIsComplete(true);
      toast.success("Chain transfer completed successfully");
    } else {
      toast.error(result.error || "Failed to process chain transfer");
    }
    setIsLoading(false);
  }

  function handleClose() {
    if (isComplete) {
      onSuccess();
    }
    onOpenChange(false);
  }

  const today = new Date().toISOString().split("T")[0];

  // Get sections for the selected class
  const selectedClass = classes.find((c) => c.id === selectedClassId);
  const sections = selectedClass?.sections || [];

  if (isComplete) {
    return (
      <Dialog open={open} onOpenChange={handleClose}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>Transfer Complete</DialogTitle>
            <DialogDescription>
              {studentName} has been transferred within the school chain.
            </DialogDescription>
          </DialogHeader>

          <Card className="border-green-200 dark:border-green-800">
            <CardContent className="pt-6 text-center">
              <CheckCircle2 className="h-12 w-12 text-green-500 mx-auto mb-3" />
              <p className="font-medium text-lg">Chain Transfer Complete</p>
              <p className="text-sm text-muted-foreground mt-1">
                {studentName} has been moved to the destination school. No
                clearance is required for within-chain transfers.
              </p>
            </CardContent>
          </Card>

          <DialogFooter>
            <Button onClick={handleClose} className="w-full">
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Transfer Within Chain</DialogTitle>
          <DialogDescription>
            Move {studentName} to another school in your chain. No clearance
            process is required.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {/* Outstanding fees advisory */}
            {feeCheck && feeCheck.has_outstanding && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-900/20">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                  <div className="text-sm">
                    <p className="font-medium text-amber-800 dark:text-amber-300">
                      Outstanding Fees (Advisory)
                    </p>
                    <p className="text-amber-700 dark:text-amber-400 mt-1">
                      This student has{" "}
                      <strong>
                        GHS {feeCheck.total_outstanding.toFixed(2)}
                      </strong>{" "}
                      in outstanding fees. Chain transfers can proceed, but you
                      may want to settle fees first.
                    </p>
                  </div>
                </div>
              </div>
            )}

            <FormField
              control={form.control}
              name="to_school_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Destination School</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    value={field.value}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select a school" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {schools.map((school) => (
                        <SelectItem key={school.id} value={school.id}>
                          {school.name}
                          {school.code ? ` (${school.code})` : ""}
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
              name="to_class_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Destination Class</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    value={field.value}
                    disabled={!selectedSchoolId || loadingClasses}
                  >
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue
                          placeholder={
                            loadingClasses
                              ? "Loading classes..."
                              : "Select a class"
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

            {sections.length > 0 && (
              <FormField
                control={form.control}
                name="to_section_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Section{" "}
                      <span className="text-muted-foreground font-normal">
                        (Optional)
                      </span>
                    </FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value || ""}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select a section" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {sections.map((section) => (
                          <SelectItem key={section.id} value={section.id}>
                            {section.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            <FormField
              control={form.control}
              name="reason"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reason for Transfer</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Enter the reason for the chain transfer..."
                      className="resize-none"
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
              name="effective_date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Effective Date</FormLabel>
                  <FormControl>
                    <Input type="date" min={today} {...field} />
                  </FormControl>
                  <FormDescription>
                    Date when the transfer takes effect (DD/MM/YYYY)
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            {feeCheck && feeCheck.has_outstanding && (
              <FormField
                control={form.control}
                name="fee_override"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-3">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel>Acknowledge outstanding fees</FormLabel>
                      <FormDescription>
                        Proceed with transfer despite outstanding fees
                      </FormDescription>
                    </div>
                  </FormItem>
                )}
              />
            )}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Transferring...
                  </>
                ) : (
                  "Transfer Student"
                )}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
