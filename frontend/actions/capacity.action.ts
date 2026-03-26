"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  EnrollmentTarget,
  EnrollmentTargetCreate,
  EnrollmentTargetListResponse,
  CapacityDashboardResponse,
  CapacityCheckResponse,
} from "@/types/admissions.type";

const BASE = "/admissions/capacity";

async function getAuthContext(): Promise<{
  token: string;
  subdomain: string | undefined;
}> {
  const token = await getValidAccessToken();
  const cookieStore = await cookies();
  const subdomain = cookieStore.get("x-subdomain")?.value;
  return { token: token || "", subdomain };
}

/**
 * Create or update an enrollment target (upsert semantics).
 */
export async function createTarget(
  data: EnrollmentTargetCreate
): Promise<ActionResult<EnrollmentTarget>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<EnrollmentTarget>(
      `${BASE}/targets`,
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
          : "Failed to set enrollment target",
    };
  }
}

/**
 * Get all enrollment targets for an academic year.
 */
export async function getTargets(
  academicYearId: string
): Promise<ActionResult<EnrollmentTargetListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<EnrollmentTargetListResponse>(
      `${BASE}/targets?academic_year_id=${encodeURIComponent(academicYearId)}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch enrollment targets",
    };
  }
}

/**
 * Get capacity dashboard for an academic year.
 */
export async function getCapacityDashboard(
  academicYearId: string
): Promise<ActionResult<CapacityDashboardResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<CapacityDashboardResponse>(
      `${BASE}/dashboard?academic_year_id=${encodeURIComponent(academicYearId)}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch capacity dashboard",
    };
  }
}

/**
 * Quick capacity check for a single class.
 */
export async function checkCapacity(
  classId: string
): Promise<ActionResult<CapacityCheckResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<CapacityCheckResponse>(
      `${BASE}/check/${encodeURIComponent(classId)}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to check class capacity",
    };
  }
}
