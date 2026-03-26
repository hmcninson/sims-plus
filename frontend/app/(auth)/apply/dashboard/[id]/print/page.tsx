"use client";

/**
 * SIMS Plus - Printable Application View
 *
 * Clean layout optimized for printing. Auto-triggers window.print() on load.
 * Uses @media print styles. No navigation chrome.
 * Path: {school}.simsplus.io/apply/dashboard/{id}/print
 */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { getPrintableApplication } from "@/actions/applicant.action";
import { useTenant } from "@/components/providers/TenantProvider";
import { formatGhanaDate } from "@/lib/format";
import { Loader2 } from "lucide-react";

import type { PrintableApplicationResponse } from "@/types/applicant.type";

export default function PrintApplicationPage() {
  const params = useParams();
  const applicationId = params.id as string;
  const { tenant } = useTenant();

  const [application, setApplication] = useState<PrintableApplicationResponse | null>(
    null
  );
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPrintableApplication(applicationId).then((result) => {
      if (result.success) setApplication(result.data);
      setLoading(false);
    });
  }, [applicationId]);

  // Auto-print once data is loaded
  useEffect(() => {
    if (application && !loading) {
      const timer = setTimeout(() => window.print(), 500);
      return () => clearTimeout(timer);
    }
  }, [application, loading]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (!application) {
    return (
      <div className="p-8 text-center">
        <p>Application not found.</p>
      </div>
    );
  }

  const a = application;

  return (
    <>
      <style jsx global>{`
        @media print {
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          .no-print { display: none !important; }
        }
      `}</style>

      <div className="mx-auto max-w-3xl p-8 text-sm">
        {/* Letterhead */}
        <div className="mb-8 border-b-2 pb-4 text-center">
          <h1 className="text-xl font-bold">
            {tenant?.name || "School Name"}
          </h1>
          <p className="mt-1 text-base font-semibold">
            Admission Application Form
          </p>
          <p className="text-xs text-gray-500">
            Tracking Code: {a.tracking_code}
          </p>
        </div>

        {/* Personal Information */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide">
            Personal Information
          </h2>
          <table className="w-full border-collapse text-sm">
            <tbody>
              <tr>
                <td className="border px-2 py-1 font-medium">Full Name</td>
                <td className="border px-2 py-1">
                  {a.applicant_first_name}{" "}
                  {a.applicant_other_names && `${a.applicant_other_names} `}
                  {a.applicant_last_name}
                </td>
                <td className="border px-2 py-1 font-medium">Gender</td>
                <td className="border px-2 py-1 capitalize">{a.gender}</td>
              </tr>
              <tr>
                <td className="border px-2 py-1 font-medium">Date of Birth</td>
                <td className="border px-2 py-1">
                  {a.date_of_birth ? formatGhanaDate(a.date_of_birth) : "---"}
                </td>
                <td className="border px-2 py-1 font-medium">Nationality</td>
                <td className="border px-2 py-1">{a.nationality || "---"}</td>
              </tr>
              <tr>
                <td className="border px-2 py-1 font-medium">Target Class</td>
                <td className="border px-2 py-1">
                  {a.target_class_name || "---"}
                </td>
                <td className="border px-2 py-1 font-medium">
                  Previous School
                </td>
                <td className="border px-2 py-1">
                  {a.previous_school || "---"}
                </td>
              </tr>
              {a.medical_info && (
                <tr>
                  <td className="border px-2 py-1 font-medium">
                    Medical Info
                  </td>
                  <td colSpan={3} className="border px-2 py-1">
                    {a.medical_info}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>

        {/* Guardians */}
        {a.guardians.length > 0 && (
          <section className="mb-6">
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wide">
              Guardian Information
            </h2>
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="bg-gray-100">
                  <th className="border px-2 py-1 text-left">Name</th>
                  <th className="border px-2 py-1 text-left">Relationship</th>
                  <th className="border px-2 py-1 text-left">Phone</th>
                  <th className="border px-2 py-1 text-left">Email</th>
                </tr>
              </thead>
              <tbody>
                {a.guardians.map((g, idx) => (
                  <tr key={idx}>
                    <td className="border px-2 py-1">
                      {g.first_name} {g.last_name}
                      {g.is_primary ? " (Primary)" : ""}
                    </td>
                    <td className="border px-2 py-1 capitalize">
                      {g.relationship}
                    </td>
                    <td className="border px-2 py-1">{g.phone}</td>
                    <td className="border px-2 py-1">{g.email || "---"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {/* Documents */}
        {a.documents.length > 0 && (
          <section className="mb-6">
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wide">
              Uploaded Documents
            </h2>
            <ul className="list-inside list-disc">
              {a.documents.map((doc, idx) => (
                <li key={idx}>
                  {doc.document_type.replace(/_/g, " ")} &mdash;{" "}
                  {doc.file_name}
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Status */}
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide">
            Application Status
          </h2>
          <p>
            <strong>Status:</strong>{" "}
            <span className="capitalize">{a.status.replace(/_/g, " ")}</span>
          </p>
          {a.submitted_at && (
            <p>
              <strong>Submitted:</strong> {formatGhanaDate(a.submitted_at)}
            </p>
          )}
        </section>

        {/* Decision */}
        {a.decision && (
          <section className="mb-6">
            <h2 className="mb-2 text-sm font-bold uppercase tracking-wide">
              Decision
            </h2>
            <p>
              <strong>Decision:</strong>{" "}
              <span className="capitalize">{a.decision.decision_type}</span>
            </p>
            {a.decision.offered_class_name && (
              <p>
                <strong>Offered Class:</strong>{" "}
                {a.decision.offered_class_name}
              </p>
            )}
            {a.decision.conditions && (
              <p>
                <strong>Conditions:</strong> {a.decision.conditions}
              </p>
            )}
          </section>
        )}

        {/* Footer */}
        <div className="mt-12 border-t pt-4 text-center text-xs text-gray-400">
          Generated from {tenant?.name || "SIMS Plus"} Admissions Portal
        </div>

        {/* Close/back button -- hidden on print */}
        <div className="no-print mt-8 text-center">
          <button
            onClick={() => window.history.back()}
            className="rounded-md border px-4 py-2 text-sm hover:bg-gray-50"
          >
            Back to Application
          </button>
        </div>
      </div>
    </>
  );
}
