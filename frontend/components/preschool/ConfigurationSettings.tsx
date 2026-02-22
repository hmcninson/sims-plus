"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Loader2, Settings, Baby, Utensils, Moon, Droplets, Camera, Bell, CheckCircle2 } from "lucide-react";
import { getPreschoolSettings, updatePreschoolSettings } from "@/actions/school.action";
import { getRatingScales } from "@/actions/preschool.action";
import type { PreschoolSettings, PreschoolSettingsUpdate } from "@/types/school.type";
import type { PreschoolRatingScale } from "@/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface SettingRowProps {
  icon: React.ReactNode;
  label: string;
  description: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
}

function SettingRow({ icon, label, description, checked, onCheckedChange, disabled }: SettingRowProps) {
  return (
    <div className="flex items-center justify-between py-4 border-b last:border-b-0">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 text-muted-foreground">{icon}</div>
        <div className="space-y-1">
          <Label className="text-sm font-medium leading-none">{label}</Label>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
      <Switch checked={checked} onCheckedChange={onCheckedChange} disabled={disabled} />
    </div>
  );
}

export function ConfigurationSettings() {
  const [settings, setSettings] = useState<PreschoolSettings | null>(null);
  const [ratingScales, setRatingScales] = useState<PreschoolRatingScale[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Local state for form
  const [formState, setFormState] = useState<PreschoolSettings>({
    enabled: false,
    daily_logs_enabled: true,
    meal_tracking: true,
    nap_tracking: true,
    diaper_tracking: true,
    potty_training_tracking: true,
    observation_photos_enabled: true,
    parent_daily_updates: true,
    default_rating_scale_id: undefined,
  });

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    setLoading(true);
    try {
      const [settingsResult, scalesResult] = await Promise.all([
        getPreschoolSettings(),
        getRatingScales(),
      ]);

      if (settingsResult.success && settingsResult.data) {
        setSettings(settingsResult.data);
        setFormState(settingsResult.data);
      }

      if (scalesResult.success && scalesResult.data) {
        setRatingScales(scalesResult.data);
      }
    } catch (err) {
      setError("Failed to load settings");
    } finally {
      setLoading(false);
    }
  }

  function handleChange(key: keyof PreschoolSettings, value: boolean | string | undefined) {
    setFormState((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
    setSaveSuccess(false);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);

    try {
      const updateData: PreschoolSettingsUpdate = { ...formState };
      const result = await updatePreschoolSettings(updateData);

      if (result.success && result.data) {
        setSettings(result.data);
        setFormState(result.data);
        setHasChanges(false);
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      } else {
        setError(result.error || "Failed to save settings");
      }
    } catch (err) {
      setError("Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

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
    <div className="space-y-6">
      {/* Main Enable/Disable Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Baby className="h-5 w-5 text-primary" />
              </div>
              <div>
                <CardTitle>Preschool Module</CardTitle>
                <CardDescription>
                  Enable preschool features for your school
                </CardDescription>
              </div>
            </div>
            <Switch
              checked={formState.enabled}
              onCheckedChange={(checked) => handleChange("enabled", checked)}
            />
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {formState.enabled
              ? "Preschool features are enabled. Teachers can track developmental milestones, daily activities, and generate progress reports for preschool students."
              : "Enable this setting to unlock preschool-specific features including developmental assessments, daily activity logs, and parent communication tools."}
          </p>
        </CardContent>
      </Card>

      {/* Daily Logs Configuration */}
      <Card className={!formState.enabled ? "opacity-60" : ""}>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Settings className="h-5 w-5 text-muted-foreground" />
            <div>
              <CardTitle className="text-lg">Daily Activity Logs</CardTitle>
              <CardDescription>
                Configure what activities to track in daily logs
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-1">
            <SettingRow
              icon={<Utensils className="h-4 w-4" />}
              label="Meal Tracking"
              description="Track breakfast, lunch, snacks and how much was eaten"
              checked={formState.meal_tracking}
              onCheckedChange={(checked) => handleChange("meal_tracking", checked)}
              disabled={!formState.enabled || !formState.daily_logs_enabled}
            />
            <SettingRow
              icon={<Moon className="h-4 w-4" />}
              label="Nap Tracking"
              description="Track nap times and sleep quality"
              checked={formState.nap_tracking}
              onCheckedChange={(checked) => handleChange("nap_tracking", checked)}
              disabled={!formState.enabled || !formState.daily_logs_enabled}
            />
            <SettingRow
              icon={<Droplets className="h-4 w-4" />}
              label="Diaper Tracking"
              description="Track diaper changes for younger children"
              checked={formState.diaper_tracking}
              onCheckedChange={(checked) => handleChange("diaper_tracking", checked)}
              disabled={!formState.enabled || !formState.daily_logs_enabled}
            />
            <SettingRow
              icon={<CheckCircle2 className="h-4 w-4" />}
              label="Potty Training Tracking"
              description="Track potty training progress and accidents"
              checked={formState.potty_training_tracking}
              onCheckedChange={(checked) => handleChange("potty_training_tracking", checked)}
              disabled={!formState.enabled || !formState.daily_logs_enabled}
            />
          </div>
        </CardContent>
      </Card>

      {/* Observations & Communication */}
      <Card className={!formState.enabled ? "opacity-60" : ""}>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Camera className="h-5 w-5 text-muted-foreground" />
            <div>
              <CardTitle className="text-lg">Observations & Communication</CardTitle>
              <CardDescription>
                Configure observation and parent communication features
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-1">
            <SettingRow
              icon={<Camera className="h-4 w-4" />}
              label="Observation Photos"
              description="Allow teachers to attach photos to observations"
              checked={formState.observation_photos_enabled}
              onCheckedChange={(checked) => handleChange("observation_photos_enabled", checked)}
              disabled={!formState.enabled}
            />
            <SettingRow
              icon={<Bell className="h-4 w-4" />}
              label="Parent Daily Updates"
              description="Send daily activity summaries to parents"
              checked={formState.parent_daily_updates}
              onCheckedChange={(checked) => handleChange("parent_daily_updates", checked)}
              disabled={!formState.enabled}
            />
          </div>
        </CardContent>
      </Card>

      {/* Default Rating Scale */}
      <Card className={!formState.enabled ? "opacity-60" : ""}>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Settings className="h-5 w-5 text-muted-foreground" />
            <div>
              <CardTitle className="text-lg">Default Rating Scale</CardTitle>
              <CardDescription>
                Select the default rating scale for preschool assessments
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Select
            value={formState.default_rating_scale_id || ""}
            onValueChange={(value) => handleChange("default_rating_scale_id", value || undefined)}
            disabled={!formState.enabled}
          >
            <SelectTrigger className="w-full max-w-sm">
              <SelectValue placeholder="Select a rating scale..." />
            </SelectTrigger>
            <SelectContent>
              {ratingScales.map((scale) => (
                <SelectItem key={scale.id} value={scale.id}>
                  {scale.name} {scale.is_default && "(System Default)"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-sm text-muted-foreground mt-2">
            This rating scale will be used by default when assessing students on developmental skills.
          </p>
        </CardContent>
      </Card>

      {/* Error Message */}
      {error && (
        <div className="p-4 bg-destructive/10 text-destructive rounded-lg">
          {error}
        </div>
      )}

      {/* Save Button */}
      <div className="flex items-center justify-end gap-4">
        {saveSuccess && (
          <span className="text-sm text-green-600 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            Settings saved successfully
          </span>
        )}
        <Button onClick={handleSave} disabled={saving || !hasChanges}>
          {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save Changes
        </Button>
      </div>
    </div>
  );
}
