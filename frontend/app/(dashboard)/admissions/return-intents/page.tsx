import { Suspense } from "react";
import { Metadata } from "next";
import { ReturnIntentsManagement } from "./return-intents-management";

export const metadata: Metadata = {
  title: "Return Intents",
  description: "Manage intent-to-return surveys",
};

export default function ReturnIntentsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <ReturnIntentsManagement />
    </Suspense>
  );
}
