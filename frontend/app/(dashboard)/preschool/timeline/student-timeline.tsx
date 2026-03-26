"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { format } from "date-fns";
import { Calendar, GitBranch, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar as CalendarPicker } from "@/components/ui/calendar";
import { StudentCombobox } from "@/components/preschool";
import { ProgressTimeline } from "@/components/preschool/ProgressTimeline";
import { getStudents } from "@/actions/students.action";
import { getStudentTimeline } from "@/actions/preschool.action";
import type { Class, TimelineEntry } from "@/types";

interface StudentItem {
  id: string;
  first_name: string;
  last_name: string;
  student_id: string;
  middle_name?: string | null;
}

interface StudentTimelinePageProps {
  classes: Class[];
}

export function StudentTimelinePage({ classes }: StudentTimelinePageProps) {
  const [selectedClassId, setSelectedClassId] = useState("");
  const [selectedStudentId, setSelectedStudentId] = useState("");
  const [students, setStudents] = useState<StudentItem[]>([]);
  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [dateFrom, setDateFrom] = useState<Date | undefined>(undefined);
  const [dateTo, setDateTo] = useState<Date | undefined>(undefined);

  // Load students when class changes
  useEffect(() => {
    if (selectedClassId) {
      setLoadingStudents(true);
      getStudents({ class_id: selectedClassId, status: "active" }).then((result) => {
        if (result.success && result.data) {
          setStudents(
            result.data.items.map((s) => ({
              id: s.id,
              first_name: s.first_name,
              last_name: s.last_name,
              student_id: s.student_id,
            }))
          );
        }
        setLoadingStudents(false);
      });
      setSelectedStudentId("");
      setEntries([]);
    } else {
      setStudents([]);
      setSelectedStudentId("");
      setEntries([]);
    }
  }, [selectedClassId]);

  // Load timeline when student or dates change
  const loadTimeline = useCallback(async () => {
    if (!selectedStudentId) return;
    setLoading(true);
    const params: { date_from?: string; date_to?: string } = {};
    if (dateFrom) params.date_from = format(dateFrom, "yyyy-MM-dd");
    if (dateTo) params.date_to = format(dateTo, "yyyy-MM-dd");

    const result = await getStudentTimeline(selectedStudentId, params);
    if (result.success && result.data) {
      setEntries(result.data);
    } else {
      toast.error(result.error || "Failed to load timeline");
    }
    setLoading(false);
  }, [selectedStudentId, dateFrom, dateTo]);

  useEffect(() => {
    if (selectedStudentId) {
      loadTimeline();
    }
  }, [selectedStudentId, loadTimeline]);

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="flex flex-col gap-3 md:flex-row md:items-end">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">Class</label>
          <Select value={selectedClassId} onValueChange={setSelectedClassId}>
            <SelectTrigger className="w-full md:w-[200px]">
              <SelectValue placeholder="Select class..." />
            </SelectTrigger>
            <SelectContent>
              {classes.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">Student</label>
          <div className="w-full md:w-[260px]">
            <StudentCombobox
              students={students}
              value={selectedStudentId}
              onValueChange={setSelectedStudentId}
              placeholder="Select student..."
              disabled={!selectedClassId}
              isLoading={loadingStudents}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">Date Range (optional)</label>
          <div className="flex gap-2">
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" className="w-full md:w-auto justify-start text-left font-normal">
                  <Calendar className="mr-2 h-4 w-4" />
                  {dateFrom ? format(dateFrom, "dd/MM/yyyy") : "From"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <CalendarPicker
                  mode="single"
                  selected={dateFrom}
                  onSelect={setDateFrom}
                  initialFocus
                />
              </PopoverContent>
            </Popover>

            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" className="w-full md:w-auto justify-start text-left font-normal">
                  <Calendar className="mr-2 h-4 w-4" />
                  {dateTo ? format(dateTo, "dd/MM/yyyy") : "To"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <CalendarPicker
                  mode="single"
                  selected={dateTo}
                  onSelect={setDateTo}
                  initialFocus
                />
              </PopoverContent>
            </Popover>

            {(dateFrom || dateTo) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setDateFrom(undefined);
                  setDateTo(undefined);
                }}
              >
                Clear
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Timeline Content */}
      {!selectedClassId && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Users className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium">Select a Class and Student</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-md">
              Choose a preschool class and then select a student to view their
              developmental journey timeline.
            </p>
          </CardContent>
        </Card>
      )}

      {selectedClassId && !selectedStudentId && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <GitBranch className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium">Select a Student</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Choose a student from the dropdown above to view their timeline.
            </p>
          </CardContent>
        </Card>
      )}

      {selectedStudentId && (
        <ProgressTimeline entries={entries} isLoading={loading} />
      )}
    </div>
  );
}
