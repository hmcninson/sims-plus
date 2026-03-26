import { getCurrentUserContext } from "@/actions/auth.action";
import { listCustomRoles } from "@/actions/custom-roles.action";
import { CustomRolesPage } from "./custom-roles-page";

export const metadata = {
  title: "Custom Roles | SIMS Plus",
};

export default async function RolesSettingsPage() {
  const [context, rolesResult] = await Promise.all([
    getCurrentUserContext(),
    listCustomRoles(),
  ]);

  const subscriptionTier = context?.tenant?.subscription_tier ?? "starter";
  const roles = rolesResult.success ? rolesResult.data.roles : [];

  return (
    <CustomRolesPage
      roles={roles}
      subscriptionTier={subscriptionTier}
    />
  );
}
