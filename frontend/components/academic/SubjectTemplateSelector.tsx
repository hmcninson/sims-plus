"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { BookOpen, Loader2, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

import { initializeSubjectsFromTemplate } from "@/actions/academic.action";

interface SubjectTemplateSelectorProps {
  schoolType: string;
  onComplete?: (result: { created: number; skipped: number }) => void;
}

const SHS_PROGRAMMES = [
  "General Science",
  "General Arts",
  "Business",
  "Visual Arts",
  "Home Economics",
  "Agriculture",
  "Technical",
];

const isSHSType = (type: string) =>
  ["shs", "basic_shs", "international"].includes(type);

export function SubjectTemplateSelector({
  schoolType,
  onComplete,
}: SubjectTemplateSelectorProps) {
  const [selectedProgrammes, setSelectedProgrammes] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    created: number;
    skipped: number;
  } | null>(null);

  const handleToggleProgramme = (programme: string) => {
    setSelectedProgrammes((prev) =>
      prev.includes(programme)
        ? prev.filter((p) => p !== programme)
        : [...prev, programme]
    );
  };

  const handleInitialize = async () => {
    setLoading(true);
    try {
      const res = await initializeSubjectsFromTemplate(
        schoolType,
        isSHSType(schoolType) ? selectedProgrammes : undefined
      );
      if (res.success) {
        setResult(res.data);
        toast.success(
          `Created ${res.data.created} subjects${res.data.skipped > 0 ? ` (${res.data.skipped} already existed)` : ""}`
        );
        onComplete?.(res.data);
      } else {
        toast.error(res.error || "Failed to initialize subjects");
      }
    } finally {
      setLoading(false);
    }
  };

  if (result) {
    return (
      <Card>
        <CardContent className="pt-6 text-center">
          <CheckCircle2 className="mx-auto h-8 w-8 text-green-600 dark:text-green-400" />
          <p className="mt-2 font-medium">
            {result.created} subjects created
            {result.skipped > 0 && ` (${result.skipped} already existed)`}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <BookOpen className="h-5 w-5" />
          Load GES Standard Subjects
        </CardTitle>
        <CardDescription>
          Automatically create standard subjects based on the GES curriculum for
          your school type.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isSHSType(schoolType) && (
          <div className="mb-4">
            <p className="text-sm font-medium mb-2">
              Select SHS elective programmes:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {SHS_PROGRAMMES.map((programme) => (
                <label
                  key={programme}
                  className="flex items-center gap-2 rounded-md border p-3 cursor-pointer hover:bg-muted/50 transition-colors"
                >
                  <Checkbox
                    checked={selectedProgrammes.includes(programme)}
                    onCheckedChange={() => handleToggleProgramme(programme)}
                  />
                  <span className="text-sm">{programme}</span>
                </label>
              ))}
            </div>
          </div>
        )}

        <Button
          onClick={handleInitialize}
          disabled={loading}
          className="w-full"
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Creating subjects...
            </>
          ) : (
            "Initialize Subjects"
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
