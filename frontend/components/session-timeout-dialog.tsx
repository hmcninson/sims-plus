"use client";

import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogAction,
  AlertDialogCancel,
} from "@/components/ui/alert-dialog";
import { Clock } from "lucide-react";

interface SessionTimeoutDialogProps {
  open: boolean;
  remainingSeconds: number;
  onContinue: () => void;
  onLogout: () => void;
}

/**
 * Non-dismissible warning dialog shown when the user has been inactive
 * for 25 minutes. Displays a countdown until auto-logout at 30 minutes.
 *
 * Uses AlertDialog (not Dialog) so the user cannot dismiss it by
 * clicking outside or pressing Escape -- they must choose an action.
 */
export function SessionTimeoutDialog({
  open,
  remainingSeconds,
  onContinue,
  onLogout,
}: SessionTimeoutDialogProps) {
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;

  return (
    <AlertDialog open={open}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-amber-500" />
            <AlertDialogTitle>Session Expiring</AlertDialogTitle>
          </div>
          <AlertDialogDescription>
            Your session will expire due to inactivity in{" "}
            <span className="font-mono font-bold text-foreground">
              {minutes}:{seconds.toString().padStart(2, "0")}
            </span>
            . Click &quot;Continue Session&quot; to stay logged in.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onLogout}>Log Out</AlertDialogCancel>
          <AlertDialogAction onClick={onContinue}>
            Continue Session
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
