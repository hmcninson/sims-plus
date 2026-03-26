"use client";

import { Check } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { CurriculumTemplateInfo, CurriculumType } from "@/types/curriculum.type";

const CURRICULUM_TYPE_COLORS: Record<CurriculumType, string> = {
  ges: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  cambridge: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  edexcel: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  american: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  ib: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200",
  french: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200",
  montessori: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  custom: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

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

interface TemplateSelectorProps {
  templates: CurriculumTemplateInfo[];
  selectedKey?: string;
  onSelect: (key: string) => void;
}

export function TemplateSelector({
  templates,
  selectedKey,
  onSelect,
}: TemplateSelectorProps) {
  if (templates.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-dashed p-8 text-center">
        <p className="text-sm text-muted-foreground">
          No templates available. You can create a custom profile instead.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {templates.map((template) => {
        const isSelected = selectedKey === template.key;
        return (
          <Card
            key={template.key}
            role="button"
            tabIndex={0}
            aria-pressed={isSelected}
            aria-label={`Select ${template.name} template`}
            onClick={() => onSelect(template.key)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(template.key);
              }
            }}
            className={cn(
              "cursor-pointer transition-all hover:shadow-md relative",
              isSelected
                ? "ring-2 ring-primary border-primary"
                : "hover:border-primary/50",
            )}
          >
            {isSelected && (
              <div className="absolute top-3 right-3 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-primary-foreground">
                <Check className="h-3 w-3" />
              </div>
            )}
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">{template.name}</CardTitle>
              </div>
              <Badge
                variant="secondary"
                className={cn(
                  "w-fit text-[10px]",
                  CURRICULUM_TYPE_COLORS[template.curriculum_type],
                )}
              >
                {CURRICULUM_TYPE_LABELS[template.curriculum_type]}
              </Badge>
            </CardHeader>
            <CardContent>
              <CardDescription className="text-xs line-clamp-3">
                {template.description}
              </CardDescription>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
