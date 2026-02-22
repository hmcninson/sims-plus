import { Suspense } from "react";
import { Metadata } from "next";
import { ScholarshipsList } from "./scholarships-list";

export const metadata: Metadata = {
  title: "Scholarships",
  description: "Manage scholarships and financial aid",
};

export default function ScholarshipsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <ScholarshipsList />
    </Suspense>
  );
}
