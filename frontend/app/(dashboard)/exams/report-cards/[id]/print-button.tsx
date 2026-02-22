"use client";

import { useState } from "react";
import { Printer, Loader2, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "sonner";
import { getTermReportPdfUrl } from "@/actions/exams.action";

interface PrintButtonProps {
  reportId: string;
}

export function PrintButton({ reportId }: PrintButtonProps) {
  const [isLoading, setIsLoading] = useState(false);

  const handleDownloadPdf = async () => {
    setIsLoading(true);
    try {
      const result = await getTermReportPdfUrl(reportId);
      if (!result.success || !result.data) {
        toast.error(result.error || "Failed to get PDF");
        return;
      }

      const { url, token, subdomain } = result.data;

      // Fetch the PDF with authentication
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain,
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Failed to download PDF");
      }

      // Get the filename from Content-Disposition header or use default
      const contentDisposition = response.headers.get("Content-Disposition");
      let filename = "Report_Card.pdf";
      if (contentDisposition) {
        const matches = contentDisposition.match(/filename="(.+)"/);
        if (matches && matches[1]) {
          filename = matches[1];
        }
      }

      // Create blob and download
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);

      toast.success("Report card downloaded successfully");
    } catch (error) {
      console.error("PDF download error:", error);
      toast.error(
        error instanceof Error ? error.message : "Failed to download PDF"
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handlePrintPdf = async () => {
    setIsLoading(true);
    try {
      const result = await getTermReportPdfUrl(reportId);
      if (!result.success || !result.data) {
        toast.error(result.error || "Failed to get PDF");
        return;
      }

      const { url, token, subdomain } = result.data;

      // Fetch the PDF with authentication
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Subdomain": subdomain,
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Failed to load PDF");
      }

      // Create blob and open in new window for printing
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);

      // Open PDF in new window and trigger print
      const printWindow = window.open(blobUrl, "_blank");
      if (printWindow) {
        printWindow.onload = () => {
          printWindow.print();
        };
      }
    } catch (error) {
      console.error("PDF print error:", error);
      toast.error(
        error instanceof Error ? error.message : "Failed to print PDF"
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button disabled={isLoading}>
          {isLoading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Printer className="mr-2 h-4 w-4" />
          )}
          Print
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={handlePrintPdf} disabled={isLoading}>
          <Printer className="mr-2 h-4 w-4" />
          Print Report Card
        </DropdownMenuItem>
        <DropdownMenuItem onClick={handleDownloadPdf} disabled={isLoading}>
          <Download className="mr-2 h-4 w-4" />
          Download PDF
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
