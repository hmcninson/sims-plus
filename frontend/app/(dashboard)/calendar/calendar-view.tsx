"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import {
  ChevronLeft,
  ChevronRight,
  CalendarDays,
  Plus,
  Download,
  Calendar as CalendarIcon,
  LayoutGrid,
  List,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
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
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { getTerms } from "@/actions/academic.action";
import { getSchoolHolidays } from "@/actions/timetable.action";
import { CalendarGrid } from "./components/calendar-grid";
import { WeekView } from "./components/week-view";
import { YearView } from "./components/year-view";
import { EventSidebar } from "./components/event-sidebar";
import { SchoolDaysCounter } from "./components/school-days-counter";
import { EventForm } from "./components/event-form";
import { UpcomingEvents } from "./components/upcoming-events";
import { downloadICalFile, generateGoogleCalendarUrl } from "./utils/export";
import type { AcademicYear, Term, SchoolHoliday } from "@/types";

interface CalendarViewProps {
  academicYears: AcademicYear[];
  initialTerms: Term[];
  initialHolidays: SchoolHoliday[];
  initialAcademicYearId?: string;
}

type ViewMode = "month" | "week" | "year";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export function CalendarView({
  academicYears,
  initialTerms,
  initialHolidays,
  initialAcademicYearId,
}: CalendarViewProps) {
  const [selectedAcademicYearId, setSelectedAcademicYearId] = useState(
    initialAcademicYearId || ""
  );
  const [terms, setTerms] = useState<Term[]>(initialTerms);
  const [holidays, setHolidays] = useState<SchoolHoliday[]>(initialHolidays);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [viewMode, setViewMode] = useState<ViewMode>("month");

  // Event form state
  const [eventFormOpen, setEventFormOpen] = useState(false);
  const [editingEvent, setEditingEvent] = useState<SchoolHoliday | null>(null);
  const [defaultEventDate, setDefaultEventDate] = useState<Date | null>(null);

  // Get current academic year
  const currentAcademicYear = useMemo(
    () => academicYears.find((y) => y.id === selectedAcademicYearId),
    [academicYears, selectedAcademicYearId]
  );

  // Refresh data function
  const refreshData = useCallback(async () => {
    if (!selectedAcademicYearId) return;

    const [termsResult, holidaysResult] = await Promise.all([
      getTerms(selectedAcademicYearId),
      getSchoolHolidays(selectedAcademicYearId),
    ]);
    if (termsResult.success) setTerms(termsResult.data || []);
    if (holidaysResult.success) setHolidays(holidaysResult.data || []);
  }, [selectedAcademicYearId]);

  // Fetch terms and holidays when academic year changes
  useEffect(() => {
    if (!selectedAcademicYearId) return;

    // Only fetch if academic year changed from initial
    if (selectedAcademicYearId !== initialAcademicYearId) {
      refreshData();
    }
  }, [selectedAcademicYearId, initialAcademicYearId, refreshData]);

  // Get current term based on today's date
  const currentTerm = useMemo(() => {
    const today = new Date();
    return terms.find((t) => {
      const start = new Date(t.start_date);
      const end = new Date(t.end_date);
      return today >= start && today <= end;
    });
  }, [terms]);

  // Create a map of holidays by date for quick lookup
  const holidaysByDate = useMemo(() => {
    const map = new Map<string, SchoolHoliday[]>();
    holidays.forEach((holiday) => {
      const dateKey = holiday.date;
      const existing = map.get(dateKey) || [];
      existing.push(holiday);
      map.set(dateKey, existing);
    });
    return map;
  }, [holidays]);

  // Get events for selected date
  const selectedDateEvents = useMemo(() => {
    if (!selectedDate) return [];
    const dateKey = selectedDate.toISOString().split("T")[0];
    return holidaysByDate.get(dateKey) || [];
  }, [selectedDate, holidaysByDate]);

  // Get term for a given date
  const getTermForDate = useCallback(
    (date: Date) => {
      return terms.find((t) => {
        const start = new Date(t.start_date);
        const end = new Date(t.end_date);
        return date >= start && date <= end;
      });
    },
    [terms]
  );

  // Navigation handlers
  const goToPrevious = useCallback(() => {
    setCurrentMonth((prev) => {
      const newDate = new Date(prev);
      if (viewMode === "week") {
        newDate.setDate(newDate.getDate() - 7);
      } else if (viewMode === "year") {
        newDate.setFullYear(newDate.getFullYear() - 1);
      } else {
        newDate.setMonth(newDate.getMonth() - 1);
      }
      return newDate;
    });
  }, [viewMode]);

  const goToNext = useCallback(() => {
    setCurrentMonth((prev) => {
      const newDate = new Date(prev);
      if (viewMode === "week") {
        newDate.setDate(newDate.getDate() + 7);
      } else if (viewMode === "year") {
        newDate.setFullYear(newDate.getFullYear() + 1);
      } else {
        newDate.setMonth(newDate.getMonth() + 1);
      }
      return newDate;
    });
  }, [viewMode]);

  const goToToday = useCallback(() => {
    setCurrentMonth(new Date());
    setSelectedDate(new Date());
  }, []);

  // Date click handler
  const handleDateClick = useCallback((date: Date) => {
    setSelectedDate(date);
  }, []);

  // Double-click to add event
  const handleDateDoubleClick = useCallback((date: Date) => {
    setDefaultEventDate(date);
    setEditingEvent(null);
    setEventFormOpen(true);
  }, []);

  // Event click handler
  const handleEventClick = useCallback((event: SchoolHoliday) => {
    setEditingEvent(event);
    setDefaultEventDate(null);
    setEventFormOpen(true);
  }, []);

  // Add event button handler
  const handleAddEvent = useCallback(() => {
    setEditingEvent(null);
    setDefaultEventDate(selectedDate);
    setEventFormOpen(true);
  }, [selectedDate]);

  // Month click handler (from year view)
  const handleMonthClick = useCallback((month: number) => {
    const newDate = new Date(currentMonth);
    newDate.setMonth(month);
    setCurrentMonth(newDate);
    setViewMode("month");
  }, [currentMonth]);

  // Export handlers
  const handleExportICal = useCallback(() => {
    const filename = currentAcademicYear
      ? `school-calendar-${currentAcademicYear.name.replace(/\s+/g, "-")}.ics`
      : "school-calendar.ics";
    downloadICalFile(holidays, terms, currentAcademicYear, filename);
    toast.success("Calendar exported successfully");
  }, [holidays, terms, currentAcademicYear]);

  const handleExportSelectedToGoogle = useCallback(() => {
    if (selectedDateEvents.length > 0) {
      const url = generateGoogleCalendarUrl(selectedDateEvents[0]);
      window.open(url, "_blank");
    } else {
      toast.error("No event selected to export");
    }
  }, [selectedDateEvents]);

  // Get navigation title based on view mode
  const navigationTitle = useMemo(() => {
    if (viewMode === "year") {
      return currentMonth.getFullYear().toString();
    } else if (viewMode === "week") {
      const weekStart = new Date(currentMonth);
      const dayOfWeek = weekStart.getDay();
      const diff = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
      weekStart.setDate(weekStart.getDate() + diff);
      const weekEnd = new Date(weekStart);
      weekEnd.setDate(weekEnd.getDate() + 6);

      if (weekStart.getMonth() === weekEnd.getMonth()) {
        return `${MONTHS[weekStart.getMonth()]} ${weekStart.getDate()} - ${weekEnd.getDate()}, ${weekStart.getFullYear()}`;
      } else {
        return `${MONTHS[weekStart.getMonth()].slice(0, 3)} ${weekStart.getDate()} - ${MONTHS[weekEnd.getMonth()].slice(0, 3)} ${weekEnd.getDate()}, ${weekEnd.getFullYear()}`;
      }
    }
    return `${MONTHS[currentMonth.getMonth()]} ${currentMonth.getFullYear()}`;
  }, [currentMonth, viewMode]);

  return (
    <div className="flex gap-6">
      {/* Main Calendar Area */}
      <div className="flex-1 space-y-4">
        {/* Controls */}
        <Card>
          <CardContent className="py-4">
            <div className="flex items-center justify-between gap-4 flex-wrap">
              {/* Academic Year Selector */}
              <div className="flex items-center gap-2">
                <CalendarDays className="h-4 w-4 text-muted-foreground" />
                <Select
                  value={selectedAcademicYearId}
                  onValueChange={setSelectedAcademicYearId}
                >
                  <SelectTrigger className="w-[180px]">
                    <SelectValue placeholder="Academic Year" />
                  </SelectTrigger>
                  <SelectContent>
                    {academicYears.map((year) => (
                      <SelectItem key={year.id} value={year.id}>
                        {year.name}
                        {year.is_current && (
                          <Badge variant="secondary" className="ml-2 text-xs">
                            Current
                          </Badge>
                        )}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* View Mode Toggle */}
              <Tabs
                value={viewMode}
                onValueChange={(v) => setViewMode(v as ViewMode)}
              >
                <TabsList>
                  <TabsTrigger value="month" className="gap-1.5">
                    <LayoutGrid className="h-3.5 w-3.5" />
                    Month
                  </TabsTrigger>
                  <TabsTrigger value="week" className="gap-1.5">
                    <List className="h-3.5 w-3.5" />
                    Week
                  </TabsTrigger>
                  <TabsTrigger value="year" className="gap-1.5">
                    <CalendarIcon className="h-3.5 w-3.5" />
                    Year
                  </TabsTrigger>
                </TabsList>
              </Tabs>

              {/* Navigation */}
              <div className="flex items-center gap-2">
                <Button variant="outline" size="icon" onClick={goToPrevious}>
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <div className="min-w-[180px] text-center font-medium">
                  {navigationTitle}
                </div>
                <Button variant="outline" size="icon" onClick={goToNext}>
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="sm" onClick={goToToday}>
                  Today
                </Button>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2">
                <Button variant="default" size="sm" onClick={handleAddEvent}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Event
                </Button>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm">
                      <Download className="h-4 w-4 mr-2" />
                      Export
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={handleExportICal}>
                      <Download className="h-4 w-4 mr-2" />
                      Download iCal (.ics)
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={handleExportSelectedToGoogle}
                      disabled={selectedDateEvents.length === 0}
                    >
                      <ExternalLink className="h-4 w-4 mr-2" />
                      Add to Google Calendar
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Term Legend (only for month/week views) */}
        {viewMode !== "year" && terms.length > 0 && (
          <div className="flex flex-wrap gap-4 px-1">
            {terms.map((term, index) => (
              <div key={term.id} className="flex items-center gap-2 text-sm">
                <div
                  className={`w-3 h-3 rounded-sm ${
                    index === 0
                      ? "bg-blue-500/20 border border-blue-500"
                      : index === 1
                      ? "bg-green-500/20 border border-green-500"
                      : index === 2
                      ? "bg-purple-500/20 border border-purple-500"
                      : "bg-orange-500/20 border border-orange-500"
                  }`}
                />
                <span className="text-muted-foreground">
                  {term.short_name || term.name}
                </span>
              </div>
            ))}
            <div className="flex items-center gap-2 text-sm ml-4">
              <div className="w-2 h-2 rounded-full bg-red-500" />
              <span className="text-muted-foreground">Holiday</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <div className="w-2 h-2 rounded-full bg-blue-500" />
              <span className="text-muted-foreground">Vacation</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <div className="w-2 h-2 rounded-full bg-yellow-500" />
              <span className="text-muted-foreground">Exam</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-muted-foreground">Event</span>
            </div>
          </div>
        )}

        {/* Calendar Views */}
        {viewMode === "month" && (
          <CalendarGrid
            currentMonth={currentMonth}
            selectedDate={selectedDate}
            holidaysByDate={holidaysByDate}
            terms={terms}
            onDateClick={handleDateClick}
            onDateDoubleClick={handleDateDoubleClick}
            onEventClick={handleEventClick}
            onEventMoved={refreshData}
            getTermForDate={getTermForDate}
          />
        )}

        {viewMode === "week" && (
          <WeekView
            currentDate={currentMonth}
            selectedDate={selectedDate}
            holidaysByDate={holidaysByDate}
            terms={terms}
            onDateClick={handleDateClick}
            onDateDoubleClick={handleDateDoubleClick}
            onEventClick={handleEventClick}
            onEventMoved={refreshData}
            getTermForDate={getTermForDate}
          />
        )}

        {viewMode === "year" && (
          <YearView
            year={currentMonth.getFullYear()}
            selectedDate={selectedDate}
            holidaysByDate={holidaysByDate}
            terms={terms}
            onDateClick={handleDateClick}
            onDateDoubleClick={handleDateDoubleClick}
            onMonthClick={handleMonthClick}
            getTermForDate={getTermForDate}
          />
        )}

        {/* Hint text */}
        <p className="text-xs text-muted-foreground text-center">
          Click on a date to view events. Double-click to add a new event.
        </p>
      </div>

      {/* Right Sidebar */}
      <div className="w-80 space-y-4">
        {/* School Days Counter */}
        <SchoolDaysCounter
          terms={terms}
          holidays={holidays}
          currentTerm={currentTerm}
        />

        {/* Upcoming Events */}
        <UpcomingEvents
          holidays={holidays}
          onEventClick={handleEventClick}
        />

        {/* Event Sidebar */}
        <EventSidebar
          selectedDate={selectedDate}
          events={selectedDateEvents}
          term={selectedDate ? getTermForDate(selectedDate) : undefined}
          onEventClick={handleEventClick}
          onAddEvent={handleAddEvent}
        />
      </div>

      {/* Event Form Dialog */}
      <EventForm
        open={eventFormOpen}
        onOpenChange={setEventFormOpen}
        event={editingEvent}
        defaultDate={defaultEventDate}
        academicYears={academicYears}
        selectedAcademicYearId={selectedAcademicYearId}
        onSuccess={refreshData}
      />
    </div>
  );
}
