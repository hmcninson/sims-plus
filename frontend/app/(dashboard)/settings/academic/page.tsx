"use client";

import { Suspense, useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AcademicYears,
  Terms,
  Classes,
  Subjects,
  GradingScales,
  AssessmentWeights,
  OtherSettings,
  SchoolPeriods,
  SchoolHolidays,
} from "@/components/academic";
import { getAcademicYears } from "@/actions/academic.action";
import { getSchoolProfile } from "@/actions/school.action";
import type { AcademicYear } from "@/types";

function PageLoading() {
  return (
    <div className="flex h-96 items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  );
}

// Separate component that uses useSearchParams - must be wrapped in Suspense
function AcademicSettingsContent() {
  const searchParams = useSearchParams();
  const defaultTab = searchParams.get("tab") || "calendar";
  const [activeTab, setActiveTab] = useState(defaultTab);
  // Track which tabs have been visited so we mount components lazily but keep them alive
  const [visitedTabs, setVisitedTabs] = useState<Set<string>>(new Set([defaultTab]));

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    setVisitedTabs(prev => {
      if (prev.has(tab)) return prev;
      const next = new Set(prev);
      next.add(tab);
      return next;
    });
  };

  // Shared academic years state — fetched once, used by AcademicYears, Terms, and SchoolHolidays
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [academicYearsLoaded, setAcademicYearsLoaded] = useState(false);
  const [schoolType, setSchoolType] = useState<string | undefined>();

  useEffect(() => {
    async function loadAcademicYears() {
      const result = await getAcademicYears();
      if (result.success && result.data) {
        setAcademicYears(result.data);
      }
      setAcademicYearsLoaded(true);
    }
    async function loadSchoolType() {
      const result = await getSchoolProfile();
      if (result.success && result.data) {
        setSchoolType(result.data.school_type);
      }
    }
    loadAcademicYears();
    loadSchoolType();
  }, []);

  // Callback for AcademicYears component to notify parent when years change (create/update/delete)
  const handleYearsChange = useCallback((updatedYears: AcademicYear[]) => {
    setAcademicYears(updatedYears);
  }, []);

  return (
    <div className="space-y-6">
      <Tabs value={activeTab} onValueChange={handleTabChange} className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="calendar">Calendar</TabsTrigger>
          <TabsTrigger value="structure">Structure</TabsTrigger>
          <TabsTrigger value="timetable">Timetable</TabsTrigger>
          <TabsTrigger value="grading">Grading</TabsTrigger>
          <TabsTrigger value="other">Other</TabsTrigger>
        </TabsList>

        {/* Hybrid mount strategy: mount on first visit, keep mounted thereafter.
           Prevents 9+ simultaneous API calls on page load while preserving state on tab switches. */}
        <TabsContent value="calendar" className="space-y-6" forceMount style={{ display: activeTab === "calendar" ? undefined : "none" }} aria-hidden={activeTab !== "calendar"}>
          {visitedTabs.has("calendar") && (
            <>
              <AcademicYears
                initialAcademicYears={academicYearsLoaded ? academicYears : undefined}
                onYearsChange={handleYearsChange}
              />
              <Terms initialAcademicYears={academicYearsLoaded ? academicYears : undefined} />
            </>
          )}
        </TabsContent>

        <TabsContent value="structure" className="space-y-6" forceMount style={{ display: activeTab === "structure" ? undefined : "none" }} aria-hidden={activeTab !== "structure"}>
          {visitedTabs.has("structure") && (
            <>
              <Classes />
              <Subjects schoolType={schoolType} />
            </>
          )}
        </TabsContent>

        <TabsContent value="timetable" className="space-y-6" forceMount style={{ display: activeTab === "timetable" ? undefined : "none" }} aria-hidden={activeTab !== "timetable"}>
          {visitedTabs.has("timetable") && (
            <>
              <SchoolPeriods />
              <SchoolHolidays initialAcademicYears={academicYearsLoaded ? academicYears : undefined} />
            </>
          )}
        </TabsContent>

        <TabsContent value="grading" className="space-y-6" forceMount style={{ display: activeTab === "grading" ? undefined : "none" }} aria-hidden={activeTab !== "grading"}>
          {visitedTabs.has("grading") && (
            <>
              <GradingScales />
              <AssessmentWeights />
            </>
          )}
        </TabsContent>

        <TabsContent value="other" className="space-y-6" forceMount style={{ display: activeTab === "other" ? undefined : "none" }} aria-hidden={activeTab !== "other"}>
          {visitedTabs.has("other") && (
            <OtherSettings />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

// Main page wrapped in Suspense for useSearchParams
export default function AcademicSettingsPage() {
  return (
    <Suspense fallback={<PageLoading />}>
      <AcademicSettingsContent />
    </Suspense>
  );
}
