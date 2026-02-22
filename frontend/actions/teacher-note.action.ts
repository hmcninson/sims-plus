"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type { ActionResult } from "@/types";
import type {
  TeacherNote,
  TeacherNoteCreate,
  TeacherNoteUpdate,
  TeacherNoteListResponse,
} from "@/types/parent.type";

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

// =========================
// Teacher Note Actions
// =========================

export async function getTeacherNotes(params?: {
  search?: string;
  noteType?: string;
  studentId?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<TeacherNoteListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.append("search", params.search);
    if (params?.noteType) searchParams.append("note_type", params.noteType);
    if (params?.studentId) searchParams.append("student_id", params.studentId);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<TeacherNoteListResponse>(
      `/teacher-notes${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch teacher notes",
    };
  }
}

export async function getTeacherNote(id: string): Promise<ActionResult<TeacherNote>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TeacherNote>(`/teacher-notes/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch teacher note",
    };
  }
}

export async function createTeacherNote(
  data: TeacherNoteCreate
): Promise<ActionResult<TeacherNote>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<TeacherNote>("/teacher-notes", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create teacher note",
    };
  }
}

export async function updateTeacherNote(
  id: string,
  data: TeacherNoteUpdate
): Promise<ActionResult<TeacherNote>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<TeacherNote>(`/teacher-notes/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update teacher note",
    };
  }
}

export async function deleteTeacherNote(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/teacher-notes/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete teacher note",
    };
  }
}
