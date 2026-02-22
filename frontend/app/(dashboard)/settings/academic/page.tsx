"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
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

function LoadingCard() {
  return (
    <Card>
      <CardContent className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin" />
      </CardContent>
    </Card>
  );
}

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

  return (
    <div className="space-y-6">
      <Tabs defaultValue={defaultTab} className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="calendar">Calendar</TabsTrigger>
          <TabsTrigger value="structure">Structure</TabsTrigger>
          <TabsTrigger value="timetable">Timetable</TabsTrigger>
          <TabsTrigger value="grading">Grading</TabsTrigger>
          <TabsTrigger value="other">Other</TabsTrigger>
        </TabsList>

        {/* Calendar Tab: Academic Years & Terms */}
        <TabsContent value="calendar" className="space-y-6">
          <AcademicYears />
          <Terms />
        </TabsContent>

        {/* Structure Tab: Classes & Subjects */}
        <TabsContent value="structure" className="space-y-6">
          <Classes />
          <Subjects />
        </TabsContent>

        {/* Timetable Tab: School Periods & Holidays */}
        <TabsContent value="timetable" className="space-y-6">
          <SchoolPeriods />
          <SchoolHolidays />
        </TabsContent>

        {/* Grading Tab: Grading Scales & Assessment Weights */}
        <TabsContent value="grading" className="space-y-6">
          <GradingScales />
          <AssessmentWeights />
        </TabsContent>

        {/* Other Settings Tab */}
        <TabsContent value="other" className="space-y-6">
          <OtherSettings />
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
