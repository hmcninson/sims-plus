"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Clock, Plus, Settings2, Trash2, Loader2, Coffee } from "lucide-react";
import {
  getSchoolPeriods,
  createSchoolPeriod,
  updateSchoolPeriod,
  deleteSchoolPeriod,
} from "@/actions/timetable.action";
import { getClasses, getSections } from "@/actions/academic.action";
import type { SchoolPeriod, SchoolPeriodCreate, SchoolPeriodUpdate, Class, ClassSection } from "@/types";

type PeriodLevel = "school" | "class" | "section";

export function SchoolPeriods() {
  const [periods, setPeriods] = useState<SchoolPeriod[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [sections, setSections] = useState<ClassSection[]>([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingPeriod, setEditingPeriod] = useState<SchoolPeriod | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [periodToDelete, setPeriodToDelete] = useState<SchoolPeriod | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Filter state
  const [selectedLevel, setSelectedLevel] = useState<PeriodLevel>("school");
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [selectedSectionId, setSelectedSectionId] = useState<string>("");

  // Form state
  const [formData, setFormData] = useState({
    period_number: 1,
    name: "",
    start_time: "08:00",
    end_time: "08:45",
    is_break: false,
  });

  // Memoized load functions to prevent recreation on each render
  const loadSections = useCallback(async (classId: string) => {
    const result = await getSections(classId);
    if (result.success && result.data) {
      setSections(result.data);
    } else {
      setSections([]);
    }
  }, []);

  const loadPeriods = useCallback(async (level: PeriodLevel, classId: string, sectionId: string) => {
    let queryClassId: string | undefined;
    let querySectionId: string | undefined;

    if (level === "class" && classId) {
      queryClassId = classId;
    } else if (level === "section" && classId && sectionId) {
      queryClassId = classId;
      querySectionId = sectionId;
    }

    // For school level, don't pass any IDs to get school-wide periods only
    const result = await getSchoolPeriods(queryClassId, querySectionId, false);

    if (result.success && result.data) {
      // Filter to only show periods at the exact level requested
      const filtered = result.data.filter(p => {
        if (level === "school") {
          return !p.class_id && !p.section_id;
        } else if (level === "class") {
          return p.class_id === classId && !p.section_id;
        } else {
          return p.class_id === classId && p.section_id === sectionId;
        }
      });
      setPeriods(filtered);
    } else {
      setPeriods([]);
    }
  }, []);

  // Track if initial load has completed
  const isInitialLoadDone = useRef(false);

  // Initial data load
  useEffect(() => {
    let mounted = true;

    async function loadInitialData() {
      setLoading(true);
      const classesResult = await getClasses();
      if (mounted && classesResult.success && classesResult.data) {
        setClasses(classesResult.data);
      }
      if (mounted) {
        await loadPeriods(selectedLevel, selectedClassId, selectedSectionId);
        setLoading(false);
        isInitialLoadDone.current = true;
      }
    }

    loadInitialData();
    return () => { mounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run once on mount

  // Load periods when filters change (after initial load)
  useEffect(() => {
    // Skip if initial load hasn't completed yet
    if (!isInitialLoadDone.current) return;
    loadPeriods(selectedLevel, selectedClassId, selectedSectionId);
  }, [selectedLevel, selectedClassId, selectedSectionId, loadPeriods]);

  // Load sections when class changes
  useEffect(() => {
    if (selectedClassId) {
      loadSections(selectedClassId);
    } else {
      setSections([]);
      setSelectedSectionId("");
    }
  }, [selectedClassId, loadSections]);

  const resetForm = () => {
    const nextPeriodNumber = periods.length > 0
      ? Math.max(...periods.map(p => p.period_number)) + 1
      : 1;
    setFormData({
      period_number: nextPeriodNumber,
      name: "",
      start_time: "08:00",
      end_time: "08:45",
      is_break: false,
    });
    setEditingPeriod(null);
    setError(null);
  };

  const openCreateDialog = () => {
    resetForm();
    setIsDialogOpen(true);
  };

  const openEditDialog = (period: SchoolPeriod) => {
    setEditingPeriod(period);
    setFormData({
      period_number: period.period_number,
      name: period.name || "",
      start_time: period.start_time,
      end_time: period.end_time,
      is_break: period.is_break,
    });
    setIsDialogOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      if (editingPeriod) {
        const updateData: SchoolPeriodUpdate = {
          name: formData.name || undefined,
          start_time: formData.start_time,
          end_time: formData.end_time,
          is_break: formData.is_break,
        };
        const result = await updateSchoolPeriod(editingPeriod.id, updateData);
        if (result.success && result.data) {
          setPeriods(periods.map((p) => (p.id === editingPeriod.id ? result.data! : p)));
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to update period");
        }
      } else {
        const createData: SchoolPeriodCreate = {
          period_number: formData.period_number,
          name: formData.name || undefined,
          start_time: formData.start_time,
          end_time: formData.end_time,
          is_break: formData.is_break,
          class_id: selectedLevel !== "school" ? selectedClassId : undefined,
          section_id: selectedLevel === "section" ? selectedSectionId : undefined,
        };
        const result = await createSchoolPeriod(createData);
        if (result.success && result.data) {
          setPeriods([...periods, result.data].sort((a, b) => a.period_number - b.period_number));
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to create period");
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const openDeleteDialog = (period: SchoolPeriod) => {
    setPeriodToDelete(period);
    setDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!periodToDelete) return;

    setIsDeleting(true);
    const result = await deleteSchoolPeriod(periodToDelete.id);
    if (result.success) {
      setPeriods(periods.filter((p) => p.id !== periodToDelete.id));
      setDeleteDialogOpen(false);
      setPeriodToDelete(null);
    } else {
      setError(result.error || "Failed to delete period");
    }
    setIsDeleting(false);
  };

  // Memoize sorted periods to avoid re-sorting on every render
  const sortedPeriods = useMemo(() =>
    [...periods].sort((a, b) => a.period_number - b.period_number),
    [periods]
  );

  // Memoize level description
  const levelDescription = useMemo(() => {
    if (selectedLevel === "school") {
      return "These periods apply to all classes by default.";
    } else if (selectedLevel === "class") {
      if (!selectedClassId) return "Select a class to manage its periods.";
      const cls = classes.find(c => c.id === selectedClassId);
      return `These periods override school defaults for ${cls?.name || "this class"}.`;
    } else {
      if (!selectedClassId || !selectedSectionId) return "Select a class and section to manage its periods.";
      const cls = classes.find(c => c.id === selectedClassId);
      const sec = sections.find(s => s.id === selectedSectionId);
      return `These periods override class/school defaults for ${cls?.name} - ${sec?.name || "this section"}.`;
    }
  }, [selectedLevel, selectedClassId, selectedSectionId, classes, sections]);

  // Memoize canAddPeriod check
  const canAddPeriod = useMemo(() => {
    if (selectedLevel === "school") return true;
    if (selectedLevel === "class") return !!selectedClassId;
    return !!selectedClassId && !!selectedSectionId;
  }, [selectedLevel, selectedClassId, selectedSectionId]);

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              School Periods
            </CardTitle>
            <CardDescription>
              Configure period timings. You can set school-wide defaults or customize for specific classes/sections.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Level Selection */}
        <Tabs value={selectedLevel} onValueChange={(v) => setSelectedLevel(v as PeriodLevel)}>
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="school">School-Wide</TabsTrigger>
            <TabsTrigger value="class">Per Class</TabsTrigger>
            <TabsTrigger value="section">Per Section</TabsTrigger>
          </TabsList>

          <TabsContent value="school" className="mt-4">
            <p className="text-sm text-muted-foreground mb-4">{levelDescription}</p>
          </TabsContent>

          <TabsContent value="class" className="mt-4 space-y-4">
            <div className="grid gap-2">
              <Label>Select Class</Label>
              <Select value={selectedClassId} onValueChange={setSelectedClassId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a class..." />
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
            <p className="text-sm text-muted-foreground">{levelDescription}</p>
          </TabsContent>

          <TabsContent value="section" className="mt-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>Select Class</Label>
                <Select value={selectedClassId} onValueChange={setSelectedClassId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a class..." />
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
              <div className="grid gap-2">
                <Label>Select Section</Label>
                <Select
                  value={selectedSectionId}
                  onValueChange={setSelectedSectionId}
                  disabled={!selectedClassId || sections.length === 0}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={sections.length === 0 ? "No sections" : "Choose a section..."} />
                  </SelectTrigger>
                  <SelectContent>
                    {sections.map((sec) => (
                      <SelectItem key={sec.id} value={sec.id}>
                        {sec.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <p className="text-sm text-muted-foreground">{levelDescription}</p>
          </TabsContent>
        </Tabs>

        {/* Add Period Button */}
        <div className="flex justify-end">
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm" onClick={openCreateDialog} disabled={!canAddPeriod}>
                <Plus className="mr-2 h-4 w-4" />
                Add Period
              </Button>
            </DialogTrigger>
            <DialogContent>
              <form onSubmit={handleSubmit}>
                <DialogHeader>
                  <DialogTitle>
                    {editingPeriod ? "Edit Period" : "Add Period"}
                  </DialogTitle>
                  <DialogDescription>
                    {editingPeriod
                      ? "Update the period details."
                      : `Add a new period ${selectedLevel === "school" ? "for the entire school" : selectedLevel === "class" ? "for this class" : "for this section"}.`}
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-4 py-4">
                  {error && (
                    <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                      {error}
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label htmlFor="period_number">Period Number</Label>
                      <Input
                        id="period_number"
                        type="number"
                        min={1}
                        max={20}
                        value={formData.period_number}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            period_number: parseInt(e.target.value) || 1,
                          })
                        }
                        disabled={!!editingPeriod}
                        required
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="name">Name (Optional)</Label>
                      <Input
                        id="name"
                        placeholder="e.g., Morning Assembly"
                        value={formData.name}
                        onChange={(e) =>
                          setFormData({ ...formData, name: e.target.value })
                        }
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-2">
                      <Label htmlFor="start_time">Start Time</Label>
                      <Input
                        id="start_time"
                        type="time"
                        value={formData.start_time}
                        onChange={(e) =>
                          setFormData({ ...formData, start_time: e.target.value })
                        }
                        required
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="end_time">End Time</Label>
                      <Input
                        id="end_time"
                        type="time"
                        value={formData.end_time}
                        onChange={(e) =>
                          setFormData({ ...formData, end_time: e.target.value })
                        }
                        required
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="is_break"
                      checked={formData.is_break}
                      onCheckedChange={(checked) =>
                        setFormData({ ...formData, is_break: !!checked })
                      }
                    />
                    <Label htmlFor="is_break" className="text-sm font-normal flex items-center gap-2">
                      <Coffee className="h-4 w-4" />
                      This is a break period (not used for teaching)
                    </Label>
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setIsDialogOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" disabled={submitting}>
                    {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    {editingPeriod ? "Update" : "Add"}
                  </Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {/* Periods List */}
        {sortedPeriods.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground border rounded-lg">
            {canAddPeriod
              ? "No periods configured. Add periods to define the daily schedule."
              : "Select a class/section to view or add periods."}
          </div>
        ) : (
          <div className="space-y-2">
            {sortedPeriods.map((period) => (
                <div
                  key={period.id}
                  className={`flex items-center justify-between rounded-lg border p-4 ${
                    period.is_break ? "bg-muted/50" : ""
                  }`}
                >
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary font-semibold">
                      {period.period_number}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium">
                          {period.name || `Period ${period.period_number}`}
                        </p>
                        {period.is_break && (
                          <Badge variant="secondary" className="flex items-center gap-1">
                            <Coffee className="h-3 w-3" />
                            Break
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {period.start_time} - {period.end_time}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditDialog(period)}
                    >
                      <Settings2 className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openDeleteDialog(period)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
          </div>
        )}
      </CardContent>

      {/* Delete Period Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Period</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{periodToDelete?.name || `Period ${periodToDelete?.period_number}`}&quot;?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isDeleting}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {isDeleting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Deleting...
                </>
              ) : (
                "Delete"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
