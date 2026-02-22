/**
 * SIMS Plus - Auth Layout
 *
 * Layout for authentication pages (login, register, etc.)
 * Wraps pages with TenantProvider for branded login.
 */

import { TenantProvider } from "@/components/providers/TenantProvider";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <TenantProvider>{children}</TenantProvider>;
}
