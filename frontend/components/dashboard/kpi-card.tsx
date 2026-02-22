"use client";

import Link from "next/link";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  TrendingUp,
  TrendingDown,
  Users,
  UserCog,
  ClipboardCheck,
  Wallet,
  type LucideIcon,
} from "lucide-react";

// Lookup map to resolve icon names to components, avoiding Server -> Client
// serialization issues (React cannot serialize component references).
const iconMap: Record<string, LucideIcon> = {
  Users,
  UserCog,
  ClipboardCheck,
  Wallet,
};

interface KpiCardProps {
  title: string;
  value: string | number;
  iconName: string;
  trend?: { value: string; positive: boolean };
  href?: string;
}

export function KpiCard({ title, value, iconName, trend, href }: KpiCardProps) {
  const Icon = iconMap[iconName] ?? Users;
  const content = (
    <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
            <Icon className="h-5 w-5 text-primary" />
          </div>
          {trend && (
            <Badge
              variant={trend.positive ? "default" : "destructive"}
              className="flex items-center gap-1 font-medium"
            >
              {trend.positive ? (
                <TrendingUp className="h-3 w-3" />
              ) : (
                <TrendingDown className="h-3 w-3" />
              )}
              {trend.value}
            </Badge>
          )}
        </div>
        <div className="mt-4">
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-sm text-muted-foreground">{title}</p>
        </div>
      </CardContent>
    </Card>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }
  return content;
}
