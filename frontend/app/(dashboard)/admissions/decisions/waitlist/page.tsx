import { Suspense } from "react";
import { Metadata } from "next";
import { WaitlistTable } from "@/components/admissions/waitlist-table";

export const metadata: Metadata = {
  title: "Waitlist Management",
  description: "Manage waitlisted applicants and priorities",
};

export default function WaitlistPage() {
  return (
    <div className="p-4 md:p-6">
      <Suspense
        fallback={
          <div className="flex h-[400px] items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          </div>
        }
      >
        <WaitlistTable />
      </Suspense>
    </div>
  );
}
