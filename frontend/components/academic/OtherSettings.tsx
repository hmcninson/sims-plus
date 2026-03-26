"use client";

import { useState, useEffect, useMemo } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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

// The toggle fields managed by this component
const TOGGLE_FIELDS = [
  "auto_promote_students",
  "allow_grade_amendments",
  "show_position_on_report_cards",
  "require_attendance_for_exams",
  "enable_continuous_assessment",
] as const;

type ToggleField = (typeof TOGGLE_FIELDS)[number];

interface ToggleFormData {
  auto_promote_students: boolean;
  allow_grade_amendments: boolean;
  show_position_on_report_cards: boolean;
  require_attendance_for_exams: boolean;
  enable_continuous_assessment: boolean;
}

const DEFAULT_FORM_DATA: ToggleFormData = {
  auto_promote_students: false,
  allow_grade_amendments: true,
  show_position_on_report_cards: true,
  require_attendance_for_exams: false,
  enable_continuous_assessment: true,
};

export function OtherSettings() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Saved state from the server — used to detect dirty changes
  const [savedData, setSavedData] = useState<ToggleFormData>(DEFAULT_FORM_DATA);
  // Local form state — updated immediately on toggle for responsive UI
  const [formData, setFormData] = useState<ToggleFormData>(DEFAULT_FORM_DATA);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    const result = await getAcademicSettings();
    if (result.success && result.data) {
      const data = extractToggleData(result.data);
      setSavedData(data);
      setFormData(data);
    } else {
      setError(result.error || "Failed to load settings");
    }
    setLoading(false);
  };

  /** Pull only the toggle fields from the full settings response */
  function extractToggleData(settings: AcademicSettings): ToggleFormData {
    return {
      auto_promote_students: settings.auto_promote_students ?? DEFAULT_FORM_DATA.auto_promote_students,
      allow_grade_amendments: settings.allow_grade_amendments ?? DEFAULT_FORM_DATA.allow_grade_amendments,
      show_position_on_report_cards: settings.show_position_on_report_cards ?? DEFAULT_FORM_DATA.show_position_on_report_cards,
      require_attendance_for_exams: settings.require_attendance_for_exams ?? DEFAULT_FORM_DATA.require_attendance_for_exams,
      enable_continuous_assessment: settings.enable_continuous_assessment ?? DEFAULT_FORM_DATA.enable_continuous_assessment,
    };
  }

  // Track whether there are unsaved changes
  const isDirty = useMemo(() => {
    return TOGGLE_FIELDS.some((field) => formData[field] !== savedData[field]);
  }, [formData, savedData]);

  const handleToggle = (field: ToggleField, checked: boolean) => {
    setFormData((prev) => ({ ...prev, [field]: checked }));
    setError(null);
    setSuccess(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);

    const result = await updateAcademicSettings(formData);

    if (result.success && result.data) {
      const data = extractToggleData(result.data);
      setSavedData(data);
      setFormData(data);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } else {
      setError(result.error || "Failed to save settings");
    }

    setSaving(false);
  };

  const handleReset = () => {
    setFormData(savedData);
    setError(null);
    setSuccess(false);
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
            Settings saved successfully!
          </div>
        )}

        <SettingItem
          label="Auto-promote students"
          description="Automatically promote passing students at end of academic year."
          checked={formData.auto_promote_students}
          onCheckedChange={(checked) =>
            handleToggle("auto_promote_students", checked)
          }
          disabled={saving}
        />

        <SettingItem
          label="Allow grade amendments"
          description="Allow teachers to amend grades after submission (with approval)."
          checked={formData.allow_grade_amendments}
          onCheckedChange={(checked) =>
            handleToggle("allow_grade_amendments", checked)
          }
          disabled={saving}
        />

        <SettingItem
          label="Show position on report cards"
          description="Display class position/ranking on student report cards."
          checked={formData.show_position_on_report_cards}
          onCheckedChange={(checked) =>
            handleToggle("show_position_on_report_cards", checked)
          }
          disabled={saving}
        />

        <SettingItem
          label="Require attendance for exams"
          description="Students must have attendance records before exam scores can be entered."
          checked={formData.require_attendance_for_exams}
          onCheckedChange={(checked) =>
            handleToggle("require_attendance_for_exams", checked)
          }
          disabled={saving}
        />

        <SettingItem
          label="Enable continuous assessment"
          description="Track class work, assignments, and tests throughout the term."
          checked={formData.enable_continuous_assessment}
          onCheckedChange={(checked) =>
            handleToggle("enable_continuous_assessment", checked)
          }
          disabled={saving}
        />

        <div className="flex items-center justify-end gap-2 pt-4">
          {isDirty && (
            <Button type="button" variant="outline" onClick={handleReset} disabled={saving}>
              Reset
            </Button>
          )}
          <Button onClick={handleSave} disabled={saving || !isDirty}>
            {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Save Settings
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
