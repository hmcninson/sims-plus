"use client";

import { useState } from "react";
import { Megaphone, Pin, ExternalLink } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { formatGhanaDate, formatRelativeTime } from "@/lib/format";
import type { Announcement } from "@/types/parent.type";

interface AnnouncementsViewProps {
  announcements: Announcement[];
}

const priorityStyles: Record<string, string> = {
  urgent: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  important: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  normal: "",
};

export function AnnouncementsView({ announcements }: AnnouncementsViewProps) {
  const [selectedAnn, setSelectedAnn] = useState<Announcement | null>(null);

  // Sort: pinned first, then by date descending
  const sorted = [...announcements].sort((a, b) => {
    if (a.is_pinned && !b.is_pinned) return -1;
    if (!a.is_pinned && b.is_pinned) return 1;
    return (
      new Date(b.published_at || b.created_at).getTime() -
      new Date(a.published_at || a.created_at).getTime()
    );
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Announcements</h1>
        <p className="text-sm text-muted-foreground">
          School announcements and important notices.
        </p>
      </div>

      {sorted.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Megaphone className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No announcements</h3>
            <p className="text-sm text-muted-foreground mt-1">
              School announcements will appear here when published.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {sorted.map((ann) => (
            <Card
              key={ann.id}
              className={cn(
                "cursor-pointer hover:shadow-md transition-shadow",
                ann.is_pinned && "border-primary/30"
              )}
              onClick={() => setSelectedAnn(ann)}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      {ann.is_pinned && (
                        <Pin className="h-3.5 w-3.5 text-primary shrink-0" />
                      )}
                      <h3 className="text-sm font-semibold truncate">
                        {ann.title}
                      </h3>
                      {ann.priority !== "normal" && (
                        <Badge
                          variant="secondary"
                          className={cn(
                            "text-[10px] h-5 capitalize",
                            priorityStyles[ann.priority]
                          )}
                        >
                          {ann.priority}
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground line-clamp-2 mt-1">
                      {ann.content}
                    </p>
                    <p className="text-xs text-muted-foreground mt-2">
                      {ann.author_name} &middot;{" "}
                      {ann.published_at
                        ? formatRelativeTime(ann.published_at)
                        : formatRelativeTime(ann.created_at)}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Detail dialog */}
      <Dialog open={!!selectedAnn} onOpenChange={() => setSelectedAnn(null)}>
        <DialogContent className="max-w-lg">
          {selectedAnn && (
            <>
              <DialogHeader>
                <div className="flex items-center gap-2">
                  {selectedAnn.is_pinned && (
                    <Pin className="h-4 w-4 text-primary shrink-0" />
                  )}
                  <DialogTitle>{selectedAnn.title}</DialogTitle>
                </div>
                <DialogDescription>
                  By {selectedAnn.author_name} &middot;{" "}
                  {selectedAnn.published_at
                    ? formatGhanaDate(selectedAnn.published_at)
                    : "Draft"}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                {selectedAnn.priority !== "normal" && (
                  <Badge
                    variant="secondary"
                    className={cn(
                      "capitalize",
                      priorityStyles[selectedAnn.priority]
                    )}
                  >
                    {selectedAnn.priority}
                  </Badge>
                )}
                <p className="text-sm whitespace-pre-wrap">
                  {selectedAnn.content}
                </p>
                {selectedAnn.attachment_url && (
                  <Button variant="outline" size="sm" asChild>
                    <a
                      href={selectedAnn.attachment_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <ExternalLink className="mr-2 h-4 w-4" />
                      View Attachment
                    </a>
                  </Button>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
