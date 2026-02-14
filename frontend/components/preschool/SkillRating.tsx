"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { PreschoolRating } from "@/types";

interface SkillRatingProps {
  ratings: PreschoolRating[];
  selectedRatingId?: string | null;
  onRatingChange: (ratingId: string | null) => void;
  disabled?: boolean;
  compact?: boolean;
}

// Default colors if not provided by rating
const DEFAULT_COLORS: Record<string, string> = {
  NYO: "#9ca3af", // Gray
  E: "#ef4444",   // Red
  D: "#eab308",   // Yellow
  P: "#22c55e",   // Green
  A: "#3b82f6",   // Blue
};

export function SkillRating({
  ratings,
  selectedRatingId,
  onRatingChange,
  disabled = false,
  compact = false,
}: SkillRatingProps) {
  // Sort ratings by numeric_value for consistent display order
  const sortedRatings = [...ratings].sort(
    (a, b) => a.numeric_value - b.numeric_value
  );

  const handleClick = (rating: PreschoolRating) => {
    if (disabled) return;

    // If clicking the already selected rating, deselect it
    if (selectedRatingId === rating.id) {
      onRatingChange(null);
    } else {
      onRatingChange(rating.id);
    }
  };

  return (
    <TooltipProvider delayDuration={300}>
      <div className={cn("flex gap-1", compact ? "gap-0.5" : "gap-1")}>
        {sortedRatings.map((rating) => {
          const isSelected = selectedRatingId === rating.id;
          const color = rating.color || DEFAULT_COLORS[rating.short_code] || "#9ca3af";

          return (
            <Tooltip key={rating.id}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => handleClick(rating)}
                  disabled={disabled}
                  className={cn(
                    "flex items-center justify-center rounded text-xs font-medium transition-all",
                    compact ? "h-5 w-5 min-w-5" : "h-6 min-w-7 px-1",
                    "border",
                    disabled && "cursor-not-allowed opacity-50",
                    !disabled && "hover:scale-105",
                    isSelected
                      ? "text-white"
                      : "bg-background text-muted-foreground hover:bg-muted"
                  )}
                  style={{
                    borderColor: color,
                    backgroundColor: isSelected ? color : undefined,
                  }}
                  aria-label={`Rate as ${rating.name}`}
                  aria-pressed={isSelected}
                >
                  {rating.short_code}
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-xs">
                <div className="text-sm">
                  <p className="font-semibold">{rating.name}</p>
                  {rating.description && (
                    <p className="text-muted-foreground">{rating.description}</p>
                  )}
                </div>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </TooltipProvider>
  );
}

// Display-only variant for showing a single rating value
interface RatingDisplayProps {
  rating?: PreschoolRating | null;
  showLabel?: boolean;
}

export function RatingDisplay({ rating, showLabel = false }: RatingDisplayProps) {
  if (!rating) {
    return (
      <span className="inline-flex h-5 min-w-5 items-center justify-center rounded border border-dashed border-muted-foreground/30 text-xs text-muted-foreground">
        —
      </span>
    );
  }

  const color = rating.color || DEFAULT_COLORS[rating.short_code] || "#9ca3af";

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className="inline-flex h-5 min-w-5 items-center justify-center rounded border text-xs font-medium text-white"
            style={{
              borderColor: color,
              backgroundColor: color,
            }}
          >
            {rating.short_code}
            {showLabel && <span className="ml-1">{rating.name}</span>}
          </span>
        </TooltipTrigger>
        <TooltipContent side="top">
          <p className="font-semibold">{rating.name}</p>
          {rating.description && (
            <p className="text-sm text-muted-foreground">{rating.description}</p>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
