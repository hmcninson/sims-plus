import { getGuardians } from "@/actions/students.action";
import { GuardiansManagement } from "./guardians-management";

export const metadata = {
  title: "Guardians",
};

export default async function GuardiansPage() {
  // Fetch initial data server-side
  const guardiansResult = await getGuardians(undefined, 1, 20);

  // Default data for empty/error states
  const defaultGuardians = {
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    total_pages: 0,
    has_next: false,
    has_previous: false,
  };

  return (
    <GuardiansManagement
      initialData={guardiansResult.success ? guardiansResult.data! : defaultGuardians}
    />
  );
}
