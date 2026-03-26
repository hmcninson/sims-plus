import { Suspense } from "react";
import { Metadata } from "next";
import { PromotionsManagement } from "./promotions-management";

export const metadata: Metadata = {
  title: "Class Promotions",
  description: "Manage end-of-year class promotions",
};

export default function PromotionsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <PromotionsManagement />
    </Suspense>
  );
}
