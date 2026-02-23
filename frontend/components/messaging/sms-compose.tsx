"use client";

import { useState, useTransition } from "react";
import { Loader2, Send, MessageSquare, Phone } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import { RecipientSelector } from "@/components/messaging/recipient-selector";
import { sendSMS, sendBulkSMS } from "@/actions/messaging.action";
import type { RecipientInfo, RecipientType } from "@/types/messaging.type";

/**
 * Max characters per SMS segment (GSM-7 encoding).
 * Messages longer than this are split into multiple segments.
 */
const SMS_SEGMENT_LENGTH = 160;

interface SMSComposeProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSent: () => void;
}

export function SMSCompose({ open, onOpenChange, onSent }: SMSComposeProps) {
  const [tab, setTab] = useState<string>("audience");
  const [message, setMessage] = useState("");

  // Audience tab state
  const [resolvedRecipients, setResolvedRecipients] = useState<RecipientInfo[]>([]);
  const [audience, setAudience] = useState<RecipientType>("all_parents");
  const [classId, setClassId] = useState<string | undefined>();

  // Specific numbers tab state
  const [phoneInput, setPhoneInput] = useState("");
  const [phones, setPhones] = useState<string[]>([]);

  const [isSending, startSending] = useTransition();

  const charCount = message.length;
  const segmentCount = charCount === 0 ? 0 : Math.ceil(charCount / SMS_SEGMENT_LENGTH);

  function handleRecipientsResolved(
    recipients: RecipientInfo[],
    aud: RecipientType,
    cId?: string
  ) {
    setResolvedRecipients(recipients);
    setAudience(aud);
    setClassId(cId);
  }

  function handleAddPhone() {
    const trimmed = phoneInput.trim();
    if (!trimmed) return;

    // Basic phone format validation
    if (trimmed.length < 9) {
      toast.error("Please enter a valid phone number");
      return;
    }

    if (phones.includes(trimmed)) {
      toast.error("This number has already been added");
      return;
    }

    setPhones((prev) => [...prev, trimmed]);
    setPhoneInput("");
  }

  function handleRemovePhone(phone: string) {
    setPhones((prev) => prev.filter((p) => p !== phone));
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      handleAddPhone();
    }
  }

  function handleSend() {
    if (!message.trim()) {
      toast.error("Please enter a message");
      return;
    }

    if (tab === "audience") {
      if (resolvedRecipients.length === 0) {
        toast.error("Please preview recipients before sending");
        return;
      }

      startSending(async () => {
        const result = await sendBulkSMS({
          audience,
          class_id: classId,
          message: message.trim(),
        });

        if (!result.success) {
          toast.error(result.error);
          return;
        }

        const logs = result.data;
        const failedCount = logs.filter((l) => l.status === "failed").length;
        const sentCount = logs.length - failedCount;
        if (failedCount > 0) {
          toast.warning(
            `Sent ${sentCount} SMS. ${failedCount} failed.`
          );
        } else {
          toast.success(`Successfully queued ${sentCount} SMS`);
        }

        handleClose();
        onSent();
      });
    } else {
      // Specific numbers tab
      if (phones.length === 0) {
        toast.error("Please add at least one phone number");
        return;
      }

      startSending(async () => {
        const result = await sendSMS({
          recipient_phones: phones,
          message: message.trim(),
        });

        if (!result.success) {
          toast.error(result.error);
          return;
        }

        toast.success(`SMS sent to ${result.data.length} recipient(s)`);
        handleClose();
        onSent();
      });
    }
  }

  function handleClose() {
    setMessage("");
    setResolvedRecipients([]);
    setPhoneInput("");
    setPhones([]);
    setTab("audience");
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MessageSquare className="size-5" />
            Compose SMS
          </DialogTitle>
          <DialogDescription>
            Send an SMS message to parents, staff, or specific phone numbers.
          </DialogDescription>
        </DialogHeader>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="w-full">
            <TabsTrigger value="audience" className="flex-1">
              Audience
            </TabsTrigger>
            <TabsTrigger value="specific" className="flex-1">
              Specific Numbers
            </TabsTrigger>
          </TabsList>

          <TabsContent value="audience" className="mt-4">
            <RecipientSelector
              mode="phone"
              onRecipientsResolved={handleRecipientsResolved}
            />
          </TabsContent>

          <TabsContent value="specific" className="mt-4 space-y-3">
            <div>
              <Label htmlFor="phone-input" className="text-sm font-medium">
                Phone Numbers
              </Label>
              <div className="mt-1.5 flex gap-2">
                <Input
                  id="phone-input"
                  type="tel"
                  placeholder="e.g. +233 24 123 4567"
                  value={phoneInput}
                  onChange={(e) => setPhoneInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAddPhone}
                  className="shrink-0"
                >
                  Add
                </Button>
              </div>
            </div>

            {phones.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {phones.map((phone) => (
                  <Badge key={phone} variant="secondary" className="gap-1">
                    <Phone className="size-3" />
                    {phone}
                    <button
                      type="button"
                      onClick={() => handleRemovePhone(phone)}
                      className="ml-0.5 hover:text-destructive"
                      aria-label={`Remove ${phone}`}
                    >
                      x
                    </button>
                  </Badge>
                ))}
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              Press Enter or click Add to add each number. Include country code
              (e.g. +233).
            </p>
          </TabsContent>
        </Tabs>

        {/* Message input -- shared between both tabs */}
        <div className="space-y-1.5">
          <Label htmlFor="sms-message" className="text-sm font-medium">
            Message
          </Label>
          <Textarea
            id="sms-message"
            placeholder="Type your message here..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={4}
            className="resize-none"
          />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {charCount} character{charCount !== 1 ? "s" : ""}
            </span>
            <span>
              {segmentCount === 0
                ? "0 SMS"
                : segmentCount === 1
                  ? "1 SMS"
                  : `${segmentCount} SMS (${segmentCount} segments)`}
            </span>
          </div>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={handleClose}
            disabled={isSending}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSend}
            disabled={isSending || !message.trim()}
          >
            {isSending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Send className="size-4" />
            )}
            Send SMS
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
