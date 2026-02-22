"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Download, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";

import { getClasses, getSections } from "@/actions/academic.action";
import { generateAttendanceReport } from "@/actions/reports.action";
import type { Class, ClassSection } from "@/types";

export default function AttendanceReportsPage() {
  const [classes, setClasses] = useState<Class[]>([]);
  const [sections, setSections] = useState<ClassSection[]>([]);

  const [classId, setClassId] = useState<string>("");
  const [sectionId, setSectionId] = useState<string>("");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");

  const [generating, setGenerating] = useState(false);
  const [loadingData, setLoadingData] = useState(true);

  useEffect(() => {
    async function loadData() {
      const classesResult = await getClasses(true);
      if (classesResult.success) setClasses(classesResult.data);
      setLoadingData(false);
    }
    loadData();
  }, []);

  const loadSections = useCallback(async (selectedClassId: string) => {
    if (!selectedClassId) {
      setSections([]);
      return;
    }
    const result = await getSections(selectedClassId);
    if (result.success) setSections(result.data);
  }, []);

  useEffect(() => {
    if (classId) {
      loadSections(classId);
      setSectionId("");
    } else {
      setSections([]);
      setSectionId("");
    }
  }, [classId, loadSections]);

  const handleGenerate = async () => {
    if (!classId) {
      toast.error("Please select a class");
      return;
    }
    if (!dateFrom || !dateTo) {
      toast.error("Please select both start and end dates");
      return;
    }

    setGenerating(true);

    const result = await generateAttendanceReport({
      class_id: classId,
      section_id: sectionId && sectionId !== "all" ? sectionId : undefined,
      date_from: dateFrom,
      date_to: dateTo,
    });

    if (result.success && result.data) {
      const url = URL.createObjectURL(result.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `attendance-report-${new Date().toISOString().split("T")[0]}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success("Report generated and downloaded");
    } else {
      toast.error(result.error || "Failed to generate report");
    }

    setGenerating(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/reports">
            <ArrowLeft className="h-4 w-4" />
            <span className="sr-only">Back to reports</span>
          </Link>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Attendance Reports</h1>
          <p className="text-muted-foreground">
            Generate attendance summary reports by class and date range
          </p>
        </div>
      </div>

      <Card className="max-w-2xl">
        <CardHeader>
          <CardTitle className="text-base">Report Filters</CardTitle>
          <CardDescription>
            Select a class and date range to generate the attendance report
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loadingData ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="class-select">
                    Class <span className="text-red-500">*</span>
                  </Label>
                  <Select value={classId} onValueChange={setClassId}>
                    <SelectTrigger id="class-select">
                      <SelectValue placeholder="Select class" />
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

                <div className="space-y-2">
                  <Label htmlFor="section-select">Section (Optional)</Label>
                  <Select value={sectionId} onValueChange={setSectionId}>
                    <SelectTrigger id="section-select" disabled={!classId}>
                      <SelectValue placeholder="All sections" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All sections</SelectItem>
                      {sections.map((section) => (
                        <SelectItem key={section.id} value={section.id}>
                          {section.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="att-date-from">
                    Date From <span className="text-red-500">*</span>
                  </Label>
                  <Input
                    id="att-date-from"
                    type="date"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="att-date-to">
                    Date To <span className="text-red-500">*</span>
                  </Label>
                  <Input
                    id="att-date-to"
                    type="date"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                  />
                </div>
              </div>

              <div className="pt-4">
                <Button
                  onClick={handleGenerate}
                  disabled={generating || !classId || !dateFrom || !dateTo}
                  className="w-full sm:w-auto"
                >
                  {generating ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Download className="mr-2 h-4 w-4" />
                      Generate Report
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
