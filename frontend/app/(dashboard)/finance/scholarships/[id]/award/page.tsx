"use client";

import { useEffect, useState, useTransition, useCallback, useRef, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
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
import { Label } from "@/components/ui/label";
import {
  ArrowLeft,
  Search,
  Loader2,
  AlertCircle,
  Award,
  Users,
  Calendar,
  GraduationCap,
  CalendarRange,
} from "lucide-react";
import {
  getScholarship,
  getScholarshipRecipients,
  awardScholarship,
  bulkAwardScholarship,
} from "@/actions/finance.action";
import { getStudents } from "@/actions/students.action";
import { getClasses, getAcademicYears, getTerms } from "@/actions/academic.action";
import type { StudentListItem, Class, AcademicYear, Term } from "@/types";
import type { Scholarship, StudentScholarshipWithDetails } from "@/types/finance.type";
import { formatCurrency } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";

// ============================================
// Types
// ============================================

type DurationType = "specific_term" | "end_of_year" | "until_completion";

// ============================================
// Main Component
// ============================================

export default function AwardScholarshipPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const [isPending, startTransition] = useTransition();
  const [isAwarding, setIsAwarding] = useState(false);
  const hasLoadedRef = useRef(false);

  // Data state
  const [scholarship, setScholarship] = useState<Scholarship | null>(null);
  const [recipients, setRecipients] = useState<StudentScholarshipWithDetails[]>([]);
  const [students, setStudents] = useState<StudentListItem[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [selectedClass, setSelectedClass] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStudents, setSelectedStudents] = useState<string[]>([]);

  // Award settings - Term based
  const [startYearId, setStartYearId] = useState<string>("");
  const [startTermId, setStartTermId] = useState<string>("");
  const [durationType, setDurationType] = useState<DurationType>("end_of_year");
  const [endYearId, setEndYearId] = useState<string>("");
  const [endTermId, setEndTermId] = useState<string>("");

  // Other award settings
  const [notes, setNotes] = useState("");
  const [coverageOverride, setCoverageOverride] = useState("");
  const [justification, setJustification] = useState("");
  const [isProvisional, setIsProvisional] = useState(false);
  const [provisionalConditions, setProvisionalConditions] = useState("");

  // Search state
  const [isSearching, setIsSearching] = useState(false);
  const [debouncedSearch, setDebouncedSearch] = useState("");

  const scholarshipId = params.id as string;

  // Load initial data on mount
  useEffect(() => {
    if (hasLoadedRef.current) return;
    hasLoadedRef.current = true;

    startTransition(async () => {
      const [scholarshipResult, recipientsResult, classesResult, yearsResult, termsResult] =
        await Promise.all([
          getScholarship(scholarshipId),
          getScholarshipRecipients(scholarshipId),
          getClasses(),
          getAcademicYears(),
          getTerms(),
        ]);

      if (scholarshipResult.success && scholarshipResult.data) {
        setScholarship(scholarshipResult.data);
      } else {
        setError(scholarshipResult.error || "Failed to load scholarship");
        return;
      }

      if (recipientsResult.success && recipientsResult.data) {
        setRecipients(recipientsResult.data.items);
      }

      if (classesResult.success && classesResult.data) {
        setClasses(classesResult.data);
      }

      if (yearsResult.success && yearsResult.data) {
        setAcademicYears(yearsResult.data);
        // Set default to current academic year
        const currentYear = yearsResult.data.find((y) => y.is_current);
        if (currentYear) {
          setStartYearId(currentYear.id);
          setEndYearId(currentYear.id);
        }
      }

      if (termsResult.success && termsResult.data) {
        setTerms(termsResult.data);
        // Set default to current term
        const currentTerm = termsResult.data.find((t) => t.is_current);
        if (currentTerm) {
          setStartTermId(currentTerm.id);
        }
      }
    });
  }, [scholarshipId]);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch students when search changes
  useEffect(() => {
    if (!debouncedSearch || debouncedSearch.length < 2) {
      setStudents([]);
      return;
    }

    const fetchStudents = async () => {
      setIsSearching(true);
      try {
        const filters: {
          status: string;
          page_size: number;
          class_id?: string;
          search: string;
        } = {
          status: "active",
          page_size: 50,
          search: debouncedSearch,
        };

        if (selectedClass !== "all") {
          filters.class_id = selectedClass;
        }

        const result = await getStudents(filters);
        if (result.success && result.data) {
          setStudents(result.data.items);
        }
      } finally {
        setIsSearching(false);
      }
    };

    fetchStudents();
  }, [selectedClass, debouncedSearch]);

  // Filter terms by selected year
  const startYearTerms = useMemo(() => {
    return terms.filter((t) => t.academic_year_id === startYearId);
  }, [terms, startYearId]);

  const endYearTerms = useMemo(() => {
    return terms.filter((t) => t.academic_year_id === endYearId);
  }, [terms, endYearId]);

  // Get term date helper
  const getTermStartDate = useCallback((termId: string): string => {
    const term = terms.find((t) => t.id === termId);
    return term?.start_date || new Date().toISOString().split("T")[0];
  }, [terms]);

  const getTermEndDate = useCallback((termId: string): string => {
    const term = terms.find((t) => t.id === termId);
    return term?.end_date || "";
  }, [terms]);

  // Existing recipient IDs
  const existingRecipientIds = useMemo(() => {
    return recipients.filter((r) => r.status === "active").map((r) => r.student_id);
  }, [recipients]);

  // Filter out students who already have this scholarship
  const eligibleStudents = useMemo(() => {
    return students.filter((s) => !existingRecipientIds.includes(s.id));
  }, [students, existingRecipientIds]);

  // Handlers
  const handleSelectAll = useCallback(() => {
    if (selectedStudents.length === eligibleStudents.length) {
      setSelectedStudents([]);
    } else {
      setSelectedStudents(eligibleStudents.map((s) => s.id));
    }
  }, [selectedStudents.length, eligibleStudents]);

  const handleToggleStudent = useCallback((studentId: string) => {
    setSelectedStudents((prev) =>
      prev.includes(studentId)
        ? prev.filter((id) => id !== studentId)
        : [...prev, studentId]
    );
  }, []);

  const handleAward = useCallback(async () => {
    if (selectedStudents.length === 0) {
      toast({
        title: "No students selected",
        description: "Please select at least one student to award.",
        variant: "destructive",
      });
      return;
    }

    if (!startYearId || !startTermId) {
      toast({
        title: "Missing start period",
        description: "Please select the starting academic year and term.",
        variant: "destructive",
      });
      return;
    }

    if (durationType === "specific_term" && (!endYearId || !endTermId)) {
      toast({
        title: "Missing end period",
        description: "Please select the ending academic year and term.",
        variant: "destructive",
      });
      return;
    }

    // Check max recipients
    if (scholarship?.max_recipients) {
      const activeCount = recipients.filter((r) => r.status === "active").length;
      const remainingSlots = scholarship.max_recipients - activeCount;
      if (selectedStudents.length > remainingSlots) {
        toast({
          title: "Too many students selected",
          description: `Only ${remainingSlots} slots remaining for this scholarship.`,
          variant: "destructive",
        });
        return;
      }
    }

    setIsAwarding(true);

    try {
      // Calculate effective dates from term selection
      const effectiveFrom = getTermStartDate(startTermId);
      let effectiveTo: string | undefined;
      let renewalType: string;

      switch (durationType) {
        case "specific_term":
          effectiveTo = getTermEndDate(endTermId);
          renewalType = "one_time";
          break;
        case "end_of_year":
          // Get the last term of the start year
          const yearTerms = terms.filter((t) => t.academic_year_id === startYearId);
          const lastTerm = yearTerms.sort((a, b) =>
            new Date(b.end_date).getTime() - new Date(a.end_date).getTime()
          )[0];
          effectiveTo = lastTerm?.end_date;
          renewalType = "annual";
          break;
        case "until_completion":
          effectiveTo = undefined;
          renewalType = "until_graduation";
          break;
        default:
          renewalType = "one_time";
      }

      const awardData = {
        effective_from: effectiveFrom,
        effective_to: effectiveTo,
        notes: notes || undefined,
        coverage_override: coverageOverride ? parseFloat(coverageOverride) : undefined,
        justification: justification || undefined,
        renewal_type: renewalType,
        is_provisional: isProvisional,
        provisional_conditions: isProvisional ? provisionalConditions || undefined : undefined,
      };

      if (selectedStudents.length === 1) {
        const result = await awardScholarship(scholarshipId, {
          student_id: selectedStudents[0],
          academic_year_id: startYearId,
          ...awardData,
        });

        if (result.success) {
          toast({
            title: "Scholarship awarded",
            description: "Successfully awarded scholarship to the student.",
          });
          router.push(`/finance/scholarships/${scholarshipId}`);
        } else {
          toast({
            title: "Error",
            description: result.error || "Failed to award scholarship",
            variant: "destructive",
          });
        }
      } else {
        const result = await bulkAwardScholarship(scholarshipId, {
          student_ids: selectedStudents,
          academic_year_id: startYearId,
          ...awardData,
        });

        if (result.success && result.data) {
          const { awarded, skipped, failed } = result.data;

          if (awarded > 0) {
            toast({
              title: "Scholarships awarded",
              description: `Successfully awarded to ${awarded} student(s).${skipped > 0 ? ` ${skipped} skipped.` : ""}${failed > 0 ? ` ${failed} failed.` : ""}`,
            });
            router.push(`/finance/scholarships/${scholarshipId}`);
          } else {
            toast({
              title: "No scholarships awarded",
              description: result.data.errors?.join(", ") || "All students were skipped or failed",
              variant: "destructive",
            });
          }
        } else {
          toast({
            title: "Error",
            description: result.error || "Failed to award scholarships",
            variant: "destructive",
          });
        }
      }
    } finally {
      setIsAwarding(false);
    }
  }, [
    selectedStudents,
    startYearId,
    startTermId,
    durationType,
    endYearId,
    endTermId,
    scholarship,
    recipients,
    terms,
    notes,
    coverageOverride,
    justification,
    isProvisional,
    provisionalConditions,
    scholarshipId,
    toast,
    router,
    getTermStartDate,
    getTermEndDate,
  ]);

  // Loading state
  if (isPending && !scholarship) {
    return (
      <div className="flex h-[400px] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <p className="text-muted-foreground">{error}</p>
        <Button onClick={() => router.push("/finance/scholarships")}>
          Back to Scholarships
        </Button>
      </div>
    );
  }

  if (!scholarship) return null;

  const activeRecipients = recipients.filter((r) => r.status === "active");
  const remainingSlots = scholarship.max_recipients
    ? scholarship.max_recipients - activeRecipients.length
    : null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href={`/finance/scholarships/${scholarshipId}`}>
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Award: {scholarship.name}
          </h1>
          <p className="text-muted-foreground">
            Select students to award this scholarship
          </p>
        </div>
      </div>

      {/* Scholarship Info */}
      <Card>
        <CardHeader>
          <CardTitle>Scholarship Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-4">
            <div>
              <Label className="text-muted-foreground">Coverage</Label>
              <p className="font-medium">
                {scholarship.coverage_type === "percentage"
                  ? `${scholarship.coverage_value}% of fees`
                  : formatCurrency(scholarship.coverage_value)}
              </p>
            </div>
            <div>
              <Label className="text-muted-foreground">Type</Label>
              <p className="font-medium capitalize">
                {scholarship.scholarship_type.replace("_", " ")}
              </p>
            </div>
            <div>
              <Label className="text-muted-foreground">Current Recipients</Label>
              <p className="font-medium">{activeRecipients.length}</p>
            </div>
            <div>
              <Label className="text-muted-foreground">Available Slots</Label>
              <p className="font-medium">
                {remainingSlots !== null ? remainingSlots : "Unlimited"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Award Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Award Settings</CardTitle>
          <CardDescription>
            Configure the award period and terms for selected students
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Effective From - Term Based */}
          <div className="space-y-4">
            <Label className="text-base font-semibold">Effective From *</Label>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="startYear">Academic Year</Label>
                <Select value={startYearId} onValueChange={setStartYearId}>
                  <SelectTrigger id="startYear" className="w-full">
                    <SelectValue placeholder="Select academic year" />
                  </SelectTrigger>
                  <SelectContent>
                    {academicYears.map((year) => (
                      <SelectItem key={year.id} value={year.id}>
                        <span className="flex items-center gap-2">
                          {year.name}
                          {year.is_current && (
                            <Badge variant="secondary" className="text-xs">Current</Badge>
                          )}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="startTerm">Term</Label>
                <Select
                  value={startTermId}
                  onValueChange={setStartTermId}
                  disabled={!startYearId}
                >
                  <SelectTrigger id="startTerm" className="w-full">
                    <SelectValue placeholder="Select term" />
                  </SelectTrigger>
                  <SelectContent>
                    {startYearTerms.map((term) => (
                      <SelectItem key={term.id} value={term.id}>
                        <span className="flex items-center gap-2">
                          {term.name}
                          {term.is_current && (
                            <Badge variant="secondary" className="text-xs">Current</Badge>
                          )}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          {/* Duration Type */}
          <div className="space-y-4">
            <Label className="text-base font-semibold">Duration</Label>
            <RadioGroup
              value={durationType}
              onValueChange={(value) => setDurationType(value as DurationType)}
              className="grid gap-3"
            >
              <div className="flex items-start space-x-3 rounded-lg border p-4">
                <RadioGroupItem value="specific_term" id="specific_term" className="mt-1" />
                <div className="flex-1">
                  <Label htmlFor="specific_term" className="flex items-center gap-2 font-medium cursor-pointer">
                    <CalendarRange className="h-4 w-4" />
                    Specific Term Range
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Scholarship is valid until a specific term ends
                  </p>

                  {durationType === "specific_term" && (
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <div className="space-y-2">
                        <Label htmlFor="endYear">End Academic Year</Label>
                        <Select value={endYearId} onValueChange={setEndYearId}>
                          <SelectTrigger id="endYear" className="w-full">
                            <SelectValue placeholder="Select academic year" />
                          </SelectTrigger>
                          <SelectContent>
                            {academicYears.map((year) => (
                              <SelectItem key={year.id} value={year.id}>
                                <span className="flex items-center gap-2">
                                  {year.name}
                                  {year.is_current && (
                                    <Badge variant="secondary" className="text-xs">Current</Badge>
                                  )}
                                </span>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="endTerm">End Term</Label>
                        <Select
                          value={endTermId}
                          onValueChange={setEndTermId}
                          disabled={!endYearId}
                        >
                          <SelectTrigger id="endTerm" className="w-full">
                            <SelectValue placeholder="Select term" />
                          </SelectTrigger>
                          <SelectContent>
                            {endYearTerms.map((term) => (
                              <SelectItem key={term.id} value={term.id}>
                                <span className="flex items-center gap-2">
                                  {term.name}
                                  {term.is_current && (
                                    <Badge variant="secondary" className="text-xs">Current</Badge>
                                  )}
                                </span>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-start space-x-3 rounded-lg border p-4">
                <RadioGroupItem value="end_of_year" id="end_of_year" className="mt-1" />
                <div>
                  <Label htmlFor="end_of_year" className="flex items-center gap-2 font-medium cursor-pointer">
                    <Calendar className="h-4 w-4" />
                    Until End of Academic Year
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Scholarship is valid until the end of the selected academic year (requires renewal each year)
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3 rounded-lg border p-4">
                <RadioGroupItem value="until_completion" id="until_completion" className="mt-1" />
                <div>
                  <Label htmlFor="until_completion" className="flex items-center gap-2 font-medium cursor-pointer">
                    <GraduationCap className="h-4 w-4" />
                    Until Completion
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    Scholarship continues until the student graduates, withdraws, or transfers
                  </p>
                </div>
              </div>
            </RadioGroup>
          </div>

          {/* Coverage Override */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="coverageOverride">Coverage Override (Optional)</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="coverageOverride"
                  type="number"
                  min="0"
                  step="0.01"
                  value={coverageOverride}
                  onChange={(e) => setCoverageOverride(e.target.value)}
                  placeholder={`Default: ${scholarship.coverage_value}${scholarship.coverage_type === "percentage" ? "%" : ""}`}
                />
                <span className="text-sm text-muted-foreground">
                  {scholarship.coverage_type === "percentage" ? "%" : "GHS"}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Override the default coverage value for these students
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="justification">Justification (Recommended)</Label>
              <Textarea
                id="justification"
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
                placeholder="Reason for awarding this scholarship..."
                rows={2}
              />
            </div>
          </div>

          {/* Provisional Settings */}
          <div className="space-y-4 rounded-lg border p-4">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="isProvisional"
                checked={isProvisional}
                onCheckedChange={(checked) => setIsProvisional(checked === true)}
              />
              <Label htmlFor="isProvisional" className="font-medium">
                Provisional/Conditional Award
              </Label>
            </div>
            <p className="text-sm text-muted-foreground">
              Mark this award as provisional if the student must meet certain conditions to retain it
            </p>

            {isProvisional && (
              <div className="space-y-2 pt-2">
                <Label htmlFor="provisionalConditions">Conditions to Maintain Award</Label>
                <Textarea
                  id="provisionalConditions"
                  value={provisionalConditions}
                  onChange={(e) => setProvisionalConditions(e.target.value)}
                  placeholder="e.g., Maintain minimum GPA of 3.0, Full attendance required..."
                  rows={2}
                />
              </div>
            )}
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <Label htmlFor="notes">Additional Notes (Optional)</Label>
            <Textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Any additional notes about this award..."
              rows={2}
            />
          </div>
        </CardContent>
      </Card>

      {/* Student Selection */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Select Students</CardTitle>
            <CardDescription>
              {selectedStudents.length} student(s) selected
            </CardDescription>
          </div>
          <Button onClick={handleAward} disabled={isAwarding || selectedStudents.length === 0}>
            {isAwarding && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            <Award className="mr-2 h-4 w-4" />
            Award to {selectedStudents.length} Student(s)
          </Button>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-col gap-4 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search by name or student ID (min 2 characters)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
              {isSearching && (
                <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
              )}
            </div>
            <Select value={selectedClass} onValueChange={setSelectedClass}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue placeholder="Filter by class" />
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

          {isSearching ? (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin" />
              <p>Searching students...</p>
            </div>
          ) : eligibleStudents.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[50px]">
                    <Checkbox
                      checked={
                        selectedStudents.length === eligibleStudents.length &&
                        eligibleStudents.length > 0
                      }
                      onCheckedChange={handleSelectAll}
                    />
                  </TableHead>
                  <TableHead>Student ID</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Class</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {eligibleStudents.map((student) => (
                  <TableRow key={student.id}>
                    <TableCell>
                      <Checkbox
                        checked={selectedStudents.includes(student.id)}
                        onCheckedChange={() => handleToggleStudent(student.id)}
                      />
                    </TableCell>
                    <TableCell className="font-mono text-sm">
                      {student.student_id}
                    </TableCell>
                    <TableCell className="font-medium">
                      {student.first_name} {student.last_name}
                    </TableCell>
                    <TableCell>{student.class_name || "-"}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{student.status}</Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <Users className="h-12 w-12" />
              <p>
                {searchQuery.length < 2
                  ? "Type at least 2 characters to search for students"
                  : students.length === 0
                    ? `No students found for "${searchQuery}"`
                    : "All matching students already have this scholarship"}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
