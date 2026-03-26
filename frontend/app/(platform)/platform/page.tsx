import { redirect } from "next/navigation";

/**
 * Platform root page -- redirect to tenants list.
 */
export default function PlatformRootPage() {
  redirect("/platform/tenants");
}
