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
import { Loader2, Settings, Baby, Utensils, Moon, Droplets, Camera, Bell, CheckCircle2, AlertTriangle, UserCheck, Heart, Clock, Send } from "lucide-react";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
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
    incident_tracking_enabled: true,
    pickup_verification_enabled: true,
    allergy_alerts_enabled: true,
    extended_care_enabled: false,
    extended_care_rate_type: "hourly" as "hourly" | "flat",
    extended_care_rate_per_hour: undefined as number | undefined,
    extended_care_flat_rate: undefined as number | undefined,
    daily_report_auto_send: false,
    daily_report_send_time: "15:00",
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

      {/* Safety & Security */}
      <Card className={!formState.enabled ? "opacity-60" : ""}>
        <CardHeader>
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-muted-foreground" />
            <div>
              <CardTitle className="text-lg">Safety & Security</CardTitle>
              <CardDescription>
                Configure safety and security features
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-1">
            <SettingRow
              icon={<AlertTriangle className="h-4 w-4" />}
              label="Incident Tracking"
              description="Enable incident/accident reporting and tracking"
              checked={formState.incident_tracking_enabled}
              onCheckedChange={(checked) => handleChange("incident_tracking_enabled", checked)}
              disabled={!formState.enabled}
            />
            <SettingRow
              icon={<UserCheck className="h-4 w-4" />}
              label="Pickup Verification"
              description="Enable authorized pickup person management and logging"
              checked={formState.pickup_verification_enabled}
              onCheckedChange={(checked) => handleChange("pickup_verification_enabled", checked)}
              disabled={!formState.enabled}
            />
            <SettingRow
              icon={<Heart className="h-4 w-4" />}
              label="Allergy Alerts"
              description="Show allergy alerts when recording daily activities"
              checked={formState.allergy_alerts_enabled}
              onCheckedChange={(checked) => handleChange("allergy_alerts_enabled", checked)}
              disabled={!formState.enabled}
            />
          </div>
        </CardContent>
      </Card>

      {/* Extended Care */}
      <Card className={!formState.enabled ? "opacity-60" : ""}>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Clock className="h-5 w-5 text-muted-foreground" />
            <div>
              <CardTitle className="text-lg">Extended Care</CardTitle>
              <CardDescription>
                Configure before/after school care tracking and billing
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-1">
            <SettingRow
              icon={<Clock className="h-4 w-4" />}
              label="Extended Care"
              description="Enable before/after school care tracking"
              checked={formState.extended_care_enabled}
              onCheckedChange={(checked) => handleChange("extended_care_enabled", checked)}
              disabled={!formState.enabled}
            />
          </div>

          {formState.extended_care_enabled && formState.enabled && (
            <div className="mt-4 ml-7 space-y-4 border-l-2 border-muted pl-4">
              <div className="space-y-3">
                <Label className="text-sm font-medium">Billing Rate Type</Label>
                <RadioGroup
                  value={formState.extended_care_rate_type || "hourly"}
                  onValueChange={(value) =>
                    handleChange("extended_care_rate_type", value)
                  }
                  className="flex gap-4"
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="hourly" id="rate-hourly" />
                    <Label htmlFor="rate-hourly" className="text-sm">Charge by hour</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="flat" id="rate-flat" />
                    <Label htmlFor="rate-flat" className="text-sm">Flat rate per session</Label>
                  </div>
                </RadioGroup>
              </div>

              {formState.extended_care_rate_type === "hourly" && (
                <div className="space-y-1.5">
                  <Label className="text-sm">Rate per Hour (GHS)</Label>
                  <Input
                    type="number"
                    min={0}
                    step={0.01}
                    placeholder="e.g. 5.00"
                    value={formState.extended_care_rate_per_hour ?? ""}
                    onChange={(e) => {
                      const val = e.target.value ? Number(e.target.value) : undefined;
                      setFormState((prev) => ({ ...prev, extended_care_rate_per_hour: val }));
                      setHasChanges(true);
                      setSaveSuccess(false);
                    }}
                    className="w-full max-w-[200px]"
                  />
                </div>
              )}

              {formState.extended_care_rate_type === "flat" && (
                <div className="space-y-1.5">
                  <Label className="text-sm">Flat Rate per Session (GHS)</Label>
                  <Input
                    type="number"
                    min={0}
                    step={0.01}
                    placeholder="e.g. 10.00"
                    value={formState.extended_care_flat_rate ?? ""}
                    onChange={(e) => {
                      const val = e.target.value ? Number(e.target.value) : undefined;
                      setFormState((prev) => ({ ...prev, extended_care_flat_rate: val }));
                      setHasChanges(true);
                      setSaveSuccess(false);
                    }}
                    className="w-full max-w-[200px]"
                  />
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Daily Report Auto-Send */}
      <Card className={!formState.enabled ? "opacity-60" : ""}>
        <CardHeader>
          <div className="flex items-center gap-3">
            <Send className="h-5 w-5 text-muted-foreground" />
            <div>
              <CardTitle className="text-lg">Daily Report Automation</CardTitle>
              <CardDescription>
                Automatically send daily activity reports to parents
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-1">
            <SettingRow
              icon={<Send className="h-4 w-4" />}
              label="Auto-Send Daily Reports"
              description="Automatically send daily activity reports to parents at a scheduled time"
              checked={formState.daily_report_auto_send}
              onCheckedChange={(checked) => handleChange("daily_report_auto_send", checked)}
              disabled={!formState.enabled}
            />
          </div>

          {formState.daily_report_auto_send && formState.enabled && (
            <div className="mt-4 ml-7 border-l-2 border-muted pl-4">
              <div className="space-y-1.5">
                <Label className="text-sm">Send Time</Label>
                <Input
                  type="time"
                  value={formState.daily_report_send_time || "15:00"}
                  onChange={(e) => {
                    setFormState((prev) => ({ ...prev, daily_report_send_time: e.target.value }));
                    setHasChanges(true);
                    setSaveSuccess(false);
                  }}
                  className="w-full max-w-[200px]"
                />
                <p className="text-xs text-muted-foreground">
                  Reports will be sent to parents at this time daily.
                </p>
              </div>
            </div>
          )}
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
