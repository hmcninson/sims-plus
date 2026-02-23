"use client";

/**
 * SIMS Plus - Teacher Student Detail
 *
 * Detailed view of a student within the teacher's class. Shows:
 * - Student profile (name, photo, class)
 * - Guardian contacts
 * - Attendance summary
 * - Subject scores
 * - Recent notes from teachers
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  AlertCircle,
  ArrowLeft,
  Loader2,
  Phone,
  Mail,
  Users,
  ClipboardCheck,
  BookOpen,
  StickyNote,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { getTeacherStudentDetail } from "@/actions/teacher.action";
import type { TeacherStudentDetail, TeacherNoteType } from "@/types/teacher.type";
import { getInitials } from "@/lib/format";
import { NOTE_TYPE_COLORS } from "@/lib/teacher-constants";

export default function TeacherStudentDetailPage() {
  const params = useParams();
  const classId = params.classId as string;
  const studentId = params.studentId as string;

  const [student, setStudent] = useState<TeacherStudentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const result = await getTeacherStudentDetail(classId, studentId);
      if (result.success) {
        setStudent(result.data);
      } else {
        setError(result.error);
      }
      setLoading(false);
    }
    load();
  }, [classId, studentId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !student) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error || "Student not found"}</AlertDescription>
      </Alert>
    );
  }

  const att = student.attendance_summary;

  return (
    <div className="space-y-6">
      {/* Back button + Header */}
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="icon" asChild className="mt-1">
          <Link href={`/teacher/classes/${classId}`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div className="flex items-center gap-4 flex-1">
          <Avatar className="h-14 w-14">
            <AvatarFallback className="bg-primary/10 text-primary text-lg">
              {getInitials(`${student.first_name} ${student.last_name}`)}
            </AvatarFallback>
          </Avatar>
          <div>
            <h1 className="text-xl font-bold">
              {student.first_name} {student.middle_name ? `${student.middle_name} ` : ""}{student.last_name}
            </h1>
            <p className="text-sm text-muted-foreground">
              {student.student_id} | {student.class_name}
              {student.section_name ? ` - ${student.section_name}` : ""}
            </p>
            <div className="flex gap-2 mt-1">
              <Badge variant={student.status === "active" ? "default" : "secondary"}>
                {student.status}
              </Badge>
              <Badge variant="outline">{student.gender}</Badge>
            </div>
          </div>
        </div>
      </div>

      <Tabs defaultValue="overview">
        <TabsList className="w-full sm:w-auto">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="guardians">Guardians</TabsTrigger>
          <TabsTrigger value="scores">Scores</TabsTrigger>
          <TabsTrigger value="notes">Notes</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="mt-4 space-y-4">
          {/* Attendance Card */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <ClipboardCheck className="h-4 w-4 text-muted-foreground" />
                <CardTitle className="text-sm">Attendance</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-4 mb-3">
                <div className="text-3xl font-bold">{Math.round(att.rate)}%</div>
                <Progress value={att.rate} className="flex-1" />
              </div>
              <div className="grid grid-cols-5 gap-2 text-center text-xs">
                <div>
                  <p className="font-medium">{att.total_days}</p>
                  <p className="text-muted-foreground">Total</p>
                </div>
                <div>
                  <p className="font-medium text-green-600">{att.present}</p>
                  <p className="text-muted-foreground">Present</p>
                </div>
                <div>
                  <p className="font-medium text-red-600">{att.absent}</p>
                  <p className="text-muted-foreground">Absent</p>
                </div>
                <div>
                  <p className="font-medium text-amber-600">{att.late}</p>
                  <p className="text-muted-foreground">Late</p>
                </div>
                <div>
                  <p className="font-medium text-blue-600">{att.excused}</p>
                  <p className="text-muted-foreground">Excused</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Student Info */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Date of Birth</span>
                <span>{new Date(student.date_of_birth).toLocaleDateString("en-GB")}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Gender</span>
                <span className="capitalize">{student.gender}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Class</span>
                <span>
                  {student.class_name}
                  {student.section_name ? ` - ${student.section_name}` : ""}
                </span>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Guardians Tab */}
        <TabsContent value="guardians" className="mt-4">
          {student.guardians.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <Users className="h-8 w-8 text-muted-foreground/50 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">No guardian information available</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {student.guardians.map((g, idx) => (
                <Card key={idx}>
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-medium">{g.name}</p>
                        <p className="text-xs text-muted-foreground capitalize">
                          {g.relationship}
                        </p>
                      </div>
                      {g.is_primary && (
                        <Badge variant="secondary" className="text-[10px]">Primary</Badge>
                      )}
                    </div>
                    <div className="flex flex-col gap-1.5 mt-3">
                      <a
                        href={`tel:${g.phone}`}
                        className="flex items-center gap-2 text-sm text-primary hover:underline"
                      >
                        <Phone className="h-3.5 w-3.5" />
                        {g.phone}
                      </a>
                      {g.email && (
                        <a
                          href={`mailto:${g.email}`}
                          className="flex items-center gap-2 text-sm text-primary hover:underline"
                        >
                          <Mail className="h-3.5 w-3.5" />
                          {g.email}
                        </a>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Scores Tab */}
        <TabsContent value="scores" className="mt-4">
          {student.subject_scores.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <BookOpen className="h-8 w-8 text-muted-foreground/50 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">No scores recorded yet</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {student.subject_scores.map((score) => (
                <Card key={score.subject_id}>
                  <CardContent className="p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-sm">{score.subject_name}</p>
                        <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
                          <span>CA: {score.ca_score ?? "--"}/{score.ca_max}</span>
                          <span>Exam: {score.exam_score ?? "--"}/{score.exam_max}</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-lg font-bold">
                          {score.total !== null ? score.total : "--"}
                        </p>
                        {score.grade && (
                          <Badge variant="outline" className="text-[10px]">{score.grade}</Badge>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Notes Tab */}
        <TabsContent value="notes" className="mt-4">
          <div className="flex justify-end mb-3">
            <Button size="sm" asChild>
              <Link href={`/teacher/notes?student_id=${student.id}`}>
                <StickyNote className="h-3.5 w-3.5 mr-1" />
                Add Note
              </Link>
            </Button>
          </div>
          {student.recent_notes.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <StickyNote className="h-8 w-8 text-muted-foreground/50 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">No notes yet</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {student.recent_notes.map((note) => (
                <Card key={note.id}>
                  <CardContent className="p-3">
                    <div className="flex items-start gap-2">
                      <Badge
                        className={`text-[10px] shrink-0 ${NOTE_TYPE_COLORS[note.note_type as TeacherNoteType] || "bg-gray-100 text-gray-800"}`}
                      >
                        {note.note_type.replace("_", " ")}
                      </Badge>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm">{note.content}</p>
                        <p className="text-[10px] text-muted-foreground mt-1">
                          {new Date(note.created_at).toLocaleDateString("en-GB")}
                          {note.subject_name ? ` | ${note.subject_name}` : ""}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
