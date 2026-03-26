/**
 * SIMS Plus - Multi-Step Application Form
 *
 * Path: {school}.simsplus.io/apply/{periodId}
 *
 * Server Component wrapper that fetches form config and passes to client.
 * Reads ?draft= query param to resume a draft application.
 * Checks applicant auth cookie to pass isAuthenticated + guardian prefill.
 */

import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";

import { getPublicFormConfig, getPublicSchoolInfo } from "@/actions/admissions.action";
import { getGuardianPrefill } from "@/actions/applicant.action";
import { ApplicationFormWizard } from "@/components/admissions/application-form-wizard";

import type { GuardianData } from "@/types/applicant.type";

interface PageProps {
  params: Promise<{ periodId: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function ApplicationFormPage({ params, searchParams }: PageProps) {
  const { periodId } = await params;
  const resolvedSearchParams = await searchParams;

  // Read the ?draft= query parameter
  const draftParam = resolvedSearchParams.draft;
  const draftId = typeof draftParam === "string" ? draftParam : undefined;

  const [formConfigResult, schoolInfoResult] = await Promise.all([
    getPublicFormConfig(periodId),
    getPublicSchoolInfo(),
  ]);

  if (!formConfigResult.success) {
    notFound();
  }

  // Check if applicant is authenticated
  const cookieStore = await cookies();
  const token = cookieStore.get("applicant_access_token")?.value;
  const isAuthenticated = !!token;

  // Redirect unauthenticated users to login for account-required periods
  if (formConfigResult.data.require_applicant_account && !isAuthenticated) {
    redirect(`/apply/login?redirect=/apply/${periodId}`);
  }

  // If authenticated, fetch guardian prefill data for pre-populating the form
  let prefillGuardians: GuardianData[] | undefined;
  if (isAuthenticated) {
    const guardianResult = await getGuardianPrefill();
    if (guardianResult.success && guardianResult.data.length > 0) {
      prefillGuardians = guardianResult.data;
    }
  }

  return (
    <ApplicationFormWizard
      formConfig={formConfigResult.data}
      schoolInfo={schoolInfoResult.success ? schoolInfoResult.data : null}
      draftId={draftId}
      isAuthenticated={isAuthenticated}
      prefillGuardians={prefillGuardians}
    />
  );
}
