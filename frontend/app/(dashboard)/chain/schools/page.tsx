import { getChainSchools } from "@/actions/chain.action";
import { ChainSchoolsList } from "./chain-schools-list";

export const metadata = {
  title: "Chain Schools",
};

export default async function ChainSchoolsPage() {
  const result = await getChainSchools(1, 20);

  const defaultData = {
    items: [],
    total: 0,
  };

  return (
    <ChainSchoolsList
      initialData={result.success ? result.data : defaultData}
      error={result.success ? undefined : result.error}
    />
  );
}
