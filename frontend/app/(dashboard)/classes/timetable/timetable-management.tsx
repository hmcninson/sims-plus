"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  Calendar,
  Clock,
  Plus,
  Pencil,
  Trash2,
  BookOpen,
  Users,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Save,
  MapPin,
  ChevronsUpDown,
  Check,
  Settings,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import { getClassTimetable, createTimetableEntry, updateTimetableEntry, deleteTimetableEntry, bulkUpdateTimetable, getSchoolPeriods } from "@/actions/timetable.action";
import { getSections, getTerms } from "@/actions/academic.action";
import type {
  Class,
  ClassSection,
  AcademicYear,
  Term,
  Subject,
  StaffListItem,
  TimetableEntry,
  TimetableWeek,
  TimetableEntryCreate,
  TimetableEntryUpdate,
  DayOfWeek,
  DAY_NAMES,
  SchoolPeriod,
} from "@/types";

const DAY_NAMES_CONST: Record<DayOfWeek, string> = {
  0: "Monday",
  1: "Tuesday",
  2: "Wednesday",
  3: "Thursday",
  4: "Friday",
  5: "Saturday",
  6: "Sunday",
};

// Default period templates (used as fallback when no periods are configured)
const DEFAULT_PERIODS = [
  { period: 1, start: "08:00", end: "08:45", name: null, is_break: false },
  { period: 2, start: "08:45", end: "09:30", name: null, is_break: false },
  { period: 3, start: "09:30", end: "10:15", name: null, is_break: false },
  { period: 4, start: "10:30", end: "11:15", name: null, is_break: false },
  { period: 5, start: "11:15", end: "12:00", name: null, is_break: false },
  { period: 6, start: "12:00", end: "12:45", name: null, is_break: false },
  { period: 7, start: "14:00", end: "14:45", name: null, is_break: false },
  { period: 8, start: "14:45", end: "15:30", name: null, is_break: false },
];

// Transform SchoolPeriod to display format
function transformPeriods(schoolPeriods: SchoolPeriod[]) {
  if (schoolPeriods.length === 0) {
    return DEFAULT_PERIODS;
  }
  return schoolPeriods
    .filter(p => !p.is_break) // Exclude break periods from timetable grid
    .map(p => ({
      period: p.period_number,
      start: p.start_time,
      end: p.end_time,
      name: p.name,
      is_break: p.is_break,
    }))
    .sort((a, b) => a.period - b.period);
}

interface TimetableManagementProps {
  classes: Class[];
  academicYears: AcademicYear[];
  subjects: Subject[];
  teachers: StaffListItem[];
  defaultPeriods: SchoolPeriod[];  // School-wide periods as default
  defaultAcademicYearId?: string;
}

export function TimetableManagement({
  classes,
  academicYears,
  subjects,
  teachers,
  defaultPeriods,
  defaultAcademicYearId,
}: TimetableManagementProps) {
  const router = useRouter();

  // Store defaultPeriods in a ref to avoid re-render triggers
  const defaultPeriodsRef = useRef<SchoolPeriod[]>(defaultPeriods);

  // Track if we're in the middle of a class change to prevent second effect from running
  const isClassChangeInProgressRef = useRef(false);

  // Periods state - will be updated when class/section changes
  const [schoolPeriods, setSchoolPeriods] = useState<SchoolPeriod[]>(defaultPeriods);

  // Transform school periods to display format (memoized to avoid recalculation on every render)
  const periods = useMemo(() => transformPeriods(schoolPeriods), [schoolPeriods]);

  // Selection state
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [selectedAcademicYearId, setSelectedAcademicYearId] = useState<string>(
    defaultAcademicYearId || ""
  );
  const [selectedTermId, setSelectedTermId] = useState<string | null>(null); // null = year-wide timetable
  const [classComboboxOpen, setClassComboboxOpen] = useState(false);
  const [subjectComboboxOpen, setSubjectComboboxOpen] = useState(false);
  const [teacherComboboxOpen, setTeacherComboboxOpen] = useState(false);

  // Data state
  const [sections, setSections] = useState<ClassSection[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);
  const [timetable, setTimetable] = useState<TimetableWeek | null>(null);
  const [loading, setLoading] = useState(false);
  const [sectionsLoading, setSectionsLoading] = useState(false);
  const [termsLoading, setTermsLoading] = useState(false);

  // Dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<TimetableEntry | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<{ day: DayOfWeek; period: number } | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    subject_id: "",
    teacher_id: "",
    start_time: "",
    end_time: "",
    room: "",
    notes: "",
  });
  const [saving, setSaving] = useState(false);

  // Load terms when academic year changes
  useEffect(() => {
    async function loadTerms() {
      if (!selectedAcademicYearId) {
        setTerms([]);
        setSelectedTermId(null);
        return;
      }

      setTermsLoading(true);
      const result = await getTerms(selectedAcademicYearId);
      if (result.success && result.data) {
        setTerms(result.data);
        // Default to year-wide timetable (no term selected)
        setSelectedTermId(null);
      } else {
        setTerms([]);
        setSelectedTermId(null);
      }
      setTermsLoading(false);
    }

    loadTerms();
  }, [selectedAcademicYearId]);

  // Track request IDs to cancel stale requests
  const requestIdRef = useRef(0);

  // Load sections, periods, and timetable when class changes
  // This is a single sequential flow to avoid race conditions
  useEffect(() => {
    // Mark that we're handling a class change - prevents second effect from running
    isClassChangeInProgressRef.current = true;

    // Increment request ID to invalidate any in-flight requests
    const currentRequestId = ++requestIdRef.current;

    // Clear data immediately
    setSections([]);
    setSelectedSectionId(null);
    setTimetable(null);

    if (!selectedClassId) {
      setSectionsLoading(false);
      setLoading(false);
      // Reset to default periods when no class selected
      setSchoolPeriods(defaultPeriodsRef.current);
      isClassChangeInProgressRef.current = false;
      return;
    }

    setSectionsLoading(true);

    async function loadSectionsPeriodsAndTimetable() {
      try {
        // Step 1: Load sections and periods in parallel
        const [sectionsResult, periodsResult] = await Promise.all([
          getSections(selectedClassId),
          getSchoolPeriods(selectedClassId), // Get class-specific periods (with hierarchy fallback)
        ]);

        // Check if this request is still valid
        if (requestIdRef.current !== currentRequestId) {
          return; // Abort - a newer request was started
        }

        // Handle periods
        if (periodsResult.success && periodsResult.data) {
          setSchoolPeriods(periodsResult.data);
        } else {
          setSchoolPeriods(defaultPeriodsRef.current);
        }

        let loadedSections: ClassSection[] = [];
        let selectedSection: string | null = null;

        if (sectionsResult.success && sectionsResult.data) {
          loadedSections = sectionsResult.data;
          // Auto-select first section if available
          if (loadedSections.length > 0) {
            selectedSection = loadedSections[0].id;
          }
          setSections(loadedSections);
          setSelectedSectionId(selectedSection);
        }
        setSectionsLoading(false);

        // Check again if this request is still valid
        if (requestIdRef.current !== currentRequestId) {
          return;
        }

        // Step 2: If section was selected, check for section-specific periods
        if (selectedSection) {
          const sectionPeriodsResult = await getSchoolPeriods(selectedClassId, selectedSection);
          if (requestIdRef.current !== currentRequestId) return;

          if (sectionPeriodsResult.success && sectionPeriodsResult.data && sectionPeriodsResult.data.length > 0) {
            // Section has its own periods, use them
            setSchoolPeriods(sectionPeriodsResult.data);
          }
          // Otherwise keep class/school-wide periods already loaded
        }

        // Step 3: Load timetable (only if we have academic year)
        if (!selectedAcademicYearId) {
          return;
        }

        setLoading(true);
        const timetableResult = await getClassTimetable(
          selectedClassId,
          selectedAcademicYearId,
          selectedSection || undefined,
          selectedTermId || undefined
        );

        // Final check if this request is still valid
        if (requestIdRef.current !== currentRequestId) {
          setLoading(false);
          return;
        }

        if (timetableResult.success && timetableResult.data) {
          setTimetable(timetableResult.data);
        } else {
          setTimetable(null);
          if (timetableResult.error) {
            toast.error(timetableResult.error);
          }
        }
        setLoading(false);
      } finally {
        // Mark class change as complete
        isClassChangeInProgressRef.current = false;
      }
    }

    loadSectionsPeriodsAndTimetable();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedClassId]); // Only depend on classId - defaultPeriods is stored in ref

  // Load periods and timetable when section, term, or academic year changes (but NOT class)
  useEffect(() => {
    // Skip if class change is in progress - that effect handles everything
    if (isClassChangeInProgressRef.current) {
      return;
    }

    // Skip if no class selected or sections are loading
    if (!selectedClassId || !selectedAcademicYearId || sectionsLoading) {
      return;
    }

    // Skip initial load (handled by the class change effect above)
    // We only want to reload when section/term/year changes AFTER initial load
    if (sections.length === 0 && !selectedSectionId) {
      return;
    }

    const currentRequestId = ++requestIdRef.current;

    async function loadPeriodsAndTimetable() {
      setLoading(true);

      // Load periods for the current class/section (uses hierarchy fallback)
      const periodsResult = await getSchoolPeriods(selectedClassId, selectedSectionId || undefined);
      if (requestIdRef.current !== currentRequestId) {
        setLoading(false);
        return;
      }

      if (periodsResult.success && periodsResult.data) {
        setSchoolPeriods(periodsResult.data);
      }

      // Load timetable
      const result = await getClassTimetable(
        selectedClassId,
        selectedAcademicYearId,
        selectedSectionId || undefined,
        selectedTermId || undefined
      );

      if (requestIdRef.current !== currentRequestId) {
        setLoading(false);
        return;
      }

      if (result.success && result.data) {
        setTimetable(result.data);
      } else {
        setTimetable(null);
        if (result.error) {
          toast.error(result.error);
        }
      }
      setLoading(false);
    }

    loadPeriodsAndTimetable();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSectionId, selectedTermId, selectedAcademicYearId]); // Intentionally exclude selectedClassId

  // Manual refresh function for use after edits
  const refreshTimetable = useCallback(async () => {
    if (!selectedClassId || !selectedAcademicYearId) return;

    setLoading(true);
    const result = await getClassTimetable(
      selectedClassId,
      selectedAcademicYearId,
      selectedSectionId || undefined,
      selectedTermId || undefined
    );

    if (result.success && result.data) {
      setTimetable(result.data);
    } else {
      setTimetable(null);
    }
    setLoading(false);
  }, [selectedClassId, selectedAcademicYearId, selectedSectionId, selectedTermId]);

  // Create a lookup map for fast entry retrieval (memoized)
  const entryMap = useMemo(() => {
    const map = new Map<string, TimetableEntry>();
    if (timetable) {
      for (const dayData of timetable.days) {
        for (const entry of dayData.entries) {
          map.set(`${dayData.day_of_week}-${entry.period_number}`, entry);
        }
      }
    }
    return map;
  }, [timetable]);

  // Get entry for a specific slot (using memoized map)
  const getEntryForSlot = useCallback((day: DayOfWeek, period: number): TimetableEntry | undefined => {
    return entryMap.get(`${day}-${period}`);
  }, [entryMap]);

  // Handle slot click (memoized to prevent unnecessary re-renders)
  const handleSlotClick = useCallback((day: DayOfWeek, period: number) => {
    const entry = getEntryForSlot(day, period);
    const periodTemplate = periods.find((p) => p.period === period);

    if (entry) {
      setSelectedEntry(entry);
      setFormData({
        subject_id: entry.subject_id || "",
        teacher_id: entry.teacher_id || "",
        start_time: entry.start_time,
        end_time: entry.end_time,
        room: entry.room || "",
        notes: entry.notes || "",
      });
    } else {
      setSelectedEntry(null);
      setFormData({
        subject_id: "",
        teacher_id: "",
        start_time: periodTemplate?.start || "08:00",
        end_time: periodTemplate?.end || "08:45",
        room: "",
        notes: "",
      });
    }
    setSelectedSlot({ day, period });
    setEditDialogOpen(true);
  }, [getEntryForSlot, periods]);

  // Handle save entry
  const handleSaveEntry = async () => {
    if (!selectedSlot || !selectedClassId || !selectedAcademicYearId) return;

    setSaving(true);
    try {
      if (selectedEntry) {
        // Update existing entry
        const updateData: TimetableEntryUpdate = {
          subject_id: formData.subject_id || undefined,
          teacher_id: formData.teacher_id || undefined,
          start_time: formData.start_time,
          end_time: formData.end_time,
          room: formData.room || undefined,
          notes: formData.notes || undefined,
        };
        const result = await updateTimetableEntry(selectedEntry.id, updateData);
        if (result.success) {
          toast.success("Timetable entry updated");
          refreshTimetable();
        } else {
          toast.error(result.error || "Failed to update entry");
        }
      } else {
        // Create new entry
        const createData: TimetableEntryCreate = {
          class_id: selectedClassId,
          section_id: selectedSectionId || undefined,
          academic_year_id: selectedAcademicYearId,
          term_id: selectedTermId || undefined,
          day_of_week: selectedSlot.day,
          period_number: selectedSlot.period,
          subject_id: formData.subject_id || undefined,
          teacher_id: formData.teacher_id || undefined,
          start_time: formData.start_time,
          end_time: formData.end_time,
          room: formData.room || undefined,
          notes: formData.notes || undefined,
        };
        const result = await createTimetableEntry(createData);
        if (result.success) {
          toast.success("Timetable entry created");
          refreshTimetable();
        } else {
          toast.error(result.error || "Failed to create entry");
        }
      }
      setEditDialogOpen(false);
    } catch {
      toast.error("An error occurred");
    } finally {
      setSaving(false);
    }
  };

  // Handle delete entry
  const handleDeleteEntry = async () => {
    if (!selectedEntry) return;

    setSaving(true);
    try {
      const result = await deleteTimetableEntry(selectedEntry.id);
      if (result.success) {
        toast.success("Timetable entry deleted");
        refreshTimetable();
      } else {
        toast.error(result.error || "Failed to delete entry");
      }
      setDeleteDialogOpen(false);
      setEditDialogOpen(false);
    } catch {
      toast.error("An error occurred");
    } finally {
      setSaving(false);
    }
  };

  // Memoize selected items to avoid recalculating on every render
  const selectedClass = useMemo(() => classes.find((c) => c.id === selectedClassId), [classes, selectedClassId]);
  const selectedSection = useMemo(() => sections.find((s) => s.id === selectedSectionId), [sections, selectedSectionId]);
  const selectedTerm = useMemo(() => terms.find((t) => t.id === selectedTermId), [terms, selectedTermId]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Class Timetable</h1>
          <p className="text-muted-foreground">
            Manage weekly class schedules and period assignments
          </p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link href="/settings/academic?tab=timetable">
            <Settings className="mr-2 h-4 w-4" />
            Configure Periods
          </Link>
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Select Class</CardTitle>
          <CardDescription>Choose a class and academic year to view or edit the timetable</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 w-full">
            {/* Academic Year */}
            <div className="space-y-2 min-w-0">
              <Label>Academic Year</Label>
              <Select
                value={selectedAcademicYearId}
                onValueChange={setSelectedAcademicYearId}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select year" />
                </SelectTrigger>
                <SelectContent>
                  {academicYears.map((year) => (
                    <SelectItem key={year.id} value={year.id}>
                      {year.name}
                      {year.is_current && " (Current)"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Class - Searchable Combobox */}
            <div className="space-y-2 min-w-0">
              <Label>Class</Label>
              <Popover open={classComboboxOpen} onOpenChange={setClassComboboxOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={classComboboxOpen}
                    className="w-full justify-between font-normal"
                  >
                    <span className="truncate">
                      {selectedClassId
                        ? classes.find((cls) => cls.id === selectedClassId)?.name
                        : "Select class..."}
                    </span>
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                  <Command>
                    <CommandInput placeholder="Search class..." />
                    <CommandList>
                      <CommandEmpty>No class found.</CommandEmpty>
                      <CommandGroup>
                        {classes.map((cls) => (
                          <CommandItem
                            key={cls.id}
                            value={cls.name}
                            onSelect={() => {
                              setSelectedClassId(cls.id);
                              setClassComboboxOpen(false);
                            }}
                          >
                            <Check
                              className={cn(
                                "mr-2 h-4 w-4",
                                selectedClassId === cls.id ? "opacity-100" : "opacity-0"
                              )}
                            />
                            {cls.name}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            {/* Section */}
            <div className="space-y-2 min-w-0">
              <Label>Section</Label>
              <Select
                value={selectedSectionId || "all"}
                onValueChange={(v) => setSelectedSectionId(v === "all" ? null : v)}
                disabled={sectionsLoading || sections.length === 0}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={sectionsLoading ? "Loading..." : "Select section"} />
                </SelectTrigger>
                <SelectContent>
                  {sections.length === 0 ? (
                    <SelectItem value="all">No sections</SelectItem>
                  ) : (
                    sections.map((section) => (
                      <SelectItem key={section.id} value={section.id}>
                        {section.name}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>

            {/* Term (Optional) */}
            <div className="space-y-2 min-w-0">
              <Label>Term (Optional)</Label>
              <Select
                value={selectedTermId || "year-wide"}
                onValueChange={(v) => setSelectedTermId(v === "year-wide" ? null : v)}
                disabled={termsLoading || !selectedAcademicYearId}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={termsLoading ? "Loading..." : "Select term"} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="year-wide">Year-wide (all terms)</SelectItem>
                  {terms.map((term) => (
                    <SelectItem key={term.id} value={term.id}>
                      {term.name}
                      {term.is_current && " (Current)"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Leave as &quot;Year-wide&quot; for a timetable that applies all year
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Timetable Grid */}
      {selectedClassId && selectedAcademicYearId ? (
        loading ? (
          <Card>
            <CardContent className="p-6">
              <div className="space-y-4">
                <Skeleton className="h-8 w-48" />
                <div className="grid grid-cols-6 gap-2">
                  {Array.from({ length: 48 }).map((_, i) => (
                    <Skeleton key={i} className="h-20" />
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>
                    {selectedClass?.name}
                    {selectedSection && ` - Section ${selectedSection.name}`}
                  </CardTitle>
                  <CardDescription>
                    {timetable?.term_name ? (
                      <span className="font-medium text-primary">{timetable.term_name}</span>
                    ) : (
                      <span className="font-medium text-muted-foreground">Year-wide timetable</span>
                    )}
                    {" "}&bull; Click on any slot to add or edit a period
                  </CardDescription>
                </div>
                {timetable && (
                  <Badge variant="secondary">
                    {timetable.total_periods} periods scheduled
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <th className="border bg-muted p-2 text-left text-sm font-medium">
                        Period
                      </th>
                      {([0, 1, 2, 3, 4] as DayOfWeek[]).map((day) => (
                        <th
                          key={day}
                          className="border bg-muted p-2 text-center text-sm font-medium min-w-[140px]"
                        >
                          {DAY_NAMES_CONST[day]}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {periods.map(({ period, start, end, name }) => (
                      <tr key={period}>
                        <td className="border bg-muted/50 p-2 text-sm">
                          <div className="font-medium">{name || `Period ${period}`}</div>
                          <div className="text-xs text-muted-foreground">
                            {start} - {end}
                          </div>
                        </td>
                        {([0, 1, 2, 3, 4] as DayOfWeek[]).map((day) => {
                          const entry = getEntryForSlot(day, period);
                          return (
                            <td
                              key={day}
                              className="border p-1 cursor-pointer hover:bg-muted/50 transition-colors"
                              onClick={() => handleSlotClick(day, period)}
                            >
                              {entry ? (
                                <div className="rounded bg-primary/10 p-2 min-h-[60px]">
                                  <div className="font-medium text-sm">
                                    {entry.subject?.name || "No Subject"}
                                  </div>
                                  {entry.teacher && (
                                    <div className="text-xs text-muted-foreground mt-1">
                                      {entry.teacher.first_name} {entry.teacher.last_name}
                                    </div>
                                  )}
                                  {entry.room && (
                                    <div className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                                      <MapPin className="h-3 w-3" />
                                      {entry.room}
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <div className="min-h-[60px] flex items-center justify-center text-muted-foreground/50">
                                  <Plus className="h-4 w-4" />
                                </div>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Calendar className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No Class Selected</h3>
            <p className="text-sm text-muted-foreground">
              Select a class and academic year to view the timetable
            </p>
          </CardContent>
        </Card>
      )}

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>
              {selectedEntry ? "Edit Period" : "Add Period"}
            </DialogTitle>
            <DialogDescription>
              {selectedSlot && (
                <>
                  {DAY_NAMES_CONST[selectedSlot.day]}, Period {selectedSlot.period}
                </>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {/* Subject - Searchable Combobox */}
            <div className="space-y-2">
              <Label htmlFor="subject">Subject</Label>
              <Popover open={subjectComboboxOpen} onOpenChange={setSubjectComboboxOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={subjectComboboxOpen}
                    className="w-full justify-between font-normal"
                  >
                    <span className="truncate">
                      {formData.subject_id
                        ? subjects.find((s) => s.id === formData.subject_id)?.name || "Select subject..."
                        : "No subject (Free period)"}
                    </span>
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                  <Command>
                    <CommandInput placeholder="Search subject..." />
                    <CommandList>
                      <CommandEmpty>No subject found.</CommandEmpty>
                      <CommandGroup>
                        <CommandItem
                          value="no-subject-free-period"
                          onSelect={() => {
                            setFormData({ ...formData, subject_id: "" });
                            setSubjectComboboxOpen(false);
                          }}
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              !formData.subject_id ? "opacity-100" : "opacity-0"
                            )}
                          />
                          No subject (Free period)
                        </CommandItem>
                        {subjects.map((subject) => (
                          <CommandItem
                            key={subject.id}
                            value={`${subject.name} ${subject.code}`}
                            onSelect={() => {
                              setFormData({ ...formData, subject_id: subject.id });
                              setSubjectComboboxOpen(false);
                            }}
                          >
                            <Check
                              className={cn(
                                "mr-2 h-4 w-4",
                                formData.subject_id === subject.id ? "opacity-100" : "opacity-0"
                              )}
                            />
                            {subject.name} ({subject.code})
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            {/* Teacher - Searchable Combobox */}
            <div className="space-y-2">
              <Label htmlFor="teacher">Teacher</Label>
              <Popover open={teacherComboboxOpen} onOpenChange={setTeacherComboboxOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={teacherComboboxOpen}
                    className="w-full justify-between font-normal"
                  >
                    <span className="truncate">
                      {formData.teacher_id
                        ? (() => {
                            const teacher = teachers.find((t) => t.id === formData.teacher_id);
                            return teacher ? `${teacher.first_name} ${teacher.last_name}` : "Select teacher...";
                          })()
                        : "No teacher assigned"}
                    </span>
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
                  <Command>
                    <CommandInput placeholder="Search teacher..." />
                    <CommandList>
                      <CommandEmpty>No teacher found.</CommandEmpty>
                      <CommandGroup>
                        <CommandItem
                          value="no-teacher-assigned"
                          onSelect={() => {
                            setFormData({ ...formData, teacher_id: "" });
                            setTeacherComboboxOpen(false);
                          }}
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              !formData.teacher_id ? "opacity-100" : "opacity-0"
                            )}
                          />
                          No teacher assigned
                        </CommandItem>
                        {teachers.map((teacher) => (
                          <CommandItem
                            key={teacher.id}
                            value={`${teacher.first_name} ${teacher.last_name}`}
                            onSelect={() => {
                              setFormData({ ...formData, teacher_id: teacher.id });
                              setTeacherComboboxOpen(false);
                            }}
                          >
                            <Check
                              className={cn(
                                "mr-2 h-4 w-4",
                                formData.teacher_id === teacher.id ? "opacity-100" : "opacity-0"
                              )}
                            />
                            {teacher.first_name} {teacher.last_name}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            </div>

            {/* Time */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="start_time">Start Time</Label>
                <Input
                  id="start_time"
                  type="time"
                  value={formData.start_time}
                  onChange={(e) =>
                    setFormData({ ...formData, start_time: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="end_time">End Time</Label>
                <Input
                  id="end_time"
                  type="time"
                  value={formData.end_time}
                  onChange={(e) =>
                    setFormData({ ...formData, end_time: e.target.value })
                  }
                />
              </div>
            </div>

            {/* Room */}
            <div className="space-y-2">
              <Label htmlFor="room">Room / Venue</Label>
              <Input
                id="room"
                placeholder="e.g., Room 101, Lab A"
                value={formData.room}
                onChange={(e) => setFormData({ ...formData, room: e.target.value })}
              />
            </div>

            {/* Notes */}
            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                placeholder="Additional notes..."
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                rows={2}
              />
            </div>
          </div>

          <DialogFooter className="flex justify-between">
            {selectedEntry && (
              <Button
                variant="destructive"
                onClick={() => setDeleteDialogOpen(true)}
                disabled={saving}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </Button>
            )}
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleSaveEntry} disabled={saving}>
                {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {selectedEntry ? "Update" : "Add"}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Period</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this period from the timetable? This action
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteEntry}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {saving && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
