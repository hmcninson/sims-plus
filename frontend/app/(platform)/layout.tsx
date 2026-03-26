import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "SIMS Plus Platform Admin",
  description: "Platform administration portal for SIMS Plus",
};

/**
 * Root layout for the (platform) route group.
 * Wraps both the login page and authenticated platform pages.
 * No tenant branding -- uses neutral SIMS Plus theme.
 */
export default function PlatformRootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
