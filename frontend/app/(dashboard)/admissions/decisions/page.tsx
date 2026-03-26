import { Suspense } from "react";
import { Metadata } from "next";
import { DecisionsManagement } from "./decisions-management";

export const metadata: Metadata = {
  title: "Admission Decisions",
  description: "Make admission decisions on applications",
};

export default function DecisionsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <DecisionsManagement />
    </Suspense>
  );
}
