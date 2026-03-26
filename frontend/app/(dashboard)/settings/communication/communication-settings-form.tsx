"use client";

import { useState } from "react";
import {
  MessageSquare,
  Mail,
  Phone,
  Save,
  Loader2,
  CheckCircle,
  AlertCircle,
  Bell,
} from "lucide-react";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { updateCommunicationSettings } from "@/actions/communication.action";
import type { CommunicationSettings } from "@/types/communication.type";

/** Default values used when no settings have been saved yet */
const DEFAULT_SETTINGS: CommunicationSettings = {
  sms: {
    sender_id: "SIMSPLUS",
    attendance_alerts_enabled: true,
    fee_reminders_enabled: true,
  },
  email: {
    from_email: null,
    from_name: null,
    reply_to: null,
    signature: null,
  },
  notifications: {
    report_card_notifications: true,
    event_announcements: true,
    weekly_digest: false,
  },
};

interface CommunicationSettingsFormProps {
  initialData?: CommunicationSettings;
}

export function CommunicationSettingsForm({
  initialData,
}: CommunicationSettingsFormProps) {
  const settings = initialData ?? DEFAULT_SETTINGS;

  const [isSaving, setIsSaving] = useState(false);

  // SMS state
  const [senderId, setSenderId] = useState(settings.sms.sender_id);
  const [attendanceAlerts, setAttendanceAlerts] = useState(
    settings.sms.attendance_alerts_enabled
  );
  const [feeReminders, setFeeReminders] = useState(
    settings.sms.fee_reminders_enabled
  );

  // Email state
  const [fromEmail, setFromEmail] = useState(settings.email.from_email ?? "");
  const [fromName, setFromName] = useState(settings.email.from_name ?? "");
  const [replyTo, setReplyTo] = useState(settings.email.reply_to ?? "");
  const [signature, setSignature] = useState(settings.email.signature ?? "");

  // Notification defaults state
  const [reportCardNotifications, setReportCardNotifications] = useState(
    settings.notifications.report_card_notifications
  );
  const [eventAnnouncements, setEventAnnouncements] = useState(
    settings.notifications.event_announcements
  );
  const [weeklyDigest, setWeeklyDigest] = useState(
    settings.notifications.weekly_digest
  );

  // Whether email has been configured (at least from_email is set)
  const isEmailConfigured = fromEmail.trim().length > 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSaving(true);

    try {
      const payload: CommunicationSettings = {
        sms: {
          sender_id: senderId,
          attendance_alerts_enabled: attendanceAlerts,
          fee_reminders_enabled: feeReminders,
        },
        email: {
          from_email: fromEmail.trim() || null,
          from_name: fromName.trim() || null,
          reply_to: replyTo.trim() || null,
          signature: signature.trim() || null,
        },
        notifications: {
          report_card_notifications: reportCardNotifications,
          event_announcements: eventAnnouncements,
          weekly_digest: weeklyDigest,
        },
      };

      const result = await updateCommunicationSettings(payload);

      if (result.success) {
        toast.success("Settings saved", {
          description: "Communication settings have been updated successfully.",
        });
      } else {
        toast.error("Save failed", {
          description: result.error || "Failed to update communication settings.",
        });
      }
    } catch {
      toast.error("Error", {
        description: "An unexpected error occurred while saving.",
      });
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* SMS Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            SMS Configuration
          </CardTitle>
          <CardDescription>
            Configure SMS gateway for sending notifications to parents.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Phone className="h-5 w-5 text-primary" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-medium">Arkesel SMS</p>
                  <Badge variant="secondary">
                    SMS Gateway
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  Configure sender ID and notification preferences below
                </p>
              </div>
            </div>
            <Button type="button" variant="outline" size="sm">
              Configure
            </Button>
          </div>

          <div className="space-y-2">
            <Label htmlFor="senderId">Sender ID</Label>
            <Input
              id="senderId"
              placeholder="e.g., PRESEC"
              value={senderId}
              onChange={(e) => {
                // Sender ID: max 11 chars, alphanumeric only, no spaces
                const value = e.target.value
                  .replace(/[^A-Za-z0-9]/g, "")
                  .slice(0, 11);
                setSenderId(value);
              }}
              maxLength={11}
            />
            <p className="text-xs text-muted-foreground">
              This name appears as the sender. Max 11 characters, no spaces.
            </p>
          </div>

          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label className="text-base">
                Send attendance alerts via SMS
              </Label>
              <p className="text-sm text-muted-foreground">
                Automatically notify parents when student is marked absent.
              </p>
            </div>
            <Switch
              checked={attendanceAlerts}
              onCheckedChange={setAttendanceAlerts}
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label className="text-base">
                Send fee reminders via SMS
              </Label>
              <p className="text-sm text-muted-foreground">
                Send payment reminders before due dates.
              </p>
            </div>
            <Switch
              checked={feeReminders}
              onCheckedChange={setFeeReminders}
            />
          </div>
        </CardContent>
      </Card>

      {/* Email Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Email Configuration
          </CardTitle>
          <CardDescription>
            Configure email settings for sending notifications.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-lg ${
                  isEmailConfigured ? "bg-primary/10" : "bg-muted"
                }`}
              >
                <Mail
                  className={`h-5 w-5 ${
                    isEmailConfigured
                      ? "text-primary"
                      : "text-muted-foreground"
                  }`}
                />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-medium">SMTP Server</p>
                  {isEmailConfigured ? (
                    <Badge
                      variant="outline"
                      className="text-green-600 border-green-600"
                    >
                      <CheckCircle className="mr-1 h-3 w-3" />
                      Configured
                    </Badge>
                  ) : (
                    <Badge variant="secondary">
                      <AlertCircle className="mr-1 h-3 w-3" />
                      Not configured
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">
                  {isEmailConfigured
                    ? `Sending from ${fromEmail}`
                    : "Configure your SMTP settings to send emails"}
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="fromEmail">From Email</Label>
              <Input
                id="fromEmail"
                type="email"
                placeholder="noreply@school.edu.gh"
                value={fromEmail}
                onChange={(e) => setFromEmail(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fromName">From Name</Label>
              <Input
                id="fromName"
                placeholder="School Name"
                value={fromName}
                onChange={(e) => setFromName(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="replyTo">Reply-To Email</Label>
            <Input
              id="replyTo"
              type="email"
              placeholder="info@school.edu.gh"
              value={replyTo}
              onChange={(e) => setReplyTo(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Replies to automated emails will be sent here.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Email Signature */}
      <Card>
        <CardHeader>
          <CardTitle>Email Signature</CardTitle>
          <CardDescription>
            Customize the signature appended to outgoing email notifications.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="emailSignature">Signature</Label>
            <Textarea
              id="emailSignature"
              placeholder="Enter your email signature..."
              rows={4}
              value={signature}
              onChange={(e) => setSignature(e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      {/* Notification Preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Default Notification Preferences
          </CardTitle>
          <CardDescription>
            Set default notification settings for all parents.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label className="text-base">Report card notifications</Label>
              <p className="text-sm text-muted-foreground">
                Notify parents when report cards are published.
              </p>
            </div>
            <Switch
              checked={reportCardNotifications}
              onCheckedChange={setReportCardNotifications}
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label className="text-base">Event announcements</Label>
              <p className="text-sm text-muted-foreground">
                Send notifications about school events and activities.
              </p>
            </div>
            <Switch
              checked={eventAnnouncements}
              onCheckedChange={setEventAnnouncements}
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label className="text-base">Weekly digest</Label>
              <p className="text-sm text-muted-foreground">
                Send weekly summary of student activities to parents.
              </p>
            </div>
            <Switch
              checked={weeklyDigest}
              onCheckedChange={setWeeklyDigest}
            />
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button type="submit" disabled={isSaving} size="lg">
          {isSaving ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              Save Changes
            </>
          )}
        </Button>
      </div>
    </form>
  );
}
