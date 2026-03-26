"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

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
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { scheduleInterview } from "@/actions/interviews.action";

const interviewSchema = z.object({
  application_id: z.string().min(1, "Application is required"),
  interviewer_id: z.string().min(1, "Interviewer is required"),
  scheduled_date: z.string().min(1, "Date is required"),
  scheduled_time: z.string().optional(),
  duration_minutes: z.coerce.number().min(10, "Minimum 10 minutes").max(180, "Maximum 180 minutes"),
  venue: z.string().min(1, "Venue is required").max(255),
});

type InterviewFormValues = z.infer<typeof interviewSchema>;

interface InterviewSchedulerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  applicationId: string;
  interviewers: Array<{ id: string; name: string }>;
  onSuccess: () => void;
}

export function InterviewScheduler({
  open,
  onOpenChange,
  applicationId,
  interviewers,
  onSuccess,
}: InterviewSchedulerProps) {
  const form = useForm<InterviewFormValues>({
    resolver: zodResolver(interviewSchema),
    defaultValues: {
      application_id: applicationId,
      interviewer_id: "",
      scheduled_date: "",
      scheduled_time: "",
      duration_minutes: 30,
      venue: "",
    },
  });

  async function onSubmit(values: InterviewFormValues) {
    const result = await scheduleInterview({
      application_id: values.application_id,
      interviewer_id: values.interviewer_id,
      scheduled_date: values.scheduled_date,
      scheduled_time: values.scheduled_time || undefined,
      duration_minutes: values.duration_minutes,
      venue: values.venue,
    });

    if (result.success) {
      toast.success("Interview scheduled");
      onOpenChange(false);
      onSuccess();
    } else {
      toast.error(result.error);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Schedule Interview</DialogTitle>
          <DialogDescription>
            Set up an interview for this applicant.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="interviewer_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Interviewer</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Select interviewer" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {interviewers.map((i) => (
                        <SelectItem key={i.id} value={i.id}>
                          {i.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="scheduled_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Date</FormLabel>
                    <FormControl>
                      <Input type="date" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="scheduled_time"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Time (Optional)</FormLabel>
                    <FormControl>
                      <Input type="time" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                control={form.control}
                name="duration_minutes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Duration (minutes)</FormLabel>
                    <FormControl>
                      <Input type="number" min={10} max={180} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="venue"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Venue</FormLabel>
                    <FormControl>
                      <Input placeholder="Room or location" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Scheduling...
                  </>
                ) : (
                  "Schedule Interview"
                )}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
