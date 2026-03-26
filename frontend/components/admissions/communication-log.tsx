"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  Phone,
  Mail,
  MessageSquare,
  User,
  ArrowDownLeft,
  ArrowUpRight,
  Plus,
  Loader2,
  MessageCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { addCommunication } from "@/actions/inquiries.action";
import type { Communication, CommunicationChannel, CommunicationDirection } from "@/types/inquiry.type";

const CHANNELS: { value: CommunicationChannel; label: string; icon: typeof Phone }[] = [
  { value: "phone", label: "Phone Call", icon: Phone },
  { value: "email", label: "Email", icon: Mail },
  { value: "sms", label: "SMS", icon: MessageSquare },
  { value: "in_person", label: "In Person", icon: User },
];

const DIRECTIONS: { value: CommunicationDirection; label: string }[] = [
  { value: "outbound", label: "Outbound (to guardian)" },
  { value: "inbound", label: "Inbound (from guardian)" },
];

const communicationSchema = z.object({
  channel: z.enum(["sms", "email", "phone", "in_person"], { message: "Select a channel" }),
  direction: z.enum(["inbound", "outbound"], { message: "Select a direction" }),
  content: z.string().min(1, "Content is required").max(2000),
});

type CommunicationFormValues = z.infer<typeof communicationSchema>;

interface CommunicationLogProps {
  inquiryId: string;
  communications: Communication[];
  onRefresh: () => void;
}

function getChannelIcon(channel: string) {
  switch (channel) {
    case "phone":
      return Phone;
    case "email":
      return Mail;
    case "sms":
      return MessageSquare;
    case "in_person":
      return User;
    default:
      return MessageCircle;
  }
}

function formatChannelLabel(channel: string): string {
  switch (channel) {
    case "in_person":
      return "In Person";
    default:
      return channel.charAt(0).toUpperCase() + channel.slice(1);
  }
}

export function CommunicationLog({
  inquiryId,
  communications,
  onRefresh,
}: CommunicationLogProps) {
  const [showForm, setShowForm] = useState(false);

  const form = useForm<CommunicationFormValues>({
    resolver: zodResolver(communicationSchema),
    defaultValues: {
      channel: "phone",
      direction: "outbound",
      content: "",
    },
  });

  async function onSubmit(values: CommunicationFormValues) {
    const result = await addCommunication(inquiryId, values);
    if (result.success) {
      toast.success("Communication logged");
      form.reset({ channel: "phone", direction: "outbound", content: "" });
      setShowForm(false);
      onRefresh();
    } else {
      toast.error(result.error);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">
          {communications.length} communication{communications.length !== 1 ? "s" : ""}
        </h3>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowForm(!showForm)}
        >
          <Plus className="mr-2 h-4 w-4" />
          Log Communication
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">New Communication Entry</CardTitle>
          </CardHeader>
          <CardContent>
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <FormField
                    control={form.control}
                    name="channel"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Channel</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {CHANNELS.map((c) => (
                              <SelectItem key={c.value} value={c.value}>
                                {c.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="direction"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Direction</FormLabel>
                        <Select onValueChange={field.onChange} value={field.value}>
                          <FormControl>
                            <SelectTrigger className="w-full">
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {DIRECTIONS.map((d) => (
                              <SelectItem key={d.value} value={d.value}>
                                {d.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                <FormField
                  control={form.control}
                  name="content"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Summary</FormLabel>
                      <FormControl>
                        <Textarea
                          placeholder="Describe the communication..."
                          rows={3}
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowForm(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" disabled={form.formState.isSubmitting}>
                    {form.formState.isSubmitting ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : null}
                    Save
                  </Button>
                </div>
              </form>
            </Form>
          </CardContent>
        </Card>
      )}

      {/* Timeline */}
      {communications.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <MessageCircle className="h-10 w-10 text-muted-foreground mb-2" />
          <p className="text-sm text-muted-foreground">
            No communications logged yet.
          </p>
          <p className="text-xs text-muted-foreground">
            Click &quot;Log Communication&quot; to record a conversation.
          </p>
        </div>
      ) : (
        <div className="relative space-y-0">
          {/* Vertical line */}
          <div className="absolute left-5 top-0 bottom-0 w-px bg-border" />

          {communications.map((comm) => {
            const Icon = getChannelIcon(comm.channel);
            const isInbound = comm.direction === "inbound";
            const DirectionIcon = isInbound ? ArrowDownLeft : ArrowUpRight;

            return (
              <div key={comm.id} className="relative flex gap-4 pb-4">
                <div className="relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full border bg-background">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="flex-1 pt-0.5">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-medium">
                      {formatChannelLabel(comm.channel)}
                    </span>
                    <DirectionIcon
                      className={`h-3 w-3 ${
                        isInbound
                          ? "text-blue-500"
                          : "text-green-500"
                      }`}
                    />
                    <span className="text-xs text-muted-foreground">
                      {isInbound ? "Inbound" : "Outbound"}
                    </span>
                    <span className="text-xs text-muted-foreground ml-auto">
                      {new Date(comm.sent_at).toLocaleDateString("en-GB", {
                        day: "2-digit",
                        month: "short",
                        year: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-foreground">{comm.content}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
