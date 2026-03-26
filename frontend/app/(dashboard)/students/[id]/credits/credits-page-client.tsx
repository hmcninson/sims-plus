"use client";

import { useState } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { CreditProgressDashboard } from "@/components/curriculum/CreditProgressDashboard";
import type { CurriculumProfile } from "@/types/curriculum.type";

interface CreditsPageClientProps {
  studentId: string;
  creditProfiles: CurriculumProfile[];
}

export function CreditsPageClient({
  studentId,
  creditProfiles,
}: CreditsPageClientProps) {
  const [selectedProfileId, setSelectedProfileId] = useState(
    creditProfiles.length > 0 ? creditProfiles[0].id : "",
  );

  return (
    <div className="space-y-4">
      {creditProfiles.length > 1 && (
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium">Curriculum Profile:</label>
          <Select value={selectedProfileId} onValueChange={setSelectedProfileId}>
            <SelectTrigger className="w-full sm:w-[250px]">
              <SelectValue placeholder="Select profile" />
            </SelectTrigger>
            <SelectContent>
              {creditProfiles.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {selectedProfileId && (
        <CreditProgressDashboard
          studentId={studentId}
          profileId={selectedProfileId}
          isAdmin
        />
      )}
    </div>
  );
}
