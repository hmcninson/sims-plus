"use client";

import Image from "next/image";
import { Pencil, Trash2, Eye, Share2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { formatGhanaDate } from "@/lib/format";
import type { LearningStory } from "@/types";

interface LearningStoryCardProps {
  story: LearningStory;
  onEdit: (story: LearningStory) => void;
  onDelete: (id: string) => void;
  learningAreaNames?: Record<string, string>;
}

const AREA_COLORS = [
  "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
  "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300",
  "bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-300",
  "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-300",
];

export function LearningStoryCard({
  story,
  onEdit,
  onDelete,
  learningAreaNames = {},
}: LearningStoryCardProps) {
  const heroImage = story.attachments?.find((a) => a.url);

  return (
    <Card className="overflow-hidden group hover:shadow-md transition-shadow">
      {/* Hero Image */}
      {heroImage && (
        <div className="relative h-40 w-full overflow-hidden">
          <Image
            src={heroImage.url}
            alt={heroImage.filename || story.title}
            fill
            className="object-cover group-hover:scale-105 transition-transform duration-300"
            sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
          />
        </div>
      )}

      <CardHeader className="pb-2">
        <h3 className="font-bold text-base leading-tight line-clamp-2">
          {story.title}
        </h3>
      </CardHeader>

      <CardContent className="pb-3 space-y-3">
        {/* Narrative Preview */}
        <p className="text-sm text-muted-foreground line-clamp-3">
          {story.narrative}
        </p>

        {/* Learning Area Badges */}
        {story.learning_area_ids && story.learning_area_ids.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {story.learning_area_ids.slice(0, 3).map((areaId, idx) => (
              <Badge
                key={areaId}
                variant="secondary"
                className={`text-xs ${AREA_COLORS[idx % AREA_COLORS.length]}`}
              >
                {learningAreaNames[areaId] || "Learning Area"}
              </Badge>
            ))}
            {story.learning_area_ids.length > 3 && (
              <Badge variant="secondary" className="text-xs">
                +{story.learning_area_ids.length - 3}
              </Badge>
            )}
          </div>
        )}

        {/* Meta Info */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{formatGhanaDate(story.created_at)}</span>
          {story.is_shared_with_parents && (
            <Badge
              variant="outline"
              className="text-xs border-green-300 text-green-700 dark:border-green-700 dark:text-green-400"
            >
              <Share2 className="mr-1 h-3 w-3" />
              Shared
            </Badge>
          )}
          {story.observation_ids && story.observation_ids.length > 0 && (
            <Badge variant="outline" className="text-xs">
              <Eye className="mr-1 h-3 w-3" />
              {story.observation_ids.length} obs.
            </Badge>
          )}
        </div>
      </CardContent>

      <CardFooter className="pt-0 gap-2">
        <Button
          variant="outline"
          size="sm"
          className="flex-1"
          onClick={() => onEdit(story)}
        >
          <Pencil className="mr-1 h-3.5 w-3.5" />
          Edit
        </Button>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="outline" size="sm" className="text-destructive hover:text-destructive">
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete Learning Story</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete &quot;{story.title}&quot;? This action cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                onClick={() => onDelete(story.id)}
              >
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardFooter>
    </Card>
  );
}
