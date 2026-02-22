"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";

interface VapidKeyResponse {
  public_key: string;
}

interface PushSubscriptionResponse {
  id: string;
  endpoint: string;
  is_active: boolean;
  created_at: string;
}

async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  return {
    token: token || undefined,
    subdomain: cookieStore.get("x-subdomain")?.value,
  };
}

export async function getVapidPublicKey(): Promise<ActionResult<VapidKeyResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<VapidKeyResponse>("/push/vapid-key", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to get VAPID key",
    };
  }
}

export async function registerPushSubscription(data: {
  endpoint: string;
  p256dh_key: string;
  auth_key: string;
  user_agent?: string;
}): Promise<ActionResult<PushSubscriptionResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<PushSubscriptionResponse>(
      "/push/subscribe",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to register subscription",
    };
  }
}

export async function removePushSubscription(
  endpoint: string
): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(
      `/push/unsubscribe?endpoint=${encodeURIComponent(endpoint)}`,
      { token, subdomain }
    );
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to remove subscription",
    };
  }
}
