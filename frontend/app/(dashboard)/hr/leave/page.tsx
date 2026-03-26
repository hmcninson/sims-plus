import { redirect } from "next/navigation";

export default function LeaveIndexPage() {
  redirect("/hr/leave/requests");
}
