import { Suspense } from "react";
import { Metadata } from "next";
import { EnrollmentQueue } from "./enrollment-queue";

export const metadata: Metadata = {
  title: "Enrollment",
  description: "Enroll accepted applicants as students",
};

export default function EnrollmentPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <EnrollmentQueue />
    </Suspense>
  );
}
