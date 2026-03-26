"use client";

import { useEffect, useState, useTransition } from "react";
import { useForm, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
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
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2, Users } from "lucide-react";

import { getSalaryGrades, bulkAssignSalaryGrade } from "@/actions/payroll.action";
import type { SalaryGrade } from "@/types/payroll.type";
import { useToast } from "@/hooks/use-toast";

interface BulkSalaryAssignProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedStaffIds: string[];
  onComplete: () => void;
}

const bulkAssignSchema = z.object({
  salary_grade_id: z.string().min(1, "Select a salary grade"),
  effective_date: z.string().min(1, "Effective date is required"),
});

type BulkAssignFormValues = z.infer<typeof bulkAssignSchema>;

function formatGHS(amount: number): string {
  return `GHS ${amount.toLocaleString("en-GH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function BulkSalaryAssign({
  open,
  onOpenChange,
  selectedStaffIds,
  onComplete,
}: BulkSalaryAssignProps) {
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [grades, setGrades] = useState<SalaryGrade[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<BulkAssignFormValues>({
    resolver: zodResolver(bulkAssignSchema) as Resolver<BulkAssignFormValues>,
    defaultValues: {
      salary_grade_id: "",
      effective_date: new Date().toISOString().split("T")[0],
    },
  });

  useEffect(() => {
    if (open) {
      startTransition(async () => {
        const result = await getSalaryGrades(true);
        if (result.success && result.data) {
          setGrades(result.data);
        }
      });
      form.reset({
        salary_grade_id: "",
        effective_date: new Date().toISOString().split("T")[0],
      });
    }
  }, [open, form]);

  const onSubmit = async (formData: BulkAssignFormValues) => {
    setIsSubmitting(true);
    try {
      const result = await bulkAssignSalaryGrade({
        staff_ids: selectedStaffIds,
        salary_grade_id: formData.salary_grade_id,
        effective_date: formData.effective_date,
      });

      if (result.success && result.data) {
        const { assigned_count, skipped_count, errors } = result.data;
        if (skipped_count > 0 || errors.length > 0) {
          toast({
            title: "Partially completed",
            description: `${assigned_count} assigned, ${skipped_count} skipped.${errors.length > 0 ? ` Errors: ${errors[0]}` : ""}`,
            variant: "destructive",
          });
        } else {
          toast({
            title: "Salary grade assigned",
            description: `${assigned_count} staff member${assigned_count !== 1 ? "s" : ""} updated.`,
          });
        }
        onOpenChange(false);
        onComplete();
      } else {
        toast({
          title: "Error",
          description: result.error,
          variant: "destructive",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Bulk Assign Salary Grade
          </DialogTitle>
          <DialogDescription>
            Assign a salary grade to{" "}
            <Badge variant="secondary" className="mx-1">
              {selectedStaffIds.length}
            </Badge>
            selected staff member{selectedStaffIds.length !== 1 ? "s" : ""}.
          </DialogDescription>
        </DialogHeader>

        {isPending ? (
          <div className="flex h-[100px] items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="salary_grade_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Salary Grade *</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select a salary grade" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {grades.map((g) => (
                          <SelectItem key={g.id} value={g.id}>
                            {g.name} {g.code ? `(${g.code})` : ""} - {formatGHS(g.basic_salary)}
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
                name="effective_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Effective Date *</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
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
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting || grades.length === 0}>
                  {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Assign to {selectedStaffIds.length} Staff
                </Button>
              </DialogFooter>
            </form>
          </Form>
        )}
      </DialogContent>
    </Dialog>
  );
}
