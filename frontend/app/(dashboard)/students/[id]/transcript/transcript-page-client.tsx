"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Printer, Download, Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { TranscriptViewer } from "@/components/curriculum/TranscriptViewer";
import { getStudentTranscript } from "@/actions/curriculum.action";
import type { TranscriptData, CurriculumProfile } from "@/types/curriculum.type";

interface TranscriptPageClientProps {
  studentId: string;
  studentName: string;
  creditProfiles: CurriculumProfile[];
}

export function TranscriptPageClient({
  studentId,
  studentName,
  creditProfiles,
}: TranscriptPageClientProps) {
  const [selectedProfileId, setSelectedProfileId] = useState(
    creditProfiles.length > 0 ? creditProfiles[0].id : "",
  );
  const [transcript, setTranscript] = useState<TranscriptData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!selectedProfileId) return;
    async function load() {
      setIsLoading(true);
      try {
        const result = await getStudentTranscript(studentId, selectedProfileId);
        if (result.success) {
          setTranscript(result.data);
        } else {
          toast.error(result.error);
        }
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, [studentId, selectedProfileId]);

  if (creditProfiles.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-12 text-center">
          <Info className="mb-3 size-10 text-blue-500" />
          <CardTitle className="mb-2 text-lg">Transcripts Not Available</CardTitle>
          <CardDescription className="max-w-md">
            Transcripts are available for credit-based curricula (American, IB). Your school
            does not currently have an applicable curriculum profile configured.
          </CardDescription>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between print-hidden">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Transcript &mdash; {studentName}
          </h1>
          <p className="text-sm text-muted-foreground">
            Official academic transcript with credits and GPA
          </p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          {creditProfiles.length > 1 && (
            <Select value={selectedProfileId} onValueChange={setSelectedProfileId}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue placeholder="Select profile" />
              </SelectTrigger>
              <SelectContent>
                {creditProfiles.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Button variant="outline" size="sm" onClick={() => window.print()}>
            <Printer className="mr-2 size-4" />
            Print
          </Button>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
        </div>
      ) : transcript ? (
        <TranscriptViewer data={transcript} />
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <Info className="mb-3 size-10 text-muted-foreground" />
            <CardTitle className="mb-2 text-lg">No Transcript Data</CardTitle>
            <CardDescription>
              No credit records found for this student. Credits will appear once grades are
              recorded for credit-bearing subjects.
            </CardDescription>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
