import { listUsers, getUserStatsByRole } from "@/actions/users.action";
import { UsersManagement } from "./users-management";

export const metadata = {
  title: "Users & Roles | SIMS Plus",
};

export default async function UsersSettingsPage() {
  // Fetch initial data server-side
  const [usersResult, statsResult] = await Promise.all([
    listUsers({ page: 1, page_size: 20 }),
    getUserStatsByRole(),
  ]);

  // Default data for empty/error states
  const defaultUsers = {
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    total_pages: 0,
  };

  const defaultStats: Record<string, number> = {
    platform_admin: 0,
    chain_admin: 0,
    school_admin: 0,
    academic_head: 0,
    finance_officer: 0,
    teacher: 0,
    house_parent: 0,
    parent: 0,
    student: 0,
  };

  return (
    <UsersManagement
      initialData={usersResult.success ? usersResult.data! : defaultUsers}
      roleStats={statsResult.success ? statsResult.data! : defaultStats}
    />
  );
}
