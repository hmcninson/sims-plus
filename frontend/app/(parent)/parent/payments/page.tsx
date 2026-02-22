import { getMyChildren } from "@/actions/parent.action";
import { PaymentsView } from "./payments-view";

export const metadata = {
  title: "Payments",
};

export default async function PaymentsPage() {
  const result = await getMyChildren();
  const children = result.success ? result.data : [];

  return <PaymentsView children={children} />;
}
