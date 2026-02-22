"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell, CheckCheck, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { NotificationItem } from "@/components/notifications/notification-item";
import {
  getNotifications,
  markAsRead,
  markAllAsRead,
  deleteNotification,
} from "@/actions/notifications.action";
import type { NotificationFilters } from "@/actions/notifications.action";
import type { Notification } from "@/types";

const CATEGORIES: { value: string; label: string }[] = [
  { value: "all", label: "All Categories" },
  { value: "academic", label: "Academic" },
  { value: "finance", label: "Finance" },
  { value: "attendance", label: "Attendance" },
  { value: "exam", label: "Exams" },
  { value: "general", label: "General" },
  { value: "admin", label: "Admin" },
];

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [category, setCategory] = useState<string>("all");
  const [readFilter, setReadFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    const filters: NotificationFilters = { page, page_size: 20 };
    if (category !== "all") filters.category = category;
    if (readFilter === "unread") filters.is_read = false;
    if (readFilter === "read") filters.is_read = true;

    const result = await getNotifications(filters);
    if (result.success) {
      setNotifications(result.data.items);
      setTotal(result.data.total);
      setTotalPages(result.data.total_pages);
    }
    setLoading(false);
  }, [page, category, readFilter]);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const handleMarkAsRead = async (id: string) => {
    await markAsRead(id);
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
    );
  };

  const handleMarkAllRead = async () => {
    await markAllAsRead();
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
  };

  const handleDelete = async (id: string) => {
    await deleteNotification(id);
    setNotifications((prev) => prev.filter((n) => n.id !== id));
    setTotal((prev) => prev - 1);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Notifications</h1>
          <p className="text-muted-foreground">
            {total} notification{total !== 1 ? "s" : ""}
          </p>
        </div>
        <Button variant="outline" onClick={handleMarkAllRead}>
          <CheckCheck className="mr-2 h-4 w-4" />
          Mark all as read
        </Button>
      </div>

      <div className="flex flex-col gap-4 sm:flex-row">
        <Select
          value={category}
          onValueChange={(v) => {
            setCategory(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-full sm:w-[180px]">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            {CATEGORIES.map((cat) => (
              <SelectItem key={cat.value} value={cat.value}>
                {cat.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={readFilter}
          onValueChange={(v) => {
            setReadFilter(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-full sm:w-[150px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="unread">Unread</SelectItem>
            <SelectItem value="read">Read</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            </div>
          ) : notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <Bell className="mb-4 h-12 w-12" />
              <p className="text-lg font-medium">No notifications</p>
              <p className="text-sm">You&apos;re all caught up!</p>
            </div>
          ) : (
            <div className="divide-y">
              {notifications.map((notification) => (
                <div key={notification.id} className="group flex items-center">
                  <div className="flex-1">
                    <NotificationItem
                      notification={notification}
                      onMarkAsRead={handleMarkAsRead}
                    />
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="mr-2 opacity-0 transition-opacity group-hover:opacity-100"
                    onClick={() => handleDelete(notification.id)}
                  >
                    <Trash2 className="h-4 w-4 text-muted-foreground hover:text-red-500" />
                    <span className="sr-only">Delete notification</span>
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
