import { getMyChildren } from "@/actions/parent.action";
import { ChildrenList } from "./children-list";

export const metadata = {
  title: "My Children",
};

export default async function ChildrenPage() {
  const result = await getMyChildren();
  const children = result.success ? result.data : [];

  return <ChildrenList children={children} />;
}
