"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPatch, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  SchoolEvent,
  EventCreate,
  EventUpdate,
  EventListResponse,
  EventRegistration,
  EventRegistrationCreate,
  EventStatsResponse,
} from "@/types/admissions.type";

const BASE = "/admissions/events";

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
 * Create a new school event.
 */
export async function createEvent(
  data: EventCreate
): Promise<ActionResult<SchoolEvent>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<SchoolEvent>(BASE, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to create event",
    };
  }
}

/**
 * List events with optional filters.
 */
export async function getEvents(params?: {
  event_type?: string;
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<ActionResult<EventListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.event_type && params.event_type !== "all") {
      searchParams.set("event_type", params.event_type);
    }
    if (params?.status && params.status !== "all") {
      searchParams.set("status", params.status);
    }
    if (params?.page) searchParams.set("page", String(params.page));
    if (params?.page_size)
      searchParams.set("page_size", String(params.page_size));

    const qs = searchParams.toString();
    const url = qs ? `${BASE}?${qs}` : BASE;
    const response = await apiGet<EventListResponse>(url, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to fetch events",
    };
  }
}

/**
 * Get a single event by ID.
 */
export async function getEvent(
  eventId: string
): Promise<ActionResult<SchoolEvent>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<SchoolEvent>(
      `${BASE}/${encodeURIComponent(eventId)}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch event details",
    };
  }
}

/**
 * Update an event (only upcoming events can be updated).
 */
export async function updateEvent(
  eventId: string,
  data: EventUpdate
): Promise<ActionResult<SchoolEvent>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<SchoolEvent>(
      `${BASE}/${encodeURIComponent(eventId)}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to update event",
    };
  }
}

/**
 * Cancel an event.
 */
export async function cancelEvent(
  eventId: string
): Promise<ActionResult<SchoolEvent>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiDelete<SchoolEvent>(
      `${BASE}/${encodeURIComponent(eventId)}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Failed to cancel event",
    };
  }
}

/**
 * Register for an event.
 */
export async function registerForEvent(
  eventId: string,
  data: EventRegistrationCreate
): Promise<ActionResult<EventRegistration>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<EventRegistration>(
      `${BASE}/${encodeURIComponent(eventId)}/register`,
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
          : "Failed to register for event",
    };
  }
}

/**
 * Cancel a registration (hard delete).
 */
export async function cancelRegistration(
  eventId: string,
  registrationId: string
): Promise<ActionResult<null>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(
      `${BASE}/${encodeURIComponent(eventId)}/registrations/${encodeURIComponent(registrationId)}`,
      { token, subdomain }
    );
    return { success: true, data: null };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to cancel registration",
    };
  }
}

/**
 * Mark attendance for a registration.
 */
export async function markAttendance(
  eventId: string,
  registrationId: string,
  attended: boolean
): Promise<ActionResult<EventRegistration>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPatch<EventRegistration>(
      `${BASE}/${encodeURIComponent(eventId)}/registrations/${encodeURIComponent(registrationId)}/attendance`,
      { attended },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to mark attendance",
    };
  }
}

/**
 * Get registrations for an event.
 */
export async function getRegistrations(
  eventId: string
): Promise<ActionResult<EventRegistration[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<EventRegistration[]>(
      `${BASE}/${encodeURIComponent(eventId)}/registrations`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch registrations",
    };
  }
}

/**
 * Get statistics for an event.
 */
export async function getEventStats(
  eventId: string
): Promise<ActionResult<EventStatsResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<EventStatsResponse>(
      `${BASE}/${encodeURIComponent(eventId)}/stats`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch event statistics",
    };
  }
}
