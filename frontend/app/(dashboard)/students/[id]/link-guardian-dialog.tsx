"use client";

import { useState, useEffect, useTransition } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Search, Check, UserPlus } from "lucide-react";
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

import { getGuardians, linkExistingGuardian } from "@/actions/students.action";
import type { Guardian, GuardianRelationship } from "@/types";

const linkSchema = z.object({
  guardian_id: z.string().min(1, "Please select a guardian"),
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

interface LinkGuardianDialogProps {
  studentId: string;
  studentName: string;
  existingGuardianIds: string[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function LinkGuardianDialog({
  studentId,
  studentName,
  existingGuardianIds,
  open,
  onOpenChange,
  onSuccess,
}: LinkGuardianDialogProps) {
  const [isPending, startTransition] = useTransition();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [guardians, setGuardians] = useState<Guardian[]>([]);
  const [selectedGuardian, setSelectedGuardian] = useState<Guardian | null>(null);

  // Store a stable reference of existing guardian IDs
  const existingIdsKey = existingGuardianIds.join(",");

  const form = useForm<LinkFormData>({
    resolver: zodResolver(linkSchema),
    defaultValues: {
      guardian_id: "",
      relationship: "guardian",
      is_primary: false,
      is_emergency_contact: true,
      can_pickup: true,
    },
  });

  // Debounce search input
  useEffect(() => {
    if (!open) return;

    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery, open]);

  // Fetch guardians when debounced search changes
  useEffect(() => {
    if (!open) return;

    startTransition(async () => {
      const result = await getGuardians(debouncedSearch || undefined, 1, 50);
      if (result.success && result.data) {
        // Filter out guardians already linked to this student
        const filtered = result.data.items.filter(
          (g) => !existingGuardianIds.includes(g.id)
        );
        setGuardians(filtered);
      }
    });
  }, [open, debouncedSearch, existingIdsKey]);

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      form.reset();
      setSearchQuery("");
      setDebouncedSearch("");
      setSelectedGuardian(null);
    }
    onOpenChange(newOpen);
  };

  const handleSelectGuardian = (guardian: Guardian) => {
    setSelectedGuardian(guardian);
    form.setValue("guardian_id", guardian.id);
  };

  const handleSubmit = async () => {
    const isValid = await form.trigger();
    if (!isValid || !selectedGuardian) return;

    setIsSubmitting(true);
    const data = form.getValues();

    const result = await linkExistingGuardian(studentId, {
      guardian_id: data.guardian_id,
      relationship: data.relationship,
      is_primary: data.is_primary,
      is_emergency_contact: data.is_emergency_contact,
      can_pickup: data.can_pickup,
    });

    if (result.success) {
      toast.success(`${selectedGuardian.first_name} ${selectedGuardian.last_name} linked successfully`);
      handleOpenChange(false);
      onSuccess();
    } else {
      toast.error(result.error || "Failed to link guardian");
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
          <DialogTitle>Link Existing Guardian</DialogTitle>
          <DialogDescription>
            Search and select an existing guardian to link to {studentName}.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={(e) => e.preventDefault()} className="space-y-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search guardians by name or phone..."
                className="pl-8"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>

            {/* Guardian List */}
            <div className="border rounded-md">
              <ScrollArea className="h-[200px]">
                {isPending ? (
                  <div className="flex items-center justify-center h-full py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : guardians.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full py-8 text-center">
                    <UserPlus className="h-8 w-8 text-muted-foreground mb-2" />
                    <p className="text-sm text-muted-foreground">
                      {searchQuery
                        ? "No guardians found matching your search"
                        : "No available guardians to link"}
                    </p>
                  </div>
                ) : (
                  <div className="p-2 space-y-1">
                    {guardians.map((guardian) => (
                      <button
                        key={guardian.id}
                        type="button"
                        className={`w-full flex items-center gap-3 p-2 rounded-md text-left transition-colors ${
                          selectedGuardian?.id === guardian.id
                            ? "bg-primary text-primary-foreground"
                            : "hover:bg-muted"
                        }`}
                        onClick={() => handleSelectGuardian(guardian)}
                      >
                        <Avatar className="h-9 w-9">
                          <AvatarImage src={guardian.photo_url || undefined} />
                          <AvatarFallback className="text-xs">
                            {getInitials(guardian.first_name, guardian.last_name)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm truncate">
                            {guardian.first_name} {guardian.last_name}
                          </p>
                          <p className={`text-xs truncate ${
                            selectedGuardian?.id === guardian.id
                              ? "text-primary-foreground/70"
                              : "text-muted-foreground"
                          }`}>
                            {guardian.phone}
                            {guardian.occupation && ` • ${guardian.occupation}`}
                          </p>
                        </div>
                        {selectedGuardian?.id === guardian.id && (
                          <Check className="h-4 w-4 shrink-0" />
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </div>

            {/* Relationship & Permissions (only show when guardian selected) */}
            {selectedGuardian && (
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
                disabled={isSubmitting || !selectedGuardian}
              >
                {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Link Guardian
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
