"use server";

import { cookies } from "next/headers";
import { apiPost } from "@/lib/api";
import { getValidAccessToken } from "@/actions/auth.action";
import type { ActionResult } from "@/types";

/**
 * Helper to get auth context for authenticated OTP actions.
 */
async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  const subdomain = cookieStore.get("x-subdomain")?.value;
  if (!token) {
    throw new Error("Not authenticated");
  }
  return { token, subdomain };
}

/**
 * Helper to get subdomain for unauthenticated OTP actions.
 */
async function getSubdomain() {
  const cookieStore = await cookies();
  return cookieStore.get("x-subdomain")?.value;
}

// =========================
// Phone Verification (Authenticated)
// =========================

/**
 * Send OTP to the authenticated user's phone for verification.
 * Requires: User must be logged in and have a phone number on profile.
 */
export async function sendPhoneOTP(): Promise<ActionResult> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiPost("/auth/send-phone-otp", {}, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to send code",
    };
  }
}

/**
 * Verify phone number using 6-digit OTP code.
 * Requires: User must be logged in.
 */
export async function verifyPhone(code: string): Promise<ActionResult> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiPost("/auth/verify-phone", { code }, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Verification failed",
    };
  }
}

// =========================
// SMS Password Reset (Unauthenticated)
// =========================

/**
 * Request SMS OTP for password reset (unauthenticated).
 * Always returns success to prevent phone enumeration.
 */
export async function forgotPasswordSMS(
  phone: string,
): Promise<ActionResult> {
  try {
    const subdomain = await getSubdomain();
    await apiPost("/auth/forgot-password-sms", { phone }, { subdomain });
    return { success: true, data: undefined };
  } catch {
    // Always return success to prevent phone enumeration
    return { success: true, data: undefined };
  }
}

/**
 * Reset password using phone + OTP code (unauthenticated).
 */
export async function resetPasswordSMS(data: {
  phone: string;
  code: string;
  new_password: string;
}): Promise<ActionResult> {
  try {
    const subdomain = await getSubdomain();
    await apiPost("/auth/reset-password-sms", data, { subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Password reset failed",
    };
  }
}
