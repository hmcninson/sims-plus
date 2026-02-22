import { Suspense } from "react";
import { Metadata } from "next";
import { BoardingHub } from "./boarding-hub";

export const metadata: Metadata = {
  title: "Boarding",
  description: "Boarding house management overview",
};

export default function BoardingPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <BoardingHub />
    </Suspense>
  );
}
