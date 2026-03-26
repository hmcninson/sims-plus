"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { format } from "date-fns";
import {
  Loader2,
  UserCheck,
  Clock,
  Users,
  Shield,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { StudentCombobox } from "@/components/preschool/StudentCombobox";
import { AuthorizedPickupList } from "@/components/preschool/AuthorizedPickupList";
import { PickupLogForm } from "@/components/preschool/PickupLogForm";
import { getStudents, getStudentGuardians } from "@/actions/students.action";
import {
  listAuthorizedPickups,
  recordPickup,
  listPickupLogs,
} from "@/actions/preschool.action";
import type {
  Class,
  Student,
  PickupLog,
  PickupLogCreate,
  AuthorizedPickup,
  StudentGuardianLink,
} from "@/types";

interface PickupsManagerProps {
  classes: Class[];
}

export function PickupsManager({ classes }: PickupsManagerProps) {
  // Tab 1 state: Record Pickup
  const [recordClassId, setRecordClassId] = useState<string>("");
  const [recordStudents, setRecordStudents] = useState<Student[]>([]);
  const [guardians, setGuardians] = useState<Map<string, StudentGuardianLink[]>>(new Map());
  const [authorizedPickups, setAuthorizedPickups] = useState<Map<string, AuthorizedPickup[]>>(new Map());
  const [todayPickups, setTodayPickups] = useState<PickupLog[]>([]);
  const [loadingStudents, setLoadingStudents] = useState(false);
  const [loadingPickups, setLoadingPickups] = useState(false);
  const [saving, setSaving] = useState(false);

  // Tab 2 state: Authorized Persons
  const [authClassId, setAuthClassId] = useState<string>("");
  const [authStudents, setAuthStudents] = useState<Student[]>([]);
  const [authSelectedStudentId, setAuthSelectedStudentId] = useState<string>("");
  const [authGuardians, setAuthGuardians] = useState<StudentGuardianLink[]>([]);
  const [loadingAuthStudents, setLoadingAuthStudents] = useState(false);
  const [loadingAuthGuardians, setLoadingAuthGuardians] = useState(false);

  // Fetch students for record pickup tab
  useEffect(() => {
    async function fetchStudents() {
      if (!recordClassId) {
        setRecordStudents([]);
        setGuardians(new Map());
        setAuthorizedPickups(new Map());
        return;
      }

      setLoadingStudents(true);
      try {
        const result = await getStudents({
          class_id: recordClassId,
          page_size: 200,
        });
        if (result.success && result.data) {
          const studentList = result.data.items.map((s) => ({
            id: s.id,
            student_id: s.student_id,
            first_name: s.first_name,
            middle_name: s.middle_name,
            last_name: s.last_name,
            gender: s.gender,
            date_of_birth: s.date_of_birth,
            status: s.status,
            class_id: s.class_id,
            section_id: s.section_id,
            photo_url: s.photo_url,
            is_boarder: false,
            created_at: "",
            updated_at: "",
          })) as Student[];
          setRecordStudents(studentList);

          // Prefetch guardians and authorized pickups for all students
          const newGuardians = new Map<string, StudentGuardianLink[]>();
          const newAuthorized = new Map<string, AuthorizedPickup[]>();

          await Promise.all(
            studentList.map(async (student) => {
              try {
                const [gResult, apResult] = await Promise.all([
                  getStudentGuardians(student.id),
                  listAuthorizedPickups(student.id),
                ]);
                if (gResult.success) {
                  newGuardians.set(student.id, gResult.data);
                }
                if (apResult.success) {
                  newAuthorized.set(student.id, apResult.data);
                }
              } catch {
                // Silent for individual failures
              }
            })
          );

          setGuardians(newGuardians);
          setAuthorizedPickups(newAuthorized);
        }
      } catch {
        toast.error("Failed to load students");
      } finally {
        setLoadingStudents(false);
      }
    }

    fetchStudents();
  }, [recordClassId]);

  // Fetch today's pickups
  const fetchTodayPickups = useCallback(async () => {
    if (!recordClassId) {
      setTodayPickups([]);
      return;
    }

    setLoadingPickups(true);
    try {
      const today = format(new Date(), "yyyy-MM-dd");
      const result = await listPickupLogs({
        class_id: recordClassId,
        date_from: today,
        date_to: today,
      });
      if (result.success) {
        setTodayPickups(result.data);
      }
    } catch {
      // Silent
    } finally {
      setLoadingPickups(false);
    }
  }, [recordClassId]);

  useEffect(() => {
    fetchTodayPickups();
  }, [fetchTodayPickups]);

  // Fetch students for authorized persons tab
  useEffect(() => {
    async function fetchAuthStudents() {
      if (!authClassId) {
        setAuthStudents([]);
        setAuthSelectedStudentId("");
        return;
      }

      setLoadingAuthStudents(true);
      try {
        const result = await getStudents({
          class_id: authClassId,
          page_size: 200,
        });
        if (result.success && result.data) {
          setAuthStudents(
            result.data.items.map((s) => ({
              id: s.id,
              student_id: s.student_id,
              first_name: s.first_name,
              middle_name: s.middle_name,
              last_name: s.last_name,
              gender: s.gender,
              date_of_birth: s.date_of_birth,
              status: s.status,
              class_id: s.class_id,
              section_id: s.section_id,
              photo_url: s.photo_url,
              is_boarder: false,
              created_at: "",
              updated_at: "",
            })) as Student[]
          );
        }
        setAuthSelectedStudentId("");
      } catch {
        toast.error("Failed to load students");
      } finally {
        setLoadingAuthStudents(false);
      }
    }

    fetchAuthStudents();
  }, [authClassId]);

  // Fetch guardians for selected student in authorized persons tab
  useEffect(() => {
    async function fetchGuardians() {
      if (!authSelectedStudentId) {
        setAuthGuardians([]);
        return;
      }

      setLoadingAuthGuardians(true);
      try {
        const result = await getStudentGuardians(authSelectedStudentId);
        if (result.success) {
          setAuthGuardians(result.data);
        }
      } catch {
        // Silent
      } finally {
        setLoadingAuthGuardians(false);
      }
    }

    fetchGuardians();
  }, [authSelectedStudentId]);

  // Handle pickup submission
  async function handleRecordPickup(data: PickupLogCreate) {
    setSaving(true);
    try {
      const result = await recordPickup(data);
      if (result.success) {
        toast.success("Pickup recorded");
        fetchTodayPickups();
      } else {
        toast.error(result.error);
      }
    } catch {
      toast.error("Failed to record pickup");
    } finally {
      setSaving(false);
    }
  }

  // Get student name by ID from current context
  function getStudentName(studentId: string): string {
    const allStudents = [...recordStudents, ...authStudents];
    const student = allStudents.find((s) => s.id === studentId);
    return student
      ? `${student.first_name} ${student.last_name}`
      : "Unknown";
  }

  return (
    <Tabs defaultValue="record" className="space-y-6">
      <TabsList>
        <TabsTrigger value="record" className="gap-1.5">
          <Clock className="h-4 w-4" />
          <span className="hidden sm:inline">Record Pickup</span>
          <span className="sm:hidden">Record</span>
        </TabsTrigger>
        <TabsTrigger value="authorized" className="gap-1.5">
          <Shield className="h-4 w-4" />
          <span className="hidden sm:inline">Authorized Persons</span>
          <span className="sm:hidden">Authorized</span>
        </TabsTrigger>
      </TabsList>

      {/* Tab 1: Record Pickup */}
      <TabsContent value="record" className="space-y-6">
        <div className="w-full sm:w-auto">
          <Label className="mb-1.5 block text-sm font-medium">Class</Label>
          <Select value={recordClassId} onValueChange={setRecordClassId}>
            <SelectTrigger className="w-full md:w-[200px]">
              <SelectValue placeholder="Select class..." />
            </SelectTrigger>
            <SelectContent>
              {classes.map((cls) => (
                <SelectItem key={cls.id} value={cls.id}>
                  {cls.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {!recordClassId ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12 text-center">
              <UserCheck className="h-12 w-12 text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-medium">Select a Class</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Choose a class to record student pickups
              </p>
            </CardContent>
          </Card>
        ) : loadingStudents ? (
          <div className="space-y-4">
            <Skeleton className="h-48 rounded-lg" />
            <Skeleton className="h-48 rounded-lg" />
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Pickup Form */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Record Pickup</CardTitle>
                <CardDescription>
                  Log a student being picked up
                </CardDescription>
              </CardHeader>
              <CardContent>
                <PickupLogForm
                  students={recordStudents}
                  guardians={guardians}
                  authorizedPickups={authorizedPickups}
                  onSubmit={handleRecordPickup}
                  isSaving={saving}
                />
              </CardContent>
            </Card>

            {/* Today's Pickups */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">
                  Today&apos;s Pickups
                </CardTitle>
                <CardDescription>
                  {format(new Date(), "dd/MM/yyyy")} &mdash;{" "}
                  {todayPickups.length} recorded
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loadingPickups ? (
                  <div className="space-y-2">
                    {[1, 2, 3].map((i) => (
                      <Skeleton key={i} className="h-10" />
                    ))}
                  </div>
                ) : todayPickups.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-8">
                    No pickups recorded today
                  </p>
                ) : (
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Time</TableHead>
                          <TableHead>Student</TableHead>
                          <TableHead className="hidden sm:table-cell">
                            Type
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {todayPickups.map((log) => (
                          <TableRow key={log.id}>
                            <TableCell className="text-sm">
                              {log.pickup_time}
                            </TableCell>
                            <TableCell className="text-sm">
                              {getStudentName(log.student_id)}
                            </TableCell>
                            <TableCell className="hidden sm:table-cell">
                              <Badge variant="outline" className="text-xs">
                                {log.picked_up_by_type === "guardian"
                                  ? "Guardian"
                                  : "Authorized"}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}
      </TabsContent>

      {/* Tab 2: Authorized Persons */}
      <TabsContent value="authorized" className="space-y-6">
        <div className="flex flex-wrap items-end gap-4">
          <div className="w-full sm:w-auto">
            <Label className="mb-1.5 block text-sm font-medium">Class</Label>
            <Select value={authClassId} onValueChange={setAuthClassId}>
              <SelectTrigger className="w-full md:w-[200px]">
                <SelectValue placeholder="Select class..." />
              </SelectTrigger>
              <SelectContent>
                {classes.map((cls) => (
                  <SelectItem key={cls.id} value={cls.id}>
                    {cls.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {authClassId && (
            <div className="w-full sm:w-auto">
              <Label className="mb-1.5 block text-sm font-medium">
                Student
              </Label>
              <StudentCombobox
                students={authStudents}
                value={authSelectedStudentId}
                onValueChange={setAuthSelectedStudentId}
                placeholder="Select student..."
                isLoading={loadingAuthStudents}
              />
            </div>
          )}
        </div>

        {!authClassId || !authSelectedStudentId ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-12 text-center">
              <Users className="h-12 w-12 text-muted-foreground/50" />
              <h3 className="mt-4 text-lg font-medium">
                Select a Student
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Choose a class and student to manage authorized pickup persons
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-6">
            {/* Guardians with can_pickup status */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  Guardians
                </CardTitle>
                <CardDescription>
                  Guardians linked to this student and their pickup permission
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loadingAuthGuardians ? (
                  <div className="space-y-2">
                    {[1, 2].map((i) => (
                      <Skeleton key={i} className="h-12" />
                    ))}
                  </div>
                ) : authGuardians.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    No guardians linked to this student
                  </p>
                ) : (
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Name</TableHead>
                          <TableHead>Relationship</TableHead>
                          <TableHead className="hidden sm:table-cell">
                            Phone
                          </TableHead>
                          <TableHead>Can Pickup</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {authGuardians.map((sg) => (
                          <TableRow key={sg.id}>
                            <TableCell className="text-sm font-medium">
                              {sg.guardian.first_name} {sg.guardian.last_name}
                            </TableCell>
                            <TableCell className="text-sm capitalize">
                              {sg.relationship}
                            </TableCell>
                            <TableCell className="hidden sm:table-cell text-sm">
                              {sg.guardian.phone}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={sg.can_pickup ? "default" : "secondary"}
                                className="text-xs"
                              >
                                {sg.can_pickup ? "Yes" : "No"}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Authorized Pickup List */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Shield className="h-5 w-5" />
                  Authorized Pickup Persons
                </CardTitle>
                <CardDescription>
                  Non-guardian individuals authorized to pick up this student
                </CardDescription>
              </CardHeader>
              <CardContent>
                <AuthorizedPickupList studentId={authSelectedStudentId} />
              </CardContent>
            </Card>
          </div>
        )}
      </TabsContent>
    </Tabs>
  );
}
