"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Download, FileText, User, Phone, Mail } from "lucide-react";
import type { ApplicationDetail } from "@/types/admissions.type";

interface ApplicationDetailCardProps {
  application: ApplicationDetail;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatGender(gender: string): string {
  return gender.charAt(0).toUpperCase() + gender.slice(1);
}

function formatDocType(docType: string): string {
  return docType
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

export function ApplicationDetailCard({
  application,
}: ApplicationDetailCardProps) {
  return (
    <div className="space-y-6">
      {/* Personal Information */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Personal Information</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">Full Name</p>
              <p className="font-medium">
                {application.applicant_first_name}{" "}
                {application.applicant_other_names
                  ? application.applicant_other_names + " "
                  : ""}
                {application.applicant_last_name}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">Date of Birth</p>
              <p className="font-medium">
                {formatDate(application.date_of_birth)}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">Gender</p>
              <p className="font-medium">
                {formatGender(application.gender)}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">Nationality</p>
              <p className="font-medium">
                {application.nationality || "Not specified"}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">Target Class</p>
              <p className="font-medium">
                {application.target_class_name || "N/A"}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">Tracking Code</p>
              <p className="font-mono font-medium">
                {application.tracking_code}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Previous School & Medical */}
      {(application.previous_school || application.medical_info) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Additional Information</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              {application.previous_school && (
                <div>
                  <p className="text-muted-foreground">Previous School</p>
                  <p className="font-medium">{application.previous_school}</p>
                </div>
              )}
              {application.medical_info && (
                <div className="md:col-span-2">
                  <p className="text-muted-foreground">Medical Information</p>
                  <p className="font-medium">{application.medical_info}</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Custom Fields */}
      {Object.keys(application.custom_fields).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Additional Fields</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              {Object.entries(application.custom_fields).map(([key, value]) => (
                <div key={key}>
                  <p className="text-muted-foreground">
                    {key
                      .split("_")
                      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
                      .join(" ")}
                  </p>
                  <p className="font-medium">{String(value)}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Guardians */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Guardians ({application.guardians.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {application.guardians.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No guardian information provided
            </p>
          ) : (
            <div className="space-y-4">
              {application.guardians.map((guardian) => (
                <div
                  key={guardian.id}
                  className="flex flex-col gap-2 rounded-lg border p-4"
                >
                  <div className="flex items-center gap-2">
                    <User className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium">
                      {guardian.first_name} {guardian.last_name}
                    </span>
                    <Badge variant="outline" className="text-xs capitalize">
                      {guardian.relationship}
                    </Badge>
                    {guardian.is_primary && (
                      <Badge variant="secondary" className="text-xs">
                        Primary
                      </Badge>
                    )}
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1.5">
                      <Phone className="h-3.5 w-3.5" />
                      {guardian.phone}
                    </div>
                    {guardian.email && (
                      <div className="flex items-center gap-1.5">
                        <Mail className="h-3.5 w-3.5" />
                        {guardian.email}
                      </div>
                    )}
                    {guardian.occupation && (
                      <div>Occupation: {guardian.occupation}</div>
                    )}
                    {guardian.address && <div>Address: {guardian.address}</div>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Documents */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Documents ({application.documents.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {application.documents.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No documents uploaded
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Document</TableHead>
                  <TableHead className="hidden sm:table-cell">Type</TableHead>
                  <TableHead className="hidden sm:table-cell">Size</TableHead>
                  <TableHead className="w-[80px]">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {application.documents.map((doc) => (
                  <TableRow key={doc.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm">{doc.file_name}</span>
                      </div>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                      {formatDocType(doc.document_type)}
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                      {formatFileSize(doc.file_size)}
                    </TableCell>
                    <TableCell>
                      {doc.download_url ? (
                        <Button variant="ghost" size="sm" asChild>
                          <a
                            href={doc.download_url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            <Download className="h-4 w-4" />
                          </a>
                        </Button>
                      ) : (
                        <Button variant="ghost" size="sm" disabled>
                          <Download className="h-4 w-4" />
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Payment Information */}
      {application.payments.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Payment Information</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {application.payments.map((payment) => (
                <div
                  key={payment.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-lg border p-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">
                        {payment.currency} {payment.amount.toFixed(2)}
                      </span>
                      <Badge
                        variant="outline"
                        className={
                          payment.status === "success"
                            ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                            : payment.status === "pending"
                              ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
                              : "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                        }
                      >
                        {payment.status}
                      </Badge>
                    </div>
                    {payment.payment_method && (
                      <p className="text-xs text-muted-foreground capitalize">
                        {payment.payment_method.replace(/_/g, " ")}
                      </p>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {payment.paid_at
                      ? formatDate(payment.paid_at)
                      : formatDate(payment.created_at)}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Exam Results */}
      {application.exam_results.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Entrance Exam Results</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Score</TableHead>
                  <TableHead>Grade</TableHead>
                  <TableHead>Result</TableHead>
                  <TableHead className="hidden sm:table-cell">
                    Remarks
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {application.exam_results.map((examResult) => (
                  <TableRow key={examResult.id}>
                    <TableCell className="font-medium">
                      {examResult.score} / {examResult.max_score}
                    </TableCell>
                    <TableCell>{examResult.grade || "N/A"}</TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={
                          examResult.passed
                            ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                            : "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300"
                        }
                      >
                        {examResult.passed ? "Passed" : "Failed"}
                      </Badge>
                    </TableCell>
                    <TableCell className="hidden sm:table-cell text-sm text-muted-foreground">
                      {examResult.remarks || "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
