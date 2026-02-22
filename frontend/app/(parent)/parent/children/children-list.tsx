"use client";

import Link from "next/link";
import {
  Users,
  CalendarCheck,
  GraduationCap,
  ChevronRight,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { getInitials } from "@/lib/format";
import type { ChildSummary } from "@/types/parent.type";

interface ChildrenListProps {
  children: ChildSummary[];
}

export function ChildrenList({ children }: ChildrenListProps) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">My Children</h1>
        <p className="text-sm text-muted-foreground">
          View and manage your children&apos;s school information.
        </p>
      </div>

      {children.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Users className="h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold">No children linked</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-sm">
              Contact the school administrator to link your children to your
              account.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {children.map((child) => (
            <Link
              key={child.id}
              href={`/parent/children/${child.id}`}
            >
              <Card className="hover:shadow-md transition-shadow cursor-pointer">
                <CardContent className="flex items-center gap-4 p-4">
                  <Avatar className="h-14 w-14">
                    <AvatarFallback className="bg-primary/10 text-primary text-lg">
                      {getInitials(
                        `${child.first_name} ${child.last_name}`
                      )}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-semibold truncate">
                        {child.first_name} {child.last_name}
                      </h3>
                      <Badge
                        variant="secondary"
                        className="text-xs shrink-0"
                      >
                        {child.gender === "male" ? "M" : "F"}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <GraduationCap className="h-3.5 w-3.5" />
                        {child.class_name}
                        {child.section_name
                          ? ` ${child.section_name}`
                          : ""}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      ID: {child.admission_number}
                    </p>
                  </div>
                  <ChevronRight className="h-5 w-5 text-muted-foreground shrink-0" />
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
