import { getSMSStats, getSMSHistory } from "@/actions/messaging.action";
import { SMSPageContent } from "./sms-page-content";

export const metadata = {
  title: "SMS Messages | SIMS Plus",
};

export default async function SMSPage() {
  const [statsResult, historyResult] = await Promise.all([
    getSMSStats(),
    getSMSHistory(),
  ]);

  return (
    <SMSPageContent
      initialStats={statsResult.success ? statsResult.data : undefined}
      initialHistory={historyResult.success ? historyResult.data : undefined}
    />
  );
}
