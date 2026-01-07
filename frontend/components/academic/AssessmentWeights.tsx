"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import { getAssessmentWeights, setAssessmentWeights } from "@/actions/academic.action";
import type { AssessmentWeight, AssessmentWeightCreate } from "@/types";

interface AssessmentWeightsProps {
  initialData?: AssessmentWeight;
}

export function AssessmentWeights({ initialData }: AssessmentWeightsProps) {
  const [weights, setWeights] = useState<AssessmentWeight | null>(initialData || null);
  const [loading, setLoading] = useState(!initialData);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    class_work_weight: 20,
    homework_weight: 10,
    midterm_weight: 20,
    end_term_weight: 50,
  });

  useEffect(() => {
    if (!initialData) {
      loadWeights();
    } else {
      setFormData({
        class_work_weight: Number(initialData.class_work_weight),
        homework_weight: Number(initialData.homework_weight),
        midterm_weight: Number(initialData.midterm_weight),
        end_term_weight: Number(initialData.end_term_weight),
      });
    }
  }, [initialData]);

  const loadWeights = async () => {
    setLoading(true);
    const result = await getAssessmentWeights();
    if (result.success && result.data) {
      setWeights(result.data);
      setFormData({
        class_work_weight: Number(result.data.class_work_weight),
        homework_weight: Number(result.data.homework_weight),
        midterm_weight: Number(result.data.midterm_weight),
        end_term_weight: Number(result.data.end_term_weight),
      });
    }
    setLoading(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    const total =
      formData.class_work_weight +
      formData.homework_weight +
      formData.midterm_weight +
      formData.end_term_weight;

    if (total !== 100) {
      setError(`Weights must sum to 100%. Current total: ${total}%`);
      return;
    }

    setSaving(true);

    try {
      const data: AssessmentWeightCreate = {
        class_work_weight: formData.class_work_weight,
        homework_weight: formData.homework_weight,
        midterm_weight: formData.midterm_weight,
        end_term_weight: formData.end_term_weight,
      };

      const result = await setAssessmentWeights(data);
      if (result.success && result.data) {
        setWeights(result.data);
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
      } else {
        setError(result.error || "Failed to save assessment weights");
      }
    } finally {
      setSaving(false);
    }
  };

  const handleInputChange = (field: keyof typeof formData, value: string) => {
    const numValue = parseInt(value) || 0;
    setFormData((prev) => ({ ...prev, [field]: numValue }));
    setError(null);
    setSuccess(false);
  };

  const total =
    formData.class_work_weight +
    formData.homework_weight +
    formData.midterm_weight +
    formData.end_term_weight;

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Assessment Weights</CardTitle>
        <CardDescription>
          Configure how different assessments contribute to final grades.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            {error && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}
            {success && (
              <div className="rounded-md bg-green-50 p-3 text-sm text-green-700 dark:bg-green-900/20 dark:text-green-400">
                Assessment weights saved successfully!
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="class_work_weight">Class Work (%)</Label>
                <Input
                  id="class_work_weight"
                  type="number"
                  min="0"
                  max="100"
                  value={formData.class_work_weight}
                  onChange={(e) =>
                    handleInputChange("class_work_weight", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="homework_weight">Homework (%)</Label>
                <Input
                  id="homework_weight"
                  type="number"
                  min="0"
                  max="100"
                  value={formData.homework_weight}
                  onChange={(e) =>
                    handleInputChange("homework_weight", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="midterm_weight">Mid-Term Exam (%)</Label>
                <Input
                  id="midterm_weight"
                  type="number"
                  min="0"
                  max="100"
                  value={formData.midterm_weight}
                  onChange={(e) =>
                    handleInputChange("midterm_weight", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="end_term_weight">End of Term Exam (%)</Label>
                <Input
                  id="end_term_weight"
                  type="number"
                  min="0"
                  max="100"
                  value={formData.end_term_weight}
                  onChange={(e) =>
                    handleInputChange("end_term_weight", e.target.value)
                  }
                />
              </div>
            </div>
            <p
              className={`text-sm ${
                total === 100 ? "text-muted-foreground" : "text-destructive"
              }`}
            >
              Total must equal 100%. Current total:{" "}
              <span className="font-medium">{total}%</span>
            </p>
            <div className="flex justify-end">
              <Button type="submit" disabled={saving || total !== 100}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Save Weights
              </Button>
            </div>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
