"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, RefreshCw } from "lucide-react";

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
import { toast } from "sonner";
import { restructureLoan } from "@/actions/loans.action";
import type { InterestMethod } from "@/types/loan.type";

const restructureSchema = z.object({
  new_interest_rate: z.coerce.number().min(0, "Rate must be 0 or more").max(100),
  new_interest_method: z.enum(["flat", "reducing_balance"], {
    message: "Select an interest method",
  }),
  new_tenure_months: z.coerce.number().min(1, "Minimum 1 month").max(120),
  new_first_deduction_date: z.string().min(1, "Effective date is required"),
  reason: z.string().min(1, "Reason is required"),
});

type RestructureFormValues = z.infer<typeof restructureSchema>;

interface LoanRestructureDialogProps {
  loanId: string;
  loanNumber: string;
  currentRate: number;
  currentMethod: InterestMethod;
  currentTenure: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function LoanRestructureDialog({
  loanId,
  loanNumber,
  currentRate,
  currentMethod,
  currentTenure,
  open,
  onOpenChange,
  onSuccess,
}: LoanRestructureDialogProps) {
  const today = new Date().toISOString().split("T")[0];

  const form = useForm<RestructureFormValues>({
    resolver: zodResolver(restructureSchema),
    defaultValues: {
      new_interest_rate: currentRate,
      new_interest_method: currentMethod,
      new_tenure_months: currentTenure,
      new_first_deduction_date: today,
      reason: "",
    },
  });

  async function onSubmit(values: RestructureFormValues) {
    const result = await restructureLoan(loanId, {
      new_interest_rate: values.new_interest_rate,
      new_interest_method: values.new_interest_method,
      new_tenure_months: values.new_tenure_months,
      new_first_deduction_date: values.new_first_deduction_date,
      reason: values.reason,
    });

    if (result.success) {
      toast.success("Loan restructured successfully");
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
            <RefreshCw className="h-5 w-5" />
            Restructure Loan
          </DialogTitle>
          <DialogDescription>
            Restructure loan {loanNumber} with new terms. A new loan record will
            be created and the current loan marked as restructured.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="new_interest_rate"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>New Interest Rate (%)</FormLabel>
                    <FormControl>
                      <Input type="number" step="0.01" min="0" max="100" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="new_interest_method"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Interest Method</FormLabel>
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
                        <SelectItem value="flat">Flat Rate</SelectItem>
                        <SelectItem value="reducing_balance">
                          Reducing Balance
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="new_tenure_months"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>New Tenure (months)</FormLabel>
                    <FormControl>
                      <Input type="number" min="1" max="120" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="new_first_deduction_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Effective Date</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="reason"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    Reason <span className="text-destructive">*</span>
                  </FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Reason for restructuring..."
                      rows={3}
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
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting && (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                )}
                Restructure
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
