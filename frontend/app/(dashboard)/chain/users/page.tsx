import { getChainUsers, getChainSchools } from "@/actions/chain.action";
import { ChainUsersManagement } from "./chain-users-management";

export const metadata = {
  title: "Chain Users",
};

export default async function ChainUsersPage() {
  const [usersResult, schoolsResult] = await Promise.all([
    getChainUsers(1, 20),
    getChainSchools(1, 100),
  ]);

  const defaultUsers = {
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    total_pages: 0,
  };

  return (
    <ChainUsersManagement
      initialData={usersResult.success ? usersResult.data : defaultUsers}
      schools={schoolsResult.success ? schoolsResult.data.items : []}
      error={usersResult.success ? undefined : usersResult.error}
    />
  );
}
