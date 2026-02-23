"use client";

/**
 * SIMS Plus - Teacher Notifications Page
 *
 * Lists all notifications for the teacher with read/unread states.
 * Supports marking individual notifications or all as read.
 */

import { useEffect, useState, useTransition } from "react";
import {
  AlertCircle,
  Bell,
  BellOff,
  Check,
  CheckCheck,
  Loader2,
  Info,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  getTeacherNotifications,
  markTeacherNotificationRead,
  markAllTeacherNotificationsRead,
} from "@/actions/teacher.action";
import type { TeacherNotification, TeacherNotificationList } from "@/types/teacher.type";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const TYPE_ICONS: Record<string, React.ReactNode> = {
  info: <Info className="h-4 w-4 text-blue-500" />,
  success: <CheckCircle2 className="h-4 w-4 text-green-500" />,
  warning: <AlertTriangle className="h-4 w-4 text-amber-500" />,
  error: <XCircle className="h-4 w-4 text-red-500" />,
};

export default function TeacherNotificationsPage() {
  const [data, setData] = useState<TeacherNotificationList | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    async function load() {
      setLoading(true);
      const result = await getTeacherNotifications(page);
      if (result.success) {
        setData(result.data);
      } else {
        setError(result.error);
      }
      setLoading(false);
    }
    load();
  }, [page]);

  const handleMarkRead = (notificationId: string) => {
    startTransition(async () => {
      const result = await markTeacherNotificationRead(notificationId);
      if (result.success) {
        setData((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            unread_count: Math.max(0, prev.unread_count - 1),
            items: prev.items.map((n) =>
              n.id === notificationId ? { ...n, is_read: true } : n
            ),
          };
        });
      }
    });
  };

  const handleMarkAllRead = () => {
    startTransition(async () => {
      const result = await markAllTeacherNotificationsRead();
      if (result.success) {
        setData((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            unread_count: 0,
            items: prev.items.map((n) => ({ ...n, is_read: true })),
          };
        });
        toast.success("All notifications marked as read");
      } else {
        toast.error(result.error);
      }
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error || "Failed to load notifications"}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Notifications</h1>
          <p className="text-muted-foreground">
            {data.unread_count > 0
              ? `${data.unread_count} unread notification${data.unread_count !== 1 ? "s" : ""}`
              : "All caught up"}
          </p>
        </div>
        {data.unread_count > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleMarkAllRead}
            disabled={isPending}
          >
            <CheckCheck className="h-3.5 w-3.5 mr-1" />
            Mark All Read
          </Button>
        )}
      </div>

      {data.items.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <BellOff className="h-12 w-12 text-muted-foreground/50 mb-3" />
            <p className="text-muted-foreground">No notifications</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {data.items.map((notification: TeacherNotification) => (
            <Card
              key={notification.id}
              className={cn(
                "transition-colors",
                !notification.is_read && "border-primary/20 bg-primary/[0.02]"
              )}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <div className="shrink-0 mt-0.5">
                    {TYPE_ICONS[notification.type] || TYPE_ICONS.info}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className={cn("text-sm", !notification.is_read && "font-semibold")}>
                        {notification.title}
                      </p>
                      {!notification.is_read && (
                        <div className="h-2 w-2 rounded-full bg-primary shrink-0" />
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {notification.message}
                    </p>
                    <div className="flex items-center gap-3 mt-2">
                      <span className="text-[10px] text-muted-foreground">
                        {new Date(notification.created_at).toLocaleDateString("en-GB", {
                          day: "numeric",
                          month: "short",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </span>
                      <Badge variant="outline" className="text-[10px]">
                        {notification.category}
                      </Badge>
                    </div>
                  </div>
                  {!notification.is_read && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0"
                      onClick={() => handleMarkRead(notification.id)}
                      disabled={isPending}
                    >
                      <Check className="h-3.5 w-3.5" />
                      <span className="sr-only">Mark as read</span>
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}

          {/* Pagination */}
          {data.total_pages > 1 && (
            <div className="flex justify-center gap-2 pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1 || loading}
              >
                Previous
              </Button>
              <span className="flex items-center text-sm text-muted-foreground">
                Page {page} of {data.total_pages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page === data.total_pages || loading}
              >
                Next
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
