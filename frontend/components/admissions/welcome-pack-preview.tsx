"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  Mail,
  Send,
} from "lucide-react";
import {
  generateEnrollmentConfirmation,
  sendWelcomePack,
} from "@/actions/admissions.action";

interface WelcomePackPreviewProps {
  applicationId: string;
  applicantName: string;
  welcomePackSent: boolean;
  confirmationUrl: string | null;
}

export function WelcomePackPreview({
  applicationId,
  applicantName,
  welcomePackSent: initialSent,
  confirmationUrl: initialUrl,
}: WelcomePackPreviewProps) {
  const [isPending, startTransition] = useTransition();
  const [generating, setGenerating] = useState(false);
  const [sent, setSent] = useState(initialSent);
  const [confirmUrl, setConfirmUrl] = useState(initialUrl);

  function handleGenerateConfirmation() {
    setGenerating(true);
    startTransition(async () => {
      const result = await generateEnrollmentConfirmation(applicationId);
      if (result.success) {
        setConfirmUrl(result.data.confirmation_url);
        toast.success("Enrollment confirmation generated");
      } else {
        toast.error(result.error);
      }
      setGenerating(false);
    });
  }

  function handleSendWelcomePack() {
    startTransition(async () => {
      const result = await sendWelcomePack(applicationId);
      if (result.success) {
        setSent(result.data.welcome_pack_sent);
        const channels = result.data.channels.join(", ");
        toast.success(`Welcome pack sent via ${channels}`);
      } else {
        toast.error(result.error);
      }
    });
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Mail className="h-4 w-4" />
            Confirmation & Welcome Pack
          </CardTitle>
          {sent && (
            <Badge className="bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
              <CheckCircle2 className="mr-1 h-3 w-3" />
              Sent
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Confirmation Letter */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-lg border p-3">
            <div className="flex items-center gap-3">
              <FileText className="h-5 w-5 text-muted-foreground shrink-0" />
              <div>
                <p className="text-sm font-medium">Enrollment Confirmation Letter</p>
                <p className="text-xs text-muted-foreground">
                  {confirmUrl
                    ? "PDF generated and ready for download"
                    : "Generate a PDF confirmation letter for this applicant"}
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              {confirmUrl ? (
                <a href={confirmUrl} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" size="sm">
                    <Download className="mr-2 h-4 w-4" />
                    Download
                  </Button>
                </a>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleGenerateConfirmation}
                  disabled={generating || isPending}
                >
                  {generating ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <FileText className="mr-2 h-4 w-4" />
                  )}
                  Generate
                </Button>
              )}
            </div>
          </div>

          {/* Welcome Pack */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between rounded-lg border p-3">
            <div className="flex items-center gap-3">
              <Send className="h-5 w-5 text-muted-foreground shrink-0" />
              <div>
                <p className="text-sm font-medium">Welcome Pack</p>
                <p className="text-xs text-muted-foreground">
                  {sent
                    ? `Welcome information has been sent to ${applicantName}'s guardians`
                    : "Send orientation details, supply list, and important dates via email and SMS"}
                </p>
              </div>
            </div>
            {sent ? (
              <Badge variant="secondary" className="shrink-0">
                <CheckCircle2 className="mr-1 h-3 w-3" />
                Delivered
              </Badge>
            ) : (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={isPending}
                    className="shrink-0"
                  >
                    {isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="mr-2 h-4 w-4" />
                    )}
                    Send Welcome Pack
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Send Welcome Pack?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This will send orientation information, supply lists, and
                      important dates to {applicantName}&apos;s guardians via email
                      and SMS. This action cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction onClick={handleSendWelcomePack}>
                      Send
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
