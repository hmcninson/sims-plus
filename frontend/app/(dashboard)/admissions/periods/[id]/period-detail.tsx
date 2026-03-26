"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  Calendar,
  DollarSign,
  GraduationCap,
  UserCheck,
  Users,
  Save,
  Loader2,
  FileText,
} from "lucide-react";
import {
  getAdmissionPeriods,
  updateFormConfig,
} from "@/actions/admissions.action";
import { ReminderSettings } from "@/components/admissions/reminder-settings";
import type {
  AdmissionPeriod,
  AdmissionPeriodStatus,
} from "@/types/admissions.type";

interface PeriodDetailProps {
  periodId: string;
}

const STATUS_CONFIG: Record<
  AdmissionPeriodStatus,
  { label: string; className: string }
> = {
  draft: {
    label: "Draft",
    className:
      "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  },
  open: {
    label: "Open",
    className:
      "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  },
  closed: {
    label: "Closed",
    className: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  },
  archived: {
    label: "Archived",
    className:
      "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
  },
};

const COMMON_DOCUMENTS = [
  { id: "birth_certificate", label: "Birth Certificate" },
  { id: "passport_photo", label: "Passport Photo" },
  { id: "transcript", label: "Academic Transcript" },
  { id: "medical_report", label: "Medical Report" },
  { id: "immunization_record", label: "Immunization Record" },
  { id: "transfer_certificate", label: "Transfer Certificate" },
  { id: "recommendation_letter", label: "Recommendation Letter" },
  { id: "national_id", label: "National ID (Guardian)" },
];

export function PeriodDetail({ periodId }: PeriodDetailProps) {
  const router = useRouter();
  const [period, setPeriod] = useState<AdmissionPeriod | null>(null);
  const [loading, setLoading] = useState(true);
  const [formSchema, setFormSchema] = useState("{}");
  const [requiredDocuments, setRequiredDocuments] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const loadPeriod = useCallback(async () => {
    const result = await getAdmissionPeriods({ page_size: 50 });
    if (result.success && result.data) {
      const found = result.data.items.find((p) => p.id === periodId);
      if (found) {
        setPeriod(found);
      }
    }
    setLoading(false);
  }, [periodId]);

  useEffect(() => {
    loadPeriod();
  }, [loadPeriod]);

  function toggleDocument(docId: string) {
    setRequiredDocuments((prev) =>
      prev.includes(docId)
        ? prev.filter((d) => d !== docId)
        : [...prev, docId]
    );
  }

  async function handleSaveFormConfig() {
    setSaving(true);
    try {
      let parsedSchema: Record<string, unknown>;
      try {
        parsedSchema = JSON.parse(formSchema);
      } catch {
        toast.error("Invalid JSON in form schema");
        setSaving(false);
        return;
      }

      const result = await updateFormConfig(periodId, {
        form_schema: parsedSchema,
        required_documents: requiredDocuments,
      });

      if (result.success) {
        toast.success("Form configuration saved");
      } else {
        toast.error(result.error);
      }
    } finally {
      setSaving(false);
    }
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    });
  }

  if (loading) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Skeleton className="h-[200px]" />
          <Skeleton className="h-[200px]" />
        </div>
        <Skeleton className="h-[300px]" />
      </div>
    );
  }

  if (!period) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4 p-6">
        <FileText className="h-10 w-10 text-muted-foreground" />
        <p className="text-muted-foreground">Period not found</p>
        <Button variant="outline" asChild>
          <Link href="/admissions/periods">Back to Periods</Link>
        </Button>
      </div>
    );
  }

  const statusConfig = STATUS_CONFIG[period.status];

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.push("/admissions/periods")}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{period.name}</h1>
            <Badge variant="outline" className={statusConfig.className}>
              {statusConfig.label}
            </Badge>
          </div>
          {period.description && (
            <p className="text-sm text-muted-foreground mt-1">
              {period.description}
            </p>
          )}
        </div>
      </div>

      {/* Period Info + Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Period Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div className="flex items-start gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground mt-0.5" />
                <div>
                  <p className="text-muted-foreground">Start Date</p>
                  <p className="font-medium">{formatDate(period.start_date)}</p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <Calendar className="h-4 w-4 text-muted-foreground mt-0.5" />
                <div>
                  <p className="text-muted-foreground">End Date</p>
                  <p className="font-medium">{formatDate(period.end_date)}</p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <DollarSign className="h-4 w-4 text-muted-foreground mt-0.5" />
                <div>
                  <p className="text-muted-foreground">Application Fee</p>
                  <p className="font-medium">
                    {period.application_fee_required
                      ? `GHS ${Number(period.application_fee_amount ?? 0).toFixed(2)}`
                      : "Not required"}
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <GraduationCap className="h-4 w-4 text-muted-foreground mt-0.5" />
                <div>
                  <p className="text-muted-foreground">Entrance Exam</p>
                  <p className="font-medium">
                    {period.entrance_exam_required ? "Required" : "Not required"}
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-2">
                <UserCheck className="h-4 w-4 text-muted-foreground mt-0.5" />
                <div>
                  <p className="text-muted-foreground">Applicant Account</p>
                  <p className="font-medium">
                    {period.require_applicant_account ? "Required" : "Not required"}
                  </p>
                </div>
              </div>
            </div>
            {period.max_applications && (
              <div className="flex items-start gap-2 text-sm">
                <Users className="h-4 w-4 text-muted-foreground mt-0.5" />
                <div>
                  <p className="text-muted-foreground">Max Applications</p>
                  <p className="font-medium">{period.max_applications}</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Statistics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div className="text-center p-4 rounded-lg bg-muted/50">
                <p className="text-2xl font-bold">
                  {period.application_count ?? 0}
                </p>
                <p className="text-xs text-muted-foreground">
                  Total Applications
                </p>
              </div>
              <div className="text-center p-4 rounded-lg bg-muted/50">
                <p className="text-2xl font-bold">
                  {period.target_classes?.length ?? 0}
                </p>
                <p className="text-xs text-muted-foreground">Target Classes</p>
              </div>
            </div>
            <div className="mt-4">
              <Button variant="outline" size="sm" className="w-full" asChild>
                <Link
                  href={`/admissions/applications?admission_period_id=${period.id}`}
                >
                  View Applications
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Form Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Form Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* JSON Schema Editor */}
          <div className="space-y-2">
            <Label>Custom Fields Schema (JSON)</Label>
            <p className="text-xs text-muted-foreground">
              Define custom form fields using a JSON schema. These fields will
              appear in the public application form.
            </p>
            <Textarea
              value={formSchema}
              onChange={(e) => setFormSchema(e.target.value)}
              className="font-mono text-sm min-h-[200px]"
              placeholder='{"fields": [{"name": "religion", "type": "text", "label": "Religion", "required": false}]}'
            />
          </div>

          {/* Required Documents */}
          <div className="space-y-3">
            <Label>Required Documents</Label>
            <p className="text-xs text-muted-foreground">
              Select which documents applicants must upload with their
              application.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {COMMON_DOCUMENTS.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center space-x-2 rounded-md border p-3 cursor-pointer hover:bg-muted/50"
                  onClick={() => toggleDocument(doc.id)}
                >
                  <Checkbox
                    checked={requiredDocuments.includes(doc.id)}
                    onCheckedChange={() => toggleDocument(doc.id)}
                  />
                  <Label className="text-sm font-normal cursor-pointer">
                    {doc.label}
                  </Label>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end">
            <Button onClick={handleSaveFormConfig} disabled={saving}>
              {saving ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              Save Configuration
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Reminder Settings */}
      <ReminderSettings
        periodId={periodId}
        initialEnabled={period.reminder_enabled ?? false}
        initialDaysBefore={period.reminder_days_before_close ?? null}
      />
    </div>
  );
}
