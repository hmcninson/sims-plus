"use client";

import { useEffect, useState, useTransition } from "react";
import { Loader2, Users, Eye } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { getClasses } from "@/actions/academic.action";
import { resolveRecipients } from "@/actions/messaging.action";
import type { Class } from "@/types";
import type { RecipientInfo, RecipientType } from "@/types/messaging.type";

interface RecipientSelectorProps {
  onRecipientsResolved: (
    recipients: RecipientInfo[],
    audience: RecipientType,
    classId?: string
  ) => void;
  /** Filter to show only recipients with phone or email */
  mode: "phone" | "email";
}

const AUDIENCE_OPTIONS: { value: RecipientType; label: string; description: string }[] = [
  {
    value: "all_parents",
    label: "All Parents",
    description: "Send to all parent/guardian contacts",
  },
  {
    value: "all_staff",
    label: "All Staff",
    description: "Send to all staff members",
  },
  {
    value: "class_parents",
    label: "Parents of a Class",
    description: "Send to parents of students in a specific class",
  },
];

export function RecipientSelector({ onRecipientsResolved, mode }: RecipientSelectorProps) {
  const [audience, setAudience] = useState<RecipientType>("all_parents");
  const [classId, setClassId] = useState<string>("");
  const [classes, setClasses] = useState<Class[]>([]);
  const [classesLoading, setClassesLoading] = useState(false);
  const [recipientCount, setRecipientCount] = useState<number | null>(null);
  const [isPending, startTransition] = useTransition();

  // Fetch classes when the component mounts (needed for class_parents option)
  useEffect(() => {
    setClassesLoading(true);
    getClasses(false)
      .then((result) => {
        if (result.success) {
          setClasses(result.data);
        }
      })
      .finally(() => setClassesLoading(false));
  }, []);

  // Reset class selection and recipient count when audience changes
  useEffect(() => {
    if (audience !== "class_parents") {
      setClassId("");
    }
    setRecipientCount(null);
  }, [audience]);

  // Reset recipient count when class changes
  useEffect(() => {
    setRecipientCount(null);
  }, [classId]);

  function handlePreview() {
    if (audience === "class_parents" && !classId) {
      toast.error("Please select a class first");
      return;
    }

    startTransition(async () => {
      const result = await resolveRecipients(
        audience,
        audience === "class_parents" ? classId : undefined
      );

      if (!result.success) {
        toast.error(result.error);
        return;
      }

      // Filter recipients based on mode (phone or email availability)
      const filtered = result.data.recipients.filter((r) =>
        mode === "phone" ? r.phone : r.email
      );

      setRecipientCount(filtered.length);
      onRecipientsResolved(filtered, audience, classId || undefined);

      if (filtered.length === 0) {
        toast.warning(
          mode === "phone"
            ? "No recipients have phone numbers on file"
            : "No recipients have email addresses on file"
        );
      }
    });
  }

  return (
    <div className="space-y-4">
      <div>
        <Label className="text-sm font-medium">Select Audience</Label>
        <RadioGroup
          value={audience}
          onValueChange={(val) => setAudience(val as RecipientType)}
          className="mt-2 space-y-2"
        >
          {AUDIENCE_OPTIONS.map((option) => (
            <label
              key={option.value}
              className="flex items-start gap-3 rounded-lg border p-3 cursor-pointer hover:bg-accent/50 transition-colors has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-primary/5"
            >
              <RadioGroupItem value={option.value} className="mt-0.5" />
              <div className="space-y-0.5">
                <div className="text-sm font-medium">{option.label}</div>
                <div className="text-xs text-muted-foreground">
                  {option.description}
                </div>
              </div>
            </label>
          ))}
        </RadioGroup>
      </div>

      {/* Class selector, visible when "class_parents" is selected */}
      {audience === "class_parents" && (
        <div>
          <Label htmlFor="class-select" className="text-sm font-medium">
            Select Class
          </Label>
          <Select value={classId} onValueChange={setClassId}>
            <SelectTrigger id="class-select" className="mt-1.5 w-full">
              <SelectValue
                placeholder={
                  classesLoading ? "Loading classes..." : "Choose a class"
                }
              />
            </SelectTrigger>
            <SelectContent>
              {classes.map((cls) => (
                <SelectItem key={cls.id} value={cls.id}>
                  {cls.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Preview button and recipient count */}
      <div className="flex items-center gap-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handlePreview}
          disabled={isPending || (audience === "class_parents" && !classId)}
        >
          {isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Eye className="size-4" />
          )}
          Preview Recipients
        </Button>

        {recipientCount !== null && (
          <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
            <Users className="size-4" />
            {recipientCount} recipient{recipientCount !== 1 ? "s" : ""}
          </span>
        )}
      </div>
    </div>
  );
}
