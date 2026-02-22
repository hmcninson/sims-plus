"use server";

import { cookies } from "next/headers";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  FinancialReportRequest,
  AttendanceReportRequest,
} from "@/types";

async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  return {
    token: token || undefined,
    subdomain: cookieStore.get("x-subdomain")?.value,
  };
}

function getBaseUrl(subdomain?: string): string {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return `${apiUrl}/api/v1`;
}

export async function generateFinancialReport(
  request: FinancialReportRequest
): Promise<ActionResult<Blob>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const baseUrl = getBaseUrl(subdomain);

    const response = await fetch(
      `${baseUrl}/finance/reports/${request.report_type.replace("_", "-")}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(subdomain ? { "X-Subdomain": subdomain } : {}),
        },
        body: JSON.stringify(request),
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Report generation failed" }));
      return { success: false, error: error.detail || "Report generation failed" };
    }

    const blob = await response.blob();
    return { success: true, data: blob };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to generate report",
    };
  }
}

export async function generateAttendanceReport(
  request: AttendanceReportRequest
): Promise<ActionResult<Blob>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const baseUrl = getBaseUrl(subdomain);

    const response = await fetch(`${baseUrl}/attendance/reports/pdf`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(subdomain ? { "X-Subdomain": subdomain } : {}),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Report generation failed" }));
      return { success: false, error: error.detail || "Report generation failed" };
    }

    const blob = await response.blob();
    return { success: true, data: blob };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to generate report",
    };
  }
}
