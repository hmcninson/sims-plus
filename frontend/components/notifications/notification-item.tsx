"use client";

import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle, Info, AlertTriangle, Settings } from "lucide-react";
import type { Notification, NotificationType } from "@/types";

const typeIcons: Record<NotificationType, React.ElementType> = {
  info: Info,
  success: CheckCircle,
  warning: AlertTriangle,
  error: AlertCircle,
  system: Settings,
};

const typeColors: Record<NotificationType, string> = {
  info: "text-blue-500",
  success: "text-green-500",
  warning: "text-yellow-500",
  error: "text-red-500",
  system: "text-gray-500",
};

function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return date.toLocaleDateString("en-GB");
}

interface NotificationItemProps {
  notification: Notification;
  onMarkAsRead?: (id: string) => void;
}

export function NotificationItem({
  notification,
  onMarkAsRead,
}: NotificationItemProps) {
  const Icon = typeIcons[notification.type] || Info;
  const color = typeColors[notification.type] || "text-gray-500";

  return (
    <div
      className={cn(
        "flex gap-3 px-4 py-3 hover:bg-muted/50 cursor-pointer transition-colors",
        !notification.is_read && "bg-blue-50/50 dark:bg-blue-950/10"
      )}
      onClick={() => {
        if (!notification.is_read && onMarkAsRead) {
          onMarkAsRead(notification.id);
        }
      }}
    >
      <div className={cn("mt-0.5 shrink-0", color)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p
          className={cn(
            "truncate text-sm",
            !notification.is_read && "font-semibold"
          )}
        >
          {notification.title}
        </p>
        <p className="line-clamp-2 text-xs text-muted-foreground">
          {notification.message}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          {timeAgo(notification.created_at)}
        </p>
      </div>
      {!notification.is_read && (
        <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-blue-500" />
      )}
    </div>
  );
}
