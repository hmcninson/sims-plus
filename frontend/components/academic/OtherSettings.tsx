"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Loader2 } from "lucide-react";
import { getAcademicSettings, updateAcademicSettings } from "@/actions/academic.action";
import type { AcademicSettings } from "@/types";

interface SettingItemProps {
  label: string;
  description: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
}

function SettingItem({
  label,
  description,
  checked,
  onCheckedChange,
  disabled,
}: SettingItemProps) {
  return (
    <div className="flex items-center justify-between rounded-lg border p-4">
      <div className="space-y-0.5">
        <Label className="text-base">{label}</Label>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <Switch
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
      />
    </div>
  );
}

export function OtherSettings() {
  const [settings, setSettings] = useState<AcademicSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingField, setSavingField] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    const result = await getAcademicSettings();
    if (result.success && result.data) {
      setSettings(result.data);
    } else {
      setError(result.error || "Failed to load settings");
    }
    setLoading(false);
  };

  const handleToggle = async (
    field: keyof AcademicSettings,
    checked: boolean
  ) => {
    if (!settings) return;

    setSavingField(field);
    setError(null);
    setSuccess(false);

    // Optimistically update UI
    const previousSettings = settings;
    setSettings({ ...settings, [field]: checked });

    const result = await updateAcademicSettings({ [field]: checked });

    if (result.success && result.data) {
      setSettings(result.data);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2000);
    } else {
      // Revert on error
      setSettings(previousSettings);
      setError(result.error || "Failed to update setting");
    }

    setSavingField(null);
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Other Academic Settings</CardTitle>
        <CardDescription>
          Additional configurations for academic management.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}
        {success && (
          <div className="rounded-md bg-green-50 p-3 text-sm text-green-700 dark:bg-green-900/20 dark:text-green-400">
            Setting updated successfully!
          </div>
        )}

        <SettingItem
          label="Auto-promote students"
          description="Automatically promote passing students at end of academic year."
          checked={settings?.auto_promote_students ?? false}
          onCheckedChange={(checked) =>
            handleToggle("auto_promote_students", checked)
          }
          disabled={savingField !== null}
        />

        <SettingItem
          label="Allow grade amendments"
          description="Allow teachers to amend grades after submission (with approval)."
          checked={settings?.allow_grade_amendments ?? true}
          onCheckedChange={(checked) =>
            handleToggle("allow_grade_amendments", checked)
          }
          disabled={savingField !== null}
        />

        <SettingItem
          label="Show position on report cards"
          description="Display class position/ranking on student report cards."
          checked={settings?.show_position_on_report_cards ?? true}
          onCheckedChange={(checked) =>
            handleToggle("show_position_on_report_cards", checked)
          }
          disabled={savingField !== null}
        />

        <SettingItem
          label="Require attendance for exams"
          description="Students must have attendance records before exam scores can be entered."
          checked={settings?.require_attendance_for_exams ?? false}
          onCheckedChange={(checked) =>
            handleToggle("require_attendance_for_exams", checked)
          }
          disabled={savingField !== null}
        />

        <SettingItem
          label="Enable continuous assessment"
          description="Track class work, assignments, and tests throughout the term."
          checked={settings?.enable_continuous_assessment ?? true}
          onCheckedChange={(checked) =>
            handleToggle("enable_continuous_assessment", checked)
          }
          disabled={savingField !== null}
        />
      </CardContent>
    </Card>
  );
}
