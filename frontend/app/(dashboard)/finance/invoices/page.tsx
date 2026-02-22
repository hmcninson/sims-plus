import { Suspense } from "react";
import { Metadata } from "next";
import { InvoicesList } from "./invoices-list";

export const metadata: Metadata = {
  title: "Invoices",
  description: "Manage student invoices",
};

export default function InvoicesPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <InvoicesList />
    </Suspense>
  );
}
