import { getAnnouncements } from "@/actions/parent.action";
import { AnnouncementsView } from "./announcements-view";

export const metadata = {
  title: "Announcements",
};

export default async function AnnouncementsPage() {
  const result = await getAnnouncements();
  const announcements = result.success ? result.data : [];

  return <AnnouncementsView announcements={announcements} />;
}
