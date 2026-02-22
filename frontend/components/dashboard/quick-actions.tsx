import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ClipboardCheck, Wallet, FileText, UserPlus } from "lucide-react";

const actions = [
  { label: "Mark Attendance", href: "/attendance/mark", icon: ClipboardCheck },
  { label: "Record Payment", href: "/finance/payments/new", icon: Wallet },
  { label: "View Reports", href: "/reports", icon: FileText },
  { label: "Add Student", href: "/students/new", icon: UserPlus },
];

export function QuickActions() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-semibold">Quick Actions</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3">
          {actions.map((action) => (
            <Button
              key={action.href}
              variant="outline"
              className="h-auto flex-col gap-2 py-4"
              asChild
            >
              <Link href={action.href}>
                <action.icon className="h-5 w-5" />
                <span className="text-xs">{action.label}</span>
              </Link>
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
