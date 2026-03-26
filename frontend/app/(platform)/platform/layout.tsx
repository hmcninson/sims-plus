import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getPlatformUser } from "@/actions/platform.action";
import { PlatformShell } from "@/components/platform/platform-shell";

/**
 * Inner layout for authenticated platform pages.
 * Checks platform_access_token cookie and redirects to login if missing.
 * Fetches the current platform user for sidebar display.
 */
export default async function PlatformLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const token = cookieStore.get("platform_access_token")?.value;

  if (!token) {
    redirect("/platform-login");
  }

  const userResult = await getPlatformUser();

  if (!userResult.success) {
    redirect("/platform-login");
  }

  return (
    <PlatformShell user={userResult.data}>
      {children}
    </PlatformShell>
  );
}
