import { Suspense } from "react";
import { getEmailStats, getEmailHistory } from "@/actions/messaging.action";
import { EmailPageContent } from "./email-page-content";

export const metadata = {
  title: "Email Messages | SIMS Plus",
};

async function EmailPageLoader() {
  const [statsResult, historyResult] = await Promise.all([
    getEmailStats(),
    getEmailHistory(),
  ]);

  return (
    <EmailPageContent
      initialStats={statsResult.success ? statsResult.data : undefined}
      initialHistory={historyResult.success ? historyResult.data : undefined}
    />
  );
}

export default function EmailPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-[400px] items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      }
    >
      <EmailPageLoader />
    </Suspense>
  );
}
