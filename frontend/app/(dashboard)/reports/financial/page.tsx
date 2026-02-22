"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Download, FileText, Loader2 } from "lucide-react";
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

import { getAcademicYears, getTerms, getClasses } from "@/actions/academic.action";
import { generateFinancialReport } from "@/actions/reports.action";
import type { AcademicYear, Term, Class, FinancialReportType } from "@/types";

const REPORT_TYPES: { value: FinancialReportType; label: string; description: string }[] = [
  {
    value: "fee_collection",
    label: "Fee Collection Report",
    description: "Summary of all fees collected within a period",
  },
  {
    value: "outstanding_fees",
    label: "Outstanding Fees Report",
    description: "List of unpaid or partially paid invoices",
  },
  {
    value: "payment_summary",
    label: "Payment Summary Report",
    description: "Breakdown of payments by method and status",
  },
];

export default function FinancialReportsPage() {
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);

  const [reportType, setReportType] = useState<FinancialReportType>("fee_collection");
  const [academicYearId, setAcademicYearId] = useState<string>("");
  const [termId, setTermId] = useState<string>("");
  const [classId, setClassId] = useState<string>("");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");

  const [generating, setGenerating] = useState(false);
  const [loadingData, setLoadingData] = useState(true);

  useEffect(() => {
    async function loadData() {
      const [yearsResult, classesResult] = await Promise.all([
        getAcademicYears(true),
        getClasses(),
      ]);
      if (yearsResult.success) setAcademicYears(yearsResult.data);
      if (classesResult.success) setClasses(classesResult.data);
      setLoadingData(false);
    }
    loadData();
  }, []);

  const loadTerms = useCallback(async (yearId: string) => {
    if (!yearId) {
      setTerms([]);
      return;
    }
    const result = await getTerms(yearId);
    if (result.success) setTerms(result.data);
  }, []);

  useEffect(() => {
    if (academicYearId) {
      loadTerms(academicYearId);
      setTermId("");
    } else {
      setTerms([]);
      setTermId("");
    }
  }, [academicYearId, loadTerms]);

  const handleGenerate = async () => {
    if (!academicYearId) {
      toast.error("Please select an academic year");
      return;
    }

    setGenerating(true);

    const result = await generateFinancialReport({
      report_type: reportType,
      academic_year_id: academicYearId,
      term_id: termId && termId !== "all" ? termId : undefined,
      class_id: classId && classId !== "all" ? classId : undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    });

    if (result.success && result.data) {
      const url = URL.createObjectURL(result.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${reportType}-report-${new Date().toISOString().split("T")[0]}.pdf`;
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
          <h1 className="text-2xl font-bold tracking-tight">Financial Reports</h1>
          <p className="text-muted-foreground">
            Generate fee collection, outstanding fees, and payment summary reports
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Report Type Selection */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Report Type</CardTitle>
            <CardDescription>Select the type of report to generate</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {REPORT_TYPES.map((type) => (
              <button
                key={type.value}
                type="button"
                onClick={() => setReportType(type.value)}
                className={`w-full rounded-lg border p-3 text-left transition-colors ${
                  reportType === type.value
                    ? "border-primary bg-primary/5"
                    : "hover:bg-muted/50"
                }`}
              >
                <div className="flex items-center gap-3">
                  <FileText
                    className={`h-5 w-5 shrink-0 ${
                      reportType === type.value
                        ? "text-primary"
                        : "text-muted-foreground"
                    }`}
                  />
                  <div>
                    <p className="text-sm font-medium">{type.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {type.description}
                    </p>
                  </div>
                </div>
              </button>
            ))}
          </CardContent>
        </Card>

        {/* Filters */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Filters</CardTitle>
            <CardDescription>
              Narrow down the report scope with optional filters
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
                    <Label htmlFor="academic-year">
                      Academic Year <span className="text-red-500">*</span>
                    </Label>
                    <Select
                      value={academicYearId}
                      onValueChange={setAcademicYearId}
                    >
                      <SelectTrigger id="academic-year">
                        <SelectValue placeholder="Select academic year" />
                      </SelectTrigger>
                      <SelectContent>
                        {academicYears.map((year) => (
                          <SelectItem key={year.id} value={year.id}>
                            {year.name}
                            {year.is_current ? " (Current)" : ""}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="term">Term (Optional)</Label>
                    <Select value={termId} onValueChange={setTermId}>
                      <SelectTrigger id="term" disabled={!academicYearId}>
                        <SelectValue placeholder="All terms" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All terms</SelectItem>
                        {terms.map((term) => (
                          <SelectItem key={term.id} value={term.id}>
                            {term.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="class-filter">Class (Optional)</Label>
                  <Select value={classId} onValueChange={setClassId}>
                    <SelectTrigger id="class-filter">
                      <SelectValue placeholder="All classes" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All classes</SelectItem>
                      {classes.map((cls) => (
                        <SelectItem key={cls.id} value={cls.id}>
                          {cls.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="date-from">Date From (Optional)</Label>
                    <Input
                      id="date-from"
                      type="date"
                      value={dateFrom}
                      onChange={(e) => setDateFrom(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="date-to">Date To (Optional)</Label>
                    <Input
                      id="date-to"
                      type="date"
                      value={dateTo}
                      onChange={(e) => setDateTo(e.target.value)}
                    />
                  </div>
                </div>

                <div className="pt-4">
                  <Button
                    onClick={handleGenerate}
                    disabled={generating || !academicYearId}
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
    </div>
  );
}
