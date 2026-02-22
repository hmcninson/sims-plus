"use client";

import { useState, useEffect, useTransition } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Search, Check, GraduationCap } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";

import { getStudents, linkExistingGuardian, getGuardianStudents } from "@/actions/students.action";
import type { Guardian, StudentListItem, GuardianRelationship } from "@/types";

const linkSchema = z.object({
  student_id: z.string().min(1, "Please select a student"),
  relationship: z.enum([
    "father",
    "mother",
    "guardian",
    "grandfather",
    "grandmother",
    "uncle",
    "aunt",
    "sibling",
    "other",
  ]),
  is_primary: z.boolean(),
  is_emergency_contact: z.boolean(),
  can_pickup: z.boolean(),
});

type LinkFormData = z.infer<typeof linkSchema>;

const relationshipOptions: { value: GuardianRelationship; label: string }[] = [
  { value: "father", label: "Father" },
  { value: "mother", label: "Mother" },
  { value: "guardian", label: "Guardian" },
  { value: "grandfather", label: "Grandfather" },
  { value: "grandmother", label: "Grandmother" },
  { value: "uncle", label: "Uncle" },
  { value: "aunt", label: "Aunt" },
  { value: "sibling", label: "Sibling" },
  { value: "other", label: "Other" },
];

interface LinkToStudentDialogProps {
  guardian: Guardian;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function LinkToStudentDialog({
  guardian,
  open,
  onOpenChange,
  onSuccess,
}: LinkToStudentDialogProps) {
  const [isPending, startTransition] = useTransition();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [students, setStudents] = useState<StudentListItem[]>([]);
  const [linkedStudentIds, setLinkedStudentIds] = useState<string[]>([]);
  const [selectedStudent, setSelectedStudent] = useState<StudentListItem | null>(null);

  const form = useForm<LinkFormData>({
    resolver: zodResolver(linkSchema),
    defaultValues: {
      student_id: "",
      relationship: "guardian",
      is_primary: false,
      is_emergency_contact: true,
      can_pickup: true,
    },
  });

  // Load existing linked students when dialog opens
  useEffect(() => {
    if (open && guardian) {
      startTransition(async () => {
        const result = await getGuardianStudents(guardian.id);
        if (result.success && result.data) {
          setLinkedStudentIds(result.data.map((s) => s.id));
        }
      });
    }
  }, [open, guardian]);

  // Search students
  useEffect(() => {
    if (!open) return;

    const timer = setTimeout(() => {
      startTransition(async () => {
        const result = await getStudents({
          search: searchQuery || undefined,
          page: 1,
          page_size: 50,
        });
        if (result.success && result.data) {
          // Filter out students already linked to this guardian
          const filtered = result.data.items.filter(
            (s) => !linkedStudentIds.includes(s.id)
          );
          setStudents(filtered);
        }
      });
    }, 300);

    return () => clearTimeout(timer);
  }, [open, searchQuery, linkedStudentIds]);

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      form.reset();
      setSearchQuery("");
      setSelectedStudent(null);
    }
    onOpenChange(newOpen);
  };

  const handleSelectStudent = (student: StudentListItem) => {
    setSelectedStudent(student);
    form.setValue("student_id", student.id);
  };

  const handleSubmit = async () => {
    const isValid = await form.trigger();
    if (!isValid || !selectedStudent) return;

    setIsSubmitting(true);
    const data = form.getValues();

    const result = await linkExistingGuardian(data.student_id, {
      guardian_id: guardian.id,
      relationship: data.relationship,
      is_primary: data.is_primary,
      is_emergency_contact: data.is_emergency_contact,
      can_pickup: data.can_pickup,
    });

    if (result.success) {
      toast.success(`Linked to ${selectedStudent.first_name} ${selectedStudent.last_name}`);
      handleOpenChange(false);
      onSuccess();
    } else {
      toast.error(result.error || "Failed to link to student");
    }

    setIsSubmitting(false);
  };

  const getInitials = (firstName: string, lastName: string) => {
    return `${firstName.charAt(0)}${lastName.charAt(0)}`.toUpperCase();
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Link to Student</DialogTitle>
          <DialogDescription>
            Link {guardian.first_name} {guardian.last_name} to a student.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={(e) => e.preventDefault()} className="space-y-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search students by name or ID..."
                className="pl-8"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            {/* Student List */}
            <div className="border rounded-md">
              <ScrollArea className="h-[200px]">
                {isPending ? (
                  <div className="flex items-center justify-center h-full py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : students.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full py-8 text-center">
                    <GraduationCap className="h-8 w-8 text-muted-foreground mb-2" />
                    <p className="text-sm text-muted-foreground">
                      {searchQuery
                        ? "No students found matching your search"
                        : "No available students to link"}
                    </p>
                  </div>
                ) : (
                  <div className="p-2 space-y-1">
                    {students.map((student) => (
                      <button
                        key={student.id}
                        type="button"
                        className={`w-full flex items-center gap-3 p-2 rounded-md text-left transition-colors ${
                          selectedStudent?.id === student.id
                            ? "bg-primary text-primary-foreground"
                            : "hover:bg-muted"
                        }`}
                        onClick={() => handleSelectStudent(student)}
                      >
                        <Avatar className="h-9 w-9">
                          <AvatarImage src={student.photo_url || undefined} />
                          <AvatarFallback className="text-xs">
                            {getInitials(student.first_name, student.last_name)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm truncate">
                            {student.first_name} {student.middle_name ? `${student.middle_name} ` : ""}
                            {student.last_name}
                          </p>
                          <p className={`text-xs truncate ${
                            selectedStudent?.id === student.id
                              ? "text-primary-foreground/70"
                              : "text-muted-foreground"
                          }`}>
                            {student.student_id}
                            {student.class_name && ` • ${student.class_name}`}
                          </p>
                        </div>
                        <Badge
                          variant={student.status === "active" ? "default" : "secondary"}
                          className={`shrink-0 text-xs ${
                            selectedStudent?.id === student.id ? "bg-primary-foreground/20" : ""
                          }`}
                        >
                          {student.status}
                        </Badge>
                        {selectedStudent?.id === student.id && (
                          <Check className="h-4 w-4 shrink-0" />
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </div>

            {/* Relationship & Permissions (only show when student selected) */}
            {selectedStudent && (
              <div className="space-y-4 pt-2 border-t">
                <FormField
                  control={form.control}
                  name="relationship"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Relationship to Student</FormLabel>
                      <Select onValueChange={field.onChange} value={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select relationship" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {relationshipOptions.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div className="space-y-3">
                  <FormField
                    control={form.control}
                    name="is_primary"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel className="text-sm">Primary Guardian</FormLabel>
                          <FormDescription className="text-xs">
                            Main contact for communications
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

                  <FormField
                    control={form.control}
                    name="is_emergency_contact"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel className="text-sm">Emergency Contact</FormLabel>
                          <FormDescription className="text-xs">
                            Contact in emergencies
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

                  <FormField
                    control={form.control}
                    name="can_pickup"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel className="text-sm">Can Pick Up</FormLabel>
                          <FormDescription className="text-xs">
                            Authorized to pick up student
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
                </div>
              </div>
            )}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOpenChange(false)}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                type="button"
                onClick={handleSubmit}
                disabled={isSubmitting || !selectedStudent}
              >
                {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Link to Student
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
