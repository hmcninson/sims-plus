"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import {
  ArrowLeft,
  Edit,
  Trash2,
  CheckCircle2,
  Clock,
  FileText,
  User,
  Hash,
  Calendar,
  MapPin,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import {
  deleteExternalExamRegistration,
  updateExternalExamRegistration,
} from "@/actions/curriculum.action";
import type { ExternalExamRegistration, ExternalExamBoard } from "@/types/curriculum.type";

const BOARD_LABELS: Record<ExternalExamBoard, string> = {
  waec: "WAEC",
  cambridge_international: "Cambridge International",
  edexcel: "Edexcel",
  college_board: "College Board",
  ibo: "IBO",
  other: "Other",
};

const BOARD_BADGE_COLORS: Record<ExternalExamBoard, string> = {
  waec: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  cambridge_international: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  edexcel: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  college_board: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  ibo: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  other: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

const STATUS_BADGE_COLORS: Record<string, string> = {
  pending: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
  registered: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  confirmed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
};

interface ExternalExamDetailProps {
  registration: ExternalExamRegistration;
}

export function ExternalExamDetail({ registration }: ExternalExamDetailProps) {
  const router = useRouter();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [currentStatus, setCurrentStatus] = useState(registration.registration_status);

  async function handleDelete() {
    setIsDeleting(true);
    const result = await deleteExternalExamRegistration(registration.id);
    if (result.success) {
      toast.success("Registration deleted");
      router.push("/exams/external");
    } else {
      toast.error(result.error);
    }
    setIsDeleting(false);
  }

  async function handleStatusChange(newStatus: string) {
    const status = newStatus as "pending" | "registered" | "confirmed";
    const result = await updateExternalExamRegistration(registration.id, {
      registration_status: status,
    });
    if (result.success) {
      setCurrentStatus(status);
      toast.success(`Status updated to ${status}`);
    } else {
      toast.error(result.error);
    }
  }

  const hasResults = registration.results && registration.results.length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => router.push("/exams/external")}>
            <ArrowLeft className="size-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">External Exam Registration</h1>
            <p className="text-sm text-muted-foreground">
              {BOARD_LABELS[registration.exam_board]} &mdash; {registration.exam_session}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Select value={currentStatus} onValueChange={handleStatusChange}>
            <SelectTrigger className="w-full sm:w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="registered">Registered</SelectItem>
              <SelectItem value="confirmed">Confirmed</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="destructive" size="icon" onClick={() => setShowDeleteDialog(true)}>
            <Trash2 className="size-4" />
          </Button>
        </div>
      </div>

      {/* Registration Info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Registration Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div className="flex items-center gap-2">
              <User className="size-4 text-muted-foreground" />
              <span className="text-muted-foreground">Student:</span>
              <Link
                href={`/students/${registration.student_id}`}
                className="font-medium text-primary hover:underline"
              >
                {registration.student_id.slice(0, 8)}
              </Link>
            </div>
            <div className="flex items-center gap-2">
              <FileText className="size-4 text-muted-foreground" />
              <span className="text-muted-foreground">Exam Board:</span>
              <Badge variant="secondary" className={BOARD_BADGE_COLORS[registration.exam_board]}>
                {BOARD_LABELS[registration.exam_board]}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <Calendar className="size-4 text-muted-foreground" />
              <span className="text-muted-foreground">Session:</span>
              <span className="font-medium">{registration.exam_session}</span>
            </div>
            <div className="flex items-center gap-2">
              <Clock className="size-4 text-muted-foreground" />
              <span className="text-muted-foreground">Status:</span>
              <Badge variant="secondary" className={STATUS_BADGE_COLORS[currentStatus]}>
                {currentStatus}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <Hash className="size-4 text-muted-foreground" />
              <span className="text-muted-foreground">Candidate #:</span>
              <span className="font-mono">
                {registration.candidate_number || <span className="text-muted-foreground">&mdash;</span>}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <MapPin className="size-4 text-muted-foreground" />
              <span className="text-muted-foreground">Center #:</span>
              <span className="font-mono">
                {registration.center_number || <span className="text-muted-foreground">&mdash;</span>}
              </span>
            </div>
          </div>
          {registration.notes && (
            <>
              <Separator className="my-4" />
              <div>
                <p className="text-sm text-muted-foreground mb-1">Notes</p>
                <p className="text-sm">{registration.notes}</p>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Registered Subjects */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Registered Subjects</CardTitle>
          <CardDescription>{registration.subjects.length} subject(s)</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Subject Code</TableHead>
                  <TableHead>Subject Name</TableHead>
                  <TableHead>Level</TableHead>
                  <TableHead className="hidden sm:table-cell">Papers</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {registration.subjects.map((subject, i) => {
                  const subjectCode = subject.subject_code as string | undefined;
                  const subjectName = subject.subject_name as string | undefined;
                  const level = subject.level as string | undefined;
                  const paperNumbers = subject.paper_numbers as string[] | undefined;
                  return (
                    <TableRow key={i}>
                      <TableCell className="font-mono">{subjectCode ?? "--"}</TableCell>
                      <TableCell className="font-medium">{subjectName ?? "--"}</TableCell>
                      <TableCell>
                        {level || <span className="text-muted-foreground">&mdash;</span>}
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        {paperNumbers?.join(", ") || (
                          <span className="text-muted-foreground">&mdash;</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Results Section */}
      {hasResults && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="size-4 text-green-600" />
                Results
              </div>
            </CardTitle>
            <CardDescription>
              {registration.results!.length} subject result(s) imported
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Subject Code</TableHead>
                    <TableHead>Grade</TableHead>
                    <TableHead>Score</TableHead>
                    <TableHead className="hidden sm:table-cell">Date Received</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {registration.results!.map((result, i) => {
                    const subjectCode = result.subject_code as string | undefined;
                    const grade = result.grade as string | undefined;
                    const score = result.score as number | undefined;
                    const dateReceived = result.date_received as string | undefined;
                    return (
                      <TableRow key={i}>
                        <TableCell className="font-mono">{subjectCode ?? "--"}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="font-semibold">
                            {grade ?? "--"}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {score != null ? (
                            <span className="font-mono">{score}</span>
                          ) : (
                            <span className="text-muted-foreground">&mdash;</span>
                          )}
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          {dateReceived ?? (
                            <span className="text-muted-foreground">&mdash;</span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Delete Confirmation */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Registration</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this external exam registration? This will also
              remove any associated results. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} disabled={isDeleting}>
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
