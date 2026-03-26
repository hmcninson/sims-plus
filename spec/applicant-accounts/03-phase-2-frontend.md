# Phase 2: Frontend — Applicant Accounts

**Sprint:** 19-20 (parallel with backend Phase 2 services/endpoints)
**Agent:** Frontend Agent
**Depends on:** Backend applicant endpoints (Phase 2 backend), Phase 1 migration
**Produces:** Applicant registration, login, dashboard, draft management, claim flow, print view

---

## Task List

| # | Task | Files | Est. |
|---|------|-------|------|
| 3.1 | Create TypeScript types | `frontend/types/applicant.type.ts` | 0.25d |
| 3.2 | Create Server Actions | `frontend/actions/applicant.action.ts` | 0.5d |
| 3.3 | Create register page | `frontend/app/(auth)/apply/register/page.tsx` | 0.5d |
| 3.4 | Create login page | `frontend/app/(auth)/apply/login/page.tsx` | 0.5d |
| 3.5 | Create verify email page | `frontend/app/(auth)/apply/verify-email/page.tsx` | 0.25d |
| 3.6 | Create forgot password page | `frontend/app/(auth)/apply/forgot-password/page.tsx` | 0.25d |
| 3.7 | Create reset password page | `frontend/app/(auth)/apply/reset-password/page.tsx` | 0.25d |
| 3.8 | Create applicant dashboard | `frontend/app/(auth)/apply/dashboard/page.tsx` | 1d |
| 3.9 | Create application detail page | `frontend/app/(auth)/apply/dashboard/[id]/page.tsx` | 0.5d |
| 3.10 | Create print view page | `frontend/app/(auth)/apply/dashboard/[id]/print/page.tsx` | 0.5d |
| 3.11 | Modify landing page | `frontend/app/(auth)/apply/page.tsx` | 0.25d |
| 3.12 | Modify form wizard (auto-save) | `frontend/components/admissions/application-form-wizard.tsx` | 0.5d |
| 3.13 | Modify apply layout (auth state) | `frontend/app/(auth)/apply/layout.tsx` | 0.25d |
| 3.14 | Modify UserRole type | `frontend/types/index.ts` | 0.1d |

**Total estimated effort: 5.6 days**

---

## 3.1 TypeScript Types

**File:** `frontend/types/applicant.type.ts`

```typescript
/**
 * SIMS Plus - Applicant Accounts Type Definitions
 *
 * Types for the applicant portal: registration, login, profile,
 * my-applications dashboard, draft management, and claim flow.
 */

import type { ApplicationStatus } from "./admissions.type";

// =========================
// Applicant Profile
// =========================

export interface ApplicantProfile {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  email_verified: boolean;
  created_at: string;
}

// =========================
// Auth — Register / Login
// =========================

export interface ApplicantRegisterData {
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  password: string;
  turnstile_token: string;
}

export interface ApplicantRegisterResponse {
  user_id: string;
  email: string;
  message: string;
}

export interface ApplicantLoginData {
  email: string;
  password: string;
}

export interface ApplicantLoginResponse {
  access_token: string;
  refresh_token: string;
  user: ApplicantProfile;
  token_type: string; // Always "bearer"
}

// =========================
// My Applications
// =========================

// These fields are included in the backend schema for dashboard display
export interface MyApplicationListItem {
  id: string;
  tracking_code: string;
  applicant_first_name: string;
  applicant_last_name: string;
  applicant_other_names?: string;
  date_of_birth: string;
  gender: string;
  target_class_id: string;
  target_class_name?: string;
  admission_period_id: string;
  admission_period_name?: string;
  status: ApplicationStatus;
  fee_waived: boolean;
  submitted_at?: string;
  created_at: string;
  updated_at: string;
}

export interface MyApplicationListResponse {
  items: MyApplicationListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// =========================
// Draft Management
// =========================

export interface DraftApplicationData {
  admission_period_id: string;
  applicant_first_name: string;
  applicant_last_name: string;
  applicant_other_names?: string;
  date_of_birth?: string;   // Optional for partial drafts
  gender?: string;           // Optional for partial drafts
  nationality?: string;
  target_class_id?: string;  // Optional for partial drafts
  previous_school?: string;
  medical_info?: string;
  custom_fields?: Record<string, unknown>;
  guardians?: GuardianData[];
}

export interface GuardianData {
  first_name: string;
  last_name: string;
  phone: string;
  email?: string;
  relationship: "father" | "mother" | "guardian" | "other";
  is_primary: boolean;
  occupation?: string;
  address?: string;
}

export interface DraftCreateResponse {
  id: string;
  tracking_code: string;
  status: string;
  payment_required: boolean;
  application_fee_amount?: number;
}

// =========================
// Print View
// =========================

export interface PrintableApplicationResponse {
  id: string;
  tracking_code: string;
  school_name: string;
  school_logo_url?: string;
  admission_period_name: string;
  applicant_first_name: string;
  applicant_last_name: string;
  applicant_other_names?: string;
  date_of_birth?: string;
  gender?: string;
  nationality?: string;
  target_class_name?: string;
  status: string;
  previous_school?: string;
  medical_info?: string;
  custom_fields: Record<string, unknown>;
  submitted_at?: string;
  created_at: string;
  guardians: GuardianData[];
  documents: Array<{
    document_type: string;
    file_name: string;
    created_at: string;
  }>;
  payments: Array<{
    amount: number;
    currency: string;
    status: string;
    paid_at?: string;
  }>;
  decision?: {
    decision_type: string;
    offered_class_name?: string;
    conditions?: string;
    decision_date: string;
  };
  generated_at: string;
}

// =========================
// Claim Flow
// =========================

export interface ClaimApplicationData {
  tracking_code: string;
}

export interface ClaimApplicationResponse {
  application_id: string;
  tracking_code: string;
  status: string;
  message: string;
}

// =========================
// Password
// =========================

export interface ChangePasswordData {
  current_password: string;
  new_password: string;
}
```

---

## 3.2 Server Actions

**File:** `frontend/actions/applicant.action.ts`

```typescript
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
  DraftApplicationData,
  DraftCreateResponse,
  ClaimApplicationResponse,
  ChangePasswordData,
  PrintableApplicationResponse,
  GuardianData,
} from "@/types/applicant.type";
import type {
  ApplicationDetail,
  DocumentUploadData,
  DocumentUploadResponse,
  PaymentInitiateResponse,
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
  email: string
): Promise<ActionResult<{ message: string }>> {
  try {
    const subdomain = await getSubdomain();
    const response = await apiPost<{ message: string }>(
      `${PUBLIC_BASE}/resend-verification`,
      { email },
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
    const response = await apiPut<{ message: string }>(
      `${AUTH_BASE}/profile/password`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
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
): Promise<ActionResult<ApplicationDetail>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiGet<ApplicationDetail>(
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
): Promise<ActionResult<ApplicationDetail>> {
  try {
    const { token, subdomain } = await getApplicantAuthContext();
    const response = await apiPut<ApplicationDetail>(
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
```

---

## 3.3 Register Page

**File:** `frontend/app/(auth)/apply/register/page.tsx`

Client component. Turnstile widget, password strength indicator, school branding.

```tsx
"use client";

/**
 * SIMS Plus - Applicant Registration Page
 *
 * Prospective parents register here to create an applicant account.
 * Includes Turnstile captcha, password strength validation, and school branding.
 * Path: {school}.simsplus.io/apply/register
 */

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import Image from "next/image";
import Script from "next/script";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

import { registerApplicant } from "@/actions/applicant.action";
import { useTenant } from "@/components/providers/TenantProvider";
import {
  Loader2,
  AlertCircle,
  GraduationCap,
  Check,
  X,
  Eye,
  EyeOff,
  ArrowLeft,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

const registerSchema = z
  .object({
    first_name: z
      .string()
      .min(1, "First name is required")
      .max(100, "First name is too long")
      .transform((v) => v.trim()),
    last_name: z
      .string()
      .min(1, "Last name is required")
      .max(100, "Last name is too long")
      .transform((v) => v.trim()),
    email: z.string().email("Please enter a valid email address"),
    phone: z
      .string()
      .min(10, "Please enter a valid phone number")
      .max(20, "Phone number is too long"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string().min(1, "Please confirm your password"),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type RegisterFormData = z.infer<typeof registerSchema>;

// ---------------------------------------------------------------------------
// Password Strength
// ---------------------------------------------------------------------------

interface PasswordCheck {
  label: string;
  test: (pw: string) => boolean;
}

const PASSWORD_CHECKS: PasswordCheck[] = [
  { label: "At least 8 characters", test: (pw) => pw.length >= 8 },
  { label: "One uppercase letter", test: (pw) => /[A-Z]/.test(pw) },
  { label: "One lowercase letter", test: (pw) => /[a-z]/.test(pw) },
  { label: "One number", test: (pw) => /[0-9]/.test(pw) },
  {
    label: "One special character",
    test: (pw) => /[^a-zA-Z0-9]/.test(pw),
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ApplicantRegisterPage() {
  const router = useRouter();
  const { tenant, isLoading: tenantLoading } = useTenant();

  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const turnstileRef = useRef<HTMLDivElement>(null);

  const form = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      first_name: "",
      last_name: "",
      email: "",
      phone: "",
      password: "",
      confirm_password: "",
    },
  });

  const { isSubmitting } = form.formState;
  const passwordValue = form.watch("password");

  // Clear form error when user types
  useEffect(() => {
    const sub = form.watch(() => {
      if (formError) setFormError(null);
    });
    return () => sub.unsubscribe();
  }, [form, formError]);

  // Render Turnstile widget
  useEffect(() => {
    if (
      typeof window !== "undefined" &&
      (window as any).turnstile &&
      turnstileRef.current &&
      turnstileRef.current.childNodes.length === 0
    ) {
      (window as any).turnstile.render(turnstileRef.current, {
        sitekey: process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "",
        callback: (token: string) => setTurnstileToken(token),
        "expired-callback": () => setTurnstileToken(null),
      });
    }
  }, [tenantLoading]);

  async function onSubmit(values: RegisterFormData) {
    if (!turnstileToken) {
      setFormError("Please complete the security check.");
      return;
    }

    // Verify all password checks pass
    const allPassed = PASSWORD_CHECKS.every((c) => c.test(values.password));
    if (!allPassed) {
      setFormError("Password does not meet all requirements.");
      return;
    }

    setFormError(null);

    const result = await registerApplicant({
      first_name: values.first_name,
      last_name: values.last_name,
      email: values.email,
      phone: values.phone,
      password: values.password,
      turnstile_token: turnstileToken,
    });

    if (result.success) {
      setSuccess(true);
    } else {
      setFormError(result.error || "Registration failed. Please try again.");
      // Reset Turnstile on failure
      if ((window as any).turnstile) {
        (window as any).turnstile.reset();
      }
      setTurnstileToken(null);
    }
  }

  // ---------- Loading ----------
  if (tenantLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  // ---------- Success ----------
  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
              <Check className="h-8 w-8 text-green-600 dark:text-green-400" />
            </div>
            <CardTitle>Check Your Email</CardTitle>
            <CardDescription>
              We have sent a verification link to{" "}
              <span className="font-medium text-foreground">
                {form.getValues("email")}
              </span>
              . Please click the link to verify your email and activate your
              account.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Button asChild variant="outline">
              <Link href="/apply/login">Go to Login</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ---------- Render ----------
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js"
        strategy="afterInteractive"
      />

      <div className="w-full max-w-lg">
        {/* School Branding */}
        <div className="mb-8 text-center">
          {tenant?.branding?.logo_url ? (
            <div className="mb-4 flex justify-center">
              <Image
                src={tenant.branding.logo_url}
                alt={`${tenant.name} logo`}
                width={72}
                height={72}
                className="rounded-lg"
              />
            </div>
          ) : (
            <div className="mb-4 flex justify-center">
              <div
                className="flex h-16 w-16 items-center justify-center rounded-xl"
                style={{
                  backgroundColor:
                    tenant?.branding?.primary_color || "#1B4F72",
                }}
              >
                <GraduationCap className="h-8 w-8 text-white" />
              </div>
            </div>
          )}
          <h1
            className="text-2xl font-bold"
            style={{ color: tenant?.branding?.primary_color || undefined }}
          >
            {tenant?.name || "SIMS Plus"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Create an Applicant Account
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Register</CardTitle>
            <CardDescription>
              Create an account to apply for admission, save drafts, and track
              your applications.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {formError && (
              <Alert variant="destructive" className="mb-4">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{formError}</AlertDescription>
              </Alert>
            )}

            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                noValidate
                className="space-y-4"
              >
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="first_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>First Name</FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            placeholder="Kwame"
                            autoComplete="given-name"
                            disabled={isSubmitting}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="last_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Last Name</FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            placeholder="Mensah"
                            autoComplete="family-name"
                            disabled={isSubmitting}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email Address</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="email"
                          placeholder="parent@example.com"
                          autoComplete="email"
                          disabled={isSubmitting}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="phone"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Phone Number</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="tel"
                          placeholder="+233 24 123 4567"
                          autoComplete="tel"
                          disabled={isSubmitting}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Password</FormLabel>
                      <FormControl>
                        <div className="relative">
                          <Input
                            {...field}
                            type={showPassword ? "text" : "password"}
                            placeholder="Create a strong password"
                            autoComplete="new-password"
                            disabled={isSubmitting}
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                            onClick={() => setShowPassword(!showPassword)}
                            tabIndex={-1}
                          >
                            {showPassword ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Password strength checklist */}
                {passwordValue && (
                  <div className="space-y-1 rounded-md border p-3">
                    {PASSWORD_CHECKS.map((check) => {
                      const passed = check.test(passwordValue);
                      return (
                        <div
                          key={check.label}
                          className="flex items-center gap-2 text-xs"
                        >
                          {passed ? (
                            <Check className="h-3.5 w-3.5 text-green-600" />
                          ) : (
                            <X className="h-3.5 w-3.5 text-muted-foreground" />
                          )}
                          <span
                            className={
                              passed
                                ? "text-green-700 dark:text-green-400"
                                : "text-muted-foreground"
                            }
                          >
                            {check.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}

                <FormField
                  control={form.control}
                  name="confirm_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Confirm Password</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="password"
                          placeholder="Confirm your password"
                          autoComplete="new-password"
                          disabled={isSubmitting}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Turnstile widget */}
                <div ref={turnstileRef} className="flex justify-center" />

                <Button
                  type="submit"
                  className="w-full"
                  disabled={isSubmitting || !turnstileToken}
                  style={{
                    backgroundColor:
                      tenant?.branding?.primary_color || undefined,
                  }}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Creating Account...
                    </>
                  ) : (
                    "Create Account"
                  )}
                </Button>
              </form>
            </Form>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link
                href="/apply/login"
                className="font-medium text-primary hover:underline"
              >
                Sign in
              </Link>
            </p>
          </CardContent>
        </Card>

        <p className="mt-4 text-center text-sm text-muted-foreground">
          <Link
            href="/apply"
            className="inline-flex items-center gap-1 hover:underline"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Admissions
          </Link>
        </p>
      </div>
    </div>
  );
}
```

---

## 3.4 Login Page

**File:** `frontend/app/(auth)/apply/login/page.tsx`

Client component. Same error-state pattern as staff login (`error`, `locked`, `rate_limited`).

```tsx
"use client";

/**
 * SIMS Plus - Applicant Login Page
 *
 * Applicants log in here (separate from staff /auth/login).
 * The login endpoint rejects non-applicant roles.
 * Path: {school}.simsplus.io/apply/login
 */

import { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

import { loginApplicant } from "@/actions/applicant.action";
import { useTenant } from "@/components/providers/TenantProvider";
import {
  Loader2,
  AlertCircle,
  GraduationCap,
  Lock,
  Clock,
  ArrowLeft,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------

const loginSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormData = z.infer<typeof loginSchema>;

// ---------------------------------------------------------------------------
// Error types
// ---------------------------------------------------------------------------

interface FormError {
  message: string;
  type: "error" | "locked" | "rate_limited";
}

const URL_ERROR_MESSAGES: Record<
  string,
  { title: string; message: string; variant: "warning" | "error" }
> = {
  session_expired: {
    title: "Session expired",
    message: "Your session has expired. Please sign in again.",
    variant: "warning",
  },
  email_verified: {
    title: "Email verified",
    message: "Your email has been verified. You can now sign in.",
    variant: "warning",
  },
  password_reset: {
    title: "Password reset",
    message: "Your password has been reset. Please sign in with your new password.",
    variant: "warning",
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ApplicantLoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { tenant, isLoading: tenantLoading } = useTenant();

  const [formError, setFormError] = useState<FormError | null>(null);

  const errorParam = searchParams.get("error");
  const msgParam = searchParams.get("msg");
  const urlError = errorParam
    ? URL_ERROR_MESSAGES[errorParam]
    : msgParam
      ? URL_ERROR_MESSAGES[msgParam]
      : undefined;

  const form = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const { isSubmitting } = form.formState;

  // Clear form error on input change
  useEffect(() => {
    const sub = form.watch(() => {
      if (formError) setFormError(null);
    });
    return () => sub.unsubscribe();
  }, [form, formError]);

  async function onSubmit(values: LoginFormData) {
    setFormError(null);

    const result = await loginApplicant(values);

    if (result.success) {
      router.push("/apply/dashboard");
      return;
    }

    const code = result.code;

    if (code === 401) {
      setFormError({ message: "Invalid email or password", type: "error" });
    } else if (code === 403) {
      setFormError({
        message: result.error || "Account is locked",
        type: "locked",
      });
    } else if (code === 429) {
      setFormError({
        message: result.error || "Too many attempts. Please wait.",
        type: "rate_limited",
      });
    } else {
      setFormError({
        message: result.error || "Login failed. Please try again.",
        type: "error",
      });
    }
  }

  if (tenantLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* URL-based messages */}
        {urlError && (
          <Alert
            className={`mb-6 ${
              urlError.variant === "warning"
                ? "border-amber-500/50 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/50 dark:text-amber-200"
                : ""
            }`}
            variant={urlError.variant === "error" ? "destructive" : undefined}
          >
            <Clock className="h-4 w-4" />
            <AlertTitle>{urlError.title}</AlertTitle>
            <AlertDescription>{urlError.message}</AlertDescription>
          </Alert>
        )}

        {/* School Branding */}
        <div className="mb-8 text-center">
          {tenant?.branding?.logo_url ? (
            <div className="mb-4 flex justify-center">
              <Image
                src={tenant.branding.logo_url}
                alt={`${tenant.name} logo`}
                width={72}
                height={72}
                className="rounded-lg"
              />
            </div>
          ) : (
            <div className="mb-4 flex justify-center">
              <div
                className="flex h-16 w-16 items-center justify-center rounded-xl"
                style={{
                  backgroundColor:
                    tenant?.branding?.primary_color || "#1B4F72",
                }}
              >
                <GraduationCap className="h-8 w-8 text-white" />
              </div>
            </div>
          )}
          <h1
            className="text-2xl font-bold"
            style={{ color: tenant?.branding?.primary_color || undefined }}
          >
            {tenant?.name || "SIMS Plus"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Applicant Portal
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Sign In</CardTitle>
            <CardDescription>
              Sign in to manage your admission applications
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Error alerts -- same pattern as staff login */}
            {formError?.type === "error" && (
              <Alert variant="destructive" className="mb-4">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Login failed</AlertTitle>
                <AlertDescription>{formError.message}</AlertDescription>
              </Alert>
            )}
            {formError?.type === "locked" && (
              <Alert className="mb-4 border-amber-500/50 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/50 dark:text-amber-200">
                <Lock className="h-4 w-4" />
                <AlertTitle>Account locked</AlertTitle>
                <AlertDescription>{formError.message}</AlertDescription>
              </Alert>
            )}
            {formError?.type === "rate_limited" && (
              <Alert className="mb-4 border-amber-500/50 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/50 dark:text-amber-200">
                <Clock className="h-4 w-4" />
                <AlertTitle>Too many attempts</AlertTitle>
                <AlertDescription>{formError.message}</AlertDescription>
              </Alert>
            )}

            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                noValidate
                className="space-y-4"
              >
                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email Address</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="email"
                          placeholder="parent@example.com"
                          autoComplete="email"
                          disabled={isSubmitting}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <div className="flex items-center justify-between">
                        <FormLabel>Password</FormLabel>
                        <Link
                          href="/apply/forgot-password"
                          className="text-xs text-primary hover:underline"
                        >
                          Forgot password?
                        </Link>
                      </div>
                      <FormControl>
                        <Input
                          {...field}
                          type="password"
                          placeholder="Enter your password"
                          autoComplete="current-password"
                          disabled={isSubmitting}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <Button
                  type="submit"
                  className="w-full"
                  disabled={isSubmitting}
                  style={{
                    backgroundColor:
                      tenant?.branding?.primary_color || undefined,
                  }}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Signing in...
                    </>
                  ) : (
                    "Sign In"
                  )}
                </Button>
              </form>
            </Form>

            <div className="mt-6 space-y-2 text-center text-sm text-muted-foreground">
              <p>
                Don&apos;t have an account?{" "}
                <Link
                  href="/apply/register"
                  className="font-medium text-primary hover:underline"
                >
                  Create Account
                </Link>
              </p>
              <p>
                <Link
                  href="/apply/status"
                  className="text-primary hover:underline"
                >
                  Check Application Status
                </Link>
              </p>
            </div>
          </CardContent>
        </Card>

        <p className="mt-4 text-center text-sm text-muted-foreground">
          <Link
            href="/apply"
            className="inline-flex items-center gap-1 hover:underline"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Admissions
          </Link>
        </p>
      </div>
    </div>
  );
}
```

---

## 3.5 Verify Email Page

**File:** `frontend/app/(auth)/apply/verify-email/page.tsx`

```tsx
"use client";

/**
 * SIMS Plus - Applicant Email Verification Page
 *
 * Auto-calls verifyApplicantEmail(token) on mount.
 * Reads `token` from URL search params.
 * Path: {school}.simsplus.io/apply/verify-email?token=...
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { verifyApplicantEmail } from "@/actions/applicant.action";
import { Loader2, CheckCircle, XCircle } from "lucide-react";

type VerifyState = "loading" | "success" | "error";

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [state, setState] = useState<VerifyState>("loading");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!token) {
      setState("error");
      setErrorMsg("No verification token provided.");
      return;
    }

    let cancelled = false;

    verifyApplicantEmail(token).then((result) => {
      if (cancelled) return;
      if (result.success) {
        setState("success");
      } else {
        setState("error");
        setErrorMsg(result.error || "Verification failed.");
      }
    });

    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          {state === "loading" && (
            <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
          )}
          {state === "success" && (
            <CheckCircle className="mx-auto h-12 w-12 text-green-600" />
          )}
          {state === "error" && (
            <XCircle className="mx-auto h-12 w-12 text-red-600" />
          )}
          <CardTitle className="mt-4">
            {state === "loading" && "Verifying your email..."}
            {state === "success" && "Email Verified"}
            {state === "error" && "Verification Failed"}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-center">
          {state === "success" && (
            <>
              <p className="mb-4 text-sm text-muted-foreground">
                Your email has been verified. You can now sign in to your
                account.
              </p>
              <Button asChild>
                <Link href="/apply/login?msg=email_verified">
                  Sign In
                </Link>
              </Button>
            </>
          )}
          {state === "error" && (
            <>
              <p className="mb-4 text-sm text-muted-foreground">{errorMsg}</p>
              <Button asChild variant="outline">
                <Link href="/apply/login">Go to Login</Link>
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

---

## 3.6 Forgot Password Page

**File:** `frontend/app/(auth)/apply/forgot-password/page.tsx`

```tsx
"use client";

/**
 * SIMS Plus - Applicant Forgot Password Page
 *
 * Email input + Turnstile captcha. Calls applicantForgotPassword().
 * Always shows a success message to prevent email enumeration.
 * Path: {school}.simsplus.io/apply/forgot-password
 */

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import Script from "next/script";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

import { applicantForgotPassword } from "@/actions/applicant.action";
import { useTenant } from "@/components/providers/TenantProvider";
import { Loader2, ArrowLeft, Mail } from "lucide-react";

const forgotSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
});

type ForgotFormData = z.infer<typeof forgotSchema>;

export default function ApplicantForgotPasswordPage() {
  const { tenant } = useTenant();
  const [success, setSuccess] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null);
  const turnstileRef = useRef<HTMLDivElement>(null);

  const form = useForm<ForgotFormData>({
    resolver: zodResolver(forgotSchema),
    defaultValues: { email: "" },
  });

  const { isSubmitting } = form.formState;

  useEffect(() => {
    if (
      typeof window !== "undefined" &&
      (window as any).turnstile &&
      turnstileRef.current &&
      turnstileRef.current.childNodes.length === 0
    ) {
      (window as any).turnstile.render(turnstileRef.current, {
        sitekey: process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || "",
        callback: (token: string) => setTurnstileToken(token),
        "expired-callback": () => setTurnstileToken(null),
      });
    }
  }, []);

  async function onSubmit(values: ForgotFormData) {
    if (!turnstileToken) return;
    await applicantForgotPassword(values.email, turnstileToken);
    // Always show success to prevent enumeration
    setSuccess(true);
  }

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <Mail className="mx-auto h-12 w-12 text-primary" />
            <CardTitle className="mt-4">Check Your Email</CardTitle>
            <CardDescription>
              If an account with that email exists, we have sent a password
              reset link. Please check your inbox and spam folder.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <Button asChild variant="outline">
              <Link href="/apply/login">Back to Login</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js"
        strategy="afterInteractive"
      />
      <div className="w-full max-w-md">
        <Card>
          <CardHeader>
            <CardTitle>Forgot Password</CardTitle>
            <CardDescription>
              Enter your email address and we will send you a link to reset
              your password.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                noValidate
                className="space-y-4"
              >
                <FormField
                  control={form.control}
                  name="email"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Email Address</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="email"
                          placeholder="parent@example.com"
                          autoComplete="email"
                          disabled={isSubmitting}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div ref={turnstileRef} className="flex justify-center" />

                <Button
                  type="submit"
                  className="w-full"
                  disabled={isSubmitting || !turnstileToken}
                  style={{
                    backgroundColor:
                      tenant?.branding?.primary_color || undefined,
                  }}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    "Send Reset Link"
                  )}
                </Button>
              </form>
            </Form>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              <Link
                href="/apply/login"
                className="inline-flex items-center gap-1 hover:underline"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Back to Login
              </Link>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
```

---

## 3.7 Reset Password Page

**File:** `frontend/app/(auth)/apply/reset-password/page.tsx`

```tsx
"use client";

/**
 * SIMS Plus - Applicant Reset Password Page
 *
 * Reads `token` from URL search params. New password + confirm.
 * Redirects to /apply/login on success.
 * Path: {school}.simsplus.io/apply/reset-password?token=...
 */

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

import { applicantResetPassword } from "@/actions/applicant.action";
import { useTenant } from "@/components/providers/TenantProvider";
import { Loader2, AlertCircle, Check, X } from "lucide-react";

const resetSchema = z
  .object({
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm_password: z.string().min(1, "Please confirm your password"),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

type ResetFormData = z.infer<typeof resetSchema>;

const PASSWORD_CHECKS = [
  { label: "At least 8 characters", test: (pw: string) => pw.length >= 8 },
  { label: "One uppercase letter", test: (pw: string) => /[A-Z]/.test(pw) },
  { label: "One lowercase letter", test: (pw: string) => /[a-z]/.test(pw) },
  { label: "One number", test: (pw: string) => /[0-9]/.test(pw) },
  {
    label: "One special character",
    test: (pw: string) => /[^a-zA-Z0-9]/.test(pw),
  },
];

export default function ApplicantResetPasswordPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { tenant } = useTenant();
  const token = searchParams.get("token");

  const [formError, setFormError] = useState<string | null>(null);

  const form = useForm<ResetFormData>({
    resolver: zodResolver(resetSchema),
    defaultValues: { password: "", confirm_password: "" },
  });

  const { isSubmitting } = form.formState;
  const passwordValue = form.watch("password");

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6 text-center">
            <AlertCircle className="mx-auto mb-4 h-12 w-12 text-red-600" />
            <p className="font-medium">Invalid Reset Link</p>
            <p className="mt-2 text-sm text-muted-foreground">
              This password reset link is invalid or has expired.
            </p>
            <Button asChild className="mt-4" variant="outline">
              <Link href="/apply/forgot-password">Request New Link</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  async function onSubmit(values: ResetFormData) {
    setFormError(null);

    const allPassed = PASSWORD_CHECKS.every((c) => c.test(values.password));
    if (!allPassed) {
      setFormError("Password does not meet all requirements.");
      return;
    }

    const result = await applicantResetPassword(token!, values.password);

    if (result.success) {
      router.push("/apply/login?msg=password_reset");
    } else {
      setFormError(result.error || "Failed to reset password.");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Card>
          <CardHeader>
            <CardTitle>Reset Password</CardTitle>
            <CardDescription>Enter your new password below.</CardDescription>
          </CardHeader>
          <CardContent>
            {formError && (
              <Alert variant="destructive" className="mb-4">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{formError}</AlertDescription>
              </Alert>
            )}

            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                noValidate
                className="space-y-4"
              >
                <FormField
                  control={form.control}
                  name="password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>New Password</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="password"
                          placeholder="Enter new password"
                          autoComplete="new-password"
                          disabled={isSubmitting}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {passwordValue && (
                  <div className="space-y-1 rounded-md border p-3">
                    {PASSWORD_CHECKS.map((check) => {
                      const passed = check.test(passwordValue);
                      return (
                        <div
                          key={check.label}
                          className="flex items-center gap-2 text-xs"
                        >
                          {passed ? (
                            <Check className="h-3.5 w-3.5 text-green-600" />
                          ) : (
                            <X className="h-3.5 w-3.5 text-muted-foreground" />
                          )}
                          <span
                            className={
                              passed
                                ? "text-green-700 dark:text-green-400"
                                : "text-muted-foreground"
                            }
                          >
                            {check.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}

                <FormField
                  control={form.control}
                  name="confirm_password"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Confirm Password</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          type="password"
                          placeholder="Confirm new password"
                          autoComplete="new-password"
                          disabled={isSubmitting}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <Button
                  type="submit"
                  className="w-full"
                  disabled={isSubmitting}
                  style={{
                    backgroundColor:
                      tenant?.branding?.primary_color || undefined,
                  }}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Resetting...
                    </>
                  ) : (
                    "Reset Password"
                  )}
                </Button>
              </form>
            </Form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
```

---

## 3.8 Applicant Dashboard

**File:** `frontend/app/(auth)/apply/dashboard/page.tsx`

The main page for logged-in applicants. Shows all applications with action buttons.

```tsx
"use client";

/**
 * SIMS Plus - Applicant Dashboard
 *
 * Lists all of the applicant's applications (drafts, submitted, decisions).
 * Provides: New Application, Claim Application, Profile menu.
 * Path: {school}.simsplus.io/apply/dashboard
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

import {
  getMyApplications,
  getApplicantProfile,
  claimApplication,
  createDraftApplication,
  logoutApplicant,
} from "@/actions/applicant.action";
import { getPublicPeriods } from "@/actions/admissions.action";
import { ApplicationStatusBadge } from "@/components/admissions/application-status-badge";
import { useTenant } from "@/components/providers/TenantProvider";

import {
  Plus,
  LinkIcon,
  User,
  LogOut,
  KeyRound,
  GraduationCap,
  FileText,
  Loader2,
  ArrowRight,
} from "lucide-react";

import type { MyApplicationListItem } from "@/types/applicant.type";
import type { ApplicantProfile } from "@/types/applicant.type";
import type { PublicPeriod } from "@/types/admissions.type";

import { formatGhanaDate } from "@/lib/format";

export default function ApplicantDashboardPage() {
  const router = useRouter();
  const { tenant } = useTenant();

  const [profile, setProfile] = useState<ApplicantProfile | null>(null);
  const [applications, setApplications] = useState<MyApplicationListItem[]>(
    []
  );
  const [loading, setLoading] = useState(true);

  // Claim dialog state
  const [claimOpen, setClaimOpen] = useState(false);
  const [claimCode, setClaimCode] = useState("");
  const [claiming, setClaiming] = useState(false);

  // New application dialog state
  const [newAppOpen, setNewAppOpen] = useState(false);
  const [periods, setPeriods] = useState<PublicPeriod[]>([]);
  const [selectedPeriodId, setSelectedPeriodId] = useState("");
  const [creatingDraft, setCreatingDraft] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const [profileResult, appsResult] = await Promise.all([
      getApplicantProfile(),
      getMyApplications({ page_size: 50 }),
    ]);

    if (profileResult.success) setProfile(profileResult.data);
    if (appsResult.success) setApplications(appsResult.data.items);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Fetch periods when new-app dialog opens
  useEffect(() => {
    if (newAppOpen && periods.length === 0) {
      getPublicPeriods().then((result) => {
        if (result.success) setPeriods(result.data.items);
      });
    }
  }, [newAppOpen, periods.length]);

  async function handleClaim() {
    if (!claimCode.trim()) return;
    setClaiming(true);

    const result = await claimApplication(claimCode.trim());

    if (result.success) {
      toast.success("Application claimed successfully");
      setClaimOpen(false);
      setClaimCode("");
      fetchData();
    } else {
      toast.error(result.error || "Failed to claim application");
    }

    setClaiming(false);
  }

  async function handleNewApplication() {
    if (!selectedPeriodId) return;
    setCreatingDraft(true);

    // Create a minimal draft -- user will fill in details in the form wizard
    const result = await createDraftApplication({
      admission_period_id: selectedPeriodId,
      applicant_first_name: "",
      applicant_last_name: "",
      date_of_birth: "",
      gender: "",
      target_class_id: "",
    });

    if (result.success) {
      setNewAppOpen(false);
      // Navigate to the form wizard with the draft ID for editing
      router.push(`/apply/${selectedPeriodId}?draft=${result.data.id}`);
    } else {
      toast.error(result.error || "Failed to create application");
    }

    setCreatingDraft(false);
  }

  async function handleLogout() {
    await logoutApplicant();
  }

  // ---------- Loading Skeleton ----------
  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-8 flex items-center justify-between">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-10 w-10 rounded-full" />
        </div>
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 w-full rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {tenant?.branding?.logo_url ? (
            <Image
              src={tenant.branding.logo_url}
              alt={`${tenant.name} logo`}
              width={40}
              height={40}
              className="rounded-lg"
            />
          ) : (
            <div
              className="flex h-10 w-10 items-center justify-center rounded-lg"
              style={{
                backgroundColor:
                  tenant?.branding?.primary_color || "#1B4F72",
              }}
            >
              <GraduationCap className="h-5 w-5 text-white" />
            </div>
          )}
          <span className="text-lg font-semibold">
            {tenant?.name || "SIMS Plus"}
          </span>
        </div>

        {/* Profile dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-2">
              <User className="h-4 w-4" />
              {profile?.first_name}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem asChild>
              <Link href="/apply/dashboard/profile">
                <User className="mr-2 h-4 w-4" />
                Profile Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/apply/dashboard/change-password">
                <KeyRound className="mr-2 h-4 w-4" />
                Change Password
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" />
              Sign Out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Welcome */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">
          Welcome, {profile?.first_name || "Applicant"}
        </h1>
        <p className="text-sm text-muted-foreground">
          Manage your admission applications
        </p>
      </div>

      {/* Action Buttons */}
      <div className="mb-6 flex flex-wrap gap-3">
        {/* New Application */}
        <Dialog open={newAppOpen} onOpenChange={setNewAppOpen}>
          <DialogTrigger asChild>
            <Button
              style={{
                backgroundColor:
                  tenant?.branding?.primary_color || undefined,
              }}
            >
              <Plus className="mr-2 h-4 w-4" />
              New Application
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Start New Application</DialogTitle>
              <DialogDescription>
                Select the admission period you would like to apply for.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Admission Period</Label>
                <Select
                  value={selectedPeriodId}
                  onValueChange={setSelectedPeriodId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a period" />
                  </SelectTrigger>
                  <SelectContent>
                    {periods.map((period) => (
                      <SelectItem key={period.id} value={period.id}>
                        {period.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setNewAppOpen(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={handleNewApplication}
                disabled={!selectedPeriodId || creatingDraft}
              >
                {creatingDraft ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  "Start Application"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Claim Application */}
        <Dialog open={claimOpen} onOpenChange={setClaimOpen}>
          <DialogTrigger asChild>
            <Button variant="outline">
              <LinkIcon className="mr-2 h-4 w-4" />
              Claim Application
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Claim Application</DialogTitle>
              <DialogDescription>
                If you previously submitted an application without an account,
                enter your tracking code to link it to your account. Your
                account email must match a guardian email on the application.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="tracking-code">Tracking Code</Label>
                <Input
                  id="tracking-code"
                  value={claimCode}
                  onChange={(e) => setClaimCode(e.target.value)}
                  placeholder="e.g. APP-A1B2C3D4"
                  disabled={claiming}
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setClaimOpen(false)}
              >
                Cancel
              </Button>
              <Button
                onClick={handleClaim}
                disabled={!claimCode.trim() || claiming}
              >
                {claiming ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Claiming...
                  </>
                ) : (
                  "Claim"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {/* Applications List */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">
          My Applications ({applications.length})
        </h2>

        {applications.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <FileText className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
              <p className="text-lg font-medium">No applications yet</p>
              <p className="mt-2 text-sm text-muted-foreground">
                Start a new application or claim an existing one using your
                tracking code.
              </p>
            </CardContent>
          </Card>
        ) : (
          applications.map((app) => (
            <Card key={app.id} className="transition-colors hover:bg-muted/30">
              <CardContent className="flex items-center justify-between p-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold">
                      {app.applicant_first_name} {app.applicant_last_name}
                    </span>
                    <ApplicationStatusBadge status={app.status} />
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                    {app.target_class_name && (
                      <span>{app.target_class_name}</span>
                    )}
                    {app.admission_period_name && (
                      <span>{app.admission_period_name}</span>
                    )}
                    <span>
                      {app.submitted_at
                        ? `Submitted ${formatGhanaDate(app.submitted_at)}`
                        : `Created ${formatGhanaDate(app.created_at)}`}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {app.tracking_code}
                  </div>
                </div>

                <div className="ml-4 flex-shrink-0">
                  {app.status === "draft" ? (
                    <Button size="sm" asChild>
                      <Link
                        href={`/apply/${app.admission_period_id}?draft=${app.id}`}
                      >
                        Continue
                        <ArrowRight className="ml-1 h-3.5 w-3.5" />
                      </Link>
                    </Button>
                  ) : (
                    <Button size="sm" variant="outline" asChild>
                      <Link href={`/apply/dashboard/${app.id}`}>
                        View Details
                      </Link>
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
```

---

## 3.9 Application Detail Page

**File:** `frontend/app/(auth)/apply/dashboard/[id]/page.tsx`

Read-only view of a submitted application with status timeline and decision info.

```tsx
"use client";

/**
 * SIMS Plus - Applicant Application Detail Page
 *
 * Read-only view of a submitted application.
 * Shows personal info, guardians, documents, payment, status timeline, decision.
 * Path: {school}.simsplus.io/apply/dashboard/{id}
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { ApplicationStatusBadge } from "@/components/admissions/application-status-badge";
import { getMyApplicationDetail } from "@/actions/applicant.action";
import { formatGhanaDate } from "@/lib/format";

import {
  ArrowLeft,
  Printer,
  User,
  Users,
  FileText,
  CreditCard,
  Clock,
  CheckCircle,
} from "lucide-react";

import type { ApplicationDetail } from "@/types/admissions.type";

export default function ApplicantApplicationDetailPage() {
  const params = useParams();
  const applicationId = params.id as string;

  const [application, setApplication] = useState<ApplicationDetail | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMyApplicationDetail(applicationId).then((result) => {
      if (result.success) {
        setApplication(result.data);
      } else {
        setError(result.error || "Failed to load application");
      }
      setLoading(false);
    });
  }, [applicationId]);

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 px-4 py-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full rounded-lg" />
      </div>
    );
  }

  if (error || !application) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 text-center">
        <p className="text-muted-foreground">{error || "Not found"}</p>
        <Button asChild className="mt-4" variant="outline">
          <Link href="/apply/dashboard">Back to Dashboard</Link>
        </Button>
      </div>
    );
  }

  const a = application;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link
            href="/apply/dashboard"
            className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Dashboard
          </Link>
          <h1 className="flex items-center gap-3 text-2xl font-bold">
            {a.applicant_first_name} {a.applicant_last_name}
            <ApplicationStatusBadge status={a.status} />
          </h1>
          <p className="text-sm text-muted-foreground">{a.tracking_code}</p>
        </div>
        <Button variant="outline" asChild>
          <Link href={`/apply/dashboard/${applicationId}/print`}>
            <Printer className="mr-2 h-4 w-4" />
            Print
          </Link>
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left column -- details */}
        <div className="space-y-6 lg:col-span-2">
          {/* Personal Information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <User className="h-4 w-4" /> Personal Information
              </CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-muted-foreground">Full Name</dt>
                  <dd className="font-medium">
                    {a.applicant_first_name}{" "}
                    {a.applicant_other_names && `${a.applicant_other_names} `}
                    {a.applicant_last_name}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Date of Birth</dt>
                  <dd className="font-medium">
                    {formatGhanaDate(a.date_of_birth)}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Gender</dt>
                  <dd className="font-medium capitalize">{a.gender}</dd>
                </div>
                {a.nationality && (
                  <div>
                    <dt className="text-muted-foreground">Nationality</dt>
                    <dd className="font-medium">{a.nationality}</dd>
                  </div>
                )}
                <div>
                  <dt className="text-muted-foreground">Target Class</dt>
                  <dd className="font-medium">
                    {a.target_class_name || "---"}
                  </dd>
                </div>
                {a.previous_school && (
                  <div>
                    <dt className="text-muted-foreground">Previous School</dt>
                    <dd className="font-medium">{a.previous_school}</dd>
                  </div>
                )}
                {a.medical_info && (
                  <div className="sm:col-span-2">
                    <dt className="text-muted-foreground">
                      Medical Information
                    </dt>
                    <dd className="font-medium">{a.medical_info}</dd>
                  </div>
                )}
              </dl>
            </CardContent>
          </Card>

          {/* Guardians */}
          {a.guardians.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Users className="h-4 w-4" /> Guardians
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {a.guardians.map((g, i) => (
                  <div key={g.id}>
                    {i > 0 && <Separator className="mb-4" />}
                    <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
                      <div>
                        <dt className="text-muted-foreground">Name</dt>
                        <dd className="font-medium">
                          {g.first_name} {g.last_name}
                          {g.is_primary && (
                            <Badge variant="secondary" className="ml-2">
                              Primary
                            </Badge>
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">Relationship</dt>
                        <dd className="font-medium capitalize">
                          {g.relationship}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">Phone</dt>
                        <dd className="font-medium">{g.phone}</dd>
                      </div>
                      {g.email && (
                        <div>
                          <dt className="text-muted-foreground">Email</dt>
                          <dd className="font-medium">{g.email}</dd>
                        </div>
                      )}
                    </dl>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Documents */}
          {a.documents.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileText className="h-4 w-4" /> Documents
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {a.documents.map((doc) => (
                    <li
                      key={doc.id}
                      className="flex items-center justify-between"
                    >
                      <span>
                        <span className="font-medium capitalize">
                          {doc.document_type.replace(/_/g, " ")}
                        </span>
                        <span className="ml-2 text-muted-foreground">
                          {doc.file_name}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right column -- timeline, payment, decision */}
        <div className="space-y-6">
          {/* Status Timeline */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Clock className="h-4 w-4" /> Status History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="relative border-l border-muted-foreground/20 pl-4">
                {a.status_history.map((entry) => (
                  <li key={entry.id} className="mb-4 last:mb-0">
                    <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-background bg-primary" />
                    <p className="text-sm font-medium capitalize">
                      {entry.to_status.replace(/_/g, " ")}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatGhanaDate(entry.created_at)}
                    </p>
                    {entry.reason && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        {entry.reason}
                      </p>
                    )}
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>

          {/* Payment */}
          {a.payments.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <CreditCard className="h-4 w-4" /> Payment
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm">
                {a.payments.map((p) => (
                  <div key={p.id} className="space-y-1">
                    <div className="flex justify-between">
                      <span>Amount</span>
                      <span className="font-medium">
                        {p.currency} {p.amount.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Status</span>
                      <Badge variant="outline" className="capitalize">
                        {p.status}
                      </Badge>
                    </div>
                    {p.paid_at && (
                      <div className="flex justify-between">
                        <span>Paid</span>
                        <span>{formatGhanaDate(p.paid_at)}</span>
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Decision */}
          {a.decision && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <CheckCircle className="h-4 w-4" /> Decision
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span>Decision</span>
                  <Badge variant="outline" className="capitalize">
                    {a.decision.decision_type}
                  </Badge>
                </div>
                {a.decision.offered_class_name && (
                  <div className="flex justify-between">
                    <span>Offered Class</span>
                    <span className="font-medium">
                      {a.decision.offered_class_name}
                    </span>
                  </div>
                )}
                {a.decision.conditions && (
                  <div>
                    <span className="text-muted-foreground">Conditions:</span>
                    <p className="mt-1">{a.decision.conditions}</p>
                  </div>
                )}
                {a.decision.response_deadline && (
                  <div className="flex justify-between">
                    <span>Response Deadline</span>
                    <span className="font-medium">
                      {formatGhanaDate(a.decision.response_deadline)}
                    </span>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
```

---

## 3.10 Print View

**File:** `frontend/app/(auth)/apply/dashboard/[id]/print/page.tsx`

```tsx
"use client";

/**
 * SIMS Plus - Printable Application View
 *
 * Clean layout optimized for printing. Auto-triggers window.print() on load.
 * Uses @media print styles. No navigation chrome.
 * Path: {school}.simsplus.io/apply/dashboard/{id}/print
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { getPrintableApplication } from "@/actions/applicant.action";
import { useTenant } from "@/components/providers/TenantProvider";
import { formatGhanaDate } from "@/lib/format";
import { Loader2 } from "lucide-react";

import type { PrintableApplicationResponse } from "@/types/applicant.type";

export default function PrintApplicationPage() {
  const params = useParams();
  const applicationId = params.id as string;
  const { tenant } = useTenant();

  const [application, setApplication] = useState<PrintableApplicationResponse | null>(
    null
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPrintableApplication(applicationId).then((result) => {
      if (result.success) setApplication(result.data);
      setLoading(false);
    });
  }, [applicationId]);

  // Auto-print once data is loaded
  useEffect(() => {
    if (application && !loading) {
      const timer = setTimeout(() => window.print(), 500);
      return () => clearTimeout(timer);
    }
  }, [application, loading]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (!application) {
    return (
      <div className="p-8 text-center">
        <p>Application not found.</p>
      </div>
    );
  }

  const a = application;

  return (
    <>
      <style jsx global>{`
        @media print {
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="mx-auto max-w-3xl p-8 text-sm">
        {/* Letterhead */}
        <div className="mb-8 border-b-2 pb-4 text-center">
          <h1 className="text-xl font-bold">
            {tenant?.name || "School Name"}
          </h1>
          {tenant?.branding?.logo_url && (
            <p className="text-xs text-gray-500">
              {tenant.branding.logo_url}
            </p>
          )}
          <p className="mt-1 text-base font-semibold">
            Admission Application Form
          </p>
          <p className="text-xs text-gray-500">
            Tracking Code: {a.tracking_code}
          </p>
        </div>

        {/* Personal Information */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide">
            Personal Information
          </h2>
          <table className="w-full border-collapse text-sm">
            <tbody>
              <tr>
                <td className="border px-2 py-1 font-medium">Full Name</td>
                <td className="border px-2 py-1">
                  {a.applicant_first_name}{" "}
                  {a.applicant_other_names && `${a.applicant_other_names} `}
                  {a.applicant_last_name}
                </td>
                <td className="border px-2 py-1 font-medium">Gender</td>
                <td className="border px-2 py-1 capitalize">{a.gender}</td>
              </tr>
              <tr>
                <td className="border px-2 py-1 font-medium">Date of Birth</td>
                <td className="border px-2 py-1">
                  {formatGhanaDate(a.date_of_birth)}
                </td>
                <td className="border px-2 py-1 font-medium">Nationality</td>
                <td className="border px-2 py-1">{a.nationality || "---"}</td>
              </tr>
              <tr>
                <td className="border px-2 py-1 font-medium">Target Class</td>
                <td className="border px-2 py-1">
                  {a.target_class_name || "---"}
                </td>
                <td className="border px-2 py-1 font-medium">
                  Previous School
                </td>
                <td className="border px-2 py-1">
                  {a.previous_school || "---"}
                </td>
              </tr>
              {a.medical_info && (
                <tr>
                  <td className="border px-2 py-1 font-medium">
                    Medical Info
                  </td>
                  <td colSpan={3} className="border px-2 py-1">
                    {a.medical_info}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>

        {/* Guardians */}
        {a.guardians.length > 0 && (
          <section className="mb-6">
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wide">
              Guardian Information
            </h2>
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-gray-100">
                  <th className="border px-2 py-1 text-left">Name</th>
                  <th className="border px-2 py-1 text-left">Relationship</th>
                  <th className="border px-2 py-1 text-left">Phone</th>
                  <th className="border px-2 py-1 text-left">Email</th>
                </tr>
              </thead>
              <tbody>
                {a.guardians.map((g) => (
                  <tr key={g.id}>
                    <td className="border px-2 py-1">
                      {g.first_name} {g.last_name}
                      {g.is_primary ? " (Primary)" : ""}
                    </td>
                    <td className="border px-2 py-1 capitalize">
                      {g.relationship}
                    </td>
                    <td className="border px-2 py-1">{g.phone}</td>
                    <td className="border px-2 py-1">{g.email || "---"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {/* Documents */}
        {a.documents.length > 0 && (
          <section className="mb-6">
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wide">
              Uploaded Documents
            </h2>
            <ul className="list-inside list-disc">
              {a.documents.map((doc) => (
                <li key={doc.id}>
                  {doc.document_type.replace(/_/g, " ")} &mdash;{" "}
                  {doc.file_name}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Status */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide">
            Application Status
          </h2>
          <p>
            <strong>Status:</strong>{" "}
            <span className="capitalize">{a.status.replace(/_/g, " ")}</span>
          </p>
          {a.submitted_at && (
            <p>
              <strong>Submitted:</strong> {formatGhanaDate(a.submitted_at)}
            </p>
          )}
        </section>

        {/* Decision */}
        {a.decision && (
          <section className="mb-6">
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wide">
              Decision
            </h2>
            <p>
              <strong>Decision:</strong>{" "}
              <span className="capitalize">{a.decision.decision_type}</span>
            </p>
            {a.decision.offered_class_name && (
              <p>
                <strong>Offered Class:</strong>{" "}
                {a.decision.offered_class_name}
              </p>
            )}
            {a.decision.conditions && (
              <p>
                <strong>Conditions:</strong> {a.decision.conditions}
              </p>
            )}
          </section>
        )}

        {/* Footer */}
        <div className="mt-12 border-t pt-4 text-center text-xs text-gray-400">
          Generated from {tenant?.name || "SIMS Plus"} Admissions Portal
        </div>

        {/* Close/back button -- hidden on print */}
        <div className="no-print mt-8 text-center">
          <button
            onClick={() => window.history.back()}
            className="rounded-md border px-4 py-2 text-sm hover:bg-gray-50"
          >
            Back to Application
          </button>
        </div>
      </div>
    </>
  );
}
```

---

## 3.11 Modify Landing Page

**File to modify:** `frontend/app/(auth)/apply/page.tsx`

Add login/register links and per-period account-required badges. Insert the following changes into the existing Server Component.

### Changes

**1. Add account links section** after the "Admissions Portal" heading (after line ~100):

```tsx
{/* Account links -- add above the periods list */}
<div className="mb-6 flex flex-wrap items-center justify-center gap-4 text-sm">
  <span className="text-muted-foreground">
    Have an account?{" "}
    <Link
      href="/apply/login"
      className="font-medium text-primary underline underline-offset-4"
    >
      Sign in
    </Link>
  </span>
  <span className="text-muted-foreground">
    New here?{" "}
    <Link
      href="/apply/register"
      className="font-medium text-primary underline underline-offset-4"
    >
      Create an account
    </Link>
  </span>
</div>
```

**2. Add "Account Required" badge** to period cards. Inside the metadata badges section (after the "Entrance Exam Required" badge), add:

```tsx
{period.require_applicant_account && (
  <Badge variant="outline" className="gap-1">
    <User className="h-3 w-3" />
    Account Required
  </Badge>
)}
```

**3. Update the "Apply Now" button** to conditionally redirect to register if account is required and user is not logged in. Since this is a Server Component and cannot check client auth state, the redirect logic will live in the form wizard page (`[periodId]/page.tsx`) -- no change needed to the button itself. The form wizard will check auth state and redirect if needed.

**4. Add `User` to the lucide-react import:**

```tsx
import { /* ...existing... */ User } from "lucide-react";
```

**5. Update `PublicPeriod` type** in `admissions.type.ts` to include the new field:

```typescript
export interface PublicPeriod {
  // ... existing fields ...
  require_applicant_account: boolean; // ADD THIS
}
```

---

## 3.12 Modify Form Wizard (Auto-Save)

**File to modify:** `frontend/components/admissions/application-form-wizard.tsx`

Add auto-save capability for authenticated applicants. Changes to the component props and internal logic.

### New Props

Add these optional props to the component:

```typescript
interface ApplicationFormWizardProps {
  formConfig: PublicFormConfig;
  school: PublicSchoolInfo;
  // NEW: Authenticated applicant props
  draftId?: string;              // Pre-existing draft to resume
  isAuthenticated?: boolean;     // Whether user is logged in as applicant
  initialData?: Partial<DraftApplicationData>; // Pre-fill from existing draft
  prefillGuardians?: GuardianData[];           // Pre-fill from previous application
}
```

### Auto-Save Logic

Add a `useEffect` that debounces draft saves on step change (inside the component, after the form state):

```typescript
import {
  updateDraftApplication,
  submitDraftApplication,
} from "@/actions/applicant.action";

// Auto-save ref to track the draft ID (may be set after initial creation)
const draftIdRef = useRef<string | undefined>(draftId);

// Debounced auto-save on step change (only for authenticated users)
const autoSaveTimerRef = useRef<NodeJS.Timeout | null>(null);
const [autoSaving, setAutoSaving] = useState(false);

useEffect(() => {
  if (!isAuthenticated || !draftIdRef.current) return;

  // Clear any existing timer
  if (autoSaveTimerRef.current) {
    clearTimeout(autoSaveTimerRef.current);
  }

  // Save after 2 seconds of inactivity on step change
  autoSaveTimerRef.current = setTimeout(async () => {
    setAutoSaving(true);
    try {
      const currentData = collectFormData(); // gather data from all forms
      await updateDraftApplication(draftIdRef.current!, currentData);
    } catch {
      // Silently fail -- user can manually save
    }
    setAutoSaving(false);
  }, 2000);

  return () => {
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }
  };
}, [currentStep, isAuthenticated]);
```

### Auto-Save Indicator

Add a saving indicator to the step header area:

```tsx
{autoSaving && (
  <span className="flex items-center gap-1 text-xs text-muted-foreground">
    <Loader2 className="h-3 w-3 animate-spin" />
    Saving...
  </span>
)}
```

### Modified Submit Handler

When `isAuthenticated` is true, use `submitDraftApplication()` instead of the anonymous `submitApplication()`:

```typescript
async function handleSubmit() {
  if (isAuthenticated && draftIdRef.current) {
    // Authenticated flow: submit the draft
    const result = await submitDraftApplication(draftIdRef.current);
    if (result.success) {
      if (result.data.payment_required) {
        // Redirect to payment
      } else {
        router.push("/apply/dashboard");
        toast.success("Application submitted successfully!");
      }
    } else {
      toast.error(result.error || "Failed to submit");
    }
  } else {
    // Anonymous flow: existing submitApplication() logic unchanged
  }
}
```

### Guardian Pre-Fill

If `prefillGuardians` is provided, use it as defaultValues for the guardians form:

```typescript
const guardiansForm = useForm<GuardiansFormValues>({
  resolver: zodResolver(guardiansFormSchema),
  defaultValues: {
    guardians: prefillGuardians?.length
      ? prefillGuardians
      : [{ first_name: "", last_name: "", phone: "", relationship: "father", is_primary: true }],
  },
});
```

---

## 3.13 Modify Apply Layout

**File to modify:** `frontend/app/(auth)/apply/layout.tsx`

Add auth state checking for `/apply/dashboard` routes.

### Updated Code

```tsx
/**
 * SIMS Plus - Public Application Form Layout
 *
 * Branded layout for the admissions portal.
 * Uses TenantProvider from parent (auth) layout for tenant context.
 * Provides minimal chrome: centered content with school branding header.
 *
 * Auth gating: /apply/dashboard/* routes require an authenticated applicant.
 * Unauthenticated users are redirected to /apply/login.
 */

import { Suspense } from "react";
import { redirect } from "next/navigation";
import { headers } from "next/headers";

import { Skeleton } from "@/components/ui/skeleton";
import { getApplicantUser } from "@/actions/applicant.action";

export default async function ApplyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Check if current path requires auth (dashboard routes)
  const headersList = await headers();
  const pathname = headersList.get("x-pathname") || "";

  const isDashboardRoute = pathname.startsWith("/apply/dashboard");

  if (isDashboardRoute) {
    const user = await getApplicantUser();
    if (!user) {
      redirect("/apply/login?error=session_expired");
    }
  }

  return (
    <div className="min-h-screen bg-muted/30">
      <Suspense
        fallback={
          <div className="flex min-h-screen items-center justify-center p-4">
            <div className="w-full max-w-3xl space-y-4">
              <Skeleton className="mx-auto h-20 w-20 rounded-full" />
              <Skeleton className="mx-auto h-8 w-64" />
              <Skeleton className="mx-auto h-4 w-48" />
              <Skeleton className="h-64 w-full rounded-lg" />
            </div>
          </div>
        }
      >
        {children}
      </Suspense>
    </div>
  );
}
```

**Implementation note:** If `x-pathname` header is not available in your Next.js setup, an alternative approach is to use Next.js middleware (`proxy.ts`) to handle the auth redirect for `/apply/dashboard` routes. Add a check in the existing middleware:

```typescript
// In proxy.ts -- add to existing matchers
if (pathname.startsWith("/apply/dashboard")) {
  const accessToken = request.cookies.get("applicant_access_token")?.value;
  if (!accessToken) {
    return NextResponse.redirect(new URL("/apply/login?error=session_expired", request.url));
  }
}
```

---

## 3.14 Modify Types

**File to modify:** `frontend/types/index.ts`

Add `"applicant"` to the `UserRole` union type.

### Current Code

```typescript
export type UserRole =
  | "platform_admin"
  | "chain_admin"
  | "school_admin"
  | "academic_head"
  | "finance_officer"
  | "teacher"
  | "house_parent"
  | "parent"
  | "student";
```

### Updated Code

```typescript
export type UserRole =
  | "platform_admin"
  | "chain_admin"
  | "school_admin"
  | "academic_head"
  | "finance_officer"
  | "teacher"
  | "house_parent"
  | "parent"
  | "student"
  | "applicant";
```

Also update the staff login page redirect logic in `frontend/app/(auth)/login/page.tsx` to handle the `applicant` role:

```typescript
// In onSubmit, after result.success check:
if (result.data.role === "applicant") {
  redirectUrl = "/apply/dashboard";
}
```

---

## File Summary

| File | Type | Purpose |
|------|------|---------|
| `frontend/types/applicant.type.ts` | New | TypeScript types for applicant portal |
| `frontend/actions/applicant.action.ts` | New | Server Actions for applicant auth + CRUD |
| `frontend/app/(auth)/apply/register/page.tsx` | New | Applicant registration form |
| `frontend/app/(auth)/apply/login/page.tsx` | New | Applicant login form |
| `frontend/app/(auth)/apply/verify-email/page.tsx` | New | Email verification handler |
| `frontend/app/(auth)/apply/forgot-password/page.tsx` | New | Forgot password form |
| `frontend/app/(auth)/apply/reset-password/page.tsx` | New | Reset password form |
| `frontend/app/(auth)/apply/dashboard/page.tsx` | New | Applicant dashboard (my applications) |
| `frontend/app/(auth)/apply/dashboard/[id]/page.tsx` | New | Application detail (read-only) |
| `frontend/app/(auth)/apply/dashboard/[id]/print/page.tsx` | New | Printable application view |
| `frontend/app/(auth)/apply/page.tsx` | Modified | Add login/register links, account-required badge |
| `frontend/app/(auth)/apply/layout.tsx` | Modified | Auth state gating for dashboard routes |
| `frontend/app/(auth)/login/page.tsx` | Modified | Handle applicant role redirect |
| `frontend/components/admissions/application-form-wizard.tsx` | Modified | Auto-save, draft props, guardian pre-fill |
| `frontend/types/index.ts` | Modified | Add "applicant" to UserRole union |
| `frontend/types/admissions.type.ts` | Modified | Add require_applicant_account to PublicPeriod |

---

## Design Patterns

- **Server Components** for data fetching pages (landing page with periods)
- **Client Components** for forms and interactive elements (login, register, dashboard)
- **React Hook Form + Zod** for all form validation (register, login, forgot/reset password)
- **Shadcn/ui components used:** Card, Button, Input, Form, Alert, Badge, Dialog, DropdownMenu, Select, Separator, Skeleton, Label
- **School branding** via `useTenant()` hook from TenantProvider -- logo, primary_color, school name
- **Responsive design** (mobile-first): `grid-cols-1 sm:grid-cols-2`, `w-full max-w-md/lg`, flex-wrap for action buttons
- **Toast notifications** (sonner) for claim success/failure, submission feedback
- **ActionResult<T> pattern** for all Server Actions: `{ success: true, data }` or `{ success: false, error, code? }`
- **Error state differentiation**: `error`, `locked`, `rate_limited` -- same as staff login
- **Cookie pattern**: applicant cookies use distinct names (`applicant_access_token`, `applicant_refresh_token`) path-scoped to `/apply` to avoid session conflicts with staff login
- **Anti-enumeration**: forgot-password and resend-verification always return success messages
- **Turnstile captcha**: registration and forgot-password forms include Cloudflare Turnstile
- **Auto-save**: draft applications saved server-side with 2s debounce on step change
- **Print view**: `@media print` styles, `window.print()` auto-trigger, `no-print` class for non-print elements
