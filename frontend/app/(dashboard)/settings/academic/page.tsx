import { Suspense } from "react";
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
} from "@/components/academic";

export const metadata = {
  title: "Academic Settings",
};

function LoadingCard() {
  return (
    <Card>
      <CardContent className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin" />
      </CardContent>
    </Card>
  );
}

export default function AcademicSettingsPage() {
  return (
    <div className="space-y-6">
      <Tabs defaultValue="calendar" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="calendar">Calendar</TabsTrigger>
          <TabsTrigger value="structure">Structure</TabsTrigger>
          <TabsTrigger value="grading">Grading</TabsTrigger>
          <TabsTrigger value="other">Other</TabsTrigger>
        </TabsList>

        {/* Calendar Tab: Academic Years & Terms */}
        <TabsContent value="calendar" className="space-y-6">
          <Suspense fallback={<LoadingCard />}>
            <AcademicYears />
          </Suspense>
          <Suspense fallback={<LoadingCard />}>
            <Terms />
          </Suspense>
        </TabsContent>

        {/* Structure Tab: Classes & Subjects */}
        <TabsContent value="structure" className="space-y-6">
          <Suspense fallback={<LoadingCard />}>
            <Classes />
          </Suspense>
          <Suspense fallback={<LoadingCard />}>
            <Subjects />
          </Suspense>
        </TabsContent>

        {/* Grading Tab: Grading Scales & Assessment Weights */}
        <TabsContent value="grading" className="space-y-6">
          <Suspense fallback={<LoadingCard />}>
            <GradingScales />
          </Suspense>
          <Suspense fallback={<LoadingCard />}>
            <AssessmentWeights />
          </Suspense>
        </TabsContent>

        {/* Other Settings Tab */}
        <TabsContent value="other" className="space-y-6">
          <Suspense fallback={<LoadingCard />}>
            <OtherSettings />
          </Suspense>
        </TabsContent>
      </Tabs>
    </div>
  );
}
