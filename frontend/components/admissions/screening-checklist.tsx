"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  CheckCircle2,
  Circle,
  Plus,
  Loader2,
  ClipboardCheck,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  addScreeningItem,
  completeScreeningItem,
} from "@/actions/interviews.action";
import type { ScreeningItem, ScreeningCategory } from "@/types/interview.type";

const CATEGORIES: { value: ScreeningCategory; label: string }[] = [
  { value: "documents", label: "Documents" },
  { value: "academic", label: "Academic" },
  { value: "medical", label: "Medical" },
  { value: "other", label: "Other" },
];

const CATEGORY_COLORS: Record<ScreeningCategory, string> = {
  documents:
    "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900 dark:text-blue-300 dark:border-blue-800",
  academic:
    "bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-900 dark:text-purple-300 dark:border-purple-800",
  medical:
    "bg-green-100 text-green-700 border-green-200 dark:bg-green-900 dark:text-green-300 dark:border-green-800",
  other:
    "bg-gray-100 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700",
};

const screeningItemSchema = z.object({
  item_name: z.string().min(1, "Item name is required").max(255),
  item_category: z.enum(["documents", "academic", "medical", "other"], {
    message: "Select a category",
  }),
});

type ScreeningItemFormValues = z.infer<typeof screeningItemSchema>;

interface ScreeningChecklistProps {
  applicationId: string;
  items: ScreeningItem[];
  totalItems: number;
  completedItems: number;
  progressPct: number;
  onRefresh: () => void;
}

export function ScreeningChecklist({
  applicationId,
  items,
  totalItems,
  completedItems,
  progressPct,
  onRefresh,
}: ScreeningChecklistProps) {
  const [showForm, setShowForm] = useState(false);
  const [completingId, setCompletingId] = useState<string | null>(null);

  const form = useForm<ScreeningItemFormValues>({
    resolver: zodResolver(screeningItemSchema),
    defaultValues: {
      item_name: "",
      item_category: "documents",
    },
  });

  async function onSubmit(values: ScreeningItemFormValues) {
    const result = await addScreeningItem(applicationId, {
      item_name: values.item_name,
      item_category: values.item_category as ScreeningCategory,
    });
    if (result.success) {
      toast.success("Screening item added");
      form.reset({ item_name: "", item_category: "documents" });
      setShowForm(false);
      onRefresh();
    } else {
      toast.error(result.error);
    }
  }

  async function handleComplete(itemId: string) {
    setCompletingId(itemId);
    const result = await completeScreeningItem(itemId);
    if (result.success) {
      toast.success("Item verified");
      onRefresh();
    } else {
      toast.error(result.error);
    }
    setCompletingId(null);
  }

  // Group items by category
  const grouped = items.reduce<Record<string, ScreeningItem[]>>((acc, item) => {
    const cat = item.item_category;
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(item);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            Screening Progress
          </span>
          <span className="font-medium">
            {completedItems} / {totalItems} ({Math.round(progressPct)}%)
          </span>
        </div>
        <Progress value={progressPct} className="h-2" />
      </div>

      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">
          Checklist Items
        </h3>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowForm(!showForm)}
        >
          <Plus className="mr-2 h-4 w-4" />
          Add Item
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">New Screening Item</CardTitle>
          </CardHeader>
          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <FormField
                    control={form.control}
                    name="item_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Item Name</FormLabel>
                        <FormControl>
                          <Input
                            placeholder="e.g., Birth certificate verified"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="item_category"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Category</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {CATEGORIES.map((c) => (
                              <SelectItem key={c.value} value={c.value}>
                                {c.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowForm(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" disabled={form.formState.isSubmitting}>
                    {form.formState.isSubmitting ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : null}
                    Add
                  </Button>
                </div>
              </form>
            </Form>
          </CardContent>
        </Card>
      )}

      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <ClipboardCheck className="h-10 w-10 text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">
            No screening items added yet.
          </p>
          <p className="text-xs text-muted-foreground">
            Add items to track document verification and requirements.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {Object.entries(grouped).map(([category, categoryItems]) => (
            <div key={category} className="space-y-2">
              <h4 className="text-sm font-medium capitalize flex items-center gap-2">
                <Badge
                  variant="outline"
                  className={
                    CATEGORY_COLORS[category as ScreeningCategory] || ""
                  }
                >
                  {category}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  ({categoryItems.filter((i) => i.is_completed).length}/
                  {categoryItems.length})
                </span>
              </h4>
              <div className="space-y-1">
                {categoryItems.map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center gap-3 py-2 px-3 rounded-md hover:bg-muted/50"
                  >
                    {item.is_completed ? (
                      <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
                    ) : (
                      <button
                        onClick={() => handleComplete(item.id)}
                        disabled={completingId === item.id}
                        className="shrink-0"
                      >
                        {completingId === item.id ? (
                          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                        ) : (
                          <Circle className="h-5 w-5 text-muted-foreground hover:text-primary transition-colors" />
                        )}
                      </button>
                    )}
                    <div className="flex-1 min-w-0">
                      <span
                        className={`text-sm ${
                          item.is_completed
                            ? "line-through text-muted-foreground"
                            : ""
                        }`}
                      >
                        {item.item_name}
                      </span>
                      {item.is_completed && item.completed_by_name && (
                        <p className="text-xs text-muted-foreground">
                          Verified by {item.completed_by_name}
                          {item.completed_at &&
                            ` on ${new Date(item.completed_at).toLocaleDateString("en-GB", {
                              day: "2-digit",
                              month: "short",
                            })}`}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
