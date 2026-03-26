"use client";

/**
 * SIMS Plus - Applicant Application Detail Page
 *
 * Read-only view of a submitted application.
 * Shows personal info, guardians, documents, payment, status timeline, decision.
 * Path: {school}.simsplus.io/apply/dashboard/{id}
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { ApplicationStatusBadge } from "@/components/admissions/application-status-badge";
import { OfferResponseForm } from "@/components/admissions/offer-response-form";
import { getMyApplicationDetail } from "@/actions/applicant.action";
import { formatGhanaDate } from "@/lib/format";

import {
  ArrowLeft,
  Printer,
  User,
  Users,
  FileText,
  CreditCard,
  Clock,
  CheckCircle,
  Download,
} from "lucide-react";

import type { MyApplicationDetail } from "@/types/applicant.type";

export default function ApplicantApplicationDetailPage() {
  const params = useParams();
  const applicationId = params.id as string;

  const [application, setApplication] = useState<MyApplicationDetail | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMyApplicationDetail(applicationId).then((result) => {
      if (result.success) {
        setApplication(result.data);
      } else {
        setError(result.error || "Failed to load application");
      }
      setLoading(false);
    });
  }, [applicationId]);

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 px-4 py-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full rounded-lg" />
      </div>
    );
  }

  if (error || !application) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 text-center">
        <p className="text-muted-foreground">{error || "Not found"}</p>
        <Button asChild className="mt-4" variant="outline">
          <Link href="/apply/dashboard">Back to Dashboard</Link>
        </Button>
      </div>
    );
  }

  const a = application;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Link
            href="/apply/dashboard"
            className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to Dashboard
          </Link>
          <h1 className="flex flex-wrap items-center gap-3 text-2xl font-bold">
            {a.applicant_first_name} {a.applicant_last_name}
            <ApplicationStatusBadge status={a.status} />
          </h1>
          <p className="text-sm text-muted-foreground">{a.tracking_code}</p>
        </div>
        <Button variant="outline" asChild>
          <Link href={`/apply/dashboard/${applicationId}/print`}>
            <Printer className="mr-2 h-4 w-4" />
            Print
          </Link>
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left column -- details */}
        <div className="space-y-6 lg:col-span-2">
          {/* Personal Information */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <User className="h-4 w-4" /> Personal Information
              </CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-muted-foreground">Full Name</dt>
                  <dd className="font-medium">
                    {a.applicant_first_name}{" "}
                    {a.applicant_other_names && `${a.applicant_other_names} `}
                    {a.applicant_last_name}
                  </dd>
                </div>
                {a.date_of_birth && (
                  <div>
                    <dt className="text-muted-foreground">Date of Birth</dt>
                    <dd className="font-medium">
                      {formatGhanaDate(a.date_of_birth)}
                    </dd>
                  </div>
                )}
                {a.gender && (
                  <div>
                    <dt className="text-muted-foreground">Gender</dt>
                    <dd className="font-medium capitalize">{a.gender}</dd>
                  </div>
                )}
                {a.nationality && (
                  <div>
                    <dt className="text-muted-foreground">Nationality</dt>
                    <dd className="font-medium">{a.nationality}</dd>
                  </div>
                )}
                <div>
                  <dt className="text-muted-foreground">Target Class</dt>
                  <dd className="font-medium">
                    {a.target_class_name || "---"}
                  </dd>
                </div>
                {a.previous_school && (
                  <div>
                    <dt className="text-muted-foreground">Previous School</dt>
                    <dd className="font-medium">{a.previous_school}</dd>
                  </div>
                )}
                {a.medical_info && (
                  <div className="sm:col-span-2">
                    <dt className="text-muted-foreground">
                      Medical Information
                    </dt>
                    <dd className="font-medium">{a.medical_info}</dd>
                  </div>
                )}
              </dl>
            </CardContent>
          </Card>

          {/* Guardians */}
          {a.guardians.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Users className="h-4 w-4" /> Guardians
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {a.guardians.map((g, i) => (
                  <div key={g.id}>
                    {i > 0 && <Separator className="mb-4" />}
                    <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
                      <div>
                        <dt className="text-muted-foreground">Name</dt>
                        <dd className="font-medium">
                          {g.first_name} {g.last_name}
                          {g.is_primary && (
                            <Badge variant="secondary" className="ml-2">
                              Primary
                            </Badge>
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">Relationship</dt>
                        <dd className="font-medium capitalize">
                          {g.relationship}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-muted-foreground">Phone</dt>
                        <dd className="font-medium">{g.phone}</dd>
                      </div>
                      {g.email && (
                        <div>
                          <dt className="text-muted-foreground">Email</dt>
                          <dd className="font-medium">{g.email}</dd>
                        </div>
                      )}
                    </dl>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Documents */}
          {a.documents.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileText className="h-4 w-4" /> Documents
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm">
                  {a.documents.map((doc) => (
                    <li
                      key={doc.id}
                      className="flex items-center justify-between"
                    >
                      <span>
                        <span className="font-medium capitalize">
                          {doc.document_type.replace(/_/g, " ")}
                        </span>
                        <span className="ml-2 text-muted-foreground">
                          {doc.file_name}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right column -- timeline, payment, decision, offer */}
        <div className="space-y-6">
          {/* Offer Response Form (shown when status is offered) */}
          {(a.status === "offered" ||
            a.status === "accepted" ||
            a.status === "withdrawn") &&
            a.decision &&
            (a.decision.decision_type === "accepted" ||
              a.decision.decision_type === "waitlisted") && (
              <OfferResponseForm applicationId={applicationId} />
            )}

          {/* Status Timeline */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Clock className="h-4 w-4" /> Status History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ol className="relative border-l border-muted-foreground/20 pl-4">
                {a.status_history.map((entry) => (
                  <li key={entry.id} className="mb-4 last:mb-0">
                    <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-background bg-primary" />
                    <p className="text-sm font-medium capitalize">
                      {entry.to_status.replace(/_/g, " ")}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatGhanaDate(entry.created_at)}
                    </p>
                    {entry.reason && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        {entry.reason}
                      </p>
                    )}
                  </li>
                ))}
              </ol>
            </CardContent>
          </Card>

          {/* Payment */}
          {a.payments.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <CreditCard className="h-4 w-4" /> Payment
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm">
                {a.payments.map((p) => (
                  <div key={p.id} className="space-y-1">
                    <div className="flex justify-between">
                      <span>Amount</span>
                      <span className="font-medium">
                        {p.currency} {p.amount.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Status</span>
                      <Badge variant="outline" className="capitalize">
                        {p.status}
                      </Badge>
                    </div>
                    {p.paid_at && (
                      <div className="flex justify-between">
                        <span>Paid</span>
                        <span>{formatGhanaDate(p.paid_at)}</span>
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Decision */}
          {a.decision && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <CheckCircle className="h-4 w-4" /> Decision
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span>Decision</span>
                  <Badge variant="outline" className="capitalize">
                    {a.decision.decision_type}
                  </Badge>
                </div>
                {a.decision.offered_class_name && (
                  <div className="flex justify-between">
                    <span>Offered Class</span>
                    <span className="font-medium">
                      {a.decision.offered_class_name}
                    </span>
                  </div>
                )}
                {a.decision.conditions && (
                  <div>
                    <span className="text-muted-foreground">Conditions:</span>
                    <p className="mt-1">{a.decision.conditions}</p>
                  </div>
                )}
                {a.decision.response_deadline && (
                  <div className="flex justify-between">
                    <span>Response Deadline</span>
                    <span className="font-medium">
                      {formatGhanaDate(a.decision.response_deadline)}
                    </span>
                  </div>
                )}
                {/* Letter download link */}
                {a.decision.decision_letter_url && (
                  <a
                    href={a.decision.decision_letter_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-sm text-primary hover:underline pt-2"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Download Letter
                  </a>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
