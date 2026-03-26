"use client";

import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, X, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
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
import type { DietaryRequirements } from "@/types";

interface DietaryRequirementsFormProps {
  studentId: string;
  initialData?: DietaryRequirements;
  onSave: (data: DietaryRequirements) => void;
  isSaving?: boolean;
}

const DIETARY_RESTRICTION_OPTIONS = [
  "vegetarian",
  "vegan",
  "halal",
  "kosher",
  "gluten-free",
  "lactose-free",
  "nut-free",
] as const;

const allergyEntrySchema = z.object({
  allergen: z.string().min(1, "Allergen is required"),
  severity: z.enum(["mild", "moderate", "severe"], { message: "Select severity" }),
  reaction: z.string().optional(),
  medication: z.string().optional(),
});

const formSchema = z.object({
  allergies: z.array(allergyEntrySchema),
  dietary_restrictions: z.array(z.string()),
  notes: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

export function DietaryRequirementsForm({
  initialData,
  onSave,
  isSaving,
}: DietaryRequirementsFormProps) {
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      allergies: initialData?.allergies ?? [],
      dietary_restrictions: initialData?.dietary_restrictions ?? [],
      notes: initialData?.notes ?? "",
    },
  });

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "allergies",
  });

  function onSubmit(values: FormValues) {
    onSave({
      allergies: values.allergies.map((a) => ({
        allergen: a.allergen,
        severity: a.severity as "mild" | "moderate" | "severe",
        reaction: a.reaction || undefined,
        medication: a.medication || undefined,
      })),
      dietary_restrictions: values.dietary_restrictions,
      notes: values.notes || undefined,
    });
  }

  const watchedRestrictions = form.watch("dietary_restrictions");

  function toggleRestriction(restriction: string) {
    const current = form.getValues("dietary_restrictions");
    if (current.includes(restriction)) {
      form.setValue(
        "dietary_restrictions",
        current.filter((r) => r !== restriction),
        { shouldDirty: true }
      );
    } else {
      form.setValue("dietary_restrictions", [...current, restriction], {
        shouldDirty: true,
      });
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        {/* Allergies Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Label className="text-base font-medium">Allergies</Label>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                append({ allergen: "", severity: "mild", reaction: "", medication: "" })
              }
            >
              <Plus className="mr-1 h-4 w-4" />
              Add Allergy
            </Button>
          </div>

          {fields.length === 0 && (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No allergies recorded. Click &quot;Add Allergy&quot; to add one.
            </p>
          )}

          {fields.map((field, index) => (
            <div
              key={field.id}
              className="grid grid-cols-1 md:grid-cols-2 gap-3 rounded-lg border p-3 relative"
            >
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute right-1 top-1 h-6 w-6"
                onClick={() => remove(index)}
              >
                <X className="h-4 w-4" />
              </Button>

              <FormField
                control={form.control}
                name={`allergies.${index}.allergen`}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Allergen</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g., Peanuts, Milk" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name={`allergies.${index}.severity`}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Severity</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select..." />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="mild">Mild</SelectItem>
                        <SelectItem value="moderate">Moderate</SelectItem>
                        <SelectItem value="severe">Severe</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name={`allergies.${index}.reaction`}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Reaction</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="e.g., Rash, Swelling"
                        {...field}
                        value={field.value ?? ""}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name={`allergies.${index}.medication`}
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Medication</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="e.g., EpiPen, Antihistamine"
                        {...field}
                        value={field.value ?? ""}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>
          ))}
        </div>

        {/* Dietary Restrictions Section */}
        <div className="space-y-3">
          <Label className="text-base font-medium">Dietary Restrictions</Label>
          <div className="flex flex-wrap gap-3">
            {DIETARY_RESTRICTION_OPTIONS.map((restriction) => (
              <div key={restriction} className="flex items-center gap-2">
                <Checkbox
                  id={`restriction-${restriction}`}
                  checked={watchedRestrictions.includes(restriction)}
                  onCheckedChange={() => toggleRestriction(restriction)}
                />
                <Label
                  htmlFor={`restriction-${restriction}`}
                  className="text-sm font-normal capitalize cursor-pointer"
                >
                  {restriction}
                </Label>
              </div>
            ))}
          </div>
        </div>

        {/* Notes Section */}
        <FormField
          control={form.control}
          name="notes"
          render={({ field }) => (
            <FormItem>
              <FormLabel className="text-base font-medium">
                Additional Notes
              </FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Any additional dietary notes or instructions..."
                  rows={3}
                  {...field}
                  value={field.value ?? ""}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" disabled={isSaving}>
          {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save Dietary Requirements
        </Button>
      </form>
    </Form>
  );
}
