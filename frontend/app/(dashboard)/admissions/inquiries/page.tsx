import { Suspense } from "react";
import { Metadata } from "next";
import { InquiriesListPage } from "./inquiries-list";

export const metadata: Metadata = {
  title: "Inquiries",
  description: "Manage prospective student inquiries and leads",
};

export default function InquiriesPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <InquiriesListPage />
    </Suspense>
  );
}
