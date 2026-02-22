import { Suspense } from "react";
import { Metadata } from "next";
import { PaymentsList } from "./payments-list";

export const metadata: Metadata = {
  title: "Payments",
  description: "Track and record payments",
};

export default function PaymentsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <PaymentsList />
    </Suspense>
  );
}
