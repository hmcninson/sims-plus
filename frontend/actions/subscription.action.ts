"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";

export interface SubscriptionStatus {
  plan: string;
  status: string;
  trial_ends_at: string | null;
  subscription_start: string | null;
  subscription_end: string | null;
  days_remaining: number | null;
  max_students: number;
  current_student_count: number;
  max_staff: number;
  current_staff_count: number;
  features: Record<string, boolean | string>;
}

export interface UpgradeCostBreakdown {
  student_count: number;
  billable_students: number;
  price_per_student: number;
  subtotal: number;
  addon_total: number;
  total: number;
  total_ghs: number;
  billing_period: string;
  tier: string;
  breakdown: Array<{ description: string; amount: number; name?: string }>;
}

export interface UpgradeInitiationResult {
  payment_url: string;
  reference: string;
}

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

export async function getSubscriptionStatus(): Promise<ActionResult<SubscriptionStatus>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<SubscriptionStatus>("/subscription/status", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch subscription status",
    };
  }
}

export async function calculateCost(
  targetTier: string,
  billingPeriod: string
): Promise<ActionResult<UpgradeCostBreakdown>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<UpgradeCostBreakdown>(
      "/subscription/calculate-cost",
      { target_tier: targetTier, billing_period: billingPeriod },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to calculate cost",
    };
  }
}

export async function initiateUpgrade(
  targetTier: string,
  billingPeriod: string,
  callbackUrl: string
): Promise<ActionResult<UpgradeInitiationResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<UpgradeInitiationResult>(
      "/subscription/upgrade",
      {
        target_tier: targetTier,
        billing_period: billingPeriod,
        callback_url: callbackUrl,
      },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to initiate upgrade",
    };
  }
}

export async function purchaseAddon(
  addonName: string,
  callbackUrl: string
): Promise<ActionResult<UpgradeInitiationResult>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<UpgradeInitiationResult>(
      "/subscription/addon",
      {
        addon_name: addonName,
        callback_url: callbackUrl,
      },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to purchase add-on",
    };
  }
}
