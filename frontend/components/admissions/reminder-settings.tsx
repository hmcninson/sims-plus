"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Bell, Loader2, Save } from "lucide-react";
import { updateReminderConfig } from "@/actions/admissions.action";

interface ReminderSettingsProps {
  periodId: string;
  initialEnabled: boolean;
  initialDaysBefore: number | null;
}

export function ReminderSettings({
  periodId,
  initialEnabled,
  initialDaysBefore,
}: ReminderSettingsProps) {
  const [enabled, setEnabled] = useState(initialEnabled);
  const [daysBefore, setDaysBefore] = useState<string>(
    initialDaysBefore ? String(initialDaysBefore) : ""
  );
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (enabled && !daysBefore) {
      toast.error("Please specify the number of days before close");
      return;
    }

    const days = daysBefore ? parseInt(daysBefore, 10) : undefined;
    if (enabled && (days === undefined || days < 1 || days > 90)) {
      toast.error("Days before close must be between 1 and 90");
      return;
    }

    setSaving(true);
    const result = await updateReminderConfig(periodId, {
      reminder_enabled: enabled,
      reminder_days_before_close: enabled ? days : undefined,
    });

    if (result.success) {
      toast.success("Reminder settings saved");
    } else {
      toast.error(result.error);
    }
    setSaving(false);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Bell className="h-4 w-4" />
          Application Reminders
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Automatically send reminders to applicants with incomplete (draft)
          applications before the admission period closes.
        </p>

        <div className="flex items-center justify-between rounded-lg border p-3">
          <div className="space-y-0.5">
            <Label htmlFor="reminder-toggle" className="text-sm font-medium">
              Enable Reminders
            </Label>
            <p className="text-xs text-muted-foreground">
              Send SMS/email reminders to applicants
            </p>
          </div>
          <Switch
            id="reminder-toggle"
            checked={enabled}
            onCheckedChange={setEnabled}
          />
        </div>

        {enabled && (
          <div className="space-y-2">
            <Label htmlFor="reminder-days">Days Before Close</Label>
            <p className="text-xs text-muted-foreground">
              How many days before the period end date should reminders be sent?
              Reminders will be sent daily from this point until the close date.
            </p>
            <Input
              id="reminder-days"
              type="number"
              min={1}
              max={90}
              value={daysBefore}
              onChange={(e) => setDaysBefore(e.target.value)}
              placeholder="e.g. 7"
              className="w-full sm:w-[120px]"
            />
          </div>
        )}

        <div className="flex justify-end">
          <Button onClick={handleSave} disabled={saving} size="sm">
            {saving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Save Settings
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
