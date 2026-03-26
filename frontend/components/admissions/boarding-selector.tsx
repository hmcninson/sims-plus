"use client";

import { useState, useTransition } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Home, Loader2 } from "lucide-react";
import { updateBoardingStatus } from "@/actions/admissions.action";

interface BoardingSelectorProps {
  applicationId: string;
  currentStatus: string | null;
}

export function BoardingSelector({
  applicationId,
  currentStatus: initialStatus,
}: BoardingSelectorProps) {
  const [isPending, startTransition] = useTransition();
  const [status, setStatus] = useState<string>(initialStatus ?? "");
  const [itemsAdded, setItemsAdded] = useState<number>(0);

  function handleStatusChange(value: string) {
    const previousStatus = status;
    setStatus(value);

    startTransition(async () => {
      const result = await updateBoardingStatus(applicationId, value);
      if (result.success) {
        setItemsAdded(result.data.boarding_items_added);
        toast.success(
          value === "boarding"
            ? `Set to Boarding${result.data.boarding_items_added > 0 ? ` (${result.data.boarding_items_added} checklist items added)` : ""}`
            : "Set to Day student"
        );
      } else {
        setStatus(previousStatus);
        toast.error(result.error);
      }
    });
  }

  const statusLabel = status === "boarding" ? "Boarding" : status === "day" ? "Day" : "Not set";
  const statusColor =
    status === "boarding"
      ? "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300"
      : status === "day"
        ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
        : "";

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Home className="h-4 w-4" />
            Residential Status
          </CardTitle>
          {status && (
            <Badge className={statusColor}>{statusLabel}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          <div className="relative">
            <Select
              value={status}
              onValueChange={handleStatusChange}
              disabled={isPending}
            >
              <SelectTrigger className="w-full">
                {isPending ? (
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Updating...</span>
                  </div>
                ) : (
                  <SelectValue placeholder="Select residential status" />
                )}
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="day">Day Student</SelectItem>
                <SelectItem value="boarding">Boarding Student</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <p className="text-xs text-muted-foreground">
            Setting status to &quot;Boarding&quot; will add boarding-specific items
            to the enrollment checklist.
          </p>
          {itemsAdded > 0 && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              {itemsAdded} boarding checklist item{itemsAdded !== 1 ? "s" : ""} were added.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
