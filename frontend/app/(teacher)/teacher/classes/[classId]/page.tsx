"use client";

/**
 * SIMS Plus - Teacher Class Detail
 *
 * Shows detailed view of a class the teacher is assigned to, including:
 * - Class overview with subjects taught
 * - Student list (loaded from separate endpoint)
 *
 * The backend ClassOverview returns: class_id, class_name, section_id,
 * section_name, student_count, subjects[], is_class_teacher.
 * The student list is fetched from GET /teacher/classes/{classId}/students.
 */

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  Loader2,
  Users,
  Search,
  BookOpen,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getTeacherClassDetail, getTeacherClassStudents } from "@/actions/teacher.action";
import type { TeacherClassDetail, TeacherStudentSummary } from "@/types/teacher.type";
import { getInitials } from "@/lib/format";

export default function TeacherClassDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const classId = params.classId as string;
  const sectionId = searchParams.get("section_id") || undefined;

  const [data, setData] = useState<TeacherClassDetail | null>(null);
  const [students, setStudents] = useState<TeacherStudentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    async function load() {
      // Load class overview and students in parallel
      const [overviewResult, studentsResult] = await Promise.all([
        getTeacherClassDetail(classId, sectionId),
        getTeacherClassStudents(classId, sectionId),
      ]);

      if (overviewResult.success) {
        setData(overviewResult.data);
      } else {
        setError(overviewResult.error);
      }

      if (studentsResult.success) {
        setStudents(studentsResult.data.students);
      }

      setLoading(false);
    }
    load();
  }, [classId, sectionId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error || "Failed to load class"}</AlertDescription>
      </Alert>
    );
  }

  const filteredStudents = students.filter((s: TeacherStudentSummary) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      s.first_name.toLowerCase().includes(q) ||
      s.last_name.toLowerCase().includes(q) ||
      s.student_id.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="icon" asChild className="mt-1">
          <Link href="/teacher/classes">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {data.class_name}
            {data.section_name ? ` - ${data.section_name}` : ""}
          </h1>
          <p className="text-muted-foreground">
            {data.student_count} student{data.student_count !== 1 ? "s" : ""}
            {data.subjects.length > 0
              ? ` | ${data.subjects.length} subject${data.subjects.length !== 1 ? "s" : ""}`
              : ""}
          </p>
        </div>
        {data.is_class_teacher && (
          <Badge variant="secondary" className="ml-auto">Class Teacher</Badge>
        )}
      </div>

      {/* Quick Stats */}
      <div className="grid gap-4 grid-cols-2">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <Users className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-xl font-bold">{data.student_count}</p>
              <p className="text-xs text-muted-foreground">Students</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <BookOpen className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-xl font-bold">{data.subjects.length}</p>
              <p className="text-xs text-muted-foreground">Subjects</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Subjects taught in this class */}
      {data.subjects.length > 0 && (
        <Card>
          <CardContent className="p-4">
            <p className="text-sm font-medium mb-2">Subjects</p>
            <div className="flex flex-wrap gap-2">
              {data.subjects.map((subject) => (
                <Badge key={subject.subject_id} variant="outline" className="text-xs py-1 px-2">
                  {subject.subject_name}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Tabs defaultValue="students">
        <TabsList>
          <TabsTrigger value="students">Students</TabsTrigger>
        </TabsList>

        <TabsContent value="students" className="mt-4">
          {/* Search */}
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search students..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>

          {/* Student List */}
          <div className="space-y-2">
            {filteredStudents.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                {search ? "No students match your search" : "No students in this class"}
              </p>
            ) : (
              filteredStudents.map((student: TeacherStudentSummary) => (
                <Link
                  key={student.id}
                  href={`/teacher/classes/${classId}/students/${student.id}`}
                >
                  <Card className="hover:border-primary/30 transition-colors cursor-pointer">
                    <CardContent className="p-3 flex items-center gap-3">
                      <Avatar className="h-9 w-9">
                        <AvatarFallback className="bg-primary/10 text-primary text-xs">
                          {getInitials(`${student.first_name} ${student.last_name}`)}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">
                          {student.first_name} {student.last_name}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {student.student_id}
                        </p>
                      </div>
                      <Badge
                        variant={student.status === "active" ? "default" : "secondary"}
                        className="text-[10px] shrink-0"
                      >
                        {student.status}
                      </Badge>
                    </CardContent>
                  </Card>
                </Link>
              ))
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
