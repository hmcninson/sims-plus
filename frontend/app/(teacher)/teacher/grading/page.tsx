"use client";

/**
 * SIMS Plus - Teacher Grading List
 *
 * Shows all exam subjects where the teacher has pending score entry.
 * Each card shows the progress (scores_entered / total_students).
 * Links to the score entry page.
 *
 * Backend: GET /teacher/grading/pending -> list[PendingScoreEntry]
 * Fields: exam_id, exam_name, exam_subject_id, subject_id, subject_name,
 *   class_id, class_name, section_id, section_name, max_score,
 *   total_students, scores_entered, status
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  Loader2,
  PenLine,
  CheckCircle2,
  Clock,
  ArrowRight,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { getTeacherGradingSubjects } from "@/actions/teacher.action";
import type { TeacherPendingScoreEntry } from "@/types/teacher.type";

function getStatusInfo(entry: TeacherPendingScoreEntry): {
  label: string;
  color: string;
  icon: React.ReactNode;
} {
  if (entry.scores_entered >= entry.total_students && entry.total_students > 0) {
    return {
      label: "Complete",
      color: "text-green-700 bg-green-50 border-green-200",
      icon: <CheckCircle2 className="h-3 w-3" />,
    };
  }
  if (entry.scores_entered > 0) {
    return {
      label: "In Progress",
      color: "text-blue-700 bg-blue-50 border-blue-200",
      icon: <PenLine className="h-3 w-3" />,
    };
  }
  return {
    label: "Pending",
    color: "text-amber-700 bg-amber-50 border-amber-200",
    icon: <Clock className="h-3 w-3" />,
  };
}

export default function TeacherGradingPage() {
  const [entries, setEntries] = useState<TeacherPendingScoreEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const result = await getTeacherGradingSubjects();
      if (result.success) {
        setEntries(result.data);
      } else {
        setError(result.error);
      }
      setLoading(false);
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  const pendingCount = entries.filter(
    (e) => e.scores_entered < e.total_students
  ).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Grading</h1>
        <p className="text-muted-foreground">
          {entries.length} exam subject{entries.length !== 1 ? "s" : ""}
          {pendingCount > 0 ? ` | ${pendingCount} pending score entry` : ""}
        </p>
      </div>

      {entries.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <PenLine className="h-12 w-12 text-muted-foreground/50 mb-3" />
            <p className="text-muted-foreground">No pending score entries</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {entries.map((entry) => {
            const status = getStatusInfo(entry);
            return (
              <Link
                key={entry.exam_subject_id}
                href={`/teacher/grading/${entry.class_id}/${entry.subject_id}?exam_subject_id=${entry.exam_subject_id}`}
              >
                <Card className="hover:border-primary/30 hover:shadow-sm transition-all cursor-pointer">
                  <CardContent className="p-4 flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary shrink-0">
                      <PenLine className="h-5 w-5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-semibold text-sm">{entry.subject_name}</h3>
                        <Badge variant="outline" className="text-[10px]">
                          {entry.exam_name}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {entry.class_name}
                        {entry.section_name ? ` - ${entry.section_name}` : ""}
                        {" | "}
                        Max: {entry.max_score}
                      </p>
                      <div className="flex items-center gap-3 mt-1.5">
                        <Badge className={`text-[10px] gap-1 ${status.color}`}>
                          {status.icon}
                          {status.label}
                        </Badge>
                        <span className="text-[10px] text-muted-foreground">
                          {entry.scores_entered}/{entry.total_students} entered
                        </span>
                      </div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0" />
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
