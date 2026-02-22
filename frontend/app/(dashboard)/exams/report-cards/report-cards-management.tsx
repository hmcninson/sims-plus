"use client";

import { useState, useTransition, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  FileText,
  Search,
  Filter,
  RefreshCw,
  Loader2,
  Eye,
  Send,
  CheckCircle,
  Clock,
  GraduationCap,
  Calendar,
  Layers,
  Users,
  MoreHorizontal,
  Pencil,
  Printer,
  Download,
  Info,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";

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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Alert, AlertDescription } from "@/components/ui/alert";

import {
  getTermReports,
  generateTermReports,
  publishTermReports,
  type TermReportFilters,
} from "@/actions/exams.action";
import type { AcademicYear, Class, TermReportWithDetails } from "@/types";

interface ReportCardsManagementProps {
  academicYears: AcademicYear[];
  classes: Class[];
}

const STATUS_CONFIG = {
  draft: { label: "Draft", color: "bg-gray-500", icon: Clock },
  published: { label: "Published", color: "bg-green-500", icon: CheckCircle },
};

export function ReportCardsManagement({
  academicYears,
  classes,
}: ReportCardsManagementProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [isGenerating, setIsGenerating] = useState(false);

  // Filter state - use lazy initialization to compute defaults
  const [selectedYearId, setSelectedYearId] = useState<string>(() => {
    // Try is_current first, then status === "active", then fall back to first year
    const activeYear = academicYears.find((y) => y.is_current)
      || academicYears.find((y) => y.status === "active")
      || academicYears[0];
    return activeYear?.id || "";
  });
  const [selectedTermId, setSelectedTermId] = useState<string>(() => {
    const activeYear = academicYears.find((y) => y.is_current)
      || academicYears.find((y) => y.status === "active")
      || academicYears[0];
    const terms = activeYear?.terms?.sort((a, b) => a.sequence - b.sequence) || [];
    const currentTerm = terms.find((t) => t.is_current) || terms[0];
    return currentTerm?.id || "";
  });
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [selectedSectionId, setSelectedSectionId] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Data state
  const [reports, setReports] = useState<TermReportWithDetails[]>([]);
  const [totalReports, setTotalReports] = useState(0);
  const [page, setPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);

  // Dialog state
  const [generateDialogOpen, setGenerateDialogOpen] = useState(false);
  const [publishDialogOpen, setPublishDialogOpen] = useState(false);
  const [selectedReportIds, setSelectedReportIds] = useState<string[]>([]);

  // Generate dialog has its own state (separate from main filters)
  const [genYearId, setGenYearId] = useState<string>("");
  const [genTermId, setGenTermId] = useState<string>("");
  const [genClassId, setGenClassId] = useState<string>("");
  const [genSectionId, setGenSectionId] = useState<string>("all");

  // Get terms for selected year (main filters)
  const terms = useMemo(() => {
    const year = academicYears.find((y) => y.id === selectedYearId);
    return year?.terms?.sort((a, b) => a.sequence - b.sequence) || [];
  }, [academicYears, selectedYearId]);

  // Get terms for generate dialog
  const genTerms = useMemo(() => {
    const year = academicYears.find((y) => y.id === genYearId);
    return year?.terms?.sort((a, b) => a.sequence - b.sequence) || [];
  }, [academicYears, genYearId]);

  // Get sections for generate dialog
  const genSections = useMemo(() => {
    const cls = classes.find((c) => c.id === genClassId);
    return cls?.sections || [];
  }, [classes, genClassId]);

  // Get student count preview for generate dialog
  const genStudentCount = useMemo(() => {
    if (!genClassId) return 0;
    const cls = classes.find((c) => c.id === genClassId);
    if (!cls) return 0;
    if (genSectionId !== "all") {
      const section = cls.sections?.find((s) => s.id === genSectionId);
      return section?.student_count || 0;
    }
    return cls.student_count || 0;
  }, [classes, genClassId, genSectionId]);

  // Update term when year changes (select current term or first term)
  useEffect(() => {
    if (terms.length > 0) {
      // Check if current term is valid for this year
      const termExists = terms.some((t) => t.id === selectedTermId);
      if (!termExists) {
        const current = terms.find((t) => t.is_current);
        setSelectedTermId(current?.id || terms[0]?.id || "");
      }
    }
  }, [terms, selectedTermId]);

  // Update generate dialog term when year changes
  useEffect(() => {
    if (genTerms.length > 0) {
      const termExists = genTerms.some((t) => t.id === genTermId);
      if (!termExists) {
        const current = genTerms.find((t) => t.is_current);
        setGenTermId(current?.id || genTerms[0]?.id || "");
      }
    }
  }, [genTerms, genTermId]);

  // Open generate dialog with current filter values as defaults
  const openGenerateDialog = () => {
    setGenYearId(selectedYearId);
    setGenTermId(selectedTermId);
    setGenClassId(selectedClassId);
    setGenSectionId(selectedSectionId);
    setGenerateDialogOpen(true);
  };

  // Get sections for selected class
  const sections = useMemo(() => {
    const cls = classes.find((c) => c.id === selectedClassId);
    return cls?.sections || [];
  }, [classes, selectedClassId]);

  // Load reports when filters change
  useEffect(() => {
    if (selectedYearId && selectedTermId) {
      loadReports();
    }
  }, [selectedYearId, selectedTermId, selectedClassId, selectedSectionId, statusFilter, page]);

  const loadReports = async () => {
    setIsLoading(true);
    const filters: TermReportFilters = {
      academic_year_id: selectedYearId,
      term_id: selectedTermId,
      page,
      page_size: 50,
    };
    if (selectedClassId) filters.class_id = selectedClassId;
    if (selectedSectionId !== "all") filters.section_id = selectedSectionId;
    if (statusFilter !== "all") filters.is_published = statusFilter === "published";

    const result = await getTermReports(filters);
    if (result.success && result.data) {
      setReports(result.data.items || []);
      setTotalReports(result.data.total || 0);
    } else {
      toast.error(result.error || "Failed to load reports");
    }
    setIsLoading(false);
  };

  // Filter reports by search
  const filteredReports = useMemo(() => {
    if (!searchQuery) return reports;
    const query = searchQuery.toLowerCase();
    return reports.filter(
      (r) =>
        r.student_name?.toLowerCase().includes(query) ||
        r.student_id_number?.toLowerCase().includes(query)
    );
  }, [reports, searchQuery]);

  // Handle generate reports
  const handleGenerateReports = async () => {
    if (!genYearId || !genTermId || !genClassId) {
      toast.error("Please select academic year, term, and class");
      return;
    }

    setIsGenerating(true);
    const result = await generateTermReports({
      academic_year_id: genYearId,
      term_id: genTermId,
      class_id: genClassId,
      section_id: genSectionId !== "all" ? genSectionId : undefined,
    });

    if (result.success) {
      const generated = result.data?.generated || 0;
      const updated = result.data?.updated || 0;
      toast.success(`Generated ${generated} new report cards${updated > 0 ? `, updated ${updated}` : ""}`);
      setGenerateDialogOpen(false);
      // Update main filters to show the generated reports
      setSelectedYearId(genYearId);
      setSelectedTermId(genTermId);
      setSelectedClassId(genClassId);
      setSelectedSectionId(genSectionId);
    } else {
      toast.error(result.error || "Failed to generate reports");
    }
    setIsGenerating(false);
  };

  // Handle publish reports
  const handlePublishReports = async () => {
    if (!selectedTermId) {
      toast.error("Please select a term");
      return;
    }

    startTransition(async () => {
      const result = await publishTermReports(
        selectedTermId,
        selectedClassId || undefined
      );
      if (result.success) {
        toast.success(`Published ${result.data?.published || 0} reports`);
        setPublishDialogOpen(false);
        setSelectedReportIds([]);
        loadReports();
      } else {
        toast.error(result.error || "Failed to publish reports");
      }
    });
  };

  // Handle select all
  const handleSelectAll = () => {
    if (selectedReportIds.length === filteredReports.length) {
      setSelectedReportIds([]);
    } else {
      setSelectedReportIds(filteredReports.map((r) => r.id));
    }
  };

  // Handle individual selection
  const handleSelectReport = (id: string) => {
    setSelectedReportIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  // Stats
  const stats = useMemo(() => {
    const total = reports.length;
    const published = reports.filter((r) => r.is_published).length;
    const draft = reports.filter((r) => !r.is_published).length;
    return { total, published, draft };
  }, [reports]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Report Cards</h1>
          <p className="text-muted-foreground">
            Generate and manage student term report cards
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={loadReports}
            disabled={isLoading}
          >
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button onClick={openGenerateDialog}>
            <FileText className="mr-2 h-4 w-4" />
            Generate Reports
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="text-lg flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-4">
            {/* Academic Year */}
            <div className="space-y-2 min-w-[180px]">
              <label className="text-sm font-medium flex items-center gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                Academic Year
              </label>
              <Select value={selectedYearId} onValueChange={setSelectedYearId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select year" />
                </SelectTrigger>
                <SelectContent>
                  {academicYears.map((year) => (
                    <SelectItem key={year.id} value={year.id}>
                      {year.name}
                      {year.status === "active" && (
                        <Badge variant="secondary" className="ml-2 text-xs">
                          Active
                        </Badge>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Term */}
            <div className="space-y-2 min-w-[180px]">
              <label className="text-sm font-medium">Term</label>
              <Select
                value={selectedTermId}
                onValueChange={setSelectedTermId}
                disabled={!selectedYearId}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select term" />
                </SelectTrigger>
                <SelectContent>
                  {terms.map((term) => (
                    <SelectItem key={term.id} value={term.id}>
                      {term.name}
                      {term.is_current && (
                        <Badge variant="secondary" className="ml-2 text-xs">
                          Current
                        </Badge>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Class */}
            <div className="space-y-2 min-w-[180px]">
              <label className="text-sm font-medium flex items-center gap-2">
                <GraduationCap className="h-4 w-4 text-muted-foreground" />
                Class
              </label>
              <Select value={selectedClassId || "all"} onValueChange={(v) => {
                setSelectedClassId(v === "all" ? "" : v);
                setSelectedSectionId("all");
              }}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="All classes" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Classes</SelectItem>
                  {classes.map((cls) => (
                    <SelectItem key={cls.id} value={cls.id}>
                      {cls.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Section */}
            <div className="space-y-2 min-w-[180px]">
              <label className="text-sm font-medium flex items-center gap-2">
                <Layers className="h-4 w-4 text-muted-foreground" />
                Section
              </label>
              <Select
                value={selectedSectionId}
                onValueChange={setSelectedSectionId}
                disabled={!selectedClassId || sections.length === 0}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="All sections" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Sections</SelectItem>
                  {sections.map((section) => (
                    <SelectItem key={section.id} value={section.id}>
                      {section.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Status */}
            <div className="space-y-2 min-w-[180px]">
              <label className="text-sm font-medium">Status</label>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="All status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="draft">Draft</SelectItem>
                  <SelectItem value="published">Published</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Reports</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2">
              <Users className="h-5 w-5 text-muted-foreground" />
              {stats.total}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Draft</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2 text-gray-600">
              <Clock className="h-5 w-5" />
              {stats.draft}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Published</CardDescription>
            <CardTitle className="text-2xl flex items-center gap-2 text-green-600">
              <CheckCircle className="h-5 w-5" />
              {stats.published}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Reports Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Report Cards</CardTitle>
            <CardDescription>
              {filteredReports.length} of {totalReports} reports
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search students..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 w-full sm:w-[250px]"
              />
            </div>
            {stats.draft > 0 && (
              <Button onClick={() => setPublishDialogOpen(true)}>
                <Send className="mr-2 h-4 w-4" />
                Publish All Draft ({stats.draft})
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredReports.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="mx-auto h-12 w-12 text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-semibold">No report cards found</h3>
              <p className="text-muted-foreground">
                {reports.length === 0
                  ? "Generate report cards for a class to get started."
                  : "No reports match your search."}
              </p>
            </div>
          ) : (
            <ScrollArea className="h-[500px]">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[50px]">
                      <Checkbox
                        checked={
                          selectedReportIds.length === filteredReports.length &&
                          filteredReports.length > 0
                        }
                        onCheckedChange={handleSelectAll}
                      />
                    </TableHead>
                    <TableHead>Student</TableHead>
                    <TableHead className="hidden sm:table-cell">Class</TableHead>
                    <TableHead className="text-center">Average</TableHead>
                    <TableHead className="hidden md:table-cell text-center">Position</TableHead>
                    <TableHead className="hidden md:table-cell text-center">Status</TableHead>
                    <TableHead className="w-[50px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredReports.map((report) => (
                    <TableRow key={report.id}>
                      <TableCell>
                        <Checkbox
                          checked={selectedReportIds.includes(report.id)}
                          onCheckedChange={() => handleSelectReport(report.id)}
                        />
                      </TableCell>
                      <TableCell>
                        <div>
                          <p className="font-medium">{report.student_name}</p>
                          <p className="text-sm text-muted-foreground">
                            {report.student_id_number}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell className="hidden sm:table-cell">
                        <div>
                          <p>{report.class_name}</p>
                          {report.section_name && (
                            <p className="text-sm text-muted-foreground">
                              {report.section_name}
                            </p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge
                          variant={
                            Number(report.average_score) >= 70
                              ? "default"
                              : Number(report.average_score) >= 50
                              ? "secondary"
                              : "destructive"
                          }
                        >
                          {Number(report.average_score || 0).toFixed(1)}%
                        </Badge>
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-center">
                        <div className="flex flex-col items-center">
                          <span className="font-semibold">
                            {report.class_position || "-"}
                          </span>
                          {report.section_position && (
                            <span className="text-xs text-muted-foreground">
                              Sec: {report.section_position}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-center">
                        <Badge
                          className={`${
                            report.is_published ? STATUS_CONFIG.published.color : STATUS_CONFIG.draft.color
                          } text-white`}
                        >
                          {report.is_published ? STATUS_CONFIG.published.label : STATUS_CONFIG.draft.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              onClick={() =>
                                router.push(`/exams/report-cards/${report.id}`)
                              }
                            >
                              <Eye className="mr-2 h-4 w-4" />
                              View
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() =>
                                router.push(`/exams/report-cards/${report.id}/edit`)
                              }
                            >
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit Remarks
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ScrollArea>
          )}
        </CardContent>
      </Card>

      {/* Generate Dialog */}
      <Dialog open={generateDialogOpen} onOpenChange={setGenerateDialogOpen}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Generate Report Cards
            </DialogTitle>
            <DialogDescription>
              Generate term report cards for students in a class.
            </DialogDescription>
          </DialogHeader>

          <Alert className="border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950">
            <Info className="h-4 w-4 text-blue-600 dark:text-blue-400" />
            <AlertDescription className="text-blue-800 dark:text-blue-200">
              This will calculate grades, class positions, section positions, and prepare reports for printing/publishing.
            </AlertDescription>
          </Alert>

          <div className="space-y-5 py-2">
            {/* Academic Year & Term Row */}
            <div className="flex gap-6">
              <div className="flex-1 space-y-2">
                <label className="text-sm font-medium flex items-center gap-2 h-5">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  Academic Year
                </label>
                <Select value={genYearId} onValueChange={setGenYearId}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select year" />
                  </SelectTrigger>
                  <SelectContent>
                    {academicYears.map((year) => (
                      <SelectItem key={year.id} value={year.id}>
                        {year.name}
                        {(year.is_current || year.status === "active") && (
                          <Badge variant="secondary" className="ml-2 text-xs">
                            Active
                          </Badge>
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex-1 space-y-2">
                <label className="text-sm font-medium flex items-center gap-2 h-5">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  Term
                </label>
                <Select
                  value={genTermId}
                  onValueChange={setGenTermId}
                  disabled={!genYearId}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select term" />
                  </SelectTrigger>
                  <SelectContent>
                    {genTerms.map((term) => (
                      <SelectItem key={term.id} value={term.id}>
                        {term.name}
                        {term.is_current && (
                          <Badge variant="secondary" className="ml-2 text-xs">
                            Current
                          </Badge>
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Class & Section Row */}
            <div className="flex gap-6">
              <div className="flex-1 space-y-2">
                <label className="text-sm font-medium flex items-center gap-2 h-5">
                  <GraduationCap className="h-4 w-4 text-muted-foreground" />
                  Class
                  <span className="text-destructive">*</span>
                </label>
                <Select
                  value={genClassId}
                  onValueChange={(v) => {
                    setGenClassId(v);
                    setGenSectionId("all");
                  }}
                >
                  <SelectTrigger className={`w-full ${!genClassId ? "border-destructive/50" : ""}`}>
                    <SelectValue placeholder="Select class" />
                  </SelectTrigger>
                  <SelectContent>
                    {classes.map((cls) => (
                      <SelectItem key={cls.id} value={cls.id}>
                        {cls.name}
                        {cls.student_count !== undefined && (
                          <span className="ml-2 text-muted-foreground">
                            ({cls.student_count})
                          </span>
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex-1 space-y-2">
                <label className="text-sm font-medium flex items-center gap-2 h-5">
                  <Layers className="h-4 w-4 text-muted-foreground" />
                  Section
                </label>
                <Select
                  value={genSectionId}
                  onValueChange={setGenSectionId}
                  disabled={!genClassId || genSections.length === 0}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="All sections" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Sections</SelectItem>
                    {genSections.map((section) => (
                      <SelectItem key={section.id} value={section.id}>
                        {section.name}
                        {section.student_count !== undefined && (
                          <span className="ml-2 text-muted-foreground">
                            ({section.student_count})
                          </span>
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Preview */}
            {genClassId && (
              <div className="rounded-lg border bg-muted/50 p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm">
                    <Users className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">Reports to generate:</span>
                  </div>
                  <Badge variant="secondary" className="text-base px-3">
                    {genStudentCount} student{genStudentCount !== 1 ? "s" : ""}
                  </Badge>
                </div>
              </div>
            )}

            {!genClassId && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <AlertCircle className="h-4 w-4" />
                Select a class to see how many reports will be generated
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setGenerateDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleGenerateReports}
              disabled={isGenerating || !genClassId || !genYearId || !genTermId}
            >
              {isGenerating ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <FileText className="mr-2 h-4 w-4" />
              )}
              Generate {genStudentCount > 0 ? `${genStudentCount} Reports` : "Reports"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Publish Confirmation Dialog */}
      <AlertDialog open={publishDialogOpen} onOpenChange={setPublishDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Publish Report Cards?</AlertDialogTitle>
            <AlertDialogDescription>
              This will publish all {stats.draft} draft report card(s)
              {selectedClassId ? ` for ${classes.find(c => c.id === selectedClassId)?.name}` : ""}
              {" "}and make them visible to parents. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handlePublishReports} disabled={isPending}>
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Publish
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
