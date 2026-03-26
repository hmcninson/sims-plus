"use server";

/**
 * SIMS Plus - Applicant Account Server Actions
 *
 * All data fetching and mutations for the applicant portal.
 * Auth actions set/clear cookies directly. Authenticated actions
 * pass the JWT token via getApplicantAuthContext().
 *
 * Cookie note: Applicant cookies are path-scoped to `/apply` and use distinct
 * names (`applicant_access_token`, `applicant_refresh_token`) to avoid session
 * conflicts with staff login. This ensures a user can be logged in as staff
 * and applicant simultaneously without cookie collisions.
 */

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { apiGet, apiPost, apiPut, ApiError } from "@/lib/api";
import type { ActionResult } from "@/types";
import type {
  ApplicantProfile,
  ApplicantRegisterData,
  ApplicantRegisterResponse,
  ApplicantLoginData,
  ApplicantLoginResponse,
  MyApplicationListResponse,
  MyApplicationDetail,
  DraftApplicationData,
  DraftCreateResponse,
  ClaimApplicationResponse,
  ChangePasswordData,
  PrintableApplicationResponse,
  GuardianData,
} from "@/types/applicant.type";
import type {
  DocumentUploadData,
  DocumentUploadResponse,
  PaymentInitiateResponse,
  OfferDetail,
  OfferResponse,
} from "@/types/admissions.type";

const PUBLIC_BASE = "/admissions/public/applicant";
const AUTH_BASE = "/admissions/applicant";

// =========================
// Helpers
// =========================

async function getSubdomain(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get("x-subdomain")?.value;
}

async function getApplicantAuthContext(): Promise<{
  token: string;
  subdomain: string | undefined;
}> {
  const cookieStore = await cookies();
  const token = cookieStore.get("applicant_access_token")?.value;
  const subdomain = await getSubdomain();
  return { token: token || "", subdomain };
}

async function setApplicantAuthCookies(accessToken: string, refreshToken: string) {
  const cookieStore = await cookies();
  cookieStore.set("applicant_access_token", accessToken, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/apply",
    maxAge: 900, // 15 min
  });
  cookieStore.set("applicant_refresh_token", refreshToken, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: "/apply",
    maxAge: 604800, // 7 days
  });
}

async function clearApplicantAuthCookies() {
  const cookieStore = await cookies();
  cookieStore.delete({ name: "applicant_access_token", path: "/apply" });
  cookieStore.delete({ name: "applicant_refresh_token", path: "/apply" });
}

// =========================
// Public Auth Actions
// =========================

export async function registerApplicant(
  data: ApplicantRegisterData
): Promise<ActionResult<ApplicantRegisterResponse>> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiPost<ApplicantRegisterResponse>(
      `${PUBLIC_BASE}/register`,
      data,
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Registration failed",
      code: error instanceof ApiError ? error.status : undefined,
    };
  }
}

export async function loginApplicant(
  data: ApplicantLoginData
): Promise<ActionResult<ApplicantLoginResponse>> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiPost<ApplicantLoginResponse>(
      `${PUBLIC_BASE}/login`,
      data,
      { subdomain }
    );
    await setApplicantAuthCookies(response.access_token, response.refresh_token);
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Login failed",
      code: error instanceof ApiError ? error.status : undefined,
    };
  }
}

export async function logoutApplicant(): Promise<void> {
  const cookieStore = await cookies();
  const token = cookieStore.get("applicant_access_token")?.value;
  const refreshToken = cookieStore.get("applicant_refresh_token")?.value;
  const subdomain = cookieStore.get("x-subdomain")?.value;

  try {
    if (token) {
      // Uses the shared /auth/logout endpoint which is role-agnostic
      // (accepts any valid JWT regardless of role)
      await apiPost(
        "/auth/logout",
        { refresh_token: refreshToken },
        { token, subdomain }
      );
    }
  } catch {
    // Ignore errors -- clear cookies regardless
  }

  await clearApplicantAuthCookies();
  redirect("/apply/login");
}

export async function verifyApplicantEmail(
  token: string
): Promise<ActionResult<{ message: string }>> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiPost<{ message: string }>(
      `${PUBLIC_BASE}/verify-email`,
      { token },
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Verification failed",
    };
  }
}

export async function resendApplicantVerification(
  email: string,
  turnstileToken: string
): Promise<ActionResult<{ message: string }>> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiPost<{ message: string }>(
      `${PUBLIC_BASE}/resend-verification`,
      { email, turnstile_token: turnstileToken },
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    // Return generic success to prevent email enumeration
    return {
      success: true,
      data: {
        message:
          "If this email is registered and unverified, you will receive a verification link shortly.",
      },
    };
  }
}

export async function applicantForgotPassword(
  email: string,
  turnstileToken: string
): Promise<ActionResult<{ message: string }>> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiPost<{ message: string }>(
      `${PUBLIC_BASE}/forgot-password`,
      { email, turnstile_token: turnstileToken },
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    // Return generic success to prevent email enumeration
    return {
      success: true,
      data: {
        message:
          "If an account with this email exists, you will receive a password reset link shortly.",
      },
    };
  }
}

export async function applicantResetPassword(
  token: string,
  password: string
): Promise<ActionResult<{ message: string }>> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiPost<{ message: string }>(
      `${PUBLIC_BASE}/reset-password`,
      { token, password },
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to reset password",
    };
  }
}

// =========================
// Profile Actions (Authenticated)
// =========================

export async function getApplicantProfile(): Promise<
  ActionResult<ApplicantProfile>
> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiGet<ApplicantProfile>(`${AUTH_BASE}/profile`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to fetch profile",
    };
  }
}

export async function updateApplicantProfile(
  data: Partial<Pick<ApplicantProfile, "first_name" | "last_name" | "phone">>
): Promise<ActionResult<ApplicantProfile>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiPut<ApplicantProfile>(
      `${AUTH_BASE}/profile`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to update profile",
    };
  }
}

export async function changeApplicantPassword(
  data: ChangePasswordData
): Promise<ActionResult<{ message: string }>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    await apiPut(
      `${AUTH_BASE}/profile/password`,
      data,
      { token, subdomain }
    );
    return { success: true, data: { message: "Password changed successfully" } };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to change password",
    };
  }
}

// =========================
// My Applications Actions (Authenticated)
// =========================

export async function getMyApplications(params?: {
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<ActionResult<MyApplicationListResponse>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    const qs = query.toString();
    const response = await apiGet<MyApplicationListResponse>(
      `${AUTH_BASE}/applications${qs ? `?${qs}` : ""}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch applications",
    };
  }
}

export async function getMyApplicationDetail(
  applicationId: string
): Promise<ActionResult<MyApplicationDetail>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiGet<MyApplicationDetail>(
      `${AUTH_BASE}/applications/${applicationId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch application details",
    };
  }
}

export async function createDraftApplication(
  data: DraftApplicationData
): Promise<ActionResult<DraftCreateResponse>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiPost<DraftCreateResponse>(
      `${AUTH_BASE}/applications`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to create draft",
    };
  }
}

export async function updateDraftApplication(
  applicationId: string,
  data: Partial<DraftApplicationData>
): Promise<ActionResult<DraftCreateResponse>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiPut<DraftCreateResponse>(
      `${AUTH_BASE}/applications/${applicationId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to update draft",
    };
  }
}

export async function submitDraftApplication(
  applicationId: string
): Promise<ActionResult<DraftCreateResponse>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiPost<DraftCreateResponse>(
      `${AUTH_BASE}/applications/${applicationId}/submit`, {}, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to submit application",
    };
  }
}

export async function uploadApplicationDocument(
  applicationId: string,
  data: DocumentUploadData
): Promise<ActionResult<DocumentUploadResponse>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiPost<DocumentUploadResponse>(
      `${AUTH_BASE}/applications/${applicationId}/documents`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to upload document",
    };
  }
}

export async function initiateApplicationPayment(
  applicationId: string,
  callbackUrl: string
): Promise<ActionResult<PaymentInitiateResponse>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiPost<PaymentInitiateResponse>(
      `${AUTH_BASE}/applications/${applicationId}/pay`,
      { callback_url: callbackUrl },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to initiate payment",
    };
  }
}

export async function getPrintableApplication(
  applicationId: string
): Promise<ActionResult<PrintableApplicationResponse>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiGet<PrintableApplicationResponse>(
      `${AUTH_BASE}/applications/${applicationId}/print`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch printable application",
    };
  }
}

// =========================
// Claim Flow (Authenticated)
// =========================

export async function claimApplication(
  trackingCode: string
): Promise<ActionResult<ClaimApplicationResponse>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiPost<ClaimApplicationResponse>(
      `${AUTH_BASE}/applications/claim`,
      { tracking_code: trackingCode },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to claim application",
    };
  }
}

// =========================
// Guardian Pre-Fill (Authenticated)
// =========================

export async function getGuardianPrefill(): Promise<ActionResult<GuardianData[]>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiGet<GuardianData[]>(
      "/admissions/applicant/applications/guardian-prefill",
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return { success: false, error: error instanceof Error ? error.message : "Failed to fetch guardian data" };
  }
}

// =========================
// Auth Context Helper
// =========================

/**
 * Get the current applicant user from the JWT.
 * Returns null if not logged in or token is invalid.
 * Used by the apply layout for auth gating on /apply/dashboard routes.
 */
export async function getApplicantUser(): Promise<ApplicantProfile | null> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    if (!token) return null;
    const response = await apiGet<ApplicantProfile>(`${AUTH_BASE}/profile`, {
      token,
      subdomain,
    });
    return response;
  } catch {
    // Try refresh once before giving up
    const cookieStore = await cookies();
    const refreshToken = cookieStore.get("applicant_refresh_token")?.value;
    if (!refreshToken) return null;
    try {
      const subdomain = await getSubdomain();
      // Uses the shared /auth/refresh endpoint which is role-agnostic
      // (rotates any valid refresh token regardless of role)
      const refreshResult = await apiPost<{ access_token: string; refresh_token: string }>(
        "/auth/refresh",
        { refresh_token: refreshToken },
        { subdomain }
      );
      await setApplicantAuthCookies(refreshResult.access_token, refreshResult.refresh_token);
      return await apiGet<ApplicantProfile>(`${AUTH_BASE}/profile`, {
        token: refreshResult.access_token,
        subdomain,
      });
    } catch {
      return null;
    }
  }
}

// =========================
// Offer Response (Applicant Portal)
// =========================

export async function getApplicantOfferDetails(
  applicationId: string
): Promise<ActionResult<OfferDetail>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiGet<OfferDetail>(
      `${AUTH_BASE}/offers/${applicationId}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch offer details",
    };
  }
}

export async function respondToApplicantOffer(
  applicationId: string,
  response: OfferResponse,
  notes?: string
): Promise<ActionResult<OfferDetail>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const result = await apiPost<OfferDetail>(
      `${AUTH_BASE}/offers/${applicationId}/respond`,
      { response, notes },
      { token, subdomain }
    );
    return { success: true, data: result };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to respond to offer",
    };
  }
}
