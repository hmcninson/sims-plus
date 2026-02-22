import { getStaff, getStaffStats } from "@/actions/staff.action";
import { StaffManagement } from "./staff-management";

export const metadata = {
  title: "Staff",
};

export default async function StaffPage() {
  // Fetch initial data server-side
  const [staffResult, statsResult] = await Promise.all([
    getStaff({ page: 1, page_size: 20 }),
    getStaffStats(),
  ]);

  // Default data for empty/error states
  const defaultStaff = {
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    total_pages: 0,
    has_next: false,
    has_previous: false,
  };

  const defaultStats = {
    total: 0,
    active: 0,
    on_leave: 0,
    suspended: 0,
    terminated: 0,
    retired: 0,
    teaching: 0,
    non_teaching: 0,
    administrative: 0,
    male: 0,
    female: 0,
  };

  return (
    <StaffManagement
      initialData={staffResult.success ? staffResult.data! : defaultStaff}
      stats={statsResult.success ? statsResult.data! : defaultStats}
    />
  );
}
