"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { apiPost, apiGet } from "@/lib/api";
import type { ActionResult, User, LoginCredentials, RegisterData, RegistrationResponse } from "@/types";

interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token: string;
}

interface RefreshResponse {
  access_token: string;
  refresh_token: string;
}

/**
 * Get subdomain from cookies (set by proxy.ts)
 */
async function getSubdomainFromCookies(): Promise<string | undefined> {
  const cookieStore = await cookies();
  return cookieStore.get("x-subdomain")?.value;
}

/**
 * Refresh the access token using the refresh token
 */
export async function refreshAccessToken(): Promise<string | null> {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get("refresh_token")?.value;
  const subdomain = cookieStore.get("x-subdomain")?.value;

  if (!refreshToken) {
    return null;
  }

  try {
    const response = await apiPost<RefreshResponse>(
      "/auth/refresh",
      { refresh_token: refreshToken },
      { subdomain }
    );

    // Update cookies with new tokens
    cookieStore.set("access_token", response.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 15, // 15 minutes
    });
    cookieStore.set("refresh_token", response.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 7, // 7 days
    });

    return response.access_token;
  } catch {
    // Refresh failed - user needs to re-login
    return null;
  }
}

/**
 * Get valid access token (refreshing if needed)
 */
export async function getValidAccessToken(): Promise<string | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  const subdomain = cookieStore.get("x-subdomain")?.value;

  if (!token) {
    // No token - try to refresh
    return refreshAccessToken();
  }

  // Check if token is still valid by calling /auth/me
  try {
    await apiGet("/auth/me", { token, subdomain });
    return token; // Token is valid
  } catch {
    // Token invalid/expired - try to refresh
    return refreshAccessToken();
  }
}

/**
 * Login action
 */
export async function login(
  credentials: LoginCredentials
): Promise<ActionResult<User>> {
  try {
    const subdomain = await getSubdomainFromCookies();
    const response = await apiPost<AuthResponse>("/auth/login", credentials, { subdomain });

    // Set cookies
    const cookieStore = await cookies();
    cookieStore.set("access_token", response.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 15, // 15 minutes
    });
    cookieStore.set("refresh_token", response.refresh_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: 60 * 60 * 24 * 7, // 7 days
    });

    return { success: true, data: response.user };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Login failed",
    };
  }
}

/**
 * Register a new school (onboarding)
 */
export async function register(data: RegisterData): Promise<ActionResult<RegistrationResponse>> {
  try {
    const response = await apiPost<RegistrationResponse>("/onboarding/register", data);
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Registration failed",
    };
  }
}

/**
 * Logout action
 */
export async function logout(): Promise<void> {
  const cookieStore = await cookies();
  const subdomain = cookieStore.get("x-subdomain")?.value;

  try {
    const token = cookieStore.get("access_token")?.value;
    if (token) {
      await apiPost("/auth/logout", {}, { token, subdomain });
    }
  } catch {
    // Ignore logout errors
  }

  // Clear cookies
  cookieStore.delete("access_token");
  cookieStore.delete("refresh_token");

  redirect("/login");
}

interface MeResponse {
  user: User;
  tenant: {
    id: string;
    name: string;
    subdomain: string;
    subscription_tier: string;
    logo_url?: string;
    primary_color?: string;
  };
  permissions: string[];
}

/**
 * Get current user from token
 */
export async function getCurrentUser(): Promise<User | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  const subdomain = cookieStore.get("x-subdomain")?.value;

  if (!token) {
    return null;
  }

  try {
    const response = await apiGet<MeResponse>("/auth/me", { token, subdomain });
    return response.user;
  } catch {
    // Token invalid or expired - try refresh
    return null;
  }
}

/**
 * Get current user with full context (user, tenant, permissions)
 */
export async function getCurrentUserContext(): Promise<MeResponse | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  const subdomain = cookieStore.get("x-subdomain")?.value;

  if (!token) {
    return null;
  }

  try {
    return await apiGet<MeResponse>("/auth/me", { token, subdomain });
  } catch {
    return null;
  }
}

// =========================
// Password Reset Actions
// =========================

interface PasswordResetResponse {
  message: string;
}

interface ValidateTokenResponse {
  valid: boolean;
}

/**
 * Request password reset email
 */
export async function requestPasswordReset(
  email: string
): Promise<ActionResult<PasswordResetResponse>> {
  try {
    const subdomain = await getSubdomainFromCookies();
    const response = await apiPost<PasswordResetResponse>(
      "/auth/forgot-password",
      { email },
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    // Return success even on error to prevent email enumeration
    // The backend already handles this, but we add a fallback
    return {
      success: true,
      data: {
        message: "If an account with this email exists, you will receive a password reset link shortly.",
      },
    };
  }
}

/**
 * Validate password reset token
 */
export async function validateResetToken(
  token: string
): Promise<ActionResult<ValidateTokenResponse>> {
  try {
    const response = await apiGet<ValidateTokenResponse>(
      `/auth/validate-reset-token?token=${encodeURIComponent(token)}`
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Invalid or expired token",
    };
  }
}

/**
 * Reset password with token
 */
export async function resetPassword(
  token: string,
  password: string
): Promise<ActionResult<PasswordResetResponse>> {
  try {
    const response = await apiPost<PasswordResetResponse>("/auth/reset-password", {
      token,
      password,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to reset password",
    };
  }
}

// =========================
// Email Verification Actions
// =========================

interface EmailVerificationResponse {
  message: string;
}

/**
 * Verify email address with token
 */
export async function verifyEmail(
  token: string
): Promise<ActionResult<EmailVerificationResponse>> {
  try {
    const response = await apiPost<EmailVerificationResponse>("/auth/verify-email", {
      token,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to verify email",
    };
  }
}

/**
 * Validate email verification token
 */
export async function validateVerificationToken(
  token: string
): Promise<ActionResult<ValidateTokenResponse>> {
  try {
    const response = await apiGet<ValidateTokenResponse>(
      `/auth/validate-verification-token?token=${encodeURIComponent(token)}`
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Invalid or expired token",
    };
  }
}

/**
 * Resend email verification link
 */
export async function resendVerificationEmail(
  email: string
): Promise<ActionResult<EmailVerificationResponse>> {
  try {
    const subdomain = await getSubdomainFromCookies();
    const response = await apiPost<EmailVerificationResponse>(
      "/auth/resend-verification",
      { email },
      { subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    // Check for specific error codes
    const errorMessage = error instanceof Error ? error.message : "Failed to send verification email";

    // Rate limit or already verified errors should be shown to user
    if (errorMessage.includes("rate") || errorMessage.includes("already verified")) {
      return {
        success: false,
        error: errorMessage,
      };
    }

    // For other errors, return generic success to prevent email enumeration
    return {
      success: true,
      data: {
        message: "If this email is registered and unverified, you will receive a verification link shortly.",
      },
    };
  }
}
