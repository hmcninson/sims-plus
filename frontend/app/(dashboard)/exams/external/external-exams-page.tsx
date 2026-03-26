"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Plus, Upload, Download, ChevronDown, FileText } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import { ExternalExamRegistrationForm } from "@/components/curriculum/ExternalExamRegistrationForm";
import { ExternalExamRegistrationTable } from "@/components/curriculum/ExternalExamRegistrationTable";
import { getExternalExamRegistrations, exportExternalExamRegistrations } from "@/actions/curriculum.action";
import type { ExternalExamRegistration } from "@/types/curriculum.type";

interface ExternalExamsPageProps {
  initialRegistrations: ExternalExamRegistration[];
  students: { id: string; name: string; student_number?: string }[];
  /** Map of student_id -> display name for the table */
  studentNames: Record<string, string>;
}

export function ExternalExamsPage({
  initialRegistrations,
  students,
  studentNames,
}: ExternalExamsPageProps) {
  const router = useRouter();
  const [registrations, setRegistrations] = useState(initialRegistrations);
  const [showForm, setShowForm] = useState(false);
  const [editingRegistration, setEditingRegistration] = useState<
    ExternalExamRegistration | undefined
  >(undefined);

  const refresh = useCallback(async () => {
    const result = await getExternalExamRegistrations();
    if (result.success && result.data) {
      setRegistrations(result.data.items);
    }
  }, []);

  function handleEdit(registration: ExternalExamRegistration) {
    setEditingRegistration(registration);
    setShowForm(true);
  }

  function handleCloseForm(open: boolean) {
    if (!open) {
      setEditingRegistration(undefined);
    }
    setShowForm(open);
  }

  async function handleExport(examBoard: string) {
    const session = prompt("Enter exam session (e.g., May 2026):");
    if (!session) return;

    const result = await exportExternalExamRegistrations(examBoard, session);

    if (result.success && result.data) {
      const blob = new Blob([result.data as BlobPart], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${examBoard}_registrations_${session.replace(/\s/g, "_")}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Export downloaded");
    } else if (!result.success) {
      toast.error(result.error);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">External Exams</h1>
          <p className="text-sm text-muted-foreground">
            Manage WAEC, Cambridge, and other external exam registrations and results.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => setShowForm(true)}>
            <Plus className="mr-2 size-4" />
            Register Student
          </Button>
          <Button
            variant="outline"
            onClick={() => router.push("/exams/external/import")}
          >
            <Upload className="mr-2 size-4" />
            Import Results
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">
                <Download className="mr-2 size-4" />
                Export
                <ChevronDown className="ml-2 size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleExport("waec")}>
                <FileText className="mr-2 size-4" />
                WAEC Registration Export
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport("cambridge_international")}>
                <FileText className="mr-2 size-4" />
                Cambridge Registration Export
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport("edexcel")}>
                <FileText className="mr-2 size-4" />
                Edexcel Registration Export
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Table */}
      <ExternalExamRegistrationTable
        registrations={registrations}
        studentNames={studentNames}
        onEdit={handleEdit}
        onRefresh={refresh}
      />

      {/* Registration Form */}
      <ExternalExamRegistrationForm
        open={showForm}
        onOpenChange={handleCloseForm}
        editingRegistration={editingRegistration}
        students={students}
        onSuccess={refresh}
      />
    </div>
  );
}
