"use client";

/**
 * SIMS Plus - Teacher Reports Page
 *
 * For class teachers: view and add comments to student report cards.
 * Uses the backend report comment endpoints:
 *   GET /teacher/reports/comments -> ReportCommentListResponse { comments, total }
 *   POST /teacher/reports/comments/students/{studentId} -> ReportCommentResponse
 *   POST /teacher/reports/comments/students/{studentId}/sign -> ReportCommentResponse
 *
 * Comments are displayed per-student with inline editing. The class teacher
 * can write comments and sign them. Head teachers use the head-teacher section.
 */

import { useEffect, useState, useTransition } from "react";
import {
  AlertCircle,
  FileText,
  Loader2,
  Save,
  Check,
  MessageSquare,
  PenLine,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  getTeacherClasses,
  getTeacherReportComments,
  writeClassTeacherComment,
  signClassTeacherComment,
} from "@/actions/teacher.action";
import type { TeacherClassSummary, TeacherReportComment } from "@/types/teacher.type";
import { toast } from "sonner";

export default function TeacherReportsPage() {
  const [classes, setClasses] = useState<TeacherClassSummary[]>([]);
  const [comments, setComments] = useState<TeacherReportComment[]>([]);
  const [drafts, setDrafts] = useState<Map<string, string>>(new Map());
  const [loading, setLoading] = useState(true);
  const [loadingComments, setLoadingComments] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const [savingId, setSavingId] = useState<string | null>(null);

  // Find the class where this teacher is the class teacher
  const classTeacherClass = classes.find((c) => c.is_class_teacher);

  // Load classes on mount
  useEffect(() => {
    async function load() {
      const result = await getTeacherClasses();
      if (result.success) {
        setClasses(result.data);
        // Auto-load comments for class teacher's class section
        const ctClass = result.data.find((c) => c.is_class_teacher);
        if (ctClass?.section_id) {
          loadComments(ctClass.section_id);
        } else if (ctClass) {
          loadComments();
        }
      } else {
        setError(result.error);
      }
      setLoading(false);
    }
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadComments(sectionId?: string) {
    setLoadingComments(true);
    // Fetch comments for the current term (backend defaults to current term)
    const result = await getTeacherReportComments(undefined, sectionId);
    if (result.success) {
      setComments(result.data.comments);
      // Initialize drafts from existing comments
      const initial = new Map<string, string>();
      result.data.comments.forEach((c: TeacherReportComment) => {
        initial.set(c.student_id, c.class_teacher_comment || "");
      });
      setDrafts(initial);
    } else {
      setError(result.error);
    }
    setLoadingComments(false);
  }

  const handleUpdateDraft = (studentId: string, value: string) => {
    setDrafts((prev) => {
      const next = new Map(prev);
      next.set(studentId, value);
      return next;
    });
  };

  // Save a single student's class teacher comment
  const handleSaveComment = (studentId: string) => {
    const draft = drafts.get(studentId) || "";
    const existing = comments.find((c) => c.student_id === studentId);
    if (existing && draft === (existing.class_teacher_comment || "")) {
      toast.info("No changes to save");
      return;
    }

    setSavingId(studentId);
    startTransition(async () => {
      const result = await writeClassTeacherComment(studentId, draft);
      if (result.success) {
        // Update the comment in the list
        setComments((prev) =>
          prev.map((c) => (c.student_id === studentId ? result.data : c))
        );
        toast.success("Comment saved");
      } else {
        toast.error(result.error);
      }
      setSavingId(null);
    });
  };

  // Sign a class teacher comment
  const handleSignComment = (studentId: string) => {
    setSavingId(studentId);
    startTransition(async () => {
      const result = await signClassTeacherComment(studentId);
      if (result.success) {
        setComments((prev) =>
          prev.map((c) => (c.student_id === studentId ? result.data : c))
        );
        toast.success("Comment signed");
      } else {
        toast.error(result.error);
      }
      setSavingId(null);
    });
  };

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

  if (!classTeacherClass) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Reports</h1>
          <p className="text-muted-foreground">
            Manage report card comments for your class
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileText className="h-12 w-12 text-muted-foreground/50 mb-3" />
            <p className="text-muted-foreground">Not a class teacher</p>
            <p className="text-xs text-muted-foreground mt-1">
              Report card comments are only available for class teachers
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Reports</h1>
          <p className="text-muted-foreground">
            {classTeacherClass.class_name}
            {classTeacherClass.section_name ? ` - ${classTeacherClass.section_name}` : ""}
            {" | "}
            {comments.length} student{comments.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {loadingComments ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : comments.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileText className="h-12 w-12 text-muted-foreground/50 mb-3" />
            <p className="text-muted-foreground">No report comments found</p>
            <p className="text-xs text-muted-foreground mt-1">
              Report comments will appear here once report cards are generated by admin
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {comments.map((comment) => {
            const draft = drafts.get(comment.student_id) || "";
            const hasChanges = draft !== (comment.class_teacher_comment || "");
            const isSaving = savingId === comment.student_id;

            return (
              <Card key={comment.id}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <p className="font-medium">{comment.student_name || "Unknown Student"}</p>
                      <p className="text-xs text-muted-foreground">
                        Student ID: {comment.student_id.slice(0, 8)}...
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {comment.class_teacher_signed && (
                        <Badge variant="outline" className="text-[10px] text-green-600 border-green-300">
                          <Check className="h-3 w-3 mr-0.5" />
                          Signed
                        </Badge>
                      )}
                      {comment.head_teacher_signed && (
                        <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-300">
                          HT Signed
                        </Badge>
                      )}
                    </div>
                  </div>

                  {/* Head teacher comment (read-only for class teacher) */}
                  {comment.head_teacher_comment && (
                    <div className="mb-3 p-2 bg-muted/50 rounded text-sm">
                      <p className="text-[10px] font-medium text-muted-foreground mb-1">
                        Head Teacher Comment
                      </p>
                      <p className="text-sm">{comment.head_teacher_comment}</p>
                    </div>
                  )}

                  <div className="space-y-1.5">
                    <div className="flex items-center gap-1.5">
                      <MessageSquare className="h-3.5 w-3.5 text-muted-foreground" />
                      <label className="text-xs font-medium text-muted-foreground">
                        Class Teacher Comment
                      </label>
                    </div>
                    <Textarea
                      value={draft}
                      onChange={(e) => handleUpdateDraft(comment.student_id, e.target.value)}
                      placeholder="Enter your comment for this student..."
                      rows={2}
                      className="text-sm"
                      disabled={comment.class_teacher_signed}
                    />
                  </div>

                  <div className="flex items-center gap-2 mt-3">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleSaveComment(comment.student_id)}
                      disabled={isSaving || !hasChanges || comment.class_teacher_signed}
                    >
                      {isSaving ? (
                        <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                      ) : (
                        <Save className="h-3.5 w-3.5 mr-1" />
                      )}
                      Save
                    </Button>
                    {!comment.class_teacher_signed && comment.class_teacher_comment && (
                      <Button
                        size="sm"
                        onClick={() => handleSignComment(comment.student_id)}
                        disabled={isSaving || hasChanges}
                      >
                        <PenLine className="h-3.5 w-3.5 mr-1" />
                        Sign
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
