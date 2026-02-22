import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Bell, Mail, MessageSquare, AlertTriangle } from "lucide-react";

export const metadata = {
  title: "Notification Settings | SIMS Plus",
};

const emailNotifications = [
  {
    id: "attendance",
    title: "Attendance Alerts",
    description: "Get notified when a student is marked absent",
  },
  {
    id: "payments",
    title: "Payment Notifications",
    description: "Receive updates about fee payments and invoices",
  },
  {
    id: "announcements",
    title: "School Announcements",
    description: "Important announcements from the school",
  },
  {
    id: "reports",
    title: "Report Cards",
    description: "When new report cards are published",
  },
];

const pushNotifications = [
  {
    id: "push-attendance",
    title: "Real-time Attendance",
    description: "Instant alerts for attendance changes",
  },
  {
    id: "push-messages",
    title: "Direct Messages",
    description: "Messages from teachers and staff",
  },
  {
    id: "push-reminders",
    title: "Reminders",
    description: "Fee due dates and upcoming events",
  },
];

export default function NotificationsSettingsPage() {
  return (
    <div className="space-y-6">
      {/* Email Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Email Notifications
          </CardTitle>
          <CardDescription>
            Choose what emails you&apos;d like to receive.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {emailNotifications.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between rounded-lg border p-4"
            >
              <div className="space-y-0.5">
                <Label htmlFor={item.id} className="text-base cursor-pointer">
                  {item.title}
                </Label>
                <p className="text-sm text-muted-foreground">
                  {item.description}
                </p>
              </div>
              <Switch id={item.id} defaultChecked />
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Push Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Push Notifications
          </CardTitle>
          <CardDescription>
            Control notifications on your device.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {pushNotifications.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between rounded-lg border p-4"
            >
              <div className="space-y-0.5">
                <Label htmlFor={item.id} className="text-base cursor-pointer">
                  {item.title}
                </Label>
                <p className="text-sm text-muted-foreground">
                  {item.description}
                </p>
              </div>
              <Switch id={item.id} />
            </div>
          ))}
        </CardContent>
      </Card>

      {/* SMS Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            SMS Notifications
          </CardTitle>
          <CardDescription>
            Important alerts sent to your phone via SMS.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label htmlFor="sms-critical" className="text-base cursor-pointer">
                Critical Alerts Only
              </Label>
              <p className="text-sm text-muted-foreground">
                Only receive SMS for urgent matters like emergencies.
              </p>
            </div>
            <Switch id="sms-critical" defaultChecked />
          </div>
        </CardContent>
      </Card>

      {/* Quiet Hours */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            Quiet Hours
          </CardTitle>
          <CardDescription>
            Pause non-urgent notifications during specific times.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label htmlFor="quiet-hours" className="text-base cursor-pointer">
                Enable Quiet Hours
              </Label>
              <p className="text-sm text-muted-foreground">
                No notifications between 10:00 PM - 7:00 AM
              </p>
            </div>
            <Switch id="quiet-hours" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
