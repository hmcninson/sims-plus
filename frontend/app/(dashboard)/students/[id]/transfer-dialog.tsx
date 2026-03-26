"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  Loader2,
} from "lucide-react";
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
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Card, CardContent } from "@/components/ui/card";

import {
  checkOutstandingFees,
  initiateTransfer,
  getWithdrawalClearance,
  updateClearance,
  completeTransfer,
  downloadTransferCertificate,
} from "@/actions/students.action";
import type {
  OutstandingFeeCheckResponse,
  WithdrawalClearanceResponse,
} from "@/types";

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

const transferSchema = z.object({
  destination_school: z
    .string()
    .min(2, "Destination school name is required"),
  reason: z.string().min(5, "Reason must be at least 5 characters"),
  effective_date: z.string().min(1, "Effective date is required"),
  fee_override: z.boolean(),
});

type TransferFormData = z.infer<typeof transferSchema>;

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface TransferDialogProps {
  studentId: string;
  studentName: string;
  isBoarder: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TransferDialog({
  studentId,
  studentName,
  isBoarder,
  open,
  onOpenChange,
  onSuccess,
}: TransferDialogProps) {
  const [step, setStep] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [feeCheck, setFeeCheck] = useState<OutstandingFeeCheckResponse | null>(
    null
  );
  const [clearance, setClearance] =
    useState<WithdrawalClearanceResponse | null>(null);
  const [isComplete, setIsComplete] = useState(false);

  const form = useForm<TransferFormData>({
    resolver: zodResolver(transferSchema),
    defaultValues: {
      destination_school: "",
      reason: "",
      effective_date: "",
      fee_override: false,
    },
  });

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setStep(1);
      setFeeCheck(null);
      setClearance(null);
      setIsComplete(false);
      form.reset();
      loadFees();
    }
  }, [open]);

  async function loadFees() {
    const result = await checkOutstandingFees(studentId);
    if (result.success) {
      setFeeCheck(result.data);
    }
  }

  // Step 1: Submit transfer form
  async function onSubmitForm(values: TransferFormData) {
    setIsLoading(true);
    const result = await initiateTransfer(studentId, {
      destination_school: values.destination_school,
      reason: values.reason,
      effective_date: values.effective_date,
      fee_override: values.fee_override,
    });

    if (result.success) {
      toast.success("Transfer initiated");
      const clearanceResult = await getWithdrawalClearance(studentId);
      if (clearanceResult.success) {
        setClearance(clearanceResult.data);
      }
      setStep(2);
    } else {
      toast.error(result.error || "Failed to initiate transfer");
    }
    setIsLoading(false);
  }

  // Step 2: Update clearance item
  async function handleClearanceToggle(
    field:
      | "library_cleared"
      | "finance_cleared"
      | "property_cleared"
      | "boarding_cleared",
    value: boolean
  ) {
    if (!clearance) return;
    setIsLoading(true);

    const result = await updateClearance(studentId, clearance.id, {
      [field]: value,
    });

    if (result.success) {
      setClearance(result.data);
    } else {
      toast.error(result.error || "Failed to update clearance");
    }
    setIsLoading(false);
  }

  // Step 2 -> 3: Complete transfer
  async function handleComplete() {
    setIsLoading(true);
    const result = await completeTransfer(studentId);

    if (result.success) {
      setIsComplete(true);
      setStep(3);
      toast.success("Transfer completed successfully");
    } else {
      toast.error(result.error || "Failed to complete transfer");
    }
    setIsLoading(false);
  }

  // Download transfer certificate
  async function handleDownloadCertificate() {
    setIsLoading(true);
    const result = await downloadTransferCertificate(studentId);
    if (result.success && result.data) {
      const url = URL.createObjectURL(result.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `transfer-certificate-${studentId}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success("Transfer certificate downloaded");
    } else {
      toast.error(result.error || "Failed to download certificate");
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

  const allCleared = clearance
    ? clearance.library_cleared &&
      clearance.finance_cleared &&
      clearance.property_cleared &&
      (!isBoarder || clearance.boarding_cleared === true)
    : false;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>
            {step === 3 ? "Transfer Complete" : "Transfer Student"}
          </DialogTitle>
          <DialogDescription>
            {step === 1 && `Initiate transfer process for ${studentName}.`}
            {step === 2 && "Complete the clearance checklist before finalizing."}
            {step === 3 && `${studentName} has been transferred successfully.`}
          </DialogDescription>
        </DialogHeader>

        {/* Step indicators */}
        {step < 3 && (
          <div className="flex items-center gap-2 mb-2">
            {[1, 2].map((s) => (
              <div key={s} className="flex items-center gap-2">
                <div
                  className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-medium ${
                    s === step
                      ? "bg-primary text-primary-foreground"
                      : s < step
                        ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                        : "bg-muted text-muted-foreground"
                  }`}
                >
                  {s < step ? <CheckCircle2 className="h-4 w-4" /> : s}
                </div>
                {s < 2 && (
                  <div
                    className={`h-0.5 w-8 ${
                      s < step ? "bg-green-500" : "bg-muted"
                    }`}
                  />
                )}
              </div>
            ))}
            <span className="text-xs text-muted-foreground ml-2">
              {step === 1 ? "Details" : "Clearance"}
            </span>
          </div>
        )}

        {/* Step 1: Transfer form */}
        {step === 1 && (
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmitForm)}
              className="space-y-4"
            >
              {/* Outstanding fees warning */}
              {feeCheck && feeCheck.has_outstanding && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-900/20">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                    <div className="text-sm">
                      <p className="font-medium text-amber-800 dark:text-amber-300">
                        Outstanding Fees
                      </p>
                      <p className="text-amber-700 dark:text-amber-400 mt-1">
                        This student has{" "}
                        <strong>
                          GHS {feeCheck.total_outstanding.toFixed(2)}
                        </strong>{" "}
                        in outstanding fees across {feeCheck.invoice_count}{" "}
                        invoice{feeCheck.invoice_count !== 1 ? "s" : ""}.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              <FormField
                control={form.control}
                name="destination_school"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Destination School</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="Enter the name of the receiving school"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="reason"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Reason for Transfer</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Enter the reason for transfer..."
                        className="resize-none"
                        rows={3}
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
                        <FormLabel>Override fee requirement</FormLabel>
                        <FormDescription>
                          Allow transfer despite outstanding fees
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
                      Processing...
                    </>
                  ) : (
                    "Initiate Transfer"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        )}

        {/* Step 2: Clearance checklist */}
        {step === 2 && clearance && (
          <div className="space-y-4">
            <div className="space-y-3">
              <ClearanceItem
                label="Library Clearance"
                description="All library books returned"
                checked={clearance.library_cleared}
                disabled={isLoading}
                onChange={(v) => handleClearanceToggle("library_cleared", v)}
              />
              <ClearanceItem
                label="Finance Clearance"
                description="All fees settled or overridden"
                checked={clearance.finance_cleared}
                disabled={isLoading}
                onChange={(v) => handleClearanceToggle("finance_cleared", v)}
              />
              <ClearanceItem
                label="Property Clearance"
                description="All school property returned"
                checked={clearance.property_cleared}
                disabled={isLoading}
                onChange={(v) => handleClearanceToggle("property_cleared", v)}
              />
              {isBoarder && (
                <ClearanceItem
                  label="Boarding Clearance"
                  description="Dormitory and boarding items cleared"
                  checked={clearance.boarding_cleared === true}
                  disabled={isLoading}
                  onChange={(v) =>
                    handleClearanceToggle("boarding_cleared", v)
                  }
                />
              )}
            </div>

            {clearance.outstanding_fees != null &&
              clearance.outstanding_fees > 0 && (
                <div className="flex items-center gap-2 text-sm text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  <span>
                    Outstanding fees: GHS{" "}
                    {clearance.outstanding_fees.toFixed(2)}
                    {clearance.fee_override && (
                      <Badge variant="outline" className="ml-2 text-xs">
                        Overridden
                      </Badge>
                    )}
                  </span>
                </div>
              )}

            <Separator />

            <DialogFooter>
              <Button variant="outline" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button
                onClick={handleComplete}
                disabled={isLoading || !allCleared}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Completing...
                  </>
                ) : (
                  "Complete Transfer"
                )}
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step 3: Success */}
        {step === 3 && (
          <div className="space-y-4">
            <Card className="border-green-200 dark:border-green-800">
              <CardContent className="pt-6 text-center">
                <CheckCircle2 className="h-12 w-12 text-green-500 mx-auto mb-3" />
                <p className="font-medium text-lg">Transfer Complete</p>
                <p className="text-sm text-muted-foreground mt-1">
                  {studentName} has been successfully transferred.
                </p>
              </CardContent>
            </Card>

            <Button
              variant="outline"
              className="w-full"
              onClick={handleDownloadCertificate}
              disabled={isLoading}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Download className="h-4 w-4 mr-2" />
              )}
              Download Transfer Certificate
            </Button>

            <DialogFooter>
              <Button onClick={handleClose} className="w-full">
                Done
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Clearance item sub-component
// ---------------------------------------------------------------------------

function ClearanceItem({
  label,
  description,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  disabled: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between rounded-lg border p-3">
      <div className="space-y-0.5">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <Switch checked={checked} disabled={disabled} onCheckedChange={onChange} />
    </div>
  );
}
