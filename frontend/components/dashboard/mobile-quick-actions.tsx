"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Plus,
  X,
  ClipboardCheck,
  CreditCard,
  Users,
  Bell,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const quickActions = [
  {
    label: "Mark Attendance",
    icon: ClipboardCheck,
    href: "/attendance/mark",
    color: "bg-green-500 hover:bg-green-600",
  },
  {
    label: "Record Payment",
    icon: CreditCard,
    href: "/finance/payments/record",
    color: "bg-blue-500 hover:bg-blue-600",
  },
  {
    label: "Roll Call",
    icon: Users,
    href: "/boarding/roll-call",
    color: "bg-purple-500 hover:bg-purple-600",
  },
  {
    label: "Notifications",
    icon: Bell,
    href: "/notifications",
    color: "bg-orange-500 hover:bg-orange-600",
  },
];

/**
 * Floating Action Button (FAB) with expandable quick actions.
 *
 * Only visible on mobile viewports (md:hidden). Provides one-tap
 * access to the most common teacher/admin workflows: attendance
 * marking, payment recording, boarding roll call, and notifications.
 */
export function MobileQuickActions() {
  const [isOpen, setIsOpen] = useState(false);
  const router = useRouter();

  return (
    <div className="fixed bottom-6 right-6 z-40 md:hidden">
      {/* Expandable action buttons */}
      {isOpen && (
        <div className="mb-3 flex flex-col-reverse gap-2">
          {quickActions.map((action) => (
            <button
              key={action.href}
              onClick={() => {
                setIsOpen(false);
                router.push(action.href);
              }}
              className="flex items-center gap-2 self-end"
            >
              <span className="rounded-md bg-background px-2 py-1 text-xs font-medium shadow-md border">
                {action.label}
              </span>
              <span
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-full text-white shadow-lg",
                  action.color
                )}
              >
                <action.icon className="h-5 w-5" />
              </span>
            </button>
          ))}
        </div>
      )}

      {/* FAB toggle button */}
      <Button
        size="icon"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "h-14 w-14 rounded-full shadow-lg transition-transform",
          isOpen && "rotate-45"
        )}
      >
        {isOpen ? <X className="h-6 w-6" /> : <Plus className="h-6 w-6" />}
      </Button>
    </div>
  );
}
