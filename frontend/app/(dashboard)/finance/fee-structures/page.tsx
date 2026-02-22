import { Suspense } from "react";
import { Metadata } from "next";
import { FeeStructuresList } from "./fee-structures-list";

export const metadata: Metadata = {
  title: "Fee Structures",
  description: "Manage fee structures and templates",
};

export default function FeeStructuresPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <FeeStructuresList />
    </Suspense>
  );
}
