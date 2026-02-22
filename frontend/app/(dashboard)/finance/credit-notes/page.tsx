import { Suspense } from "react";
import { Metadata } from "next";
import { CreditNotesList } from "./credit-notes-list";

export const metadata: Metadata = {
  title: "Credit Notes",
  description: "Manage credit notes, refunds, and fee adjustments",
};

export default function CreditNotesPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <CreditNotesList />
    </Suspense>
  );
}
