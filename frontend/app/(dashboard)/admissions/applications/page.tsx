import { Suspense } from "react";
import { Metadata } from "next";
import { ApplicationsList } from "./applications-list";

export const metadata: Metadata = {
  title: "Applications",
  description: "Manage admission applications",
};

export default function ApplicationsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <ApplicationsList />
    </Suspense>
  );
}
