"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2 } from "lucide-react";
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
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Textarea } from "@/components/ui/textarea";

import { updateStudent } from "@/actions/students.action";

const notesSchema = z.object({
  notes: z.string().max(5000, "Notes cannot exceed 5000 characters"),
});

type NotesFormData = z.infer<typeof notesSchema>;

interface AddNotesDialogProps {
  studentId: string;
  studentName: string;
  currentNotes?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function AddNotesDialog({
  studentId,
  studentName,
  currentNotes,
  open,
  onOpenChange,
  onSuccess,
}: AddNotesDialogProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  const form = useForm<NotesFormData>({
    resolver: zodResolver(notesSchema),
    defaultValues: {
      notes: currentNotes || "",
    },
  });

  // Reset form when dialog opens with current notes
  const handleOpenChange = (newOpen: boolean) => {
    if (newOpen) {
      form.reset({ notes: currentNotes || "" });
    }
    onOpenChange(newOpen);
  };

  const onSubmit = async (data: NotesFormData) => {
    setIsSubmitting(true);

    const result = await updateStudent(studentId, {
      notes: data.notes || undefined,
    });

    if (result.success) {
      toast.success("Notes saved successfully");
      onOpenChange(false);
      onSuccess();
    } else {
      toast.error(result.error || "Failed to save notes");
    }

    setIsSubmitting(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>
            {currentNotes ? "Edit Notes" : "Add Notes"}
          </DialogTitle>
          <DialogDescription>
            Add notes or remarks about {studentName}. These notes are only visible to staff.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="notes"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Notes</FormLabel>
                  <FormControl>
                    <Textarea
                      {...field}
                      placeholder="Enter any additional notes, observations, or remarks about this student..."
                      className="min-h-[200px] resize-y"
                    />
                  </FormControl>
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>Visible only to authorized staff</span>
                    <span>{field.value?.length || 0}/5000</span>
                  </div>
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
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save Notes
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
