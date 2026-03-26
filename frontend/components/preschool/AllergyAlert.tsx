"use client";

import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, Pill } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { AllergyAlertResponse } from "@/types";

interface AllergyAlertProps {
  alerts: AllergyAlertResponse[];
  selectedStudentId?: string;
}

function severityVariant(severity: "mild" | "moderate" | "severe") {
  switch (severity) {
    case "severe":
      return "destructive" as const;
    case "moderate":
      return "secondary" as const;
    case "mild":
      return "outline" as const;
  }
}

function severityColor(severity: "mild" | "moderate" | "severe") {
  switch (severity) {
    case "severe":
      return "text-red-700 dark:text-red-400";
    case "moderate":
      return "text-amber-700 dark:text-amber-400";
    case "mild":
      return "text-muted-foreground";
  }
}

function StudentAllergyDetail({ alert }: { alert: AllergyAlertResponse }) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{alert.student_name}</p>
      <div className="flex flex-wrap gap-2">
        {alert.allergies.map((allergy, idx) => (
          <div
            key={idx}
            className="rounded-md border p-2 text-sm space-y-1"
          >
            <div className="flex items-center gap-2">
              <span className={`font-medium ${severityColor(allergy.severity)}`}>
                {allergy.allergen}
              </span>
              <Badge variant={severityVariant(allergy.severity)} className="text-xs">
                {allergy.severity}
              </Badge>
            </div>
            {allergy.reaction && (
              <p className="text-xs text-muted-foreground">
                Reaction: {allergy.reaction}
              </p>
            )}
            {allergy.medication && (
              <p className="text-xs flex items-center gap-1">
                <Pill className="h-3 w-3" />
                {allergy.medication}
              </p>
            )}
          </div>
        ))}
      </div>
      {alert.dietary_restrictions.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {alert.dietary_restrictions.map((restriction) => (
            <Badge key={restriction} variant="outline" className="text-xs">
              {restriction}
            </Badge>
          ))}
        </div>
      )}
      {alert.notes && (
        <p className="text-xs text-muted-foreground">{alert.notes}</p>
      )}
    </div>
  );
}

export function AllergyAlert({ alerts, selectedStudentId }: AllergyAlertProps) {
  const [expanded, setExpanded] = useState(false);

  if (alerts.length === 0) return null;

  // If a specific student is selected, show only their alerts
  if (selectedStudentId) {
    const studentAlert = alerts.find((a) => a.student_id === selectedStudentId);
    if (!studentAlert || studentAlert.allergies.length === 0) return null;

    const hasSevere = studentAlert.allergies.some((a) => a.severity === "severe");

    return (
      <Alert variant={hasSevere ? "destructive" : "default"} className="border-amber-300 dark:border-amber-700">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Allergy Alert</AlertTitle>
        <AlertDescription>
          <StudentAllergyDetail alert={studentAlert} />
        </AlertDescription>
      </Alert>
    );
  }

  // Class-wide view: show count with collapsible detail
  const totalAlerts = alerts.length;
  const severeCount = alerts.filter((a) =>
    a.allergies.some((al) => al.severity === "severe")
  ).length;

  return (
    <Alert
      variant={severeCount > 0 ? "destructive" : "default"}
      className="border-amber-300 dark:border-amber-700"
    >
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle className="flex items-center justify-between">
        <span>
          Allergy Alerts ({totalAlerts} student{totalAlerts !== 1 ? "s" : ""})
          {severeCount > 0 && (
            <Badge variant="destructive" className="ml-2 text-xs">
              {severeCount} severe
            </Badge>
          )}
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </Button>
      </AlertTitle>
      {expanded && (
        <AlertDescription>
          <div className="mt-3 space-y-4">
            {alerts.map((alert) => (
              <StudentAllergyDetail key={alert.student_id} alert={alert} />
            ))}
          </div>
        </AlertDescription>
      )}
    </Alert>
  );
}
