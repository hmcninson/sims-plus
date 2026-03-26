"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { ApplicationStatusBadge } from "@/components/admissions/application-status-badge";
import { ApplicationDetailCard } from "@/components/admissions/application-detail-card";
import { DecisionDialog } from "@/components/admissions/decision-dialog";
import { LetterPreview } from "@/components/admissions/letter-preview";
import {
  ArrowLeft,
  MoreHorizontal,
  Loader2,
  FileText,
  Send,
  DollarSign,
  Download,
  GraduationCap,
  MessageSquare,
  CheckCircle,
  UserPlus,
} from "lucide-react";
import {
  getApplicationDetail,
  changeApplicationStatus,
  addApplicationNote,
  waiveApplicationFee,
  waiveApplicationExam,
  enrollApplicant,
} from "@/actions/admissions.action";
import { getClasses } from "@/actions/academic.action";
import type {
  ApplicationDetail,
  ApplicationStatus,
} from "@/types/admissions.type";
import type { Class, ClassSection } from "@/types";

// Valid status transitions for admin
const VALID_TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  draft: [],
  submitted: ["under_review"],
  under_review: ["shortlisted", "rejected"],
  shortlisted: ["exam_scheduled"],
  exam_scheduled: ["exam_completed"],
  exam_completed: [],
  offered: ["accepted", "rejected"],
  accepted: [],
  waitlisted: [],
  rejected: [],
  enrolled: [],
  withdrawn: [],
  expired: [],
  deferred: ["submitted"],
};

const waiveReasonSchema = z.object({
  reason: z.string().min(1, "Reason is required"),
});

type WaiveReasonValues = z.infer<typeof waiveReasonSchema>;

const noteSchema = z.object({
  content: z.string().min(1, "Note content is required"),
  is_internal: z.boolean(),
});

type NoteFormValues = z.infer<typeof noteSchema>;

interface ApplicationDetailViewProps {
  applicationId: string;
}

export function ApplicationDetailView({
  applicationId,
}: ApplicationDetailViewProps) {
  const router = useRouter();
  const [application, setApplication] = useState<ApplicationDetail | null>(
    null
  );
  const [loading, setLoading] = useState(true);

  // Dialogs
  const [showWaiveFeeDialog, setShowWaiveFeeDialog] = useState(false);
  const [showWaiveExamDialog, setShowWaiveExamDialog] = useState(false);
  const [showEnrollDialog, setShowEnrollDialog] = useState(false);
  const [showNoteForm, setShowNoteForm] = useState(false);
  const [enrolling, setEnrolling] = useState(false);
  const [generateInvoice, setGenerateInvoice] = useState(true);
  const [enrollSectionId, setEnrollSectionId] = useState("");
  const [classes, setClasses] = useState<Class[]>([]);

  const waiveFeeForm = useForm<WaiveReasonValues>({
    resolver: zodResolver(waiveReasonSchema),
    defaultValues: { reason: "" },
  });

  const waiveExamForm = useForm<WaiveReasonValues>({
    resolver: zodResolver(waiveReasonSchema),
    defaultValues: { reason: "" },
  });

  const noteForm = useForm<NoteFormValues>({
    resolver: zodResolver(noteSchema),
    defaultValues: { content: "", is_internal: true },
  });

  const loadApplication = useCallback(async () => {
    const result = await getApplicationDetail(applicationId);
    if (result.success && result.data) {
      setApplication(result.data);
    }
    setLoading(false);
  }, [applicationId]);

  useEffect(() => {
    loadApplication();
  }, [loadApplication]);

  async function handleStatusChange(newStatus: ApplicationStatus) {
    const result = await changeApplicationStatus(applicationId, newStatus);
    if (result.success) {
      toast.success(`Status changed to ${newStatus.replace(/_/g, " ")}`);
      loadApplication();
    } else {
      toast.error(result.error);
    }
  }

  async function handleWaiveFee(values: WaiveReasonValues) {
    const result = await waiveApplicationFee(applicationId, values.reason);
    if (result.success) {
      toast.success("Application fee waived");
      setShowWaiveFeeDialog(false);
      waiveFeeForm.reset();
      loadApplication();
    } else {
      toast.error(result.error);
    }
  }

  async function handleWaiveExam(values: WaiveReasonValues) {
    const result = await waiveApplicationExam(applicationId, values.reason);
    if (result.success) {
      toast.success("Entrance exam waived");
      setShowWaiveExamDialog(false);
      waiveExamForm.reset();
      loadApplication();
    } else {
      toast.error(result.error);
    }
  }

  async function handleAddNote(values: NoteFormValues) {
    const result = await addApplicationNote(
      applicationId,
      values.content,
      values.is_internal
    );
    if (result.success) {
      toast.success("Note added");
      setShowNoteForm(false);
      noteForm.reset({ content: "", is_internal: true });
      loadApplication();
    } else {
      toast.error(result.error);
    }
  }

  async function handleEnroll() {
    setEnrolling(true);
    try {
      const result = await enrollApplicant(applicationId, {
        generate_invoice: generateInvoice,
        class_section_id: enrollSectionId || undefined,
      });
      if (result.success && result.data) {
        toast.success(
          `Enrolled successfully. Student #: ${result.data.student_number}`
        );
        setShowEnrollDialog(false);
        loadApplication();
      } else {
        toast.error(result.error);
      }
    } finally {
      setEnrolling(false);
    }
  }

  function loadClasses() {
    if (classes.length === 0) {
      getClasses(true).then((res) => {
        if (res.success && res.data) setClasses(res.data);
      });
    }
  }

  if (loading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10" />
          <Skeleton className="h-8 w-64" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <Skeleton className="h-[200px]" />
            <Skeleton className="h-[150px]" />
            <Skeleton className="h-[200px]" />
          </div>
          <div className="space-y-4">
            <Skeleton className="h-[300px]" />
            <Skeleton className="h-[200px]" />
          </div>
        </div>
      </div>
    );
  }

  if (!application) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4 p-6">
        <FileText className="h-10 w-10 text-muted-foreground" />
        <p className="text-muted-foreground">Application not found</p>
        <Button variant="outline" asChild>
          <Link href="/admissions/applications">Back to Applications</Link>
        </Button>
      </div>
    );
  }

  const transitions = VALID_TRANSITIONS[application.status] || [];
  const canDecide = [
    "shortlisted",
    "exam_completed",
    "waitlisted",
    "under_review",
  ].includes(application.status);
  const canEnroll = application.status === "accepted";
  const sections: ClassSection[] =
    classes.find((c) => c.id === application.target_class_id)?.sections ?? [];

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push("/admissions/applications")}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-xl font-bold">
              {application.applicant_first_name}{" "}
              {application.applicant_last_name}
            </h1>
            <ApplicationStatusBadge status={application.status} />
            {application.fee_waived && (
              <Badge
                variant="outline"
                className="bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
              >
                Fee Waived
              </Badge>
            )}
            {application.exam_waived && (
              <Badge
                variant="outline"
                className="bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
              >
                Exam Waived
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground font-mono">
            {application.tracking_code}
          </p>
        </div>

        {/* Actions Menu */}
        <div className="flex gap-2">
          {canDecide && (
            <DecisionDialog
              applicationId={applicationId}
              currentStatus={application.status}
              applicantName={`${application.applicant_first_name} ${application.applicant_last_name}`}
              onSuccess={loadApplication}
              trigger={
                <Button>
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Make Decision
                </Button>
              }
            />
          )}

          {canEnroll && (
            <Button
              onClick={() => {
                loadClasses();
                setShowEnrollDialog(true);
              }}
            >
              <UserPlus className="mr-2 h-4 w-4" />
              Enroll
            </Button>
          )}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="icon">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {transitions.map((status) => (
                <DropdownMenuItem
                  key={status}
                  onClick={() => handleStatusChange(status)}
                >
                  <Send className="mr-2 h-4 w-4" />
                  Move to{" "}
                  {status
                    .split("_")
                    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                    .join(" ")}
                </DropdownMenuItem>
              ))}
              {transitions.length > 0 && <DropdownMenuSeparator />}
              {!application.fee_waived && (
                <DropdownMenuItem onClick={() => setShowWaiveFeeDialog(true)}>
                  <DollarSign className="mr-2 h-4 w-4" />
                  Waive Fee
                </DropdownMenuItem>
              )}
              {!application.exam_waived && (
                <DropdownMenuItem onClick={() => setShowWaiveExamDialog(true)}>
                  <GraduationCap className="mr-2 h-4 w-4" />
                  Waive Exam
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onClick={() => setShowNoteForm(true)}>
                <MessageSquare className="mr-2 h-4 w-4" />
                Add Note
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Application Details */}
        <div className="lg:col-span-2">
          <ApplicationDetailCard application={application} />
        </div>

        {/* Right Column: Timeline + Notes + Decision */}
        <div className="space-y-6">
          {/* Decision Info */}
          {application.decision && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Decision</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Decision</span>
                  <Badge variant="outline" className="capitalize">
                    {application.decision.decision_type}
                  </Badge>
                </div>
                {application.decision.offered_class_name && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Offered Class</span>
                    <span>{application.decision.offered_class_name}</span>
                  </div>
                )}
                {application.decision.conditions && (
                  <div>
                    <span className="text-muted-foreground">Conditions</span>
                    <p className="mt-1">{application.decision.conditions}</p>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Decided By</span>
                  <span>
                    {application.decision.decided_by_name || "Unknown"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Date</span>
                  <span>
                    {new Date(
                      application.decision.decision_date
                    ).toLocaleDateString("en-GB")}
                  </span>
                </div>
                {application.decision.response_deadline && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">
                      Response Deadline
                    </span>
                    <span>
                      {new Date(
                        application.decision.response_deadline
                      ).toLocaleDateString("en-GB")}
                    </span>
                  </div>
                )}
                {/* Waitlist info */}
                {application.decision.decision_type === "waitlisted" &&
                  application.decision.waitlist_rank && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        Waitlist Rank
                      </span>
                      <Badge variant="secondary">
                        #{application.decision.waitlist_rank}
                      </Badge>
                    </div>
                  )}
                {/* Letter download links */}
                {application.decision.decision_letter_url && (
                  <a
                    href={application.decision.decision_letter_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-sm text-primary hover:underline"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Download Admission Letter
                  </a>
                )}
                {application.decision.rejection_letter_url && (
                  <a
                    href={application.decision.rejection_letter_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-sm text-primary hover:underline"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Download Rejection Letter
                  </a>
                )}
                {/* Letter generation button */}
                {(application.decision.decision_type === "accepted" ||
                  application.decision.decision_type === "rejected") && (
                  <div className="pt-2 border-t">
                    <LetterPreview
                      decision={application.decision}
                      onLetterGenerated={loadApplication}
                    />
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Enrolled Student Link */}
          {application.converted_student_id && (
            <Card>
              <CardContent className="pt-6">
                <Button variant="outline" className="w-full" asChild>
                  <Link
                    href={`/students?id=${application.converted_student_id}`}
                  >
                    <UserPlus className="mr-2 h-4 w-4" />
                    View Student Record
                  </Link>
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Status Timeline */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Status History</CardTitle>
            </CardHeader>
            <CardContent>
              {application.status_history.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No status changes recorded
                </p>
              ) : (
                <div className="relative space-y-0">
                  {application.status_history.map((entry, index) => (
                    <div key={entry.id} className="flex gap-3 pb-4">
                      {/* Timeline line */}
                      <div className="flex flex-col items-center">
                        <div className="h-2.5 w-2.5 rounded-full bg-primary" />
                        {index < application.status_history.length - 1 && (
                          <div className="w-px flex-1 bg-border" />
                        )}
                      </div>
                      <div className="flex-1 pb-2">
                        <div className="flex flex-wrap items-center gap-2">
                          {entry.from_status && (
                            <>
                              <span className="text-xs text-muted-foreground capitalize">
                                {entry.from_status.replace(/_/g, " ")}
                              </span>
                              <span className="text-xs text-muted-foreground">
                                -&gt;
                              </span>
                            </>
                          )}
                          <span className="text-xs font-medium capitalize">
                            {entry.to_status.replace(/_/g, " ")}
                          </span>
                        </div>
                        {entry.reason && (
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {entry.reason}
                          </p>
                        )}
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {new Date(entry.created_at).toLocaleDateString(
                            "en-GB",
                            {
                              day: "2-digit",
                              month: "short",
                              year: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            }
                          )}
                          {entry.changed_by_name &&
                            ` by ${entry.changed_by_name}`}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Notes */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Notes</CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowNoteForm(true)}
              >
                <MessageSquare className="mr-1 h-4 w-4" />
                Add
              </Button>
            </CardHeader>
            <CardContent>
              {application.notes.length === 0 ? (
                <p className="text-sm text-muted-foreground">No notes yet</p>
              ) : (
                <div className="space-y-3">
                  {application.notes.map((note) => (
                    <div
                      key={note.id}
                      className="rounded-lg border p-3 space-y-1"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">
                          {note.author_name || "Unknown"}
                        </span>
                        {note.is_internal && (
                          <Badge variant="secondary" className="text-xs">
                            Internal
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm">{note.content}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(note.created_at).toLocaleDateString("en-GB", {
                          day: "2-digit",
                          month: "short",
                          year: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Waive Fee Dialog */}
      <Dialog open={showWaiveFeeDialog} onOpenChange={setShowWaiveFeeDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Waive Application Fee</DialogTitle>
            <DialogDescription>
              This will waive the application fee for this applicant. Please
              provide a reason.
            </DialogDescription>
          </DialogHeader>
          <Form {...waiveFeeForm}>
            <form
              onSubmit={waiveFeeForm.handleSubmit(handleWaiveFee)}
              className="space-y-4"
            >
              <FormField
                control={waiveFeeForm.control}
                name="reason"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Reason</FormLabel>
                    <FormControl>
                      <Textarea placeholder="Reason for waiving fee..." {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowWaiveFeeDialog(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={waiveFeeForm.formState.isSubmitting}
                >
                  {waiveFeeForm.formState.isSubmitting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Waive Fee
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Waive Exam Dialog */}
      <Dialog open={showWaiveExamDialog} onOpenChange={setShowWaiveExamDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Waive Entrance Exam</DialogTitle>
            <DialogDescription>
              This will waive the entrance exam requirement for this applicant.
            </DialogDescription>
          </DialogHeader>
          <Form {...waiveExamForm}>
            <form
              onSubmit={waiveExamForm.handleSubmit(handleWaiveExam)}
              className="space-y-4"
            >
              <FormField
                control={waiveExamForm.control}
                name="reason"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Reason</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Reason for waiving exam..."
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowWaiveExamDialog(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={waiveExamForm.formState.isSubmitting}
                >
                  {waiveExamForm.formState.isSubmitting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Waive Exam
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Add Note Dialog */}
      <Dialog open={showNoteForm} onOpenChange={setShowNoteForm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Note</DialogTitle>
            <DialogDescription>
              Add a note to this application.
            </DialogDescription>
          </DialogHeader>
          <Form {...noteForm}>
            <form
              onSubmit={noteForm.handleSubmit(handleAddNote)}
              className="space-y-4"
            >
              <FormField
                control={noteForm.control}
                name="content"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Note</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Write your note here..."
                        rows={4}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={noteForm.control}
                name="is_internal"
                render={({ field }) => (
                  <FormItem className="flex items-center space-x-2 space-y-0">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormLabel className="font-normal cursor-pointer">
                      Internal note (not visible to applicant)
                    </FormLabel>
                  </FormItem>
                )}
              />
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowNoteForm(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={noteForm.formState.isSubmitting}
                >
                  {noteForm.formState.isSubmitting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  )}
                  Add Note
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Enroll Dialog */}
      <AlertDialog open={showEnrollDialog} onOpenChange={setShowEnrollDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Enroll Applicant</AlertDialogTitle>
            <AlertDialogDescription>
              Convert this applicant into a student record. This action will
              create a student account, assign a student ID, and optionally
              generate an invoice.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-4 py-4">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="generate-invoice"
                checked={generateInvoice}
                onCheckedChange={(checked) =>
                  setGenerateInvoice(Boolean(checked))
                }
              />
              <Label htmlFor="generate-invoice" className="cursor-pointer">
                Generate invoice
              </Label>
            </div>
            <div className="space-y-2">
              <Label>Section (Optional)</Label>
              <Select
                value={enrollSectionId}
                onValueChange={setEnrollSectionId}
              >
                <SelectTrigger>
                  <SelectValue placeholder="No section" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">No section</SelectItem>
                  {sections.map((sec) => (
                    <SelectItem key={sec.id} value={sec.id}>
                      {sec.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={enrolling}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleEnroll} disabled={enrolling}>
              {enrolling && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enroll
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
