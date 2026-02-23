"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { apiPost, apiGet, ApiError } from "@/lib/api";
import type { ActionResult, User, SessionContext, LoginCredentials, RegisterData, RegistrationResponse } from "@/types";

interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token: string;
}

interface RefreshResponse {
  access_token: string;
  refresh_token: string;
}

// =========================
// Cookie Helpers
// =========================

/**
 * Set both auth cookies with secure defaults.
 * Extracted to avoid duplicating cookie config across login and refresh.
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

/**
 * Clear both auth cookies on logout or session invalidation.
 */
async function clearAuthCookies() {
  const cookieStore = await cookies();
  cookieStore.delete("access_token");
  cookieStore.delete("refresh_token");
  cookieStore.delete("x-active-school");
}

// =========================
// Token Management
// =========================

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

    await setAuthCookies(response.access_token, response.refresh_token);

    return response.access_token;
  } catch {
    // Refresh failed - user needs to re-login
    return null;
  }
}

/**
 * Get valid access token (refreshing if needed).
 *
 * Returns the current access_token cookie value if it exists, otherwise
 * attempts a refresh. We intentionally do NOT validate the token against
 * /auth/me here -- that would double every API request. Instead, callers
 * should handle 401 errors at the fetch level (server-api.ts does this
 * automatically; individual Server Actions catch ApiError in their own
 * try/catch blocks).
 */
export async function getValidAccessToken(): Promise<string | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;

  if (!token) {
    // No access_token cookie - attempt refresh from refresh_token
    return refreshAccessToken();
  }

  return token;
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

    await setAuthCookies(response.access_token, response.refresh_token);

    return { success: true, data: response.user };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Login failed",
      code: error instanceof ApiError ? error.status : undefined,
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
      code: error instanceof ApiError ? error.status : undefined,
    };
  }
}

/**
 * Logout action.
 * Sends the refresh_token to the backend so it can be blacklisted,
 * preventing reuse after logout.
 */
export async function logout(): Promise<void> {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  const refreshToken = cookieStore.get("refresh_token")?.value;
  const subdomain = cookieStore.get("x-subdomain")?.value;

  try {
    if (token) {
      // Send refresh_token in body so backend can blacklist it
      await apiPost("/auth/logout",
        { refresh_token: refreshToken },
        { token, subdomain }
      );
    }
  } catch {
    // Ignore logout errors - we clear cookies regardless
  }

  await clearAuthCookies();

  redirect("/login");
}

/**
 * Get current user from token.
 * If the access token is missing or returns 401, attempts a single
 * token refresh before giving up.
 *
 * IMPORTANT: A 429 (rate limited) response does NOT mean the session
 * is invalid. We throw instead of returning null so the dashboard
 * layout can distinguish "rate limited" from "session expired".
 */
export async function getCurrentUser(): Promise<User | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  const subdomain = cookieStore.get("x-subdomain")?.value;

  if (!token) {
    // No access token - try to refresh and retry
    const newToken = await refreshAccessToken();
    if (!newToken) return null;

    try {
      const response = await apiGet<SessionContext>("/auth/me", { token: newToken, subdomain });
      return response.user;
    } catch (error) {
      // Propagate rate limit errors so callers know the session may still be valid
      if (error instanceof ApiError && error.status === 429) {
        throw error;
      }
      return null;
    }
  }

  try {
    const response = await apiGet<SessionContext>("/auth/me", { token, subdomain });
    return response.user;
  } catch (error) {
    // If 401 (expired/invalid token), try refresh once then retry
    if (error instanceof ApiError && error.status === 401) {
      const newToken = await refreshAccessToken();
      if (!newToken) return null;

      try {
        const response = await apiGet<SessionContext>("/auth/me", { token: newToken, subdomain });
        return response.user;
      } catch (retryError) {
        // Propagate rate limit errors
        if (retryError instanceof ApiError && retryError.status === 429) {
          throw retryError;
        }
        return null;
      }
    }
    // Propagate rate limit errors so callers know the session may still be valid
    if (error instanceof ApiError && error.status === 429) {
      throw error;
    }
    return null;
  }
}

/**
 * Get current user with full context (user, tenant, permissions).
 * Same refresh-on-401 logic as getCurrentUser.
 *
 * IMPORTANT: A 429 (rate limited) response does NOT mean the session
 * is invalid. We throw instead of returning null so the dashboard
 * layout can distinguish "rate limited" from "session expired".
 */
export async function getCurrentUserContext(): Promise<SessionContext | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  const subdomain = cookieStore.get("x-subdomain")?.value;

  if (!token) {
    // No access token - try to refresh and retry
    const newToken = await refreshAccessToken();
    if (!newToken) return null;

    try {
      return await apiGet<SessionContext>("/auth/me", { token: newToken, subdomain });
    } catch (error) {
      // Propagate rate limit errors so callers know the session may still be valid
      if (error instanceof ApiError && error.status === 429) {
        throw error;
      }
      return null;
    }
  }

  try {
    return await apiGet<SessionContext>("/auth/me", { token, subdomain });
  } catch (error) {
    // If 401 (expired/invalid token), try refresh once then retry
    if (error instanceof ApiError && error.status === 401) {
      const newToken = await refreshAccessToken();
      if (!newToken) return null;

      try {
        return await apiGet<SessionContext>("/auth/me", { token: newToken, subdomain });
      } catch (retryError) {
        // Propagate rate limit errors
        if (retryError instanceof ApiError && retryError.status === 429) {
          throw retryError;
        }
        return null;
      }
    }
    // Propagate rate limit errors so callers know the session may still be valid
    if (error instanceof ApiError && error.status === 429) {
      throw error;
    }
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
