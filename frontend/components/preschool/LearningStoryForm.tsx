"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Share2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import type {
  LearningStory,
  LearningStoryCreate,
  LearningStoryUpdate,
  LearningArea,
  DevelopmentalSkill,
  ProgressObservation,
} from "@/types";

const learningStorySchema = z.object({
  student_id: z.string().min(1, "Student is required"),
  title: z.string().min(1, "Title is required").max(200, "Title must be under 200 characters"),
  narrative: z.string().min(10, "Narrative must be at least 10 characters"),
  learning_area_ids: z.array(z.string()).optional(),
  skill_ids: z.array(z.string()).optional(),
  observation_ids: z.array(z.string()).optional(),
  is_shared_with_parents: z.boolean().optional(),
});

type FormValues = z.infer<typeof learningStorySchema>;

interface Student {
  id: string;
  first_name: string;
  last_name: string;
  student_id: string;
}

interface LearningStoryFormProps {
  story?: LearningStory;
  students: Student[];
  learningAreas: LearningArea[];
  skills: DevelopmentalSkill[];
  observations: ProgressObservation[];
  onSubmit: (data: LearningStoryCreate | LearningStoryUpdate) => Promise<void>;
  onCancel: () => void;
  isSaving?: boolean;
}

export function LearningStoryForm({
  story,
  students,
  learningAreas,
  skills,
  observations,
  onSubmit,
  onCancel,
  isSaving = false,
}: LearningStoryFormProps) {
  const isEditing = !!story;

  const form = useForm<FormValues>({
    resolver: zodResolver(learningStorySchema),
    defaultValues: {
      student_id: story?.student_id || "",
      title: story?.title || "",
      narrative: story?.narrative || "",
      learning_area_ids: story?.learning_area_ids || [],
      skill_ids: story?.skill_ids || [],
      observation_ids: story?.observation_ids || [],
      is_shared_with_parents: story?.is_shared_with_parents || false,
    },
  });

  const selectedAreaIds = form.watch("learning_area_ids") || [];

  // Filter skills by selected learning areas
  const filteredSkills = selectedAreaIds.length > 0
    ? skills.filter((s) => selectedAreaIds.includes(s.learning_area_id))
    : skills;

  async function handleSubmit(values: FormValues) {
    if (isEditing) {
      const updateData: LearningStoryUpdate = {
        title: values.title,
        narrative: values.narrative,
        learning_area_ids: values.learning_area_ids,
        skill_ids: values.skill_ids,
        observation_ids: values.observation_ids,
        is_shared_with_parents: values.is_shared_with_parents,
      };
      await onSubmit(updateData);
    } else {
      await onSubmit(values as LearningStoryCreate);
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-5">
        {/* Student Select */}
        <FormField
          control={form.control}
          name="student_id"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Student</FormLabel>
              <Select
                onValueChange={field.onChange}
                defaultValue={field.value}
                disabled={isEditing}
              >
                <FormControl>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select student..." />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {students.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.first_name} {s.last_name} ({s.student_id})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Title */}
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Title</FormLabel>
              <FormControl>
                <Input placeholder="A meaningful title for this story..." {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Narrative */}
        <FormField
          control={form.control}
          name="narrative"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Narrative</FormLabel>
              <FormControl>
                <Textarea
                  placeholder="Describe what happened, what the child was doing, what they said, and what it shows about their learning..."
                  className="min-h-[160px] resize-y"
                  {...field}
                />
              </FormControl>
              <FormDescription>
                Write a rich narrative about the child&apos;s learning experience.
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Learning Areas */}
        <FormField
          control={form.control}
          name="learning_area_ids"
          render={() => (
            <FormItem>
              <FormLabel>Learning Areas</FormLabel>
              <FormDescription>
                Select the learning areas this story relates to.
              </FormDescription>
              <ScrollArea className="h-[140px] rounded-md border p-3">
                <div className="space-y-2">
                  {learningAreas.map((area) => (
                    <FormField
                      key={area.id}
                      control={form.control}
                      name="learning_area_ids"
                      render={({ field }) => (
                        <FormItem className="flex items-center space-x-2 space-y-0">
                          <FormControl>
                            <Checkbox
                              checked={field.value?.includes(area.id)}
                              onCheckedChange={(checked) => {
                                const current = field.value || [];
                                if (checked) {
                                  field.onChange([...current, area.id]);
                                } else {
                                  field.onChange(current.filter((id) => id !== area.id));
                                }
                              }}
                            />
                          </FormControl>
                          <span className="text-sm leading-none">
                            {area.name}
                          </span>
                        </FormItem>
                      )}
                    />
                  ))}
                </div>
              </ScrollArea>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Skills */}
        {filteredSkills.length > 0 && (
          <FormField
            control={form.control}
            name="skill_ids"
            render={() => (
              <FormItem>
                <FormLabel>Skills Demonstrated</FormLabel>
                <FormDescription>
                  Select skills the child demonstrated.
                </FormDescription>
                <ScrollArea className="h-[140px] rounded-md border p-3">
                  <div className="space-y-2">
                    {filteredSkills.map((skill) => (
                      <FormField
                        key={skill.id}
                        control={form.control}
                        name="skill_ids"
                        render={({ field }) => (
                          <FormItem className="flex items-center space-x-2 space-y-0">
                            <FormControl>
                              <Checkbox
                                checked={field.value?.includes(skill.id)}
                                onCheckedChange={(checked) => {
                                  const current = field.value || [];
                                  if (checked) {
                                    field.onChange([...current, skill.id]);
                                  } else {
                                    field.onChange(current.filter((id) => id !== skill.id));
                                  }
                                }}
                              />
                            </FormControl>
                            <span className="text-sm leading-none">
                              {skill.name}
                            </span>
                          </FormItem>
                        )}
                      />
                    ))}
                  </div>
                </ScrollArea>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {/* Linked Observations */}
        {observations.length > 0 && (
          <FormField
            control={form.control}
            name="observation_ids"
            render={() => (
              <FormItem>
                <FormLabel>Linked Observations</FormLabel>
                <FormDescription>
                  Link existing observations to this story.
                </FormDescription>
                <ScrollArea className="h-[120px] rounded-md border p-3">
                  <div className="space-y-2">
                    {observations.map((obs) => (
                      <FormField
                        key={obs.id}
                        control={form.control}
                        name="observation_ids"
                        render={({ field }) => (
                          <FormItem className="flex items-center space-x-2 space-y-0">
                            <FormControl>
                              <Checkbox
                                checked={field.value?.includes(obs.id)}
                                onCheckedChange={(checked) => {
                                  const current = field.value || [];
                                  if (checked) {
                                    field.onChange([...current, obs.id]);
                                  } else {
                                    field.onChange(current.filter((id) => id !== obs.id));
                                  }
                                }}
                              />
                            </FormControl>
                            <div className="flex flex-col">
                              <span className="text-sm leading-none">{obs.title}</span>
                              <span className="text-xs text-muted-foreground">
                                {obs.observation_date}
                              </span>
                            </div>
                          </FormItem>
                        )}
                      />
                    ))}
                  </div>
                </ScrollArea>
                <FormMessage />
              </FormItem>
            )}
          />
        )}

        {/* Share with Parents */}
        <FormField
          control={form.control}
          name="is_shared_with_parents"
          render={({ field }) => (
            <FormItem className="flex items-center justify-between rounded-lg border p-4">
              <div className="space-y-0.5">
                <FormLabel className="text-sm font-medium">
                  <Share2 className="mr-2 inline h-4 w-4" />
                  Share with Parents
                </FormLabel>
                <FormDescription>
                  Make this story visible to the child&apos;s parents/guardians.
                </FormDescription>
              </div>
              <FormControl>
                <Switch
                  checked={field.value}
                  onCheckedChange={field.onChange}
                />
              </FormControl>
            </FormItem>
          )}
        />

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-4">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={isSaving}>
            {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isEditing ? "Update Story" : "Create Story"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
