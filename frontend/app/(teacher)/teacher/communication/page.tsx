"use client";

/**
 * SIMS Plus - Teacher Communication Broadcast Page
 *
 * Allows teachers to send announcements to all parents in a class.
 * Features:
 * - Class selector from teacher's assigned classes
 * - Title and content fields
 * - Priority selector (normal, important, urgent)
 * - Submit with loading state and success feedback
 * - Mobile responsive layout
 */

import { useEffect, useState, useTransition } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  Megaphone,
  Send,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getTeacherClasses,
  sendClassBroadcast,
} from "@/actions/teacher.action";
import type {
  TeacherClassSummary,
  TeacherClassBroadcastResponse,
} from "@/types/teacher.type";
import { toast } from "sonner";

const PRIORITY_OPTIONS = [
  { value: "normal", label: "Normal", color: "bg-gray-100 text-gray-800" },
  { value: "important", label: "Important", color: "bg-amber-100 text-amber-800" },
  { value: "urgent", label: "Urgent", color: "bg-red-100 text-red-800" },
] as const;

type Priority = "normal" | "important" | "urgent";

interface SentBroadcast {
  id: string;
  title: string;
  className: string;
  priority: Priority;
  sentAt: Date;
}

export default function TeacherCommunicationPage() {
  // ---- Class data ----
  const [classes, setClasses] = useState<TeacherClassSummary[]>([]);
  const [loadingClasses, setLoadingClasses] = useState(true);

  // ---- Form state ----
  const [selectedClassId, setSelectedClassId] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [priority, setPriority] = useState<Priority>("normal");
  const [isPending, startTransition] = useTransition();

  // ---- Recent broadcasts (local session memory) ----
  const [recentBroadcasts, setRecentBroadcasts] = useState<SentBroadcast[]>([]);

  // Load classes on mount
  useEffect(() => {
    async function loadClasses() {
      const result = await getTeacherClasses();
      if (result.success) {
        setClasses(result.data);
      } else {
        toast.error("Failed to load classes");
      }
      setLoadingClasses(false);
    }
    loadClasses();
  }, []);

  const handleSend = () => {
    if (!selectedClassId) {
      toast.error("Please select a class");
      return;
    }
    if (!title.trim()) {
      toast.error("Please enter a title");
      return;
    }
    if (!content.trim()) {
      toast.error("Please enter a message");
      return;
    }

    const selectedClass = classes.find((c) => c.class_id === selectedClassId);

    startTransition(async () => {
      const result = await sendClassBroadcast({
        class_id: selectedClassId,
        title: title.trim(),
        content: content.trim(),
        priority,
      });

      if (result.success) {
        toast.success("Broadcast sent successfully");
        // Track in session history
        setRecentBroadcasts((prev) => [
          {
            id: result.data.announcement_id,
            title: title.trim(),
            className: selectedClass
              ? `${selectedClass.class_name}${selectedClass.section_name ? ` - ${selectedClass.section_name}` : ""}`
              : "Unknown",
            priority,
            sentAt: new Date(),
          },
          ...prev,
        ]);
        // Reset form
        setTitle("");
        setContent("");
        setPriority("normal");
        setSelectedClassId("");
      } else {
        toast.error(result.error);
      }
    });
  };

  // Character count for content
  const contentLength = content.length;
  const MAX_CONTENT = 2000;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Communication</h1>
        <p className="text-muted-foreground">
          Send announcements to parents in your classes
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Broadcast form */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Megaphone className="h-4 w-4" />
                New Broadcast
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Class *</Label>
                  {loadingClasses ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground p-2">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Loading classes...
                    </div>
                  ) : (
                    <Select value={selectedClassId} onValueChange={setSelectedClassId}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select a class" />
                      </SelectTrigger>
                      <SelectContent>
                        {classes.map((cls) => (
                          <SelectItem
                            key={`${cls.class_id}-${cls.section_id || "main"}`}
                            value={cls.class_id}
                          >
                            {cls.class_name}
                            {cls.section_name ? ` - ${cls.section_name}` : ""}
                            <span className="text-muted-foreground ml-1">
                              ({cls.student_count} students)
                            </span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </div>

                <div className="space-y-2">
                  <Label>Priority</Label>
                  <Select value={priority} onValueChange={(v) => setPriority(v as Priority)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PRIORITY_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Title *</Label>
                <Input
                  placeholder="Announcement title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={200}
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Message *</Label>
                  <span className={`text-xs ${contentLength > MAX_CONTENT ? "text-destructive" : "text-muted-foreground"}`}>
                    {contentLength} / {MAX_CONTENT}
                  </span>
                </div>
                <Textarea
                  placeholder="Write your announcement message here...

This message will be sent to all parents in the selected class."
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  rows={8}
                  maxLength={MAX_CONTENT}
                />
              </div>

              {priority === "urgent" && (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    Urgent messages may trigger push notifications and SMS to parents.
                    Use this priority only for time-sensitive announcements.
                  </AlertDescription>
                </Alert>
              )}

              <div className="flex justify-end pt-2">
                <Button
                  onClick={handleSend}
                  disabled={isPending || !selectedClassId || !title.trim() || !content.trim()}
                  size="lg"
                >
                  {isPending ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Sending...
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4 mr-2" />
                      Send Broadcast
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent broadcasts sidebar */}
        <div>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recent Broadcasts</CardTitle>
            </CardHeader>
            <CardContent>
              {recentBroadcasts.length === 0 ? (
                <div className="flex flex-col items-center py-6 text-center">
                  <Megaphone className="h-8 w-8 text-muted-foreground/50 mb-2" />
                  <p className="text-sm text-muted-foreground">
                    No broadcasts sent this session
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Your sent broadcasts will appear here
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {recentBroadcasts.map((broadcast) => {
                    const priorityCfg = PRIORITY_OPTIONS.find(
                      (o) => o.value === broadcast.priority
                    );
                    return (
                      <div
                        key={broadcast.id}
                        className="flex items-start gap-2 p-2 rounded-md bg-muted/30"
                      >
                        <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0 mt-0.5" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">
                            {broadcast.title}
                          </p>
                          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                            <span className="text-xs text-muted-foreground">
                              {broadcast.className}
                            </span>
                            {broadcast.priority !== "normal" && (
                              <Badge className={`text-[10px] ${priorityCfg?.color || ""}`}>
                                {priorityCfg?.label || broadcast.priority}
                              </Badge>
                            )}
                          </div>
                          <p className="text-[10px] text-muted-foreground mt-0.5">
                            {broadcast.sentAt.toLocaleTimeString("en-GB", {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
