import { redirect } from "next/navigation";
import { getCurrentUserContext } from "@/actions/auth.action";

/**
 * Chain admin layout guard.
 *
 * Only chain_admin and platform_admin roles can access chain management
 * pages. All other roles are redirected to the main dashboard.
 */
export default async function ChainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getCurrentUserContext();
  if (!session) redirect("/login");

  const allowedRoles = ["chain_admin", "platform_admin"];
  if (!allowedRoles.includes(session.user.role)) {
    redirect("/dashboard");
  }

  return <>{children}</>;
}
