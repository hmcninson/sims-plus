import { Suspense } from "react";
import type { Metadata } from "next";
import { TeacherNotesPage } from "./teacher-notes-page";

export const metadata: Metadata = {
  title: "Teacher Notes",
  description: "Manage teacher notes about students",
};

export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <TeacherNotesPage />
    </Suspense>
  );
}
