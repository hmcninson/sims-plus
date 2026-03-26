"use client";

import { Badge } from "@/components/ui/badge";

import type { TranscriptData, TranscriptTerm, TranscriptSubject } from "@/types/curriculum.type";

interface TranscriptViewerProps {
  data: TranscriptData;
  /** Optional school info for the header (not in backend TranscriptResponse) */
  schoolName?: string;
  schoolAddress?: string;
  schoolLogoUrl?: string;
}

export function TranscriptViewer({
  data,
  schoolName,
  schoolAddress,
  schoolLogoUrl,
}: TranscriptViewerProps) {
  return (
    <div className="transcript-viewer mx-auto max-w-[210mm] bg-white text-black print:shadow-none shadow-lg">
      <style jsx global>{`
        @media print {
          body * {
            visibility: hidden;
          }
          .transcript-viewer,
          .transcript-viewer * {
            visibility: visible;
          }
          .transcript-viewer {
            position: absolute;
            left: 0;
            top: 0;
            width: 210mm;
            margin: 0;
            padding: 15mm;
            box-shadow: none;
          }
          .print-hidden {
            display: none !important;
          }
          .term-section {
            break-inside: avoid;
          }
        }
      `}</style>

      <div className="p-8 print:p-0 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between border-b-2 border-black pb-4">
          <div className="flex items-center gap-4">
            {schoolLogoUrl && (
              <img
                src={schoolLogoUrl}
                alt={`${schoolName ?? "School"} logo`}
                className="size-16 object-contain"
              />
            )}
            <div>
              {schoolName && <h1 className="text-xl font-bold">{schoolName}</h1>}
              {schoolAddress && (
                <p className="text-sm text-gray-600">{schoolAddress}</p>
              )}
            </div>
          </div>
          <div className="text-right">
            <h2 className="text-lg font-bold uppercase tracking-wide">Official Transcript</h2>
            <p className="text-sm text-gray-600">{data.curriculum_profile}</p>
          </div>
        </div>

        {/* Student Info */}
        <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm border border-gray-300 rounded p-4">
          <div className="flex justify-between">
            <span className="font-medium text-gray-600">Student Name:</span>
            <span className="font-semibold">{data.student_name}</span>
          </div>
          <div className="flex justify-between">
            <span className="font-medium text-gray-600">Student ID:</span>
            <span className="font-mono">{data.student_id.slice(0, 8)}</span>
          </div>
        </div>

        {/* Term Sections */}
        {data.academic_records.map((term: TranscriptTerm, termIndex: number) => (
          <div key={termIndex} className="term-section border border-gray-300 rounded overflow-hidden">
            <div className="bg-gray-100 px-4 py-2 font-semibold text-sm">
              {term.academic_year}
              {term.term && <> &mdash; {term.term}</>}
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs uppercase text-gray-500">
                  <th className="px-4 py-2">Subject</th>
                  <th className="px-4 py-2">Code</th>
                  <th className="px-4 py-2 text-center">Credits</th>
                  <th className="px-4 py-2 text-center">Grade</th>
                  <th className="px-4 py-2 text-center">Points</th>
                  <th className="px-4 py-2 text-center">Type</th>
                </tr>
              </thead>
              <tbody>
                {term.subjects.map((subject: TranscriptSubject, subIndex: number) => (
                  <tr key={subIndex} className="border-b border-gray-100">
                    <td className="px-4 py-1.5 font-medium">{subject.subject_name}</td>
                    <td className="px-4 py-1.5 text-gray-600 font-mono text-xs">
                      {subject.subject_code ?? "--"}
                    </td>
                    <td className="px-4 py-1.5 text-center">
                      {subject.credits_earned}/{subject.credits_attempted}
                    </td>
                    <td className="px-4 py-1.5 text-center font-semibold">
                      {subject.grade ?? "--"}
                    </td>
                    <td className="px-4 py-1.5 text-center font-mono">
                      {subject.grade_points != null ? subject.grade_points.toFixed(1) : "--"}
                    </td>
                    <td className="px-4 py-1.5 text-center">
                      {subject.is_ap && (
                        <span className="inline-block rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-800">
                          AP
                        </span>
                      )}
                      {subject.is_honors && (
                        <span className="inline-block rounded bg-purple-100 px-1.5 py-0.5 text-[10px] font-medium text-purple-800">
                          Honors
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-gray-50 font-medium text-sm">
                  <td colSpan={2} className="px-4 py-2 text-right">Term Summary:</td>
                  <td className="px-4 py-2 text-center">{term.term_credits_earned}</td>
                  <td colSpan={2} className="px-4 py-2 text-center">
                    GPA: {term.term_gpa != null ? term.term_gpa.toFixed(2) : "--"}
                  </td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        ))}

        {/* Cumulative Summary */}
        <div className="border-2 border-black rounded p-4 space-y-2">
          <h3 className="text-center font-bold uppercase tracking-wide text-sm mb-3">
            Cumulative Summary
          </h3>
          <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
            <div className="flex justify-between">
              <span className="font-medium">Cumulative GPA (Unweighted):</span>
              <span className="font-bold text-lg">
                {data.cumulative_gpa != null ? data.cumulative_gpa.toFixed(2) : "--"}
              </span>
            </div>
            {data.weighted_gpa != null && (
              <div className="flex justify-between">
                <span className="font-medium">Cumulative GPA (Weighted):</span>
                <span className="font-bold text-lg">
                  {data.weighted_gpa.toFixed(2)}
                </span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="font-medium">Total Credits Earned:</span>
              <span className="font-bold">
                {data.total_credits_earned}
                {data.graduation_credits_required != null && (
                  <span className="font-normal text-gray-600">
                    {" "}
                    / {data.graduation_credits_required} required
                  </span>
                )}
              </span>
            </div>
            {data.credits_remaining != null && (
              <div className="flex justify-between">
                <span className="font-medium">Credits Remaining:</span>
                <span className="font-bold">{data.credits_remaining}</span>
              </div>
            )}
          </div>
          {data.honors.length > 0 && (
            <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-200 mt-2">
              <span className="text-sm font-medium">Honors:</span>
              {data.honors.map((honor, i) => (
                <Badge
                  key={i}
                  className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200"
                >
                  {honor}
                </Badge>
              ))}
            </div>
          )}
        </div>

        {/* Signature */}
        <div className="mt-12 flex justify-between items-end pt-8">
          <div className="text-center">
            <div className="w-48 border-b border-black mb-1" />
            <p className="text-sm">Registrar</p>
          </div>
          <div className="text-center">
            <div className="w-48 border-b border-black mb-1" />
            <p className="text-sm">Date</p>
          </div>
        </div>

        {/* Notice */}
        <p className="text-center text-xs text-gray-500 mt-4 italic">
          This is an official transcript. Generated on{" "}
          {formatTranscriptDate(data.generated_at)}. Any erasure or alteration renders
          this document invalid.
        </p>
      </div>
    </div>
  );
}

function formatTranscriptDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}
