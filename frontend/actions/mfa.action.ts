"use server";

import { cookies } from "next/headers";
import { apiPost, ApiError } from "@/lib/api";
import { getValidAccessToken } from "@/actions/auth.action";
import type { ActionResult, User } from "@/types";

// =========================
// Types
// =========================

export interface MFASetupData {
  secret: string;
  provisioning_uri: string;
  qr_code_base64: string;
  backup_codes: string[];
}

interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token: string;
}

// =========================
// Auth Context Helper
// =========================

async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  const subdomain = cookieStore.get("x-subdomain")?.value;
  return { token, subdomain };
}

/**
 * Set both auth cookies with secure defaults.
 * Duplicated from auth.action.ts because it's not exported.
 */
async function setAuthCookies(accessToken: string, refreshToken: string) {
  const cookieStore = await cookies();
  cookieStore.set("access_token", accessToken, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 900, // 15 minutes
  });
  cookieStore.set("refresh_token", refreshToken, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 604800, // 7 days
  });
}

// =========================
// MFA Actions
// =========================

/**
 * Begin MFA setup. Returns QR code, manual secret, and backup codes.
 * MFA is NOT enabled until verifyMFASetup() is called.
 */
export async function setupMFA(): Promise<ActionResult<MFASetupData>> {
  try {
    const { token, subdomain } = await getAuthContext();
    if (!token) {
      return { success: false, error: "Not authenticated" };
    }
    const response = await apiPost<MFASetupData>(
      "/auth/mfa/setup",
      {},
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "MFA setup failed",
    };
  }
}

/**
 * Verify a TOTP code from the authenticator app to complete MFA setup.
 * On success, MFA is enabled for the account.
 */
export async function verifyMFASetup(
  code: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    if (!token) {
      return { success: false, error: "Not authenticated" };
    }
    await apiPost("/auth/mfa/verify-setup", { code }, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Verification failed",
    };
  }
}

/**
 * Verify MFA code during login flow.
 * Uses the mfa_pending_token from the initial login response.
 * On success, returns full auth tokens and sets cookies.
 */
export async function verifyMFALogin(data: {
  mfa_pending_token: string;
  code: string;
}): Promise<ActionResult<User>> {
  try {
    const cookieStore = await cookies();
    const subdomain = cookieStore.get("x-subdomain")?.value;

    const response = await apiPost<AuthResponse>(
      "/auth/mfa/verify",
      data,
      { subdomain }
    );

    // Set auth cookies (same as normal login)
    await setAuthCookies(response.access_token, response.refresh_token);

    return { success: true, data: response.user };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "MFA verification failed",
      code: error instanceof ApiError ? error.status : undefined,
    };
  }
}

/**
 * Disable MFA for the current user. Requires password confirmation.
 */
export async function disableMFA(
  password: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    if (!token) {
      return { success: false, error: "Not authenticated" };
    }
    await apiPost(
      "/auth/mfa/disable",
      { password },
      { token, subdomain }
    );
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to disable MFA",
    };
  }
}

/**
 * Regenerate backup codes. Old codes are invalidated.
 * Requires password confirmation.
 */
export async function regenerateBackupCodes(
  password: string
): Promise<ActionResult<{ backup_codes: string[] }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    if (!token) {
      return { success: false, error: "Not authenticated" };
    }
    const response = await apiPost<{ backup_codes: string[] }>(
      "/auth/mfa/backup-codes",
      { password },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to regenerate codes",
    };
  }
}
