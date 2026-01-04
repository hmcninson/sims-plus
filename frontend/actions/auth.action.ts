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

/**
 * Login action
 */
export async function login(
  credentials: LoginCredentials
): Promise<ActionResult<User>> {
  try {
    const response = await apiPost<AuthResponse>("/auth/login", credentials);

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

  try {
    const token = cookieStore.get("access_token")?.value;
    if (token) {
      await apiPost("/auth/logout", {}, token);
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

  if (!token) {
    return null;
  }

  try {
    const response = await apiGet<MeResponse>("/auth/me", token);
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

  if (!token) {
    return null;
  }

  try {
    return await apiGet<MeResponse>("/auth/me", token);
  } catch {
    return null;
  }
}
