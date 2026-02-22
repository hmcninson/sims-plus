"use client";

import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import {
  Loader2,
  FileHeart,
  AlertTriangle,
  Send,
  Eye,
  FileText,
  CheckCircle,
  Clock,
  Users,
  Sparkles,
  Download,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

import { getStudents } from "@/actions/students.action";
import {
  getClassReports,
  generatePreschoolReports,
  updatePreschoolReport,
  publishPreschoolReports,
  getReportPdfDownloadInfo,
} from "@/actions/preschool.action";
import type {
  Class,
  AcademicYear,
  LearningArea,
  PreschoolReport,
  Student,
} from "@/types";

interface ReportsManagerProps {
  classes: Class[];
  academicYears: AcademicYear[];
  currentAcademicYear: AcademicYear | null;
  learningAreas: LearningArea[];
}

export function ReportsManager({
  classes,
  academicYears,
  currentAcademicYear,
  learningAreas,
}: ReportsManagerProps) {
  // Selection state
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [selectedTermId, setSelectedTermId] = useState<string>("");

  // Data state
  const [students, setStudents] = useState<Student[]>([]);
  const [reports, setReports] = useState<PreschoolReport[]>([]);
  const studentsRef = useRef<Student[]>([]);
  const [selectedReportIds, setSelectedReportIds] = useState<string[]>([]);

  // Loading state
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);
  const [isLoadingReports, setIsLoadingReports] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedReport, setSelectedReport] = useState<PreschoolReport | null>(null);

  // Form state for editing
  const [editFormData, setEditFormData] = useState({
    overall_progress: "",
    strengths: "",
    areas_for_growth: "",
    teacher_recommendations: "",
    class_teacher_remark: "",
    head_teacher_remark: "",
  });

  // Get current academic year's terms
  const currentTerms = currentAcademicYear?.terms || [];

  // Set default term if not selected
  useEffect(() => {
    if (!selectedTermId && currentTerms.length > 0) {
      const currentTerm = currentTerms.find((t) => t.is_current) || currentTerms[0];
      if (currentTerm) {
        setSelectedTermId(currentTerm.id);
      }
    }
  }, [currentTerms, selectedTermId]);

  // Fetch students when class changes
  useEffect(() => {
    async function fetchStudents() {
      if (!selectedClassId) {
        setStudents([]);
        return;
      }

      setIsLoadingStudents(true);
      try {
        const result = await getStudents({
          class_id: selectedClassId,
          page_size: 100,
        });

        if (result.success && result.data) {
          setStudents(
            result.data.items.map((s) => ({
              id: s.id,
              student_id: s.student_id,
              first_name: s.first_name,
              middle_name: s.middle_name,
              last_name: s.last_name,
              gender: s.gender,
              date_of_birth: s.date_of_birth,
              status: s.status,
              class_id: s.class_id,
              section_id: s.section_id,
              photo_url: s.photo_url,
              is_boarder: false,
              created_at: "",
              updated_at: "",
            })) as Student[]
          );
        } else {
          setStudents([]);
        }
      } catch {
        setStudents([]);
      } finally {
        setIsLoadingStudents(false);
      }
    }

    fetchStudents();
  }, [selectedClassId]);

  // Fetch reports for class (single API call)
  const fetchReportsForClass = async (classId: string, termId: string) => {
    setIsLoadingReports(true);
    try {
      const result = await getClassReports(classId, termId);
      if (result.success && result.data) {
        setReports(result.data);
      } else {
        setReports([]);
      }
    } catch {
      setReports([]);
    } finally {
      setIsLoadingReports(false);
    }
  };

  // Helper to refetch reports
  const refetchReports = () => {
    if (selectedClassId && selectedTermId) {
      fetchReportsForClass(selectedClassId, selectedTermId);
    }
  };

  // Fetch reports when class or term changes
  useEffect(() => {
    studentsRef.current = students;
    if (selectedClassId && selectedTermId) {
      fetchReportsForClass(selectedClassId, selectedTermId);
    } else {
      setReports([]);
    }
  }, [selectedClassId, selectedTermId]);

  // Generate reports
  const handleGenerate = async () => {
    if (!selectedClassId || !selectedTermId || !currentAcademicYear) {
      toast.error("Please select a class and term");
      return;
    }

    setIsGenerating(true);
    try {
      const result = await generatePreschoolReports(
        selectedClassId,
        currentAcademicYear.id,
        selectedTermId
      );

      if (result.success) {
        toast.success(`Generated ${result.data?.generated || 0} reports`);
        refetchReports();
      } else {
        toast.error(result.error || "Failed to generate reports");
      }
    } catch {
      toast.error("Failed to generate reports");
    } finally {
      setIsGenerating(false);
    }
  };

  // Publish selected reports
  const handlePublish = async () => {
    if (selectedReportIds.length === 0) {
      toast.error("Please select reports to publish");
      return;
    }

    setIsPublishing(true);
    try {
      const result = await publishPreschoolReports(selectedReportIds);

      if (result.success) {
        toast.success(`Published ${result.data?.published || 0} reports`);
        setSelectedReportIds([]);
        refetchReports();
      } else {
        toast.error(result.error || "Failed to publish reports");
      }
    } catch {
      toast.error("Failed to publish reports");
    } finally {
      setIsPublishing(false);
    }
  };

  // Open edit dialog
  const openEditDialog = (report: PreschoolReport) => {
    setSelectedReport(report);
    setEditFormData({
      overall_progress: report.overall_progress || "",
      strengths: report.strengths || "",
      areas_for_growth: report.areas_for_growth || "",
      teacher_recommendations: report.teacher_recommendations || "",
      class_teacher_remark: report.class_teacher_remark || "",
      head_teacher_remark: report.head_teacher_remark || "",
    });
    setEditDialogOpen(true);
  };

  // Save report changes
  const handleSaveReport = async () => {
    if (!selectedReport) return;

    setIsSaving(true);
    try {
      const result = await updatePreschoolReport(selectedReport.id, editFormData);

      if (result.success) {
        toast.success("Report updated");
        setEditDialogOpen(false);
        setSelectedReport(null);
        refetchReports();
      } else {
        toast.error(result.error || "Failed to update report");
      }
    } catch {
      toast.error("Failed to update report");
    } finally {
      setIsSaving(false);
    }
  };

  // Toggle report selection
  const toggleReportSelection = (reportId: string) => {
    setSelectedReportIds((prev) =>
      prev.includes(reportId)
        ? prev.filter((id) => id !== reportId)
        : [...prev, reportId]
    );
  };

  // Select all unpublished reports
  const selectAllUnpublished = () => {
    const unpublishedIds = reports.filter((r) => !r.is_published).map((r) => r.id);
    setSelectedReportIds(unpublishedIds);
  };

  // Download report as PDF
  const handleDownloadPdf = async (reportId: string) => {
    try {
      const result = await getReportPdfDownloadInfo(reportId);
      if (!result.success || !result.data) {
        toast.error(result.error || "Failed to get download info");
        console.error("Download info error:", result.error);
        return;
      }

      const { url, token, subdomain } = result.data;
      console.log("Downloading PDF from:", url);

      // Fetch the PDF
      const response = await fetch(url, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain,
        },
      });

      console.log("Response status:", response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error("Download error response:", errorText);
        try {
          const error = JSON.parse(errorText);
          toast.error(error.detail || `Failed to download report (${response.status})`);
        } catch {
          toast.error(`Failed to download report (${response.status})`);
        }
        return;
      }

      // Get filename from Content-Disposition header or use default
      const contentDisposition = response.headers.get("Content-Disposition");
      let filename = "Progress_Report.pdf";
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?(.+?)"?$/);
        if (match) filename = match[1];
      }

      // Create blob and download
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(blobUrl);

      toast.success("Report downloaded successfully");
    } catch (error) {
      console.error("Download error:", error);
      toast.error("Failed to download report");
    }
  };

  // Get student by ID
  const getStudent = (studentId: string) => students.find((s) => s.id === studentId);

  // Stats
  const stats = {
    total: students.length,
    generated: reports.length,
    published: reports.filter((r) => r.is_published).length,
    pending: reports.filter((r) => !r.is_published).length,
  };

  // No classes
  if (classes.length === 0) {
    return (
      <Alert>
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>No Preschool Classes</AlertTitle>
        <AlertDescription>
          There are no preschool classes available. Please create preschool classes first.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Selection Controls */}
      <div className="flex flex-wrap items-end gap-4">
        <div className="w-full sm:w-auto">
          <Label className="mb-1.5 block text-sm font-medium">Class</Label>
          <Select value={selectedClassId} onValueChange={setSelectedClassId}>
            <SelectTrigger className="w-full sm:w-[200px]">
              <SelectValue placeholder="Select class..." />
            </SelectTrigger>
            <SelectContent>
              {classes.map((cls) => (
                <SelectItem key={cls.id} value={cls.id}>
                  {cls.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="w-full sm:w-auto">
          <Label className="mb-1.5 block text-sm font-medium">Term</Label>
          <Select value={selectedTermId} onValueChange={setSelectedTermId}>
            <SelectTrigger className="w-full sm:w-[250px]">
              <SelectValue placeholder="Select term..." />
            </SelectTrigger>
            <SelectContent>
              {currentTerms.map((term) => (
                <SelectItem key={term.id} value={term.id}>
                  {term.name}
                  {term.is_current && " (Current)"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {selectedClassId && selectedTermId && (
          <div className="flex gap-2">
            <Button
              onClick={handleGenerate}
              disabled={isGenerating}
              className="gap-2"
            >
              {isGenerating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Generate Reports
            </Button>
            {selectedReportIds.length > 0 && (
              <Button
                onClick={handlePublish}
                disabled={isPublishing}
                variant="outline"
                className="gap-2"
              >
                {isPublishing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                Publish ({selectedReportIds.length})
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Stats Cards */}
      {selectedClassId && selectedTermId && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2">
                <Users className="h-4 w-4" />
                Total Students
              </CardDescription>
              <CardTitle className="text-2xl">{stats.total}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2">
                <FileText className="h-4 w-4" />
                Reports Generated
              </CardDescription>
              <CardTitle className="text-2xl">{stats.generated}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-amber-500" />
                Pending Publication
              </CardDescription>
              <CardTitle className="text-2xl text-amber-600">{stats.pending}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-green-500" />
                Published
              </CardDescription>
              <CardTitle className="text-2xl text-green-600">{stats.published}</CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Reports Table */}
      {selectedClassId && selectedTermId ? (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-lg">Student Reports</CardTitle>
              <CardDescription>
                View and edit progress reports for the selected class and term
              </CardDescription>
            </div>
            {stats.pending > 0 && (
              <Button variant="outline" size="sm" onClick={selectAllUnpublished}>
                Select All Unpublished
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {isLoadingStudents || isLoadingReports ? (
              <div className="flex h-48 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : students.length === 0 ? (
              <div className="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed">
                <Users className="h-10 w-10 text-muted-foreground/50" />
                <p className="mt-4 text-muted-foreground">No students in this class</p>
              </div>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12"></TableHead>
                      <TableHead>Student</TableHead>
                      <TableHead>Report Status</TableHead>
                      <TableHead className="hidden sm:table-cell">Progress</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {students.map((student) => {
                      const report = reports.find((r) => r.student_id === student.id);
                      const isSelected = report ? selectedReportIds.includes(report.id) : false;

                      return (
                        <TableRow key={student.id}>
                          <TableCell>
                            {report && !report.is_published && (
                              <Checkbox
                                checked={isSelected}
                                onCheckedChange={() => toggleReportSelection(report.id)}
                              />
                            )}
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-3">
                              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-xs font-medium">
                                {student.first_name?.[0]}
                                {student.last_name?.[0]}
                              </div>
                              <div>
                                <p className="font-medium">
                                  {student.first_name} {student.last_name}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {student.student_id}
                                </p>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell>
                            {report ? (
                              report.is_published ? (
                                <Badge className="gap-1 bg-green-100 text-green-800">
                                  <CheckCircle className="h-3 w-3" />
                                  Published
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="gap-1 text-amber-600">
                                  <Clock className="h-3 w-3" />
                                  Draft
                                </Badge>
                              )
                            ) : (
                              <Badge variant="secondary">Not Generated</Badge>
                            )}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell">
                            {report?.overall_progress ? (
                              <p className="max-w-[200px] truncate text-sm text-muted-foreground">
                                {report.overall_progress}
                              </p>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </TableCell>
                          <TableCell className="text-right">
                            {report && (
                              <div className="flex items-center justify-end gap-1">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => openEditDialog(report)}
                                >
                                  <Eye className="mr-1 h-4 w-4" />
                                  View/Edit
                                </Button>
                                {report.is_published && (
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => handleDownloadPdf(report.id)}
                                    title="Download PDF"
                                  >
                                    <Download className="h-4 w-4" />
                                  </Button>
                                )}
                              </div>
                            )}
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
      ) : (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <FileHeart className="h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-medium">Select Class and Term</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Choose a class and term to generate and manage progress reports
            </p>
          </CardContent>
        </Card>
      )}

      {/* Edit Report Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Edit Progress Report
              {selectedReport && (
                <span className="ml-2 text-muted-foreground font-normal">
                  - {getStudent(selectedReport.student_id)?.first_name}{" "}
                  {getStudent(selectedReport.student_id)?.last_name}
                </span>
              )}
            </DialogTitle>
            <DialogDescription>
              Edit the narrative sections of this progress report
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Overall Progress</Label>
              <Textarea
                placeholder="Describe the child's overall developmental progress..."
                value={editFormData.overall_progress}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, overall_progress: e.target.value })
                }
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label>Strengths</Label>
              <Textarea
                placeholder="Areas where the child excels..."
                value={editFormData.strengths}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, strengths: e.target.value })
                }
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label>Areas for Growth</Label>
              <Textarea
                placeholder="Areas that need more development..."
                value={editFormData.areas_for_growth}
                onChange={(e) =>
                  setEditFormData({ ...editFormData, areas_for_growth: e.target.value })
                }
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label>Teacher Recommendations</Label>
              <Textarea
                placeholder="Suggestions for parents to support learning at home..."
                value={editFormData.teacher_recommendations}
                onChange={(e) =>
                  setEditFormData({
                    ...editFormData,
                    teacher_recommendations: e.target.value,
                  })
                }
                rows={3}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Class Teacher Remark</Label>
                <Textarea
                  placeholder="Class teacher's comments..."
                  value={editFormData.class_teacher_remark}
                  onChange={(e) =>
                    setEditFormData({
                      ...editFormData,
                      class_teacher_remark: e.target.value,
                    })
                  }
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <Label>Head Teacher Remark</Label>
                <Textarea
                  placeholder="Head teacher's comments..."
                  value={editFormData.head_teacher_remark}
                  onChange={(e) =>
                    setEditFormData({
                      ...editFormData,
                      head_teacher_remark: e.target.value,
                    })
                  }
                  rows={3}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveReport} disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
