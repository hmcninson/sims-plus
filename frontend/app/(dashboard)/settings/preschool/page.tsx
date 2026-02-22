import { Suspense } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfigurationSettings, LearningAreas, RatingScales } from "@/components/preschool";

export const metadata = {
  title: "Preschool Settings",
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

export default function PreschoolSettingsPage() {
  return (
    <div className="space-y-6">
      <Tabs defaultValue="configuration" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="configuration">Configuration</TabsTrigger>
          <TabsTrigger value="learning-areas">Learning Areas</TabsTrigger>
          <TabsTrigger value="rating-scales">Rating Scales</TabsTrigger>
        </TabsList>

        {/* Configuration Tab */}
        <TabsContent value="configuration" className="space-y-6">
          <Suspense fallback={<LoadingCard />}>
            <ConfigurationSettings />
          </Suspense>
        </TabsContent>

        {/* Learning Areas Tab */}
        <TabsContent value="learning-areas" className="space-y-6">
          <Suspense fallback={<LoadingCard />}>
            <LearningAreas />
          </Suspense>
        </TabsContent>

        {/* Rating Scales Tab */}
        <TabsContent value="rating-scales" className="space-y-6">
          <Suspense fallback={<LoadingCard />}>
            <RatingScales />
          </Suspense>
        </TabsContent>
      </Tabs>
    </div>
  );
}
