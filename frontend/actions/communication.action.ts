"use server";

/**
 * SIMS Plus - Communication Settings Server Actions
 *
 * Server actions for reading and updating school communication
 * configuration (SMS, email, notification defaults).
 */

import { cookies } from "next/headers";
import { apiGet, apiPut } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type { CommunicationSettings } from "@/types/communication.type";

/**
 * Get auth token and subdomain from cookies with token refresh
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
 * Fetch the current communication settings for this school
 */
export async function getCommunicationSettings(): Promise<
  ActionResult<CommunicationSettings>
> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<CommunicationSettings>(
      "/communication-settings",
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch communication settings",
    };
  }
}

/**
 * Update communication settings (partial update supported)
 */
export async function updateCommunicationSettings(
  data: Partial<CommunicationSettings>
): Promise<ActionResult<CommunicationSettings>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<CommunicationSettings>(
      "/communication-settings",
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
          : "Failed to update communication settings",
    };
  }
}
