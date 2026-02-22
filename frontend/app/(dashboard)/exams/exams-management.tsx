"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Plus,
  Search,
  FileText,
  MoreHorizontal,
  Loader2,
  Pencil,
  Trash2,
  Eye,
  ClipboardList,
  CheckCircle,
  AlertCircle,
  Clock,
  Calendar,
} from "lucide-react";
import { toast } from "sonner";
import { format } from "date-fns";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import {
  getExams,
  createExam,
  updateExam,
  deleteExam,
  updateExamStatus,
  publishExamResults,
} from "@/actions/exams.action";
import type {
  Exam,
  ExamCreate,
  ExamUpdate,
  ExamType,
  ExamStatus,
  AcademicYear,
  Term,
} from "@/types";

const EXAM_TYPE_CONFIG: Record<ExamType, { label: string; color: string }> = {
  quiz: { label: "Quiz", color: "bg-purple-500" },
  midterm: { label: "Mid-Term", color: "bg-blue-500" },
  end_term: { label: "End of Term", color: "bg-green-500" },
  mock: { label: "Mock", color: "bg-amber-500" },
  practical: { label: "Practical", color: "bg-cyan-500" },
  project: { label: "Project", color: "bg-rose-500" },
};

const EXAM_STATUS_CONFIG: Record<ExamStatus, { label: string; icon: React.ElementType; color: string }> = {
  draft: { label: "Draft", icon: FileText, color: "text-gray-500" },
  scheduled: { label: "Scheduled", icon: Calendar, color: "text-blue-500" },
  ongoing: { label: "Ongoing", icon: Clock, color: "text-amber-500" },
  completed: { label: "Completed", icon: CheckCircle, color: "text-green-500" },
  results_published: { label: "Published", icon: CheckCircle, color: "text-green-700" },
  cancelled: { label: "Cancelled", icon: AlertCircle, color: "text-red-500" },
};

interface ExamsManagementProps {
  initialExams: Exam[];
  academicYears: AcademicYear[];
}

export function ExamsManagement({ initialExams, academicYears }: ExamsManagementProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const [exams, setExams] = useState<Exam[]>(initialExams);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<ExamStatus | "all">("all");
  const [typeFilter, setTypeFilter] = useState<ExamType | "all">("all");
  const [yearFilter, setYearFilter] = useState<string>("all");

  // Dialog states
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedExam, setSelectedExam] = useState<Exam | null>(null);

  // Form data
  const [formData, setFormData] = useState({
    academic_year_id: "",
    term_id: "",
    name: "",
    exam_type: "midterm" as ExamType,
    description: "",
    start_date: "",
    end_date: "",
  });

  // Get terms for selected academic year
  const selectedYear = academicYears.find((y) => y.id === formData.academic_year_id);
  const availableTerms = selectedYear?.terms || [];

  // Filter exams
  const filteredExams = exams.filter((exam) => {
    const matchesSearch = exam.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || exam.status === statusFilter;
    const matchesType = typeFilter === "all" || exam.exam_type === typeFilter;
    const matchesYear = yearFilter === "all" || exam.academic_year_id === yearFilter;
    return matchesSearch && matchesStatus && matchesType && matchesYear;
  });

  const refreshExams = () => {
    startTransition(async () => {
      const result = await getExams({ page_size: 50 });
      if (result.success && result.data) {
        setExams(result.data.items);
      }
    });
  };

  const openAddDialog = () => {
    // Default to current academic year if available
    const currentYear = academicYears.find((y) => y.is_current);
    const currentTerm = currentYear?.terms?.find((t) => t.is_current);

    setFormData({
      academic_year_id: currentYear?.id || "",
      term_id: currentTerm?.id || "",
      name: "",
      exam_type: "midterm",
      description: "",
      start_date: "",
      end_date: "",
    });
    setAddDialogOpen(true);
  };

  const openEditDialog = (exam: Exam) => {
    setSelectedExam(exam);
    setFormData({
      academic_year_id: exam.academic_year_id,
      term_id: exam.term_id,
      name: exam.name,
      exam_type: exam.exam_type,
      description: exam.description || "",
      start_date: exam.start_date || "",
      end_date: exam.end_date || "",
    });
    setEditDialogOpen(true);
  };

  const openDeleteDialog = (exam: Exam) => {
    setSelectedExam(exam);
    setDeleteDialogOpen(true);
  };

  const handleCreateExam = async () => {
    if (!formData.academic_year_id || !formData.term_id || !formData.name) {
      toast.error("Please fill in all required fields");
      return;
    }

    startTransition(async () => {
      const data: ExamCreate = {
        academic_year_id: formData.academic_year_id,
        term_id: formData.term_id,
        name: formData.name,
        exam_type: formData.exam_type,
        description: formData.description || undefined,
        start_date: formData.start_date || undefined,
        end_date: formData.end_date || undefined,
      };

      const result = await createExam(data);

      if (result.success) {
        toast.success("Exam created", {
          description: `${formData.name} has been created.`,
        });
        setAddDialogOpen(false);
        refreshExams();
      } else {
        toast.error("Failed to create exam", {
          description: result.error,
        });
      }
    });
  };

  const handleUpdateExam = async () => {
    if (!selectedExam || !formData.name) {
      toast.error("Please fill in all required fields");
      return;
    }

    startTransition(async () => {
      const data: ExamUpdate = {
        name: formData.name,
        exam_type: formData.exam_type,
        description: formData.description || undefined,
        start_date: formData.start_date || undefined,
        end_date: formData.end_date || undefined,
      };

      const result = await updateExam(selectedExam.id, data);

      if (result.success) {
        toast.success("Exam updated", {
          description: `${formData.name} has been updated.`,
        });
        setEditDialogOpen(false);
        setSelectedExam(null);
        refreshExams();
      } else {
        toast.error("Failed to update exam", {
          description: result.error,
        });
      }
    });
  };

  const handleDeleteExam = async () => {
    if (!selectedExam) return;

    startTransition(async () => {
      const result = await deleteExam(selectedExam.id);

      if (result.success) {
        toast.success("Exam deleted", {
          description: `${selectedExam.name} has been deleted.`,
        });
        setDeleteDialogOpen(false);
        setSelectedExam(null);
        refreshExams();
      } else {
        toast.error("Failed to delete exam", {
          description: result.error,
        });
      }
    });
  };

  const handleStatusChange = async (exam: Exam, newStatus: ExamStatus) => {
    startTransition(async () => {
      const result = await updateExamStatus(exam.id, newStatus);

      if (result.success) {
        toast.success(`Exam status changed to ${EXAM_STATUS_CONFIG[newStatus].label}`);
        refreshExams();
      } else {
        toast.error("Failed to update status", {
          description: result.error,
        });
      }
    });
  };

  const handlePublishResults = async (exam: Exam) => {
    startTransition(async () => {
      const result = await publishExamResults(exam.id);

      if (result.success) {
        toast.success("Exam results published");
        refreshExams();
      } else {
        toast.error("Failed to publish results", {
          description: result.error,
        });
      }
    });
  };

  // Stats
  const stats = {
    total: exams.length,
    ongoing: exams.filter((e) => e.status === "ongoing").length,
    completed: exams.filter((e) => e.status === "completed").length,
    published: exams.filter((e) => e.status === "results_published").length,
  };

  const examFormFields = (
    <div className="grid gap-4 py-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Academic Year *</Label>
          <Select
            value={formData.academic_year_id}
            onValueChange={(value) =>
              setFormData({ ...formData, academic_year_id: value, term_id: "" })
            }
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select academic year" />
            </SelectTrigger>
            <SelectContent>
              {academicYears.map((year) => (
                <SelectItem key={year.id} value={year.id}>
                  {year.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Term *</Label>
          <Select
            value={formData.term_id}
            onValueChange={(value) => setFormData({ ...formData, term_id: value })}
            disabled={!formData.academic_year_id}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select term" />
            </SelectTrigger>
            <SelectContent>
              {availableTerms.map((term) => (
                <SelectItem key={term.id} value={term.id}>
                  {term.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Exam Type</Label>
          <Select
            value={formData.exam_type}
            onValueChange={(value) =>
              setFormData({ ...formData, exam_type: value as ExamType })
            }
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(EXAM_TYPE_CONFIG).map(([key, config]) => (
                <SelectItem key={key} value={key}>
                  {config.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Exam Name *</Label>
          <Input
            placeholder="e.g., First Term Mid-Term Examination"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>Start Date</Label>
          <Input
            type="date"
            value={formData.start_date}
            onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label>End Date</Label>
          <Input
            type="date"
            value={formData.end_date}
            onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>Description</Label>
        <Textarea
          placeholder="Optional description..."
          value={formData.description}
          onChange={(e) => setFormData({ ...formData, description: e.target.value })}
          rows={3}
        />
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Examinations</h1>
          <p className="text-muted-foreground">
            Create and manage exams, enter scores, and publish results.
          </p>
        </div>
        <Button onClick={openAddDialog}>
          <Plus className="mr-2 h-4 w-4" />
          Create Exam
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Exams</CardDescription>
            <CardTitle className="text-3xl">{stats.total}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Ongoing</CardDescription>
            <CardTitle className="text-3xl text-amber-600">{stats.ongoing}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Completed</CardDescription>
            <CardTitle className="text-3xl text-blue-600">{stats.completed}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Published</CardDescription>
            <CardTitle className="text-3xl text-green-600">{stats.published}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Exam List</CardTitle>
          <CardDescription>View and manage all examinations.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search exams..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <Select
              value={yearFilter}
              onValueChange={(value) => setYearFilter(value)}
            >
              <SelectTrigger className="w-full sm:w-[180px]">
                <SelectValue placeholder="Filter by year" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Years</SelectItem>
                {academicYears.map((year) => (
                  <SelectItem key={year.id} value={year.id}>
                    {year.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={typeFilter}
              onValueChange={(value) => setTypeFilter(value as ExamType | "all")}
            >
              <SelectTrigger className="w-full sm:w-[150px]">
                <SelectValue placeholder="Filter by type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {Object.entries(EXAM_TYPE_CONFIG).map(([key, config]) => (
                  <SelectItem key={key} value={key}>
                    {config.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={statusFilter}
              onValueChange={(value) => setStatusFilter(value as ExamStatus | "all")}
            >
              <SelectTrigger className="w-full sm:w-[150px]">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                {Object.entries(EXAM_STATUS_CONFIG).map(([key, config]) => (
                  <SelectItem key={key} value={key}>
                    {config.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Exam Table */}
          {filteredExams.length === 0 ? (
            <div className="text-center py-12">
              <ClipboardList className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-semibold">No exams found</h3>
              <p className="text-muted-foreground">
                {searchQuery || statusFilter !== "all" || typeFilter !== "all"
                  ? "Try adjusting your search or filters."
                  : "Get started by creating your first exam."}
              </p>
              {!searchQuery && statusFilter === "all" && typeFilter === "all" && (
                <Button onClick={openAddDialog} className="mt-4">
                  <Plus className="mr-2 h-4 w-4" />
                  Create Exam
                </Button>
              )}
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Exam Name</TableHead>
                    <TableHead className="hidden sm:table-cell">Type</TableHead>
                    <TableHead className="hidden md:table-cell">Term</TableHead>
                    <TableHead className="hidden lg:table-cell">Dates</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[70px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredExams.map((exam) => {
                    const StatusIcon = EXAM_STATUS_CONFIG[exam.status]?.icon || FileText;
                    return (
                      <TableRow key={exam.id}>
                        <TableCell>
                          <div>
                            <Link
                              href={`/exams/${exam.id}`}
                              className="font-medium hover:underline hover:text-primary"
                            >
                              {exam.name}
                            </Link>
                            <p className="text-sm text-muted-foreground">
                              {exam.academic_year_name}
                            </p>
                          </div>
                        </TableCell>
                        <TableCell className="hidden sm:table-cell">
                          <Badge
                            className={`${EXAM_TYPE_CONFIG[exam.exam_type]?.color || "bg-gray-500"} text-white`}
                          >
                            {EXAM_TYPE_CONFIG[exam.exam_type]?.label || exam.exam_type}
                          </Badge>
                        </TableCell>
                        <TableCell className="hidden md:table-cell">{exam.term_name || "-"}</TableCell>
                        <TableCell className="hidden lg:table-cell">
                          {exam.start_date ? (
                            <span className="text-sm" suppressHydrationWarning>
                              {format(new Date(exam.start_date), "MMM d")}
                              {exam.end_date && ` - ${format(new Date(exam.end_date), "MMM d, yyyy")}`}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <StatusIcon
                              className={`h-4 w-4 ${EXAM_STATUS_CONFIG[exam.status]?.color || "text-gray-500"}`}
                            />
                            <span className="text-sm">
                              {EXAM_STATUS_CONFIG[exam.status]?.label || exam.status}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon" className="h-8 w-8">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuLabel>Actions</DropdownMenuLabel>
                              <DropdownMenuSeparator />
                              <DropdownMenuItem asChild>
                                <Link href={`/exams/${exam.id}`}>
                                  <Eye className="mr-2 h-4 w-4" />
                                  View Details
                                </Link>
                              </DropdownMenuItem>
                              <DropdownMenuItem asChild>
                                <Link href={`/exams/${exam.id}/scores`}>
                                  <ClipboardList className="mr-2 h-4 w-4" />
                                  Enter Scores
                                </Link>
                              </DropdownMenuItem>
                              <DropdownMenuItem asChild>
                                <Link href={`/exams/${exam.id}/results`}>
                                  <Eye className="mr-2 h-4 w-4" />
                                  View Results
                                </Link>
                              </DropdownMenuItem>
                              <DropdownMenuItem onClick={() => openEditDialog(exam)}>
                                <Pencil className="mr-2 h-4 w-4" />
                                Edit
                              </DropdownMenuItem>
                              <DropdownMenuSeparator />
                              <DropdownMenuLabel className="text-xs text-muted-foreground">
                                Change Status
                              </DropdownMenuLabel>
                              {exam.status !== "ongoing" && exam.status !== "results_published" && (
                                <DropdownMenuItem
                                  onClick={() => handleStatusChange(exam, "ongoing")}
                                >
                                  <Clock className="mr-2 h-4 w-4" />
                                  Start Exam
                                </DropdownMenuItem>
                              )}
                              {exam.status === "ongoing" && (
                                <DropdownMenuItem
                                  onClick={() => handleStatusChange(exam, "completed")}
                                >
                                  <CheckCircle className="mr-2 h-4 w-4" />
                                  Mark Completed
                                </DropdownMenuItem>
                              )}
                              {exam.status === "completed" && (
                                <DropdownMenuItem
                                  onClick={() => handlePublishResults(exam)}
                                >
                                  <CheckCircle className="mr-2 h-4 w-4 text-green-600" />
                                  Publish Results
                                </DropdownMenuItem>
                              )}
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                onClick={() => openDeleteDialog(exam)}
                                className="text-destructive"
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Exam Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Create Exam</DialogTitle>
            <DialogDescription>
              Create a new examination for a term.
            </DialogDescription>
          </DialogHeader>
          {examFormFields}
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateExam} disabled={isPending}>
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Create Exam
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Exam Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-xl">
          <DialogHeader>
            <DialogTitle>Edit Exam</DialogTitle>
            <DialogDescription>Update the exam details.</DialogDescription>
          </DialogHeader>
          {examFormFields}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleUpdateExam} disabled={isPending}>
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Exam</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete {selectedExam?.name}? This will also
              delete all associated scores and cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteExam}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
