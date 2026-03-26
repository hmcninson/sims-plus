import { Suspense } from "react";
import { Metadata } from "next";
import { Skeleton } from "@/components/ui/skeleton";
import { CSSPSUpload } from "@/components/admissions/cssps-upload";

export const metadata: Metadata = {
  title: "CSSPS Import",
  description: "Import CSSPS placement data for SHS admissions",
};

function CSSPSLoading() {
  return (
    <div className="p-4 md:p-6 space-y-6">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-4 w-96" />
      <Skeleton className="h-[500px]" />
    </div>
  );
}

export default function CSSPSPage() {
  return (
    <Suspense fallback={<CSSPSLoading />}>
      <div className="p-4 md:p-6 space-y-6">
        <div>
          <h1 className="text-xl font-semibold md:text-2xl">CSSPS Import</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Import Computerised School Selection and Placement System (CSSPS) data
            to create applications for placed students.
          </p>
        </div>
        <CSSPSUpload />
      </div>
    </Suspense>
  );
}
