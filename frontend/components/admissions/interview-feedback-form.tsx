"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Loader2, Plus, Trash2 } from "lucide-react";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { recordInterviewFeedback } from "@/actions/interviews.action";
import type { Interview } from "@/types/interview.type";

const feedbackSchema = z.object({
  status: z.enum(["completed", "no_show"], { message: "Select an outcome" }),
  feedback: z.string().max(5000).optional(),
});

type FeedbackFormValues = z.infer<typeof feedbackSchema>;

interface CriterionEntry {
  name: string;
  score: number;
  max: number;
}

interface InterviewFeedbackFormProps {
  interview: Interview;
  onSuccess: () => void;
}

export function InterviewFeedbackForm({
  interview,
  onSuccess,
}: InterviewFeedbackFormProps) {
  const [criteria, setCriteria] = useState<CriterionEntry[]>(() => {
    // Initialize from existing scoring_criteria if present
    if (interview.scoring_criteria && Object.keys(interview.scoring_criteria).length > 0) {
      return Object.entries(interview.scoring_criteria).map(([name, vals]) => ({
        name,
        score: vals.score,
        max: vals.max,
      }));
    }
    return [];
  });
  const [newCriterionName, setNewCriterionName] = useState("");

  const form = useForm<FeedbackFormValues>({
    resolver: zodResolver(feedbackSchema),
    defaultValues: {
      status: "completed",
      feedback: interview.feedback || "",
    },
  });

  function addCriterion() {
    if (!newCriterionName.trim()) return;
    if (criteria.some((c) => c.name.toLowerCase() === newCriterionName.trim().toLowerCase())) {
      toast.error("Criterion already exists");
      return;
    }
    setCriteria((prev) => [
      ...prev,
      { name: newCriterionName.trim(), score: 0, max: 10 },
    ]);
    setNewCriterionName("");
  }

  function removeCriterion(index: number) {
    setCriteria((prev) => prev.filter((_, i) => i !== index));
  }

  function updateCriterion(index: number, field: "score" | "max", value: number) {
    setCriteria((prev) =>
      prev.map((c, i) => (i === index ? { ...c, [field]: value } : c))
    );
  }

  const totalScore = criteria.reduce((sum, c) => sum + c.score, 0);
  const maxScore = criteria.reduce((sum, c) => sum + c.max, 0);

  async function onSubmit(values: FeedbackFormValues) {
    const scoringCriteria: Record<string, { score: number; max: number }> = {};
    criteria.forEach((c) => {
      scoringCriteria[c.name] = { score: c.score, max: c.max };
    });

    const result = await recordInterviewFeedback(interview.id, {
      status: values.status,
      feedback: values.feedback || undefined,
      score: criteria.length > 0 ? totalScore : undefined,
      max_score: criteria.length > 0 ? maxScore : undefined,
      scoring_criteria: criteria.length > 0 ? scoringCriteria : undefined,
    });

    if (result.success) {
      toast.success("Interview feedback recorded");
      onSuccess();
    } else {
      toast.error(result.error);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Record Feedback</CardTitle>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="status"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Outcome</FormLabel>
                  <Select onValueChange={field.onChange} value={field.value}>
                    <FormControl>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="completed">Completed</SelectItem>
                      <SelectItem value="no_show">No Show</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Scoring Criteria */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <FormLabel>Scoring Criteria</FormLabel>
                {criteria.length > 0 && (
                  <span className="text-sm font-medium">
                    Total: {totalScore} / {maxScore}
                  </span>
                )}
              </div>

              {criteria.map((c, index) => (
                <div
                  key={index}
                  className="grid grid-cols-[1fr_80px_80px_32px] items-center gap-2"
                >
                  <span className="text-sm capitalize truncate">
                    {c.name.replace(/_/g, " ")}
                  </span>
                  <Input
                    type="number"
                    min={0}
                    max={c.max}
                    value={c.score}
                    onChange={(e) =>
                      updateCriterion(index, "score", Number(e.target.value))
                    }
                    className="text-center"
                  />
                  <Input
                    type="number"
                    min={1}
                    value={c.max}
                    onChange={(e) =>
                      updateCriterion(index, "max", Number(e.target.value))
                    }
                    className="text-center"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => removeCriterion(index)}
                  >
                    <Trash2 className="h-4 w-4 text-muted-foreground" />
                  </Button>
                </div>
              ))}

              {criteria.length > 0 && (
                <div className="grid grid-cols-[1fr_80px_80px_32px] items-center gap-2 text-xs text-muted-foreground">
                  <span />
                  <span className="text-center">Score</span>
                  <span className="text-center">Max</span>
                  <span />
                </div>
              )}

              <div className="flex items-center gap-2">
                <Input
                  placeholder="Add criterion (e.g., Communication)"
                  value={newCriterionName}
                  onChange={(e) => setNewCriterionName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addCriterion();
                    }
                  }}
                  className="flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addCriterion}
                  disabled={!newCriterionName.trim()}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
            </div>

            <FormField
              control={form.control}
              name="feedback"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Written Feedback (Optional)</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Overall impressions and notes..."
                      rows={4}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <Button type="submit" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Submit Feedback"
              )}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
