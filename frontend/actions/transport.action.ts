"use server";

import { cookies } from "next/headers";
import { apiGet, apiPost, apiPut, apiDelete } from "@/lib/api";
import { getValidAccessToken } from "./auth.action";
import type {
  ActionResult,
  // Vehicles
  Vehicle,
  VehicleCreate,
  VehicleUpdate,
  VehicleDetail,
  VehicleListResponse,
  // Drivers
  Driver,
  DriverCreate,
  DriverUpdate,
  DriverListResponse,
  // Routes
  TransportRoute,
  TransportRouteCreate,
  TransportRouteUpdate,
  TransportRouteDetail,
  TransportRouteListResponse,
  // Route Stops
  RouteStop,
  RouteStopCreate,
  RouteStopUpdate,
  // Student Transport
  StudentTransport,
  StudentTransportCreate,
  StudentTransportUpdate,
  StudentTransportDetail,
  StudentTransportListResponse,
  // Trip Logs
  TripLog,
  TripLogCreate,
  TripLogUpdate,
  TripLogDetail,
  TripLogListResponse,
  // Maintenance
  VehicleMaintenance,
  VehicleMaintenanceCreate,
  VehicleMaintenanceDetail,
  VehicleMaintenanceListResponse,
  // Stats
  TransportStats,
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

export async function getTransportStats(): Promise<ActionResult<TransportStats>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TransportStats>("/transport/stats", {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch transport stats",
    };
  }
}

// =========================
// Vehicle Actions
// =========================

export async function getVehicles(params?: {
  search?: string;
  vehicleType?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<VehicleListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.append("search", params.search);
    if (params?.vehicleType) searchParams.append("vehicle_type", params.vehicleType);
    if (params?.status) searchParams.append("status", params.status);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<VehicleListResponse>(`/transport/vehicles${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch vehicles",
    };
  }
}

export async function getVehicle(id: string): Promise<ActionResult<VehicleDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<VehicleDetail>(`/transport/vehicles/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch vehicle",
    };
  }
}

export async function createVehicle(data: VehicleCreate): Promise<ActionResult<Vehicle>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Vehicle>("/transport/vehicles", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create vehicle",
    };
  }
}

export async function updateVehicle(
  id: string,
  data: VehicleUpdate
): Promise<ActionResult<Vehicle>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<Vehicle>(`/transport/vehicles/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update vehicle",
    };
  }
}

export async function deleteVehicle(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/transport/vehicles/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete vehicle",
    };
  }
}

// =========================
// Driver Actions
// =========================

export async function getDrivers(params?: {
  search?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<DriverListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.append("search", params.search);
    if (params?.status) searchParams.append("status", params.status);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<DriverListResponse>(`/transport/drivers${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch drivers",
    };
  }
}

export async function getDriver(id: string): Promise<ActionResult<Driver>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<Driver>(`/transport/drivers/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch driver",
    };
  }
}

export async function createDriver(data: DriverCreate): Promise<ActionResult<Driver>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<Driver>("/transport/drivers", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create driver",
    };
  }
}

export async function updateDriver(
  id: string,
  data: DriverUpdate
): Promise<ActionResult<Driver>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<Driver>(`/transport/drivers/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update driver",
    };
  }
}

export async function deleteDriver(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/transport/drivers/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete driver",
    };
  }
}

// =========================
// Route Actions
// =========================

export async function getRoutes(params?: {
  search?: string;
  routeType?: string;
  isActive?: boolean;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<TransportRouteListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.append("search", params.search);
    if (params?.routeType) searchParams.append("route_type", params.routeType);
    if (params?.isActive !== undefined) searchParams.append("is_active", String(params.isActive));
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<TransportRouteListResponse>(`/transport/routes${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch routes",
    };
  }
}

export async function getRoute(id: string): Promise<ActionResult<TransportRouteDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TransportRouteDetail>(`/transport/routes/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch route",
    };
  }
}

export async function createRoute(
  data: TransportRouteCreate
): Promise<ActionResult<TransportRoute>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<TransportRoute>("/transport/routes", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create route",
    };
  }
}

export async function updateRoute(
  id: string,
  data: TransportRouteUpdate
): Promise<ActionResult<TransportRoute>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<TransportRoute>(`/transport/routes/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update route",
    };
  }
}

export async function deleteRoute(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/transport/routes/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete route",
    };
  }
}

// Route Stops

export async function addStop(
  routeId: string,
  data: RouteStopCreate
): Promise<ActionResult<RouteStop>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<RouteStop>(
      `/transport/routes/${routeId}/stops`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to add stop",
    };
  }
}

export async function updateStop(
  routeId: string,
  stopId: string,
  data: RouteStopUpdate
): Promise<ActionResult<RouteStop>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<RouteStop>(
      `/transport/routes/${routeId}/stops/${stopId}`,
      data,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update stop",
    };
  }
}

export async function deleteStop(routeId: string, stopId: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/transport/routes/${routeId}/stops/${stopId}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to delete stop",
    };
  }
}

export async function reorderStops(
  routeId: string,
  stopIds: string[]
): Promise<ActionResult<RouteStop[]>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<RouteStop[]>(
      `/transport/routes/${routeId}/stops/reorder`,
      { stop_ids: stopIds },
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to reorder stops",
    };
  }
}

// =========================
// Student Transport Assignment Actions
// =========================

export async function getTransportAssignments(params?: {
  routeId?: string;
  academicYearId?: string;
  status?: string;
  search?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<StudentTransportListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.routeId) searchParams.append("route_id", params.routeId);
    if (params?.academicYearId) searchParams.append("academic_year_id", params.academicYearId);
    if (params?.status) searchParams.append("status", params.status);
    if (params?.search) searchParams.append("search", params.search);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<StudentTransportListResponse>(
      `/transport/assignments${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch transport assignments",
    };
  }
}

export async function getTransportAssignment(
  id: string
): Promise<ActionResult<StudentTransportDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<StudentTransportDetail>(`/transport/assignments/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch transport assignment",
    };
  }
}

export async function assignStudentTransport(
  data: StudentTransportCreate
): Promise<ActionResult<StudentTransport>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<StudentTransport>("/transport/assignments", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to assign student to transport",
    };
  }
}

export async function updateTransportAssignment(
  id: string,
  data: StudentTransportUpdate
): Promise<ActionResult<StudentTransport>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<StudentTransport>(`/transport/assignments/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update transport assignment",
    };
  }
}

export async function cancelTransportAssignment(id: string): Promise<ActionResult<void>> {
  try {
    const { token, subdomain } = await getAuthContext();
    await apiDelete(`/transport/assignments/${id}`, { token, subdomain });
    return { success: true, data: undefined };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to cancel transport assignment",
    };
  }
}

// =========================
// Trip Log Actions
// =========================

export async function getTrips(params?: {
  routeId?: string;
  vehicleId?: string;
  driverId?: string;
  status?: string;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<TripLogListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.routeId) searchParams.append("route_id", params.routeId);
    if (params?.vehicleId) searchParams.append("vehicle_id", params.vehicleId);
    if (params?.driverId) searchParams.append("driver_id", params.driverId);
    if (params?.status) searchParams.append("status", params.status);
    if (params?.dateFrom) searchParams.append("date_from", params.dateFrom);
    if (params?.dateTo) searchParams.append("date_to", params.dateTo);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<TripLogListResponse>(`/transport/trips${query}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch trips",
    };
  }
}

export async function getTrip(id: string): Promise<ActionResult<TripLogDetail>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiGet<TripLogDetail>(`/transport/trips/${id}`, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch trip",
    };
  }
}

export async function createTrip(data: TripLogCreate): Promise<ActionResult<TripLog>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<TripLog>("/transport/trips", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create trip",
    };
  }
}

export async function updateTrip(
  id: string,
  data: TripLogUpdate
): Promise<ActionResult<TripLog>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPut<TripLog>(`/transport/trips/${id}`, data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to update trip",
    };
  }
}

export async function startTrip(id: string): Promise<ActionResult<TripLog>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<TripLog>(`/transport/trips/${id}/start`, {}, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to start trip",
    };
  }
}

export async function completeTrip(id: string): Promise<ActionResult<TripLog>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<TripLog>(`/transport/trips/${id}/complete`, {}, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to complete trip",
    };
  }
}

export async function cancelTrip(id: string): Promise<ActionResult<TripLog>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<TripLog>(`/transport/trips/${id}/cancel`, {}, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to cancel trip",
    };
  }
}

// =========================
// Vehicle Maintenance Actions
// =========================

export async function getMaintenanceHistory(params?: {
  vehicleId?: string;
  maintenanceType?: string;
  page?: number;
  pageSize?: number;
}): Promise<ActionResult<VehicleMaintenanceListResponse>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const searchParams = new URLSearchParams();
    if (params?.vehicleId) searchParams.append("vehicle_id", params.vehicleId);
    if (params?.maintenanceType) searchParams.append("maintenance_type", params.maintenanceType);
    if (params?.page) searchParams.append("page", String(params.page));
    if (params?.pageSize) searchParams.append("page_size", String(params.pageSize));
    const query = searchParams.toString() ? `?${searchParams.toString()}` : "";
    const response = await apiGet<VehicleMaintenanceListResponse>(
      `/transport/maintenance${query}`,
      { token, subdomain }
    );
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to fetch maintenance history",
    };
  }
}

export async function createMaintenance(
  data: VehicleMaintenanceCreate
): Promise<ActionResult<VehicleMaintenance>> {
  try {
    const { token, subdomain } = await getAuthContext();
    const response = await apiPost<VehicleMaintenance>("/transport/maintenance", data, {
      token,
      subdomain,
    });
    return { success: true, data: response };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : "Failed to create maintenance record",
    };
  }
}
