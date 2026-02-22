"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Bell,
  User as UserIcon,
  Shield,
  LogOut,
  ChevronRight,
  Loader2,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { toast } from "sonner";
import { getInitials } from "@/lib/format";
import { logout } from "@/actions/auth.action";
import {
  getNotificationPreferences,
  updateNotificationPreferences,
} from "@/actions/parent.action";
import type { User } from "@/types";
import type { NotificationPreferences } from "@/types/parent.type";

interface ParentSettingsViewProps {
  user: User | null;
}

export function ParentSettingsView({ user }: ParentSettingsViewProps) {
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [loadingPrefs, setLoadingPrefs] = useState(true);
  const [savingField, setSavingField] = useState<string | null>(null);

  const loadPrefs = useCallback(async () => {
    setLoadingPrefs(true);
    const result = await getNotificationPreferences();
    if (result.success) {
      setPrefs(result.data);
    }
    setLoadingPrefs(false);
  }, []);

  useEffect(() => {
    loadPrefs();
  }, [loadPrefs]);

  async function handleToggle(field: keyof NotificationPreferences, value: boolean) {
    if (!prefs) return;
    setSavingField(field);
    const result = await updateNotificationPreferences({ [field]: value });
    if (result.success) {
      setPrefs(result.data);
      toast.success("Preference updated");
    } else {
      toast.error(result.error);
    }
    setSavingField(null);
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your account and notification preferences.
        </p>
      </div>

      {/* Profile card */}
      {user && (
        <Card>
          <CardHeader className="flex flex-row items-center gap-4 pb-4">
            <Avatar className="h-16 w-16">
              <AvatarFallback className="bg-primary/10 text-primary text-xl">
                {getInitials(`${user.first_name} ${user.last_name}`)}
              </AvatarFallback>
            </Avatar>
            <div>
              <CardTitle className="text-lg">
                {user.first_name} {user.last_name}
              </CardTitle>
              <p className="text-sm text-muted-foreground">{user.email}</p>
              {user.phone && (
                <p className="text-sm text-muted-foreground">{user.phone}</p>
              )}
            </div>
          </CardHeader>
        </Card>
      )}

      {/* Notification preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Bell className="h-4 w-4" />
            Notification Preferences
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loadingPrefs ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
            </div>
          ) : prefs ? (
            <div className="space-y-4">
              <h4 className="text-sm font-medium text-muted-foreground">
                Channels
              </h4>
              <NotifToggle
                label="Email notifications"
                description="Receive updates via email"
                checked={prefs.email_enabled}
                saving={savingField === "email_enabled"}
                onToggle={(v) => handleToggle("email_enabled", v)}
              />
              <NotifToggle
                label="SMS notifications"
                description="Receive updates via text message"
                checked={prefs.sms_enabled}
                saving={savingField === "sms_enabled"}
                onToggle={(v) => handleToggle("sms_enabled", v)}
              />
              <NotifToggle
                label="Push notifications"
                description="Receive in-app push notifications"
                checked={prefs.push_enabled}
                saving={savingField === "push_enabled"}
                onToggle={(v) => handleToggle("push_enabled", v)}
              />

              <Separator className="my-4" />

              <h4 className="text-sm font-medium text-muted-foreground">
                Categories
              </h4>
              <NotifToggle
                label="Attendance alerts"
                description="When your child is marked absent or late"
                checked={prefs.notify_attendance}
                saving={savingField === "notify_attendance"}
                onToggle={(v) => handleToggle("notify_attendance", v)}
              />
              <NotifToggle
                label="Grade updates"
                description="When new grades or report cards are published"
                checked={prefs.notify_grades}
                saving={savingField === "notify_grades"}
                onToggle={(v) => handleToggle("notify_grades", v)}
              />
              <NotifToggle
                label="Finance updates"
                description="Invoice reminders and payment confirmations"
                checked={prefs.notify_finance}
                saving={savingField === "notify_finance"}
                onToggle={(v) => handleToggle("notify_finance", v)}
              />
              <NotifToggle
                label="Announcements"
                description="School-wide announcements and notices"
                checked={prefs.notify_announcements}
                saving={savingField === "notify_announcements"}
                onToggle={(v) => handleToggle("notify_announcements", v)}
              />
              <NotifToggle
                label="Transport updates"
                description="Route changes and trip notifications"
                checked={prefs.notify_transport}
                saving={savingField === "notify_transport"}
                onToggle={(v) => handleToggle("notify_transport", v)}
              />
              <NotifToggle
                label="Boarding updates"
                description="Exeat approvals and boarding notifications"
                checked={prefs.notify_boarding}
                saving={savingField === "notify_boarding"}
                onToggle={(v) => handleToggle("notify_boarding", v)}
              />
            </div>
          ) : (
            <p className="text-sm text-muted-foreground py-4">
              Could not load notification preferences. Please try again.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Account actions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Shield className="h-4 w-4" />
            Account
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Button
            variant="outline"
            className="w-full justify-start text-destructive hover:text-destructive"
            onClick={() => logout()}
          >
            <LogOut className="mr-2 h-4 w-4" />
            Sign out
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function NotifToggle({
  label,
  description,
  checked,
  saving,
  onToggle,
}: {
  label: string;
  description: string;
  checked: boolean;
  saving: boolean;
  onToggle: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="space-y-0.5">
        <Label className="text-sm font-medium">{label}</Label>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <div className="flex items-center gap-2">
        {saving && <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />}
        <Switch
          checked={checked}
          onCheckedChange={onToggle}
          disabled={saving}
          aria-label={label}
        />
      </div>
    </div>
  );
}
