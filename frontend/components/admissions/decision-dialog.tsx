"use client";

import { useState, useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
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
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Loader2 } from "lucide-react";
import { makeDecision } from "@/actions/admissions.action";
import { getClasses } from "@/actions/academic.action";
import type { ApplicationStatus, DecisionType } from "@/types/admissions.type";
import type { Class } from "@/types";

const decisionSchema = z.object({
  decision_type: z.enum(["accepted", "rejected", "waitlisted", "deferred"], {
    message: "Please select a decision",
  }),
  offered_class_id: z.string().optional(),
  conditions: z.string().optional(),
  response_deadline: z.string().optional(),
});

type DecisionFormValues = z.infer<typeof decisionSchema>;

interface DecisionDialogProps {
  applicationId: string;
  currentStatus: ApplicationStatus;
  applicantName: string;
  onSuccess: () => void;
  trigger: React.ReactNode;
}

const DECISION_LABELS: Record<DecisionType, string> = {
  accepted: "Accept",
  rejected: "Reject",
  waitlisted: "Waitlist",
  deferred: "Defer",
};

export function DecisionDialog({
  applicationId,
  currentStatus,
  applicantName,
  onSuccess,
  trigger,
}: DecisionDialogProps) {
  const [open, setOpen] = useState(false);
  const [classes, setClasses] = useState<Class[]>([]);
  const [loadingClasses, setLoadingClasses] = useState(false);

  const form = useForm<DecisionFormValues>({
    resolver: zodResolver(decisionSchema),
    defaultValues: {
      decision_type: undefined,
      offered_class_id: "",
      conditions: "",
      response_deadline: "",
    },
  });

  const watchedDecision = form.watch("decision_type");

  useEffect(() => {
    if (open && classes.length === 0) {
      setLoadingClasses(true);
      getClasses()
        .then((result) => {
          if (result.success && result.data) {
            setClasses(result.data);
          }
        })
        .finally(() => setLoadingClasses(false));
    }
  }, [open, classes.length]);

  async function onSubmit(values: DecisionFormValues) {
    const result = await makeDecision({
      application_id: applicationId,
      decision_type: values.decision_type,
      offered_class_id:
        values.decision_type === "accepted" && values.offered_class_id
          ? values.offered_class_id
          : undefined,
      conditions: values.conditions || undefined,
      response_deadline: values.response_deadline || undefined,
    });

    if (result.success) {
      toast.success(
        `Application ${DECISION_LABELS[values.decision_type].toLowerCase()}ed successfully`
      );
      form.reset();
      setOpen(false);
      onSuccess();
    } else {
      toast.error(result.error);
    }
  }

  // Only allow decisions from specific statuses
  const canDecide = [
    "shortlisted",
    "exam_completed",
    "waitlisted",
    "under_review",
  ].includes(currentStatus);

  if (!canDecide) return null;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Make Decision</DialogTitle>
          <DialogDescription>
            Make an admission decision for {applicantName}.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="decision_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Decision</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select decision" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="accepted">Accept</SelectItem>
                      <SelectItem value="rejected">Reject</SelectItem>
                      <SelectItem value="waitlisted">Waitlist</SelectItem>
                      <SelectItem value="deferred">Defer</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {watchedDecision === "accepted" && (
              <>
                <FormField
                  control={form.control}
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
                  control={form.control}
                  name="response_deadline"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Response Deadline</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </>
            )}

            <FormField
              control={form.control}
              name="conditions"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Conditions (Optional)</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Any conditions for this decision..."
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
                onClick={() => setOpen(false)}
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
                Confirm Decision
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
