"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  CheckCircle2,
  CreditCard,
  Loader2,
} from "lucide-react";
import { recordEnrollmentDeposit } from "@/actions/admissions.action";

const depositSchema = z.object({
  amount: z.coerce
    .number({ message: "Amount is required" })
    .positive("Amount must be greater than 0"),
  reference: z
    .string()
    .min(1, "Payment reference is required")
    .max(255, "Reference is too long"),
});

type DepositFormValues = z.infer<typeof depositSchema>;

interface DepositPaymentProps {
  applicationId: string;
  depositPaid: boolean;
  depositAmount: number | null;
  depositReference: string | null;
}

export function DepositPayment({
  applicationId,
  depositPaid: initialPaid,
  depositAmount: initialAmount,
  depositReference: initialReference,
}: DepositPaymentProps) {
  const [isPending, startTransition] = useTransition();
  const [paid, setPaid] = useState(initialPaid);
  const [amount, setAmount] = useState(initialAmount);
  const [reference, setReference] = useState(initialReference);

  const form = useForm<DepositFormValues>({
    resolver: zodResolver(depositSchema) as Resolver<DepositFormValues>,
    defaultValues: {
      amount: 0,
      reference: "",
    },
  });

  function onSubmit(values: DepositFormValues) {
    startTransition(async () => {
      const result = await recordEnrollmentDeposit(
        applicationId,
        values.amount,
        values.reference
      );
      if (result.success) {
        setPaid(result.data.enrollment_deposit_paid);
        setAmount(result.data.enrollment_deposit_amount);
        setReference(result.data.enrollment_deposit_reference);
        toast.success("Enrollment deposit recorded");
        form.reset();
      } else {
        toast.error(result.error);
      }
    });
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <CreditCard className="h-4 w-4" />
            Enrollment Deposit
          </CardTitle>
          {paid && (
            <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
              <CheckCircle2 className="mr-1 h-3 w-3" />
              Paid
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {paid ? (
          <div className="space-y-2 text-sm">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div>
                <p className="text-muted-foreground">Amount</p>
                <p className="font-medium">
                  GHS {amount?.toLocaleString("en-GH", { minimumFractionDigits: 2 }) ?? "--"}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Reference</p>
                <p className="font-medium">{reference ?? "--"}</p>
              </div>
            </div>
          </div>
        ) : (
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3">
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
                        min="0"
                        placeholder="e.g., 500.00"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="reference"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Payment Reference</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="e.g., REC-2026-001 or bank reference"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button
                type="submit"
                size="sm"
                disabled={isPending}
                className="w-full sm:w-auto"
              >
                {isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <CreditCard className="mr-2 h-4 w-4" />
                )}
                Record Payment
              </Button>
            </form>
          </Form>
        )}
      </CardContent>
    </Card>
  );
}
