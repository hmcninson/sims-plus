import { Suspense } from "react";
import { Metadata } from "next";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getApplicationDetail, getEnrollmentChecklist } from "@/actions/admissions.action";
import { EnrollmentChecklistUI } from "@/components/admissions/enrollment-checklist-ui";
import { DepositPayment } from "@/components/admissions/deposit-payment";
import { BoardingSelector } from "@/components/admissions/boarding-selector";
import { WelcomePackPreview } from "@/components/admissions/welcome-pack-preview";
import type { ApplicationDetail, EnrollmentChecklist } from "@/types/admissions.type";

export const metadata: Metadata = {
  title: "Enrollment Checklist",
  description: "Manage enrollment checklist for accepted applicant",
};

function ChecklistLoading() {
  return (
    <div className="p-4 md:p-6 space-y-6">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-[120px]" />
      <Skeleton className="h-[400px]" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Skeleton className="h-[200px]" />
        <Skeleton className="h-[200px]" />
      </div>
    </div>
  );
}

async function ChecklistContent({ applicationId }: { applicationId: string }) {
  const [appResult, checklistResult] = await Promise.all([
    getApplicationDetail(applicationId),
    getEnrollmentChecklist(applicationId),
  ]);

  if (!appResult.success) {
    return (
      <div className="p-4 md:p-6">
        <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
          <p className="text-sm text-muted-foreground">{appResult.error}</p>
          <Link href="/admissions/enrollment">
            <Button variant="outline">Back to Enrollment</Button>
          </Link>
        </div>
      </div>
    );
  }

  const application = appResult.data;
  const checklist = checklistResult.success ? checklistResult.data : null;

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Link href="/admissions/enrollment">
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <ChevronLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-semibold md:text-2xl">
              Enrollment Checklist
            </h1>
            <p className="text-sm text-muted-foreground">
              {application.applicant_first_name} {application.applicant_last_name}
              {" "}&middot;{" "}
              {application.tracking_code}
              {application.target_class_name && (
                <> &middot; {application.target_class_name}</>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Boarding Selector + Deposit in a row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <BoardingSelector
          applicationId={applicationId}
          currentStatus={application.boarding_status ?? null}
        />
        <DepositPayment
          applicationId={applicationId}
          depositPaid={application.enrollment_deposit_paid ?? false}
          depositAmount={application.enrollment_deposit_amount ?? null}
          depositReference={application.enrollment_deposit_reference ?? null}
        />
      </div>

      {/* Checklist */}
      <EnrollmentChecklistUI
        applicationId={applicationId}
        initialChecklist={checklist}
      />

      {/* Welcome Pack */}
      <WelcomePackPreview
        applicationId={applicationId}
        applicantName={`${application.applicant_first_name} ${application.applicant_last_name}`}
        welcomePackSent={application.welcome_pack_sent ?? false}
        confirmationUrl={application.enrollment_confirmation_url ?? null}
      />
    </div>
  );
}

export default async function EnrollmentChecklistPage(props: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await props.params;

  return (
    <Suspense fallback={<ChecklistLoading />}>
      <ChecklistContent applicationId={id} />
    </Suspense>
  );
}
