"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  Loader2,
  Save,
  CheckCircle,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AssessmentStructureEditor } from "@/components/curriculum/AssessmentStructureEditor";
import {
  createAssessmentStructure,
  validateAssessmentStructure,
} from "@/actions/curriculum.action";
import type {
  CurriculumProfileDetail,
  AssessmentComponentCreate,
} from "@/types/curriculum.type";

interface AssessmentEditorPageProps {
  profile: CurriculumProfileDetail;
}

export function AssessmentEditorPage({ profile }: AssessmentEditorPageProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [validationResult, setValidationResult] = useState<{
    is_valid: boolean;
    message: string;
  } | null>(null);

  const [components, setComponents] = useState<AssessmentComponentCreate[]>(
    profile.assessment_structure?.components.map((c) => ({
      component_type: c.component_type,
      name: c.name,
      weight: c.weight,
      max_score: c.max_score,
      is_external: c.is_external,
      sequence: c.sequence,
      maps_to_ca: c.maps_to_ca,
      maps_to_exam: c.maps_to_exam,
    })) || [],
  );

  const handleSave = () => {
    // Coerce to number — API returns Decimal-serialized strings (e.g. "20.00")
    const totalWeight = components.reduce(
      (sum, c) => sum + (Number(c.weight) || 0),
      0,
    );
    if (components.length > 0 && Math.abs(totalWeight - 100) > 0.01) {
      toast.error("Assessment weights must total 100%");
      return;
    }

    const hasNames = components.every((c) => c.name.trim() !== "");
    if (!hasNames) {
      toast.error("All components must have a name");
      return;
    }

    startTransition(async () => {
      const result = await createAssessmentStructure(profile.id, {
        name: `${profile.name} Assessment`,
        description: `Assessment structure for ${profile.name}`,
        components,
      });

      if (result.success) {
        toast.success("Assessment structure saved");
        setValidationResult(null);
        router.refresh();
      } else {
        toast.error("Failed to save", { description: result.error });
      }
    });
  };

  const handleValidate = () => {
    if (!profile.assessment_structure?.id) {
      // Local validation only
      // Coerce to number — API returns Decimal-serialized strings
      const totalWeight = components.reduce(
        (sum, c) => sum + (Number(c.weight) || 0),
        0,
      );
      const isValid = Math.abs(totalWeight - 100) < 0.01;
      setValidationResult({
        is_valid: isValid,
        message: isValid
          ? "Weights total 100%. Structure is valid."
          : `Weights total ${totalWeight}%. Must equal 100%.`,
      });
      return;
    }

    startTransition(async () => {
      const result = await validateAssessmentStructure(
        profile.assessment_structure!.id,
      );
      if (result.success) {
        setValidationResult(result.data);
        if (result.data.is_valid) {
          toast.success("Structure is valid");
        } else {
          toast.error(result.data.message);
        }
      } else {
        toast.error("Validation failed", { description: result.error });
      }
    });
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <CardTitle className="text-base">{profile.name}</CardTitle>
            <CardDescription>
              Define the assessment components and weights for this curriculum
              profile.
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleValidate}
              disabled={isPending}
            >
              {isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle className="mr-2 h-4 w-4" />
              )}
              Validate
            </Button>
            <Button size="sm" onClick={handleSave} disabled={isPending}>
              {isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              <Save className="mr-2 h-4 w-4" />
              Save
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {validationResult && (
          <div
            className={`flex items-center gap-2 rounded-lg border px-4 py-2 text-sm ${
              validationResult.is_valid
                ? "border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"
                : "border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
            }`}
          >
            {validationResult.is_valid ? (
              <CheckCircle className="h-4 w-4" />
            ) : (
              <AlertCircle className="h-4 w-4" />
            )}
            <span>{validationResult.message}</span>
          </div>
        )}

        <AssessmentStructureEditor
          initialComponents={components}
          onChange={setComponents}
        />
      </CardContent>
    </Card>
  );
}
