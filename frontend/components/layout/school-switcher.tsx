"use client";

/**
 * SIMS Plus - School Switcher
 *
 * Dropdown for chain tenants to switch between schools.
 * Hidden entirely for single-school tenants.
 * Shows the active school name with a check indicator.
 */

import { useSchool } from "@/contexts/school-context";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenuButton,
} from "@/components/ui/sidebar";
import { Check, ChevronsUpDown, School, Loader2 } from "lucide-react";

/**
 * School switcher for the sidebar.
 *
 * Only renders when `isChain` is true and there are multiple schools.
 * Single-school tenants never see this component.
 */
export function SchoolSwitcher() {
  const { activeSchoolId, accessibleSchools, isChain, isSwitching, switchSchool } =
    useSchool();

  // Do not render for single-school tenants or if there is only one school
  if (!isChain || accessibleSchools.length <= 1) {
    return null;
  }

  const activeSchool = accessibleSchools.find((s) => s.id === activeSchoolId);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <SidebarMenuButton
          size="lg"
          className="w-full data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
        >
          <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            {isSwitching ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <School className="size-4" />
            )}
          </div>
          <div className="grid flex-1 text-left text-sm leading-tight">
            <span className="truncate font-semibold">
              {activeSchool?.name ?? "Select School"}
            </span>
            <span className="truncate text-xs text-muted-foreground">
              {activeSchool?.code ?? "Switch school"}
            </span>
          </div>
          <ChevronsUpDown className="ml-auto size-4 shrink-0 opacity-50" />
        </SidebarMenuButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
        side="bottom"
        align="start"
        sideOffset={4}
      >
        <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">
          Schools
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {accessibleSchools.map((school) => (
          <DropdownMenuItem
            key={school.id}
            onSelect={() => switchSchool(school.id)}
            className="flex items-center gap-2"
          >
            <div className="flex aspect-square size-6 items-center justify-center rounded bg-muted text-muted-foreground">
              <School className="size-3.5" />
            </div>
            <div className="flex-1 truncate">
              <span className="text-sm">{school.name}</span>
              {school.code && (
                <span className="ml-1 text-xs text-muted-foreground">
                  ({school.code})
                </span>
              )}
            </div>
            {school.id === activeSchoolId && (
              <Check className="size-4 shrink-0 text-primary" />
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default SchoolSwitcher;
