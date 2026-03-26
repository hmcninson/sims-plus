"use client";

import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { getCurriculumProfiles } from "@/actions/curriculum.action";
import type { CurriculumProfile, CurriculumType } from "@/types/curriculum.type";

const CURRICULUM_TYPE_LABELS: Record<CurriculumType, string> = {
  ges: "GES",
  cambridge: "Cambridge",
  edexcel: "Edexcel",
  american: "American",
  ib: "IB",
  french: "French",
  montessori: "Montessori",
  custom: "Custom",
};

interface CurriculumSelectorProps {
  value?: string;
  onChange: (value: string | undefined) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function CurriculumSelector({
  value,
  onChange,
  placeholder = "Select curriculum profile",
  disabled = false,
}: CurriculumSelectorProps) {
  const [profiles, setProfiles] = useState<CurriculumProfile[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    async function load() {
      const result = await getCurriculumProfiles();
      if (mounted && result.success) {
        setProfiles(result.data.filter((p) => p.is_active));
      }
      if (mounted) setIsLoading(false);
    }
    load();
    return () => {
      mounted = false;
    };
  }, []);

  if (isLoading) {
    return (
      <div className="flex h-9 items-center gap-2 rounded-md border px-3 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading profiles...
      </div>
    );
  }

  if (profiles.length === 0) {
    return (
      <div className="flex h-9 items-center rounded-md border px-3 text-sm text-muted-foreground">
        No curriculum profiles available
      </div>
    );
  }

  return (
    <Select
      value={value || ""}
      onValueChange={(v) => onChange(v === "__none__" ? undefined : v)}
      disabled={disabled}
    >
      <SelectTrigger className="w-full">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="__none__">
          <span className="text-muted-foreground">None (use school default)</span>
        </SelectItem>
        {profiles.map((profile) => (
          <SelectItem key={profile.id} value={profile.id}>
            <span className="flex items-center gap-2">
              {profile.name}
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                {CURRICULUM_TYPE_LABELS[profile.curriculum_type]}
              </Badge>
              {profile.is_default && (
                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                  Default
                </Badge>
              )}
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
