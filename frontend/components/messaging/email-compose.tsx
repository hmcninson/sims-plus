"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loader2, Send } from "lucide-react";
import { RecipientSelector } from "./recipient-selector";
import { sendEmail, sendBulkEmail } from "@/actions/messaging.action";
import type { RecipientInfo, RecipientType } from "@/types/messaging.type";

interface EmailComposeProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSent: () => void;
}

/**
 * Email compose dialog supporting two sending modes:
 * 1. Audience mode -- uses the shared RecipientSelector to resolve an audience
 *    segment (all parents, all staff, class parents) and sends via the /bulk endpoint.
 * 2. Specific emails -- manual comma-separated email input, sent via /send endpoint.
 */
export function EmailCompose({ open, onOpenChange, onSent }: EmailComposeProps) {
  const [isPending, startTransition] = useTransition();
  const [tab, setTab] = useState<"audience" | "specific">("audience");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [specificEmails, setSpecificEmails] = useState("");

  // Audience mode state
  const [resolvedRecipients, setResolvedRecipients] = useState<RecipientInfo[]>([]);
  const [audience, setAudience] = useState<RecipientType>("all_parents");
  const [classId, setClassId] = useState<string | undefined>();

  function resetForm() {
    setSubject("");
    setBody("");
    setSpecificEmails("");
    setResolvedRecipients([]);
    setAudience("all_parents");
    setClassId(undefined);
    setTab("audience");
  }

  /**
   * Parse and validate the comma-separated email input.
   * Returns a cleaned array of email addresses or null if validation fails.
   */
  function parseSpecificEmails(): string[] | null {
    const emails = specificEmails
      .split(",")
      .map((e) => e.trim().toLowerCase())
      .filter(Boolean);

    if (emails.length === 0) {
      toast.error("Enter at least one email address");
      return null;
    }

    // Basic format check -- full validation happens server-side
    const invalid = emails.filter((e) => !e.includes("@") || !e.split("@")[1]?.includes("."));
    if (invalid.length > 0) {
      toast.error(`Invalid email format: ${invalid[0]}`);
      return null;
    }

    return emails;
  }

  function handleSend() {
    if (!subject.trim()) {
      toast.error("Subject is required");
      return;
    }
    if (!body.trim()) {
      toast.error("Email body is required");
      return;
    }

    startTransition(async () => {
      if (tab === "specific") {
        const emails = parseSpecificEmails();
        if (!emails) return;

        const result = await sendEmail({
          recipient_emails: emails,
          subject: subject.trim(),
          body: body.trim(),
        });

        if (result.success) {
          toast.success(`Email sent to ${emails.length} recipient${emails.length > 1 ? "s" : ""}`);
          resetForm();
          onSent();
          onOpenChange(false);
        } else {
          toast.error(result.error);
        }
      } else {
        // Audience mode: recipients must have been previewed first
        if (resolvedRecipients.length === 0) {
          toast.error("Preview recipients first to confirm the audience");
          return;
        }

        const result = await sendBulkEmail({
          audience,
          class_id: classId,
          subject: subject.trim(),
          body: body.trim(),
        });

        if (result.success) {
          toast.success("Bulk email sent successfully");
          resetForm();
          onSent();
          onOpenChange(false);
        } else {
          toast.error(result.error);
        }
      }
    });
  }

  function handleRecipientsResolved(
    recipients: RecipientInfo[],
    resolvedAudience: RecipientType,
    resolvedClassId?: string
  ) {
    setResolvedRecipients(recipients);
    setAudience(resolvedAudience);
    setClassId(resolvedClassId);
  }

  // Whether the send button should be enabled
  const canSend =
    subject.trim().length > 0 &&
    body.trim().length > 0 &&
    (tab === "specific"
      ? specificEmails.trim().length > 0
      : resolvedRecipients.length > 0);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-sm:h-full max-sm:max-h-full max-sm:rounded-none">
        <DialogHeader>
          <DialogTitle>Compose Email</DialogTitle>
          <DialogDescription>
            Send an email to specific addresses or a group of recipients.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 max-h-[60vh] overflow-y-auto px-1">
          {/* Subject */}
          <div className="space-y-1.5">
            <Label htmlFor="email-subject">Subject</Label>
            <Input
              id="email-subject"
              placeholder="Enter email subject"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              maxLength={500}
              required
            />
            <p className="text-xs text-muted-foreground text-right">
              {subject.length}/500
            </p>
          </div>

          {/* Body */}
          <div className="space-y-1.5">
            <Label htmlFor="email-body">Message</Label>
            <Textarea
              id="email-body"
              placeholder="Write your email message here..."
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={6}
              className="resize-y"
              required
            />
          </div>

          {/* Recipient selection */}
          <Tabs value={tab} onValueChange={(v) => setTab(v as "audience" | "specific")}>
            <TabsList className="w-full">
              <TabsTrigger value="audience" className="flex-1">
                Audience
              </TabsTrigger>
              <TabsTrigger value="specific" className="flex-1">
                Specific Emails
              </TabsTrigger>
            </TabsList>

            <TabsContent value="audience" className="mt-4">
              <RecipientSelector
                onRecipientsResolved={handleRecipientsResolved}
                mode="email"
              />
            </TabsContent>

            <TabsContent value="specific" className="mt-4 space-y-2">
              <Label htmlFor="specific-emails">Email Addresses</Label>
              <Textarea
                id="specific-emails"
                placeholder="Enter email addresses separated by commas, e.g. parent@example.com, teacher@school.edu"
                value={specificEmails}
                onChange={(e) => setSpecificEmails(e.target.value)}
                rows={3}
                className="resize-y"
              />
              <p className="text-xs text-muted-foreground">
                Separate multiple addresses with commas.
                {specificEmails.trim() && (
                  <>
                    {" "}
                    {specificEmails.split(",").map((e) => e.trim()).filter(Boolean).length} address
                    {specificEmails.split(",").map((e) => e.trim()).filter(Boolean).length !== 1
                      ? "es"
                      : ""}{" "}
                    entered.
                  </>
                )}
              </p>
            </TabsContent>
          </Tabs>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSend}
            disabled={isPending || !canSend}
          >
            {isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Send className="mr-2 h-4 w-4" />
            )}
            Send Email
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
