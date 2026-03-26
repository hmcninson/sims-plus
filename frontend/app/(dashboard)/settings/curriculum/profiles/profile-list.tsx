"use client";

import { useState, useTransition, useMemo } from "react";
import Link from "next/link";
import {
  Plus,
  Search,
  MoreHorizontal,
  Loader2,
  Star,
  Pencil,
  Trash2,
  CheckCircle,
  AlertCircle,
  BookOpen,
} from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  getCurriculumProfiles,
  deleteCurriculumProfile,
  setDefaultProfile,
} from "@/actions/curriculum.action";
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

const CALENDAR_LABELS: Record<string, string> = {
  terms: "Terms",
  semesters: "Semesters",
  quarters: "Quarters",
};

interface ProfileListProps {
  initialProfiles: CurriculumProfile[];
  error?: string;
}

export function ProfileList({ initialProfiles, error }: ProfileListProps) {
  const [profiles, setProfiles] = useState(initialProfiles);
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<CurriculumType | "all">("all");
  const [isPending, startTransition] = useTransition();
  const [deleteTarget, setDeleteTarget] = useState<CurriculumProfile | null>(null);

  const filteredProfiles = useMemo(() => {
    return profiles.filter((p) => {
      const matchesSearch =
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.description?.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesType = typeFilter === "all" || p.curriculum_type === typeFilter;
      return matchesSearch && matchesType;
    });
  }, [profiles, searchQuery, typeFilter]);

  const refreshProfiles = () => {
    startTransition(async () => {
      const result = await getCurriculumProfiles();
      if (result.success) {
        setProfiles(result.data);
      }
    });
  };

  const handleSetDefault = (profile: CurriculumProfile) => {
    startTransition(async () => {
      const result = await setDefaultProfile(profile.id);
      if (result.success) {
        toast.success(`${profile.name} set as default`);
        refreshProfiles();
      } else {
        toast.error("Failed to set default", { description: result.error });
      }
    });
  };

  const handleDelete = () => {
    if (!deleteTarget) return;
    startTransition(async () => {
      const result = await deleteCurriculumProfile(deleteTarget.id);
      if (result.success) {
        toast.success(`${deleteTarget.name} deleted`);
        setDeleteTarget(null);
        refreshProfiles();
      } else {
        toast.error("Failed to delete profile", { description: result.error });
      }
    });
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-destructive/50 bg-destructive/10 p-8 gap-3">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={refreshProfiles}>
          Try again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Curriculum Profiles</h2>
          <p className="text-sm text-muted-foreground">
            {profiles.length} profile{profiles.length !== 1 && "s"} configured
          </p>
        </div>
        <Button asChild size="sm">
          <Link href="/settings/curriculum/profiles/new">
            <Plus className="mr-2 h-4 w-4" />
            Create Profile
          </Link>
        </Button>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search profiles..."
                className="pl-9"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Select
              value={typeFilter}
              onValueChange={(v) => setTypeFilter(v as CurriculumType | "all")}
            >
              <SelectTrigger className="w-full sm:w-[180px]">
                <SelectValue placeholder="All types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {Object.entries(CURRICULUM_TYPE_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {filteredProfiles.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <BookOpen className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {profiles.length === 0
                  ? "No curriculum profiles yet."
                  : "No profiles match your search."}
              </p>
              {profiles.length === 0 && (
                <Button asChild size="sm">
                  <Link href="/settings/curriculum/profiles/new">
                    <Plus className="mr-2 h-4 w-4" />
                    Create Profile
                  </Link>
                </Button>
              )}
            </div>
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden md:block">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Calendar</TableHead>
                      <TableHead className="text-center">Default</TableHead>
                      <TableHead className="text-center">Status</TableHead>
                      <TableHead className="w-[60px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredProfiles.map((profile) => (
                      <TableRow key={profile.id}>
                        <TableCell>
                          <Link
                            href={`/settings/curriculum/profiles/${profile.id}`}
                            className="font-medium hover:underline"
                          >
                            {profile.name}
                          </Link>
                          {profile.description && (
                            <p className="text-xs text-muted-foreground truncate max-w-[200px]">
                              {profile.description}
                            </p>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="secondary"
                            className={CURRICULUM_TYPE_COLORS[profile.curriculum_type]}
                          >
                            {CURRICULUM_TYPE_LABELS[profile.curriculum_type]}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">
                          {CALENDAR_LABELS[profile.academic_calendar_type] ||
                            profile.academic_calendar_type}
                        </TableCell>
                        <TableCell className="text-center">
                          {profile.is_default ? (
                            <Star className="h-4 w-4 mx-auto text-amber-500 fill-amber-500" />
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-center">
                          {profile.is_active ? (
                            <Badge
                              variant="secondary"
                              className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                            >
                              Active
                            </Badge>
                          ) : (
                            <Badge variant="secondary">Inactive</Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                              >
                                <MoreHorizontal className="h-4 w-4" />
                                <span className="sr-only">Actions</span>
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem asChild>
                                <Link
                                  href={`/settings/curriculum/profiles/${profile.id}`}
                                >
                                  <Pencil className="mr-2 h-4 w-4" />
                                  Edit
                                </Link>
                              </DropdownMenuItem>
                              {!profile.is_default && (
                                <DropdownMenuItem
                                  onClick={() => handleSetDefault(profile)}
                                  disabled={isPending}
                                >
                                  <Star className="mr-2 h-4 w-4" />
                                  Set as Default
                                </DropdownMenuItem>
                              )}
                              <DropdownMenuSeparator />
                              <DropdownMenuItem
                                onClick={() => setDeleteTarget(profile)}
                                className="text-destructive focus:text-destructive"
                              >
                                <Trash2 className="mr-2 h-4 w-4" />
                                Delete
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Mobile cards */}
              <div className="md:hidden space-y-3">
                {filteredProfiles.map((profile) => (
                  <div
                    key={profile.id}
                    className="rounded-lg border p-4 space-y-3"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <Link
                          href={`/settings/curriculum/profiles/${profile.id}`}
                          className="font-medium text-sm hover:underline"
                        >
                          {profile.name}
                        </Link>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge
                            variant="secondary"
                            className={`text-[10px] ${CURRICULUM_TYPE_COLORS[profile.curriculum_type]}`}
                          >
                            {CURRICULUM_TYPE_LABELS[profile.curriculum_type]}
                          </Badge>
                          {profile.is_default && (
                            <Star className="h-3.5 w-3.5 text-amber-500 fill-amber-500" />
                          )}
                        </div>
                      </div>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem asChild>
                            <Link
                              href={`/settings/curriculum/profiles/${profile.id}`}
                            >
                              <Pencil className="mr-2 h-4 w-4" />
                              Edit
                            </Link>
                          </DropdownMenuItem>
                          {!profile.is_default && (
                            <DropdownMenuItem
                              onClick={() => handleSetDefault(profile)}
                            >
                              <Star className="mr-2 h-4 w-4" />
                              Set as Default
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            onClick={() => setDeleteTarget(profile)}
                            className="text-destructive"
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span>
                        {CALENDAR_LABELS[profile.academic_calendar_type]}
                      </span>
                      <span>
                        {profile.score_display_mode.replace(/_/g, " ")}
                      </span>
                      {profile.is_active ? (
                        <CheckCircle className="h-3 w-3 text-green-600" />
                      ) : (
                        <span>Inactive</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {isPending && (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete confirmation */}
      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Curriculum Profile</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete &ldquo;{deleteTarget?.name}&rdquo;?
              This will remove the profile, its assessment structure, and report
              card configuration. Classes using this profile will need to be
              reassigned.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={isPending}
              className="bg-destructive text-white hover:bg-destructive/90"
            >
              {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
