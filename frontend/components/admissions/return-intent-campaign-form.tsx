"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
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
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Loader2, Info } from "lucide-react";
import { createReturnIntentCampaign } from "@/actions/admissions.action";
import { getAcademicYears, getClasses } from "@/actions/academic.action";
import type { AcademicYear, Class } from "@/types";

const campaignSchema = z.object({
  name: z.string().min(1, "Campaign name is required"),
  academic_year_id: z.string().min(1, "Academic year is required"),
  target_classes: z
    .array(z.string())
    .min(1, "Select at least one target class"),
  message_template: z.string().optional(),
  deadline: z.string().optional(),
});

type CampaignFormValues = z.infer<typeof campaignSchema>;

interface ReturnIntentCampaignFormProps {
  onSuccess: () => void;
  onCancel: () => void;
}

export function ReturnIntentCampaignForm({
  onSuccess,
  onCancel,
}: ReturnIntentCampaignFormProps) {
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [loading, setLoading] = useState(true);

  const form = useForm<CampaignFormValues>({
    resolver: zodResolver(campaignSchema),
    defaultValues: {
      name: "",
      academic_year_id: "",
      target_classes: [],
      message_template:
        "Dear Parent/Guardian,\n\nWe would like to know if {student_name} (currently in {class_name}) will be returning to our school for the next academic year.\n\nPlease respond at your earliest convenience.\n\nThank you.",
      deadline: "",
    },
  });

  useEffect(() => {
    async function loadData() {
      const [yearsResult, classesResult] = await Promise.all([
        getAcademicYears(),
        getClasses(),
      ]);
      if (yearsResult.success && yearsResult.data) {
        setAcademicYears(yearsResult.data);
      }
      if (classesResult.success && classesResult.data) {
        setClasses(classesResult.data);
      }
      setLoading(false);
    }
    loadData();
  }, []);

  async function onSubmit(values: CampaignFormValues) {
    const result = await createReturnIntentCampaign({
      name: values.name,
      academic_year_id: values.academic_year_id,
      target_classes: values.target_classes,
      message_template: values.message_template || undefined,
      deadline: values.deadline || undefined,
    });

    if (result.success) {
      toast.success("Campaign created successfully");
      form.reset();
      onSuccess();
    } else {
      toast.error(result.error);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <Alert>
          <Info className="h-4 w-4" />
          <AlertDescription>
            This survey is informational only and does not affect promotions or
            enrollment.
          </AlertDescription>
        </Alert>

        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Campaign Name</FormLabel>
              <FormControl>
                <Input
                  placeholder="e.g., 2026/2027 Return Intent Survey"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="academic_year_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Academic Year</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Select academic year" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {academicYears.map((year) => (
                    <SelectItem key={year.id} value={year.id}>
                      {year.name}
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
          name="target_classes"
          render={() => (
            <FormItem>
              <FormLabel>Target Classes</FormLabel>
              <FormDescription>
                Select which classes to survey
              </FormDescription>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 rounded-md border p-3">
                {classes.map((cls) => (
                  <FormField
                    key={cls.id}
                    control={form.control}
                    name="target_classes"
                    render={({ field }) => (
                      <FormItem className="flex items-center space-x-2 space-y-0">
                        <FormControl>
                          <Checkbox
                            checked={field.value.includes(cls.id)}
                            onCheckedChange={(checked) => {
                              if (checked) {
                                field.onChange([...field.value, cls.id]);
                              } else {
                                field.onChange(
                                  field.value.filter(
                                    (v: string) => v !== cls.id
                                  )
                                );
                              }
                            }}
                          />
                        </FormControl>
                        <FormLabel className="text-sm font-normal cursor-pointer">
                          {cls.name}
                        </FormLabel>
                      </FormItem>
                    )}
                  />
                ))}
              </div>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="deadline"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Response Deadline (Optional)</FormLabel>
              <FormControl>
                <Input type="date" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="message_template"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Message Template (Optional)</FormLabel>
              <FormDescription>
                Use &#123;student_name&#125; and &#123;class_name&#125; as
                placeholders.
              </FormDescription>
              <FormControl>
                <Textarea rows={5} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Create Campaign
          </Button>
        </div>
      </form>
    </Form>
  );
}
