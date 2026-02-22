"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  User,
  UserListResponse,
  UserInviteRequest,
  UserInviteResponse,
} from "@/types";

async function getAuthContext() {
  const cookieStore = await cookies();
  const token = await getValidAccessToken();
  return {
    token: token || undefined,
    subdomain: cookieStore.get("x-subdomain")?.value,
  };
}

export async function getUsers(
  page: number = 1,
  page_size: number = 20,
  search?: string,
): Promise<ActionResult<UserListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const params = new URLSearchParams();
    params.append("page", String(page));
    params.append("page_size", String(page_size));
    if (search) params.append("search", search);

    const response = await apiGet<UserListResponse>(`/users?${params.toString()}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch users",
    };
  }
}

export async function inviteUser(
  data: UserInviteRequest
): Promise<ActionResult<UserInviteResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<UserInviteResponse>("/users/invite", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to invite user",
    };
  }
}

export async function updateProfile(data: {
  first_name?: string;
  last_name?: string;
  phone?: string;
  avatar_url?: string;
}): Promise<ActionResult<User>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<User>("/users/me", data, { token, subdomain });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update profile",
    };
  }
}

export async function changePassword(data: {
  current_password: string;
  new_password: string;
}): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiPost("/auth/change-password", data, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to change password",
    };
  }
}
