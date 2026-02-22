"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  // Houses
  House,
  HouseCreate,
  HouseUpdate,
  HouseDetail,
  HouseListResponse,
  // Dormitories
  Dormitory,
  DormitoryCreate,
  DormitoryUpdate,
  DormitoryDetail,
  DormitoryListResponse,
  // Beds
  Bed,
  BedCreate,
  BedBulkCreate,
  BedUpdate,
  BedListResponse,
  // Student Boarding
  StudentBoarding,
  StudentBoardingCreate,
  StudentBoardingUpdate,
  StudentBoardingBulkAssign,
  StudentBoardingDetail,
  StudentBoardingListResponse,
  // Roll Calls
  BoardingRollCall,
  BoardingRollCallDetail,
  BoardingRollCallSubmit,
  BoardingRollCallListResponse,
  // Exeats
  Exeat,
  ExeatCreate,
  ExeatApprovalUpdate,
  ExeatReturnUpdate,
  ExeatDetail,
  ExeatListResponse,
  // Incidents
  BoardingIncident,
  BoardingIncidentCreate,
  BoardingIncidentUpdate,
  BoardingIncidentResolve,
  BoardingIncidentDetail,
  BoardingIncidentListResponse,
  // Dining
  DiningMeal,
  DiningMealCreate,
  DiningMealUpdate,
  DiningMealListResponse,
  // Stats
  BoardingStats,
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

// =========================
// Stats
// =========================

export async function getBoardingStats(): Promise<ActionResult<BoardingStats>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<BoardingStats>("/boarding/stats", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch boarding stats",
    };
  }
}

// =========================
// House Actions
// =========================

export async function getHouses(params?: {
  search?: string;
  gender?: string;
  isActive?: boolean;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<HouseListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.append("search", params.search);
    if (params?.gender) searchParams.append("gender", params.gender);
    if (params?.isActive !== undefined) searchParams.append("is_active", String(params.isActive));
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<HouseListResponse>(`/boarding/houses${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch houses",
    };
  }
}

export async function getHouse(id: string): Promise<ActionResult<HouseDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<HouseDetail>(`/boarding/houses/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch house",
    };
  }
}

export async function createHouse(data: HouseCreate): Promise<ActionResult<House>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<House>("/boarding/houses", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create house",
    };
  }
}

export async function updateHouse(id: string, data: HouseUpdate): Promise<ActionResult<House>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<House>(`/boarding/houses/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update house",
    };
  }
}

export async function deleteHouse(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/boarding/houses/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete house",
    };
  }
}

// =========================
// Dormitory Actions
// =========================

export async function getDormitories(params?: {
  houseId?: string;
  isActive?: boolean;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<DormitoryListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.houseId) searchParams.append("house_id", params.houseId);
    if (params?.isActive !== undefined) searchParams.append("is_active", String(params.isActive));
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<DormitoryListResponse>(`/boarding/dormitories${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch dormitories",
    };
  }
}

export async function getDormitory(id: string): Promise<ActionResult<DormitoryDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<DormitoryDetail>(`/boarding/dormitories/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch dormitory",
    };
  }
}

export async function createDormitory(data: DormitoryCreate): Promise<ActionResult<Dormitory>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Dormitory>("/boarding/dormitories", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create dormitory",
    };
  }
}

export async function updateDormitory(
  id: string,
  data: DormitoryUpdate
): Promise<ActionResult<Dormitory>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<Dormitory>(`/boarding/dormitories/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update dormitory",
    };
  }
}

export async function deleteDormitory(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/boarding/dormitories/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete dormitory",
    };
  }
}

// =========================
// Bed Actions
// =========================

export async function getBeds(params?: {
  dormitoryId?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<BedListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.dormitoryId) searchParams.append("dormitory_id", params.dormitoryId);
    if (params?.status) searchParams.append("status", params.status);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<BedListResponse>(`/boarding/beds${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch beds",
    };
  }
}

export async function createBed(data: BedCreate): Promise<ActionResult<Bed>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Bed>("/boarding/beds", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create bed",
    };
  }
}

export async function createBedsBulk(data: BedBulkCreate): Promise<ActionResult<Bed[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Bed[]>("/boarding/beds/bulk", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create beds",
    };
  }
}

export async function updateBed(id: string, data: BedUpdate): Promise<ActionResult<Bed>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<Bed>(`/boarding/beds/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update bed",
    };
  }
}

// =========================
// Student Boarding Assignment Actions
// =========================

export async function getAssignments(params?: {
  houseId?: string;
  academicYearId?: string;
  status?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<StudentBoardingListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.houseId) searchParams.append("house_id", params.houseId);
    if (params?.academicYearId) searchParams.append("academic_year_id", params.academicYearId);
    if (params?.status) searchParams.append("status", params.status);
    if (params?.search) searchParams.append("search", params.search);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<StudentBoardingListResponse>(
      `/boarding/assignments${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch boarding assignments",
    };
  }
}

export async function getAssignment(id: string): Promise<ActionResult<StudentBoardingDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StudentBoardingDetail>(`/boarding/assignments/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch boarding assignment",
    };
  }
}

export async function assignStudent(
  data: StudentBoardingCreate
): Promise<ActionResult<StudentBoarding>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StudentBoarding>("/boarding/assignments", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to assign student to boarding",
    };
  }
}

export async function updateAssignment(
  id: string,
  data: StudentBoardingUpdate
): Promise<ActionResult<StudentBoarding>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<StudentBoarding>(`/boarding/assignments/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update boarding assignment",
    };
  }
}

export async function unassignStudent(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/boarding/assignments/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to unassign student from boarding",
    };
  }
}

export async function bulkAssign(
  data: StudentBoardingBulkAssign
): Promise<ActionResult<{ assigned: number; failed: number; errors: Array<{ student_id: string; error: string }> }>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<{ assigned: number; failed: number; errors: Array<{ student_id: string; error: string }> }>(
      "/boarding/assignments/bulk",
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to bulk assign students",
    };
  }
}

// =========================
// Roll Call Actions
// =========================

export async function getRollCalls(params?: {
  houseId?: string;
  rollCallType?: string;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<BoardingRollCallListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.houseId) searchParams.append("house_id", params.houseId);
    if (params?.rollCallType) searchParams.append("roll_call_type", params.rollCallType);
    if (params?.dateFrom) searchParams.append("date_from", params.dateFrom);
    if (params?.dateTo) searchParams.append("date_to", params.dateTo);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<BoardingRollCallListResponse>(
      `/boarding/roll-calls${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch roll calls",
    };
  }
}

export async function getRollCall(id: string): Promise<ActionResult<BoardingRollCallDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<BoardingRollCallDetail>(`/boarding/roll-calls/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch roll call",
    };
  }
}

export async function submitRollCall(
  data: BoardingRollCallSubmit
): Promise<ActionResult<BoardingRollCallDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<BoardingRollCallDetail>("/boarding/roll-calls", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to submit roll call",
    };
  }
}

// =========================
// Exeat Actions
// =========================

export async function getExeats(params?: {
  status?: string;
  studentId?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<ExeatListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.append("status", params.status);
    if (params?.studentId) searchParams.append("student_id", params.studentId);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<ExeatListResponse>(`/boarding/exeats${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch exeats",
    };
  }
}

export async function getExeat(id: string): Promise<ActionResult<ExeatDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<ExeatDetail>(`/boarding/exeats/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch exeat",
    };
  }
}

export async function createExeat(data: ExeatCreate): Promise<ActionResult<Exeat>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Exeat>("/boarding/exeats", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create exeat",
    };
  }
}

export async function approveExeat(
  id: string,
  data: ExeatApprovalUpdate
): Promise<ActionResult<Exeat>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Exeat>(`/boarding/exeats/${id}/approve`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to approve/deny exeat",
    };
  }
}

export async function activateExeat(id: string): Promise<ActionResult<Exeat>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Exeat>(`/boarding/exeats/${id}/activate`, {}, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to activate exeat",
    };
  }
}

export async function recordReturn(
  id: string,
  data: ExeatReturnUpdate
): Promise<ActionResult<Exeat>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Exeat>(`/boarding/exeats/${id}/return`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to record exeat return",
    };
  }
}

// =========================
// Incident Actions
// =========================

export async function getIncidents(params?: {
  severity?: string;
  resolved?: boolean;
  studentId?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<BoardingIncidentListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.severity) searchParams.append("severity", params.severity);
    if (params?.resolved !== undefined) searchParams.append("resolved", String(params.resolved));
    if (params?.studentId) searchParams.append("student_id", params.studentId);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<BoardingIncidentListResponse>(
      `/boarding/incidents${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch incidents",
    };
  }
}

export async function getIncident(id: string): Promise<ActionResult<BoardingIncidentDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<BoardingIncidentDetail>(`/boarding/incidents/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch incident",
    };
  }
}

export async function reportIncident(
  data: BoardingIncidentCreate
): Promise<ActionResult<BoardingIncident>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<BoardingIncident>("/boarding/incidents", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to report incident",
    };
  }
}

export async function updateIncident(
  id: string,
  data: BoardingIncidentUpdate
): Promise<ActionResult<BoardingIncident>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<BoardingIncident>(
      `/boarding/incidents/${id}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update incident",
    };
  }
}

export async function resolveIncident(
  id: string,
  data: BoardingIncidentResolve
): Promise<ActionResult<BoardingIncident>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<BoardingIncident>(
      `/boarding/incidents/${id}/resolve`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to resolve incident",
    };
  }
}

// =========================
// Dining Actions
// =========================

export async function getMeals(params?: {
  dateFrom?: string;
  dateTo?: string;
  mealType?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<DiningMealListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.dateFrom) searchParams.append("date_from", params.dateFrom);
    if (params?.dateTo) searchParams.append("date_to", params.dateTo);
    if (params?.mealType) searchParams.append("meal_type", params.mealType);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<DiningMealListResponse>(`/boarding/dining${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch meals",
    };
  }
}

export async function logMeal(data: DiningMealCreate): Promise<ActionResult<DiningMeal>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<DiningMeal>("/boarding/dining", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to log meal",
    };
  }
}

export async function updateMeal(
  id: string,
  data: DiningMealUpdate
): Promise<ActionResult<DiningMeal>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<DiningMeal>(`/boarding/dining/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update meal",
    };
  }
}

export async function deleteMeal(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/boarding/dining/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete meal",
    };
  }
}
