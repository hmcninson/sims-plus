import {
  GraduationCap,
  Sparkles,
  Target,
  MessageSquare,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

import type { MontessoriAssessmentData, MontessoriProgressLevel } from "@/types/curriculum.type";

const PROGRESS_LABELS: Record<MontessoriProgressLevel, { label: string; color: string }> = {
  emerging: { label: "Emerging", color: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200" },
  developing: { label: "Developing", color: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200" },
  practicing: { label: "Practicing", color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200" },
  mastery: { label: "Mastery", color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200" },
};

interface MontessoriReportViewProps {
  data: MontessoriAssessmentData;
}

export function MontessoriReportView({ data }: MontessoriReportViewProps) {
  const hasAreas = data.developmental_areas && data.developmental_areas.length > 0;
  const hasWorkSamples = data.work_samples && data.work_samples.length > 0;
  const hasGoals = data.goals && data.goals.length > 0;
  const hasNarrative = data.general_narrative && data.general_narrative.trim().length > 0;

  if (!hasAreas && !hasWorkSamples && !hasGoals && !hasNarrative) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <GraduationCap className="mx-auto h-12 w-12 text-muted-foreground/50" />
          <h3 className="mt-4 text-lg font-semibold">No Assessment Data</h3>
          <p className="text-muted-foreground">
            Montessori narrative assessment has not been entered for this term yet.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Developmental Areas */}
      {hasAreas && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <GraduationCap className="h-5 w-5" />
              Developmental Progress
            </CardTitle>
            <CardDescription>
              Assessment across {data.developmental_areas.length} developmental areas
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Accordion
              type="multiple"
              defaultValue={data.developmental_areas.map((_, i) => `area-${i}`)}
            >
              {data.developmental_areas.map((area, index) => (
                <AccordionItem key={index} value={`area-${index}`}>
                  <AccordionTrigger className="text-base font-semibold">
                    {area.name}
                  </AccordionTrigger>
                  <AccordionContent className="space-y-4">
                    {/* Skills */}
                    {area.skills && area.skills.length > 0 && (
                      <div className="space-y-2">
                        {area.skills.map((skill, skillIndex) => {
                          const levelConfig =
                            PROGRESS_LABELS[skill.progress_level as MontessoriProgressLevel];
                          return (
                            <div
                              key={skillIndex}
                              className="flex flex-col gap-1 rounded-md border p-3 sm:flex-row sm:items-center sm:justify-between"
                            >
                              <span className="font-medium">{skill.name}</span>
                              {levelConfig && (
                                <Badge
                                  variant="outline"
                                  className={levelConfig.color}
                                >
                                  {levelConfig.label}
                                </Badge>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Area Narrative */}
                    {area.narrative && area.narrative.trim() && (
                      <div className="rounded-md bg-muted/50 p-4">
                        <p className="text-sm font-medium text-muted-foreground mb-1">
                          Teacher's Observation
                        </p>
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">
                          {area.narrative}
                        </p>
                      </div>
                    )}
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          </CardContent>
        </Card>
      )}

      {/* Work Samples */}
      {hasWorkSamples && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Sparkles className="h-5 w-5" />
              Work Samples
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {data.work_samples.map((sample, index) => (
                <li
                  key={index}
                  className="flex items-start gap-3 rounded-md border p-3"
                >
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
                    {index + 1}
                  </span>
                  <span className="text-sm">{sample.description}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Goals */}
      {hasGoals && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Target className="h-5 w-5" />
              Goals for Next Term
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {data.goals.map((goal, index) => (
                <li
                  key={index}
                  className="flex items-start gap-3 rounded-md border p-3"
                >
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-medium text-primary">
                    {index + 1}
                  </span>
                  <span className="text-sm">{goal}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* General Narrative */}
      {hasNarrative && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <MessageSquare className="h-5 w-5" />
              General Comments
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed whitespace-pre-wrap">
              {data.general_narrative}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
