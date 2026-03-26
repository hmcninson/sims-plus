"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, CreditCard } from "lucide-react";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import { earlyRepayment } from "@/actions/loans.action";
import { formatGHS } from "@/lib/format";

const earlyRepaymentSchema = z.object({
  amount: z.coerce.number().min(0.01, "Amount must be greater than 0"),
  payment_date: z.string().min(1, "Payment date is required"),
  payment_method: z.enum(["cash", "bank_transfer", "mobile_money"], {
    message: "Select a payment method",
  }),
  reference: z.string().optional(),
  is_full_settlement: z.boolean(),
  notes: z.string().optional(),
});

type EarlyRepaymentFormValues = z.infer<typeof earlyRepaymentSchema>;

interface EarlyRepaymentDialogProps {
  loanId: string;
  loanNumber: string;
  outstandingBalance: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function EarlyRepaymentDialog({
  loanId,
  loanNumber,
  outstandingBalance,
  open,
  onOpenChange,
  onSuccess,
}: EarlyRepaymentDialogProps) {
  const today = new Date().toISOString().split("T")[0];

  const form = useForm<EarlyRepaymentFormValues>({
    resolver: zodResolver(earlyRepaymentSchema),
    defaultValues: {
      amount: 0,
      payment_date: today,
      payment_method: "bank_transfer",
      reference: "",
      is_full_settlement: false,
      notes: "",
    },
  });

  const isFullSettlement = form.watch("is_full_settlement");

  async function onSubmit(values: EarlyRepaymentFormValues) {
    const amount = isFullSettlement ? outstandingBalance : values.amount;
    if (amount > outstandingBalance) {
      toast.error(
        `Amount cannot exceed outstanding balance of ${formatGHS(outstandingBalance)}`
      );
      return;
    }

    const result = await earlyRepayment(loanId, {
      amount,
      payment_date: values.payment_date,
      payment_method: values.payment_method,
      reference: values.reference || undefined,
      is_full_settlement: values.is_full_settlement,
      notes: values.notes || undefined,
    });

    if (result.success) {
      toast.success("Early repayment recorded successfully");
      form.reset();
      onOpenChange(false);
      onSuccess();
    } else {
      toast.error(result.error);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CreditCard className="h-5 w-5" />
            Early Repayment
          </DialogTitle>
          <DialogDescription>
            Record early repayment for loan {loanNumber}. Outstanding balance:{" "}
            {formatGHS(outstandingBalance)}
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="is_full_settlement"
              render={({ field }) => (
                <FormItem className="flex items-center gap-2 space-y-0">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <FormLabel className="font-normal">
                    Full settlement ({formatGHS(outstandingBalance)})
                  </FormLabel>
                </FormItem>
              )}
            />

            {!isFullSettlement && (
              <FormField
                control={form.control}
                name="amount"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Amount (GHS)</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        step="0.01"
                        min="0.01"
                        max={outstandingBalance}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="payment_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Payment Date</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="payment_method"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Payment Method</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="cash">Cash</SelectItem>
                        <SelectItem value="bank_transfer">
                          Bank Transfer
                        </SelectItem>
                        <SelectItem value="mobile_money">
                          Mobile Money
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="reference"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Reference (optional)</FormLabel>
                  <FormControl>
                    <Input placeholder="Receipt or transaction reference" {...field} />
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
                    <Textarea placeholder="Additional notes..." rows={2} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting && (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                )}
                Record Payment
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
