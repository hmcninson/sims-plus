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
import { Textarea } from "@/components/ui/textarea";
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
import { CalendarDays, Plus, Settings2, Trash2, Loader2, Repeat } from "lucide-react";
import {
  getSchoolHolidays,
  createSchoolHoliday,
  updateSchoolHoliday,
  deleteSchoolHoliday,
} from "@/actions/timetable.action";
import { getAcademicYears } from "@/actions/academic.action";
import type { SchoolHoliday, SchoolHolidayCreate, SchoolHolidayUpdate, AcademicYear, HolidayType } from "@/types";

const HOLIDAY_TYPES: { value: HolidayType; label: string; color: string }[] = [
  { value: "holiday", label: "Public Holiday", color: "bg-red-100 text-red-800" },
  { value: "vacation", label: "Vacation", color: "bg-blue-100 text-blue-800" },
  { value: "exam", label: "Exam Period", color: "bg-yellow-100 text-yellow-800" },
  { value: "event", label: "School Event", color: "bg-green-100 text-green-800" },
];

export function SchoolHolidays() {
  const [holidays, setHolidays] = useState<SchoolHoliday[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [loading, setLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingHoliday, setEditingHoliday] = useState<SchoolHoliday | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [holidayToDelete, setHolidayToDelete] = useState<SchoolHoliday | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Filter state
  const [selectedYearId, setSelectedYearId] = useState<string>("");

  // Form state
  const [formData, setFormData] = useState({
    date: "",
    name: "",
    description: "",
    holiday_type: "holiday" as HolidayType,
    is_recurring: false,
  });

  // Memoized load function
  const loadHolidays = useCallback(async (yearId: string) => {
    if (!yearId) {
      setHolidays([]);
      return;
    }
    const result = await getSchoolHolidays(yearId);
    if (result.success && result.data) {
      setHolidays(result.data);
    } else {
      setHolidays([]);
    }
  }, []);

  // Track if initial load has completed
  const isInitialLoadDone = useRef(false);

  // Initial data load
  useEffect(() => {
    let mounted = true;

    async function loadInitialData() {
      setLoading(true);
      const yearsResult = await getAcademicYears();
      if (mounted && yearsResult.success && yearsResult.data) {
        setAcademicYears(yearsResult.data);
        // Auto-select current year
        const currentYear = yearsResult.data.find(y => y.is_current);
        const yearToSelect = currentYear?.id || yearsResult.data[0]?.id || "";
        setSelectedYearId(yearToSelect);
        // Load holidays for the selected year
        if (yearToSelect) {
          await loadHolidays(yearToSelect);
        }
      }
      if (mounted) {
        setLoading(false);
        isInitialLoadDone.current = true;
      }
    }

    loadInitialData();
    return () => { mounted = false; };
  }, [loadHolidays]);

  // Load holidays when year changes (after initial load)
  useEffect(() => {
    // Skip if initial load hasn't completed yet
    if (!isInitialLoadDone.current) return;
    loadHolidays(selectedYearId);
  }, [selectedYearId, loadHolidays]);

  const resetForm = () => {
    setFormData({
      date: "",
      name: "",
      description: "",
      holiday_type: "holiday",
      is_recurring: false,
    });
    setEditingHoliday(null);
    setError(null);
  };

  const openCreateDialog = () => {
    resetForm();
    setIsDialogOpen(true);
  };

  const openEditDialog = (holiday: SchoolHoliday) => {
    setEditingHoliday(holiday);
    setFormData({
      date: holiday.date,
      name: holiday.name,
      description: holiday.description || "",
      holiday_type: holiday.holiday_type,
      is_recurring: holiday.is_recurring,
    });
    setIsDialogOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      if (editingHoliday) {
        const updateData: SchoolHolidayUpdate = {
          date: formData.date,
          name: formData.name,
          description: formData.description || undefined,
          holiday_type: formData.holiday_type,
          is_recurring: formData.is_recurring,
        };
        const result = await updateSchoolHoliday(editingHoliday.id, updateData);
        if (result.success && result.data) {
          setHolidays(holidays.map((h) => (h.id === editingHoliday.id ? result.data! : h)));
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to update holiday");
        }
      } else {
        const createData: SchoolHolidayCreate = {
          date: formData.date,
          name: formData.name,
          description: formData.description || undefined,
          holiday_type: formData.holiday_type,
          academic_year_id: selectedYearId || undefined,
          is_recurring: formData.is_recurring,
        };
        const result = await createSchoolHoliday(createData);
        if (result.success && result.data) {
          setHolidays([...holidays, result.data].sort((a, b) =>
            new Date(a.date).getTime() - new Date(b.date).getTime()
          ));
          setIsDialogOpen(false);
          resetForm();
        } else {
          setError(result.error || "Failed to create holiday");
        }
      }
    } finally {
      setSubmitting(false);
    }
  };

  const openDeleteDialog = (holiday: SchoolHoliday) => {
    setHolidayToDelete(holiday);
    setDeleteDialogOpen(true);
  };

  const handleDelete = async () => {
    if (!holidayToDelete) return;

    setIsDeleting(true);
    const result = await deleteSchoolHoliday(holidayToDelete.id);
    if (result.success) {
      setHolidays(holidays.filter((h) => h.id !== holidayToDelete.id));
      setDeleteDialogOpen(false);
      setHolidayToDelete(null);
    } else {
      setError(result.error || "Failed to delete holiday");
    }
    setIsDeleting(false);
  };

  // Memoized sorted holidays to avoid re-sorting on every render
  const sortedHolidays = useMemo(() =>
    [...holidays].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()),
    [holidays]
  );

  // Memoized date formatter
  const formatDate = useCallback((dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }, []);

  // Memoized type badge getter
  const getTypeBadge = useCallback((type: HolidayType) => {
    const typeInfo = HOLIDAY_TYPES.find(t => t.value === type);
    return (
      <Badge variant="secondary" className={typeInfo?.color}>
        {typeInfo?.label || type}
      </Badge>
    );
  }, []);

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
              <CalendarDays className="h-5 w-5" />
              School Holidays & Events
            </CardTitle>
            <CardDescription>
              Configure holidays, vacations, and special events when classes don&apos;t run.
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Year Filter */}
        <div className="flex items-center gap-4">
          <div className="grid gap-2 flex-1 max-w-xs">
            <Label>Academic Year</Label>
            <Select value={selectedYearId} onValueChange={setSelectedYearId}>
              <SelectTrigger>
                <SelectValue placeholder="Select academic year..." />
              </SelectTrigger>
              <SelectContent>
                {academicYears.map((year) => (
                  <SelectItem key={year.id} value={year.id}>
                    {year.name} {year.is_current && "(Current)"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="pt-6">
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
              <DialogTrigger asChild>
                <Button size="sm" onClick={openCreateDialog} disabled={!selectedYearId}>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Holiday
                </Button>
              </DialogTrigger>
              <DialogContent>
                <form onSubmit={handleSubmit}>
                  <DialogHeader>
                    <DialogTitle>
                      {editingHoliday ? "Edit Holiday" : "Add Holiday"}
                    </DialogTitle>
                    <DialogDescription>
                      {editingHoliday
                        ? "Update the holiday details."
                        : "Add a new holiday or event to the calendar."}
                    </DialogDescription>
                  </DialogHeader>
                  <div className="grid gap-4 py-4">
                    {error && (
                      <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                        {error}
                      </div>
                    )}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="grid gap-2">
                        <Label htmlFor="date">Date</Label>
                        <Input
                          id="date"
                          type="date"
                          value={formData.date}
                          onChange={(e) =>
                            setFormData({ ...formData, date: e.target.value })
                          }
                          required
                        />
                      </div>
                      <div className="grid gap-2">
                        <Label htmlFor="holiday_type">Type</Label>
                        <Select
                          value={formData.holiday_type}
                          onValueChange={(v) =>
                            setFormData({ ...formData, holiday_type: v as HolidayType })
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {HOLIDAY_TYPES.map((type) => (
                              <SelectItem key={type.value} value={type.value}>
                                {type.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="name">Name</Label>
                      <Input
                        id="name"
                        placeholder="e.g., Independence Day"
                        value={formData.name}
                        onChange={(e) =>
                          setFormData({ ...formData, name: e.target.value })
                        }
                        required
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="description">Description (Optional)</Label>
                      <Textarea
                        id="description"
                        placeholder="Additional details about this holiday..."
                        value={formData.description}
                        onChange={(e) =>
                          setFormData({ ...formData, description: e.target.value })
                        }
                        rows={2}
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="is_recurring"
                        checked={formData.is_recurring}
                        onCheckedChange={(checked) =>
                          setFormData({ ...formData, is_recurring: !!checked })
                        }
                      />
                      <Label htmlFor="is_recurring" className="text-sm font-normal flex items-center gap-2">
                        <Repeat className="h-4 w-4" />
                        Recurring every year (same date)
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
                      {editingHoliday ? "Update" : "Add"}
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Holidays List */}
        {!selectedYearId ? (
          <div className="py-8 text-center text-muted-foreground border rounded-lg">
            Select an academic year to view holidays.
          </div>
        ) : sortedHolidays.length === 0 ? (
          <div className="py-8 text-center text-muted-foreground border rounded-lg">
            No holidays configured for this academic year. Add holidays to mark days off.
          </div>
        ) : (
          <div className="space-y-2">
            {sortedHolidays.map((holiday) => (
                <div
                  key={holiday.id}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div className="flex items-center gap-4">
                    <div className="text-center min-w-[60px]">
                      <div className="text-2xl font-bold text-primary">
                        {new Date(holiday.date).getDate()}
                      </div>
                      <div className="text-xs text-muted-foreground uppercase">
                        {new Date(holiday.date).toLocaleDateString("en-US", { month: "short" })}
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{holiday.name}</p>
                        {getTypeBadge(holiday.holiday_type)}
                        {holiday.is_recurring && (
                          <Badge variant="outline" className="flex items-center gap-1">
                            <Repeat className="h-3 w-3" />
                            Yearly
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {formatDate(holiday.date)}
                        {holiday.description && ` - ${holiday.description}`}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditDialog(holiday)}
                    >
                      <Settings2 className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openDeleteDialog(holiday)}
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

      {/* Delete Holiday Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Holiday</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &quot;{holidayToDelete?.name}&quot;?
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
