"use server";

import { cookies } from "next/headers";
import { apiGet } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  DashboardStats,
  AttendanceTrendPoint,
  FeeCollectionTrendPoint,
  ClassPerformancePoint,
  GenderDistribution,
} from "@/types";

/**
 * Get auth context from cookies with token refresh
 */
async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  return {
    token: token || undefined,
    subdomain: cookieStore.get("x-subdomain")?.value,
  };
}

/**
 * Fetch top-level dashboard KPI stats (students, staff, attendance, finance)
 */
export async function getDashboardStats(): Promise<ActionResult<DashboardStats>> {
  try {
    const ctx = await getAuthContext();
    const response = await apiGet<DashboardStats>("/dashboard", ctx);
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch dashboard stats",
    };
  }
}

/**
 * Fetch daily attendance trend for the last N days
 */
export async function getAttendanceTrend(
  days: number = 30
): Promise<ActionResult<AttendanceTrendPoint[]>> {
  try {
    const ctx = await getAuthContext();
    const response = await apiGet<AttendanceTrendPoint[]>(
      `/dashboard/attendance-trend?days=${days}`,
      ctx
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch attendance trend",
    };
  }
}

/**
 * Fetch monthly fee billed vs collected for the last N months
 */
export async function getFeeCollectionTrend(
  months: number = 6
): Promise<ActionResult<FeeCollectionTrendPoint[]>> {
  try {
    const ctx = await getAuthContext();
    const response = await apiGet<FeeCollectionTrendPoint[]>(
      `/dashboard/fee-trend?months=${months}`,
      ctx
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch fee trend",
    };
  }
}

/**
 * Fetch class average performance for a given term
 */
export async function getClassPerformance(
  termId: string
): Promise<ActionResult<ClassPerformancePoint[]>> {
  try {
    const ctx = await getAuthContext();
    const response = await apiGet<ClassPerformancePoint[]>(
      `/dashboard/class-performance?term_id=${termId}`,
      ctx
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch class performance",
    };
  }
}

/**
 * Fetch student gender distribution (male/female counts)
 */
export async function getGenderDistribution(): Promise<ActionResult<GenderDistribution>> {
  try {
    const ctx = await getAuthContext();
    const response = await apiGet<GenderDistribution>(
      "/dashboard/gender-distribution",
      ctx
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch gender distribution",
    };
  }
}
