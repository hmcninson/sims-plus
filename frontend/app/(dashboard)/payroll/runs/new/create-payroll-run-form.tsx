"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
  FormDescription,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { createPayrollRun } from "@/actions/payroll.action";
import type { PayrollRunType } from "@/types/payroll.type";

const MONTH_OPTIONS = [
  { value: 1, label: "January" },
  { value: 2, label: "February" },
  { value: 3, label: "March" },
  { value: 4, label: "April" },
  { value: 5, label: "May" },
  { value: 6, label: "June" },
  { value: 7, label: "July" },
  { value: 8, label: "August" },
  { value: 9, label: "September" },
  { value: 10, label: "October" },
  { value: 11, label: "November" },
  { value: 12, label: "December" },
];

const RUN_TYPE_OPTIONS: { value: PayrollRunType; label: string; description: string }[] = [
  { value: "regular", label: "Regular", description: "Standard monthly payroll" },
  { value: "supplementary", label: "Supplementary", description: "Additional run for corrections" },
  { value: "bonus", label: "Bonus", description: "Bonus or 13th month payment" },
  { value: "arrears", label: "Arrears", description: "Back-pay or arrears payment" },
];

const formSchema = z.object({
  month: z.number().min(1).max(12, { message: "Select a valid month" }),
  year: z
    .number()
    .min(2020, { message: "Year must be 2020 or later" })
    .max(2099, { message: "Year must be before 2100" }),
  run_type: z.enum(["regular", "supplementary", "bonus", "arrears"], {
    message: "Select a run type",
  }),
  notes: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

export function CreatePayrollRunForm() {
  const router = useRouter();
  const currentDate = new Date();

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      month: currentDate.getMonth() + 1,
      year: currentDate.getFullYear(),
      run_type: "regular",
      notes: "",
    },
  });

  async function onSubmit(values: FormValues) {
    const result = await createPayrollRun({
      month: values.month,
      year: values.year,
      run_type: values.run_type,
      notes: values.notes || undefined,
    });

    if (result.success) {
      toast.success("Payroll run created successfully");
      router.push(`/payroll/runs/${result.data.id}`);
    } else {
      toast.error(result.error);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/payroll/runs">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Create Payroll Run</h1>
          <p className="text-muted-foreground">
            Set up a new monthly payroll processing run
          </p>
        </div>
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle>Run Details</CardTitle>
          <CardDescription>
            Select the pay period and run type. A draft run will be created that you can then calculate.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="month"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Month</FormLabel>
                      <Select
                        onValueChange={(v) => field.onChange(parseInt(v))}
                        value={String(field.value)}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select month" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {MONTH_OPTIONS.map((m) => (
                            <SelectItem key={m.value} value={String(m.value)}>
                              {m.label}
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
                  name="year"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Year</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          {...field}
                          onChange={(e) => field.onChange(parseInt(e.target.value))}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={form.control}
                name="run_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Run Type</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select type" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {RUN_TYPE_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            <div>
                              <span>{opt.label}</span>
                              <span className="text-xs text-muted-foreground ml-2">
                                - {opt.description}
                              </span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      Regular runs are for standard monthly payroll. Use supplementary for corrections.
                    </FormDescription>
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
                        {...field}
                        placeholder="Add any notes about this payroll run..."
                        rows={3}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="flex gap-3">
                <Button
                  type="submit"
                  disabled={form.formState.isSubmitting}
                >
                  {form.formState.isSubmitting ? "Creating..." : "Create Payroll Run"}
                </Button>
                <Button type="button" variant="outline" asChild>
                  <Link href="/payroll/runs">Cancel</Link>
                </Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
