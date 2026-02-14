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

  // Form state - only report card weights
  const [formData, setFormData] = useState({
    ca_total_weight: 50,
    exam_total_weight: 50,
  });

  useEffect(() => {
    if (!initialData) {
      loadWeights();
    } else {
      setFormData({
        ca_total_weight: Number(initialData.ca_total_weight ?? 50),
        exam_total_weight: Number(initialData.exam_total_weight ?? 50),
      });
    }
  }, [initialData]);

  const loadWeights = async () => {
    setLoading(true);
    const result = await getAssessmentWeights();
    if (result.success && result.data) {
      setWeights(result.data);
      setFormData({
        ca_total_weight: Number(result.data.ca_total_weight ?? 50),
        exam_total_weight: Number(result.data.exam_total_weight ?? 50),
      });
    }
    setLoading(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    // Validate report card weights
    const reportCardTotal = formData.ca_total_weight + formData.exam_total_weight;
    if (reportCardTotal !== 100) {
      setError(`Report card weights (CA + Exams) must sum to 100%. Current total: ${reportCardTotal}%`);
      return;
    }

    setSaving(true);

    try {
      const data: AssessmentWeightCreate = {
        // Keep defaults for individual weights (not used but required by backend)
        class_work_weight: 20,
        homework_weight: 10,
        midterm_weight: 20,
        end_term_weight: 50,
        // Actual weights used for report cards
        ca_total_weight: formData.ca_total_weight,
        exam_total_weight: formData.exam_total_weight,
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

  const reportCardTotal = formData.ca_total_weight + formData.exam_total_weight;

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
        <CardTitle>Report Card Weights</CardTitle>
        <CardDescription>
          Configure how Class Score (CA) and Exams Score are weighted on report cards.
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
                Report card weights saved successfully!
              </div>
            )}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="ca_total_weight">Class Score / CA (%)</Label>
                <Input
                  id="ca_total_weight"
                  type="number"
                  min="0"
                  max="100"
                  value={formData.ca_total_weight}
                  onChange={(e) =>
                    handleInputChange("ca_total_weight", e.target.value)
                  }
                />
                <p className="text-xs text-muted-foreground">
                  All continuous assessments (classwork, homework, quizzes, midterm, etc.)
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="exam_total_weight">Exams Score (%)</Label>
                <Input
                  id="exam_total_weight"
                  type="number"
                  min="0"
                  max="100"
                  value={formData.exam_total_weight}
                  onChange={(e) =>
                    handleInputChange("exam_total_weight", e.target.value)
                  }
                />
                <p className="text-xs text-muted-foreground">
                  End of term examination only
                </p>
              </div>
            </div>
            <p
              className={`text-sm ${
                reportCardTotal === 100 ? "text-muted-foreground" : "text-destructive"
              }`}
            >
              Weights must equal 100%. Current total:{" "}
              <span className="font-medium">{reportCardTotal}%</span>
            </p>
            <div className="flex justify-end pt-4">
              <Button type="submit" disabled={saving || reportCardTotal !== 100}>
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
