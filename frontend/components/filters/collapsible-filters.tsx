"use client";

import { useState } from "react";
import { Filter, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface CollapsibleFiltersProps {
  activeFilterCount?: number;
  children: React.ReactNode;
  className?: string;
}

export function CollapsibleFilters({
  activeFilterCount = 0,
  children,
  className,
}: CollapsibleFiltersProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* Desktop: Always show filters inline */}
      <div className={`hidden md:flex md:flex-wrap md:items-center md:gap-2 ${className || ""}`}>
        {children}
      </div>

      {/* Mobile: Collapsible filter panel */}
      <div className="md:hidden">
        <Collapsible open={isOpen} onOpenChange={setIsOpen}>
          <CollapsibleTrigger asChild>
            <Button variant="outline" size="sm" className="w-full justify-between">
              <span className="flex items-center gap-2">
                <Filter className="h-4 w-4" />
                Filters
                {activeFilterCount > 0 && (
                  <Badge variant="secondary" className="h-5 min-w-[20px] px-1.5 text-xs">
                    {activeFilterCount}
                  </Badge>
                )}
              </span>
              {isOpen ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 space-y-2">
            {children}
          </CollapsibleContent>
        </Collapsible>
      </div>
    </>
  );
}
