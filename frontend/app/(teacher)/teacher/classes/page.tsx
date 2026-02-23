"use client";

/**
 * SIMS Plus - Teacher Classes List
 *
 * Shows all classes assigned to the current teacher. Each card
 * links to the class detail page. Class teacher assignments are highlighted.
 *
 * The backend TeacherClassSummary returns: class_id, class_name,
 * section_id, section_name, student_count, is_class_teacher.
 * Note: NO subject_id/subject_name/subject_code/periods_per_week.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, BookOpen, Loader2, Users, Star } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { getTeacherClasses } from "@/actions/teacher.action";
import type { TeacherClassSummary } from "@/types/teacher.type";

export default function TeacherClassesPage() {
  const [classes, setClasses] = useState<TeacherClassSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const result = await getTeacherClasses();
      if (result.success) {
        setClasses(result.data);
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">My Classes</h1>
        <p className="text-muted-foreground">
          {classes.length} class{classes.length !== 1 ? "es" : ""} assigned to you
        </p>
      </div>

      {classes.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BookOpen className="h-12 w-12 text-muted-foreground/50 mb-3" />
            <p className="text-muted-foreground">No classes assigned yet</p>
            <p className="text-xs text-muted-foreground mt-1">
              Contact your school administrator
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {classes.map((cls) => (
            <Link
              key={`${cls.class_id}-${cls.section_id || "main"}`}
              href={`/teacher/classes/${cls.class_id}${cls.section_id ? `?section_id=${cls.section_id}` : ""}`}
            >
              <Card className="hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer h-full">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <BookOpen className="h-5 w-5" />
                    </div>
                    {cls.is_class_teacher && (
                      <Badge variant="secondary" className="text-[10px] gap-1">
                        <Star className="h-3 w-3" />
                        Class Teacher
                      </Badge>
                    )}
                  </div>

                  <h3 className="font-semibold text-sm">
                    {cls.class_name}
                    {cls.section_name ? ` - ${cls.section_name}` : ""}
                  </h3>

                  <div className="flex items-center gap-3 mt-3 pt-3 border-t">
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Users className="h-3 w-3" />
                      {cls.student_count} student{cls.student_count !== 1 ? "s" : ""}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
