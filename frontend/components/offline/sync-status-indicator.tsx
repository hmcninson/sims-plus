"use client";

import { useState, useEffect } from "react";
import { Cloud, CloudOff, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useNetworkStatus } from "@/hooks/use-network-status";
import { getTotalQueueSize } from "@/lib/offline/sync";

export function SyncStatusIndicator() {
  const { isOnline } = useNetworkStatus();
  const [pendingCount, setPendingCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);

  useEffect(() => {
    let interval: NodeJS.Timeout;

    const checkQueue = async () => {
      try {
        const count = await getTotalQueueSize();
        setPendingCount(count);
      } catch {
        // IndexedDB not available
      }
    };

    checkQueue();
    interval = setInterval(checkQueue, 10000);

    return () => clearInterval(interval);
  }, []);

  // Show syncing state when coming back online with pending items
  useEffect(() => {
    if (isOnline && pendingCount > 0) {
      setIsSyncing(true);
      // The actual sync is done by page-level hooks or the service worker.
      // Clear after a short delay or when queue empties.
      const timer = setTimeout(async () => {
        try {
          const count = await getTotalQueueSize();
          setPendingCount(count);
        } catch {
          // Ignore
        }
        setIsSyncing(false);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [isOnline]); // eslint-disable-line react-hooks/exhaustive-deps

  // Don't show anything if online and no pending items
  if (isOnline && pendingCount === 0) return null;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex items-center gap-1">
            {!isOnline ? (
              <Badge variant="destructive" className="gap-1 text-xs">
                <CloudOff className="h-3 w-3" />
                <span className="hidden sm:inline">Offline</span>
              </Badge>
            ) : isSyncing ? (
              <Badge variant="secondary" className="gap-1 text-xs">
                <Loader2 className="h-3 w-3 animate-spin" />
                <span className="hidden sm:inline">Syncing</span>
              </Badge>
            ) : pendingCount > 0 ? (
              <Badge variant="outline" className="gap-1 text-xs">
                <Cloud className="h-3 w-3" />
                {pendingCount}
              </Badge>
            ) : null}
          </div>
        </TooltipTrigger>
        <TooltipContent>
          {!isOnline
            ? "You are offline. Data will sync when reconnected."
            : isSyncing
            ? "Syncing pending data..."
            : `${pendingCount} item(s) waiting to sync`}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
