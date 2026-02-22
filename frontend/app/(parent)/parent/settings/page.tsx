import { getCurrentUser } from "@/actions/auth.action";
import { ParentSettingsView } from "./parent-settings";

export const metadata = {
  title: "Settings",
};

export default async function ParentSettingsPage() {
  const user = await getCurrentUser();

  return <ParentSettingsView user={user} />;
}
