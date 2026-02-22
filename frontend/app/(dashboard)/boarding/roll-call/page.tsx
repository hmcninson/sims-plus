"use client";

import { useEffect, useState, useTransition, useCallback } from "react";
import { format } from "date-fns";
import {
  ClipboardCheck,
  Loader2,
  Plus,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ShieldAlert,
  Eye,
  Users,
  Search,
  Check,
  ArrowRight,
  ArrowLeft,
  WifiOff,
  RefreshCw,
  CloudOff,
} from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import {
  getRollCalls,
  getRollCall,
  submitRollCall,
  getHouses,
  getAssignments,
} from "@/actions/boarding.action";
import { useNetworkStatus } from "@/hooks/use-network-status";
import { queueRollCall, syncPendingRollCalls, getRollCallQueueSize } from "@/lib/offline/sync";
import { useSession } from "@/components/providers/SessionProvider";
import type {
  BoardingRollCall,
  BoardingRollCallDetail,
  House,
  StudentBoardingDetail,
  RollCallType,
  RollCallEntryStatus,
  RollCallEntryCreate,
} from "@/types";

// =========================
// Status badge helpers
// =========================

const ROLL_CALL_STATUS_OPTIONS: {
  value: RollCallEntryStatus;
  label: string;
  icon: React.ElementType;
  bgColor: string;
  selectedClass: string;
}[] = [
  {
    value: "present",
    label: "Present",
    icon: CheckCircle2,
    bgColor: "bg-green-500",
    selectedClass:
      "!bg-green-100 !text-green-700 dark:!bg-green-900 dark:!text-green-300 ring-1 ring-green-400",
  },
  {
    value: "absent",
    label: "Absent",
    icon: XCircle,
    bgColor: "bg-red-500",
    selectedClass:
      "!bg-red-100 !text-red-700 dark:!bg-red-900 dark:!text-red-300 ring-1 ring-red-400",
  },
  {
    value: "sick_bay",
    label: "Sick Bay",
    icon: AlertTriangle,
    bgColor: "bg-orange-500",
    selectedClass:
      "!bg-orange-100 !text-orange-700 dark:!bg-orange-900 dark:!text-orange-300 ring-1 ring-orange-400",
  },
  {
    value: "exeat",
    label: "On Exeat",
    icon: ShieldAlert,
    bgColor: "bg-blue-500",
    selectedClass:
      "!bg-blue-100 !text-blue-700 dark:!bg-blue-900 dark:!text-blue-300 ring-1 ring-blue-400",
  },
  {
    value: "awol",
    label: "AWOL",
    icon: AlertTriangle,
    bgColor: "bg-purple-500",
    selectedClass:
      "!bg-purple-100 !text-purple-700 dark:!bg-purple-900 dark:!text-purple-300 ring-1 ring-purple-400",
  },
];

function getRollCallTypeBadge(type: string) {
  switch (type) {
    case "morning":
      return (
        <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200">
          Morning
        </Badge>
      );
    case "evening":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          Evening
        </Badge>
      );
    case "lights_out":
      return (
        <Badge className="bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200">
          Lights Out
        </Badge>
      );
    case "emergency":
      return <Badge variant="destructive">Emergency</Badge>;
    default:
      return <Badge variant="secondary">{type}</Badge>;
  }
}

function getEntryStatusBadge(status: RollCallEntryStatus) {
  switch (status) {
    case "present":
      return (
        <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
          Present
        </Badge>
      );
    case "absent":
      return (
        <Badge className="bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200">
          Absent
        </Badge>
      );
    case "sick_bay":
      return (
        <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200">
          Sick Bay
        </Badge>
      );
    case "exeat":
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
          On Exeat
        </Badge>
      );
    case "awol":
      return (
        <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200">
          AWOL
        </Badge>
      );
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function formatRollCallType(type: RollCallType): string {
  switch (type) {
    case "morning":
      return "Morning";
    case "evening":
      return "Evening";
    case "lights_out":
      return "Lights Out";
    case "emergency":
      return "Emergency";
    default:
      return type;
  }
}

// =========================
// Main Page Component
// =========================

export default function RollCallPage() {
  const { tenant } = useSession();
  const [isPending, startTransition] = useTransition();
  const [rollCalls, setRollCalls] = useState<BoardingRollCall[]>([]);
  const [houses, setHouses] = useState<House[]>([]);
  const [total, setTotal] = useState(0);
  const [filterHouse, setFilterHouse] = useState("all");
  const [filterType, setFilterType] = useState("all");

  // Sheet & Dialog state
  const [conductOpen, setConductOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedDetail, setSelectedDetail] = useState<BoardingRollCallDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  // Offline support
  const { isOnline } = useNetworkStatus();
  const [pendingCount, setPendingCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);

  // Poll pending queue size
  useEffect(() => {
    const updateCount = async () => {
      try {
        const count = await getRollCallQueueSize();
        setPendingCount(count);
      } catch {
        // Ignore
      }
    };
    updateCount();
    const interval = setInterval(updateCount, 5000);
    return () => clearInterval(interval);
  }, []);

  // Auto-sync when coming back online
  useEffect(() => {
    if (isOnline && pendingCount > 0) {
      handleSyncNow();
    }
  }, [isOnline]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSyncNow = async () => {
    if (!isOnline || isSyncing) return;
    setIsSyncing(true);
    try {
      const result = await syncPendingRollCalls(async (houseId, date, timeOfDay, records) => {
        const res = await submitRollCall({
          house_id: houseId,
          date,
          roll_call_type: timeOfDay as RollCallType,
          entries: records.map((r) => ({
            student_id: r.student_id,
            status: r.status as RollCallEntryStatus,
          })),
        });
        return res.success;
      });
      const count = await getRollCallQueueSize();
      setPendingCount(count);
      if (result.synced > 0) {
        toast.success(`Synced ${result.synced} pending roll call${result.synced !== 1 ? "s" : ""}`);
        loadRollCalls(); // Refresh the list
      }
      if (result.failed > 0) {
        toast.error(`${result.failed} roll call${result.failed !== 1 ? "s" : ""} failed to sync`);
      }
    } catch {
      toast.error("Failed to sync pending roll calls");
    } finally {
      setIsSyncing(false);
    }
  };

  // Load houses on mount
  useEffect(() => {
    startTransition(async () => {
      const housesResult = await getHouses({ pageSize: 100 });
      if (housesResult.success && housesResult.data) {
        setHouses(
          Array.isArray(housesResult.data)
            ? housesResult.data
            : (housesResult.data.items ?? [])
        );
      }
    });
  }, []);

  // Load roll calls
  const loadRollCalls = useCallback(() => {
    startTransition(async () => {
      const result = await getRollCalls({
        houseId: filterHouse !== "all" ? filterHouse : undefined,
        rollCallType: filterType !== "all" ? filterType : undefined,
        pageSize: 50,
      });
      if (result.success && result.data) {
        const data = result.data;
        const items = Array.isArray(data) ? data : (data.items ?? []);
        const count = Array.isArray(data) ? data.length : (data.total ?? 0);
        setRollCalls(items);
        setTotal(count);
      }
    });
  }, [filterHouse, filterType]);

  useEffect(() => {
    loadRollCalls();
  }, [loadRollCalls]);

  // View roll call detail
  const handleViewDetail = async (id: string) => {
    setIsLoadingDetail(true);
    setDetailOpen(true);
    setSelectedDetail(null);

    const result = await getRollCall(id);
    if (result.success && result.data) {
      setSelectedDetail(result.data);
    } else {
      toast.error(result.error || "Failed to load roll call details");
      setDetailOpen(false);
    }
    setIsLoadingDetail(false);
  };

  // After conducting roll call, close sheet and refresh
  const handleConductSuccess = () => {
    setConductOpen(false);
    loadRollCalls();
  };

  // Map house_id to name for display
  const getHouseName = (houseId: string): string => {
    const house = houses.find((h) => h.id === houseId);
    return house?.name ?? "--";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Roll Call</h1>
          <p className="text-muted-foreground">
            Conduct and view boarding roll calls
          </p>
        </div>
        <div className="flex items-center gap-2">
          {pendingCount > 0 && isOnline && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleSyncNow}
              disabled={isSyncing}
            >
              {isSyncing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Sync ({pendingCount})
            </Button>
          )}
          <Button onClick={() => setConductOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Conduct Roll Call
          </Button>
        </div>
      </div>

      {/* Offline Mode Banner */}
      {!isOnline && (
        <div className="flex items-center gap-3 rounded-lg border border-yellow-300 bg-yellow-50 px-4 py-3 text-sm text-yellow-800 dark:border-yellow-700 dark:bg-yellow-950 dark:text-yellow-200">
          <WifiOff className="h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">Offline Mode</p>
            <p className="text-yellow-700 dark:text-yellow-300">
              You are currently offline. Roll calls will be saved locally and synced when your connection is restored.
            </p>
          </div>
        </div>
      )}

      {/* Pending Sync Banner */}
      {pendingCount > 0 && isOnline && (
        <div className="flex items-center gap-3 rounded-lg border border-blue-300 bg-blue-50 px-4 py-3 text-sm text-blue-800 dark:border-blue-700 dark:bg-blue-950 dark:text-blue-200">
          <CloudOff className="h-4 w-4 shrink-0" />
          <p>
            {pendingCount} roll call{pendingCount !== 1 ? "s" : ""} pending sync.
          </p>
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 sm:flex-row">
            <Select value={filterHouse} onValueChange={setFilterHouse}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue placeholder="House" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Houses</SelectItem>
                {houses.map((h) => (
                  <SelectItem key={h.id} value={h.id}>
                    {h.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger className="w-full sm:w-[180px]">
                <SelectValue placeholder="Type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="morning">Morning</SelectItem>
                <SelectItem value="evening">Evening</SelectItem>
                <SelectItem value="lights_out">Lights Out</SelectItem>
                <SelectItem value="emergency">Emergency</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Roll Calls List */}
      <Card>
        <CardHeader>
          <CardTitle>Roll Calls</CardTitle>
          <CardDescription>
            {total} roll call{total !== 1 ? "s" : ""}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isPending ? (
            <div className="flex h-[200px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : rollCalls.length > 0 ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>House</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="hidden sm:table-cell">Notes</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rollCalls.map((rc) => (
                    <TableRow key={rc.id}>
                      <TableCell className="font-medium">
                        {new Date(rc.date).toLocaleDateString("en-GB")}
                      </TableCell>
                      <TableCell>{getHouseName(rc.house_id)}</TableCell>
                      <TableCell>{getRollCallTypeBadge(rc.roll_call_type)}</TableCell>
                      <TableCell className="hidden max-w-[250px] truncate sm:table-cell">
                        {rc.notes || "--"}
                      </TableCell>
                      <TableCell>
                        {new Date(rc.created_at).toLocaleDateString("en-GB")}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewDetail(rc.id)}
                        >
                          <Eye className="mr-1 h-4 w-4" />
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
              <ClipboardCheck className="h-12 w-12" />
              <p className="font-medium">No roll calls recorded yet</p>
              <p className="max-w-md text-center text-sm">
                Click &quot;Conduct Roll Call&quot; to record student attendance
                for a boarding house.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Conduct Roll Call Sheet */}
      <ConductRollCallSheet
        open={conductOpen}
        onOpenChange={setConductOpen}
        houses={houses}
        onSuccess={handleConductSuccess}
        isOnline={isOnline}
        onOfflineQueue={() => setPendingCount((c) => c + 1)}
      />

      {/* Roll Call Detail Dialog */}
      <RollCallDetailDialog
        open={detailOpen}
        onOpenChange={setDetailOpen}
        detail={selectedDetail}
        isLoading={isLoadingDetail}
      />
    </div>
  );
}

// =========================
// Conduct Roll Call Sheet
// =========================

interface ConductRollCallSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  houses: House[];
  onSuccess: () => void;
  isOnline: boolean;
  onOfflineQueue: () => void;
}

function ConductRollCallSheet({
  open,
  onOpenChange,
  houses,
  onSuccess,
  isOnline,
  onOfflineQueue,
}: ConductRollCallSheetProps) {
  const { tenant } = useSession();
  // Step management: 1 = Select house/type, 2 = Mark students
  const [step, setStep] = useState<1 | 2>(1);

  // Step 1 form state
  const [selectedHouseId, setSelectedHouseId] = useState("");
  const [rollCallType, setRollCallType] = useState<RollCallType>("morning");
  const [rollCallDate, setRollCallDate] = useState(format(new Date(), "yyyy-MM-dd"));
  const [notes, setNotes] = useState("");

  // Step 2 state
  const [students, setStudents] = useState<StudentBoardingDetail[]>([]);
  const [statusData, setStatusData] = useState<Record<string, RollCallEntryStatus>>({});
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Reset everything when sheet closes
  useEffect(() => {
    if (!open) {
      setStep(1);
      setSelectedHouseId("");
      setRollCallType("morning");
      setRollCallDate(format(new Date(), "yyyy-MM-dd"));
      setNotes("");
      setStudents([]);
      setStatusData({});
      setSearchQuery("");
    }
  }, [open]);

  // Proceed to step 2: load students for the selected house
  const handleNext = async () => {
    if (!selectedHouseId) {
      toast.error("Please select a house");
      return;
    }
    if (!rollCallDate) {
      toast.error("Please select a date");
      return;
    }

    setIsLoadingStudents(true);
    setStep(2);

    const result = await getAssignments({
      houseId: selectedHouseId,
      status: "active",
      pageSize: 500,
    });

    if (result.success && result.data) {
      const items = Array.isArray(result.data)
        ? result.data
        : (result.data.items ?? []);
      setStudents(items);

      // Default all students to "present"
      const defaults: Record<string, RollCallEntryStatus> = {};
      items.forEach((s) => {
        defaults[s.student_id] = "present";
      });
      setStatusData(defaults);
    } else {
      toast.error(result.error || "Failed to load students");
      setStep(1);
    }

    setIsLoadingStudents(false);
  };

  // Handle individual status change
  const handleStatusChange = (studentId: string, status: RollCallEntryStatus) => {
    setStatusData((prev) => ({
      ...prev,
      [studentId]: status,
    }));
  };

  // Mark all students with a status
  const handleMarkAll = (status: RollCallEntryStatus) => {
    const newData: Record<string, RollCallEntryStatus> = {};
    students.forEach((s) => {
      newData[s.student_id] = status;
    });
    setStatusData(newData);
  };

  // Submit roll call (with offline fallback)
  const handleSubmit = async () => {
    if (students.length === 0) {
      toast.error("No students to mark");
      return;
    }

    const entries: RollCallEntryCreate[] = Object.entries(statusData).map(
      ([studentId, status]) => ({
        student_id: studentId,
        status,
      })
    );

    if (entries.length === 0) {
      toast.error("Please mark at least one student");
      return;
    }

    setIsSubmitting(true);

    if (!isOnline) {
      // Queue offline
      try {
        await queueRollCall(
          selectedHouseId,
          rollCallDate,
          rollCallType,
          entries.map((e) => ({ student_id: e.student_id, status: e.status })),
          tenant.id
        );
        onOfflineQueue();
        toast.info("Saved locally -- will sync when online", {
          description: `Roll call for ${entries.length} students queued`,
        });
        onSuccess();
      } catch {
        toast.error("Failed to save offline. Please try again.");
      }
      setIsSubmitting(false);
      return;
    }

    const result = await submitRollCall({
      house_id: selectedHouseId,
      date: rollCallDate,
      roll_call_type: rollCallType,
      notes: notes.trim() || undefined,
      entries,
    });

    if (result.success) {
      toast.success("Roll call submitted successfully");
      onSuccess();
    } else {
      // Try offline fallback on failure
      try {
        await queueRollCall(
          selectedHouseId,
          rollCallDate,
          rollCallType,
          entries.map((e) => ({ student_id: e.student_id, status: e.status })),
          tenant.id
        );
        onOfflineQueue();
        toast.info("Saved locally -- will sync when online", {
          description: result.error || "Network error occurred",
        });
        onSuccess();
      } catch {
        toast.error(result.error || "Failed to submit roll call");
      }
    }

    setIsSubmitting(false);
  };

  // Filter students by search
  const filteredStudents = students.filter((s) => {
    if (!searchQuery.trim()) return true;
    const name = (s.student_name ?? "").toLowerCase();
    return name.includes(searchQuery.toLowerCase());
  });

  // Compute summary counts
  const presentCount = Object.values(statusData).filter((s) => s === "present").length;
  const absentCount = Object.values(statusData).filter((s) => s === "absent").length;
  const sickBayCount = Object.values(statusData).filter((s) => s === "sick_bay").length;
  const exeatCount = Object.values(statusData).filter((s) => s === "exeat").length;
  const awolCount = Object.values(statusData).filter((s) => s === "awol").length;

  const selectedHouse = houses.find((h) => h.id === selectedHouseId);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-2xl overflow-y-auto" side="right">
        <SheetHeader>
          <SheetTitle>Conduct Roll Call</SheetTitle>
          <SheetDescription>
            {step === 1
              ? "Select the house, type, and date for this roll call."
              : `Mark attendance for ${students.length} student${students.length !== 1 ? "s" : ""} in ${selectedHouse?.name ?? "house"}.`}
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Step indicator */}
          <div className="flex items-center gap-3">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                step === 1
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              {step > 1 ? <Check className="h-4 w-4" /> : "1"}
            </div>
            <span className={`text-sm ${step === 1 ? "font-medium" : "text-muted-foreground"}`}>
              Setup
            </span>
            <Separator className="flex-1" />
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                step === 2
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              2
            </div>
            <span className={`text-sm ${step === 2 ? "font-medium" : "text-muted-foreground"}`}>
              Mark Students
            </span>
          </div>

          <Separator />

          {/* Step 1: Setup */}
          {step === 1 && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="rc-house">House</Label>
                <Select value={selectedHouseId} onValueChange={setSelectedHouseId}>
                  <SelectTrigger id="rc-house" className="w-full">
                    <SelectValue placeholder="Select a house" />
                  </SelectTrigger>
                  <SelectContent>
                    {houses.map((h) => (
                      <SelectItem key={h.id} value={h.id}>
                        {h.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="rc-type">Roll Call Type</Label>
                <Select
                  value={rollCallType}
                  onValueChange={(v) => setRollCallType(v as RollCallType)}
                >
                  <SelectTrigger id="rc-type" className="w-full">
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="morning">Morning</SelectItem>
                    <SelectItem value="evening">Evening</SelectItem>
                    <SelectItem value="lights_out">Lights Out</SelectItem>
                    <SelectItem value="emergency">Emergency</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="rc-date">Date</Label>
                <Input
                  id="rc-date"
                  type="date"
                  value={rollCallDate}
                  onChange={(e) => setRollCallDate(e.target.value)}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="rc-notes">Notes (optional)</Label>
                <Textarea
                  id="rc-notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Any notes for this roll call..."
                  rows={3}
                />
              </div>

              <div className="flex justify-end pt-4">
                <Button onClick={handleNext} disabled={!selectedHouseId || !rollCallDate}>
                  Next: Mark Students
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            </div>
          )}

          {/* Step 2: Mark Students */}
          {step === 2 && (
            <div className="space-y-4">
              {/* Roll call info summary */}
              <div className="rounded-md border bg-muted/50 p-3">
                <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                  <span>
                    <span className="text-muted-foreground">House:</span>{" "}
                    <span className="font-medium">{selectedHouse?.name}</span>
                  </span>
                  <span>
                    <span className="text-muted-foreground">Type:</span>{" "}
                    <span className="font-medium">{formatRollCallType(rollCallType)}</span>
                  </span>
                  <span>
                    <span className="text-muted-foreground">Date:</span>{" "}
                    <span className="font-medium">
                      {new Date(rollCallDate).toLocaleDateString("en-GB")}
                    </span>
                  </span>
                </div>
              </div>

              {/* Summary counts */}
              {students.length > 0 && (
                <div className="grid grid-cols-5 gap-2">
                  <div className="rounded-md border bg-green-50 p-2 text-center dark:bg-green-950">
                    <div className="text-lg font-bold text-green-700 dark:text-green-300">
                      {presentCount}
                    </div>
                    <div className="text-xs text-green-600 dark:text-green-400">Present</div>
                  </div>
                  <div className="rounded-md border bg-red-50 p-2 text-center dark:bg-red-950">
                    <div className="text-lg font-bold text-red-700 dark:text-red-300">
                      {absentCount}
                    </div>
                    <div className="text-xs text-red-600 dark:text-red-400">Absent</div>
                  </div>
                  <div className="rounded-md border bg-orange-50 p-2 text-center dark:bg-orange-950">
                    <div className="text-lg font-bold text-orange-700 dark:text-orange-300">
                      {sickBayCount}
                    </div>
                    <div className="text-xs text-orange-600 dark:text-orange-400">Sick Bay</div>
                  </div>
                  <div className="rounded-md border bg-blue-50 p-2 text-center dark:bg-blue-950">
                    <div className="text-lg font-bold text-blue-700 dark:text-blue-300">
                      {exeatCount}
                    </div>
                    <div className="text-xs text-blue-600 dark:text-blue-400">Exeat</div>
                  </div>
                  <div className="rounded-md border bg-purple-50 p-2 text-center dark:bg-purple-950">
                    <div className="text-lg font-bold text-purple-700 dark:text-purple-300">
                      {awolCount}
                    </div>
                    <div className="text-xs text-purple-600 dark:text-purple-400">AWOL</div>
                  </div>
                </div>
              )}

              {/* Quick actions & search */}
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleMarkAll("present")}
                >
                  <Check className="mr-1 h-4 w-4" />
                  Mark All Present
                </Button>
                <div className="relative w-full sm:w-[260px]">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Search students..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9"
                  />
                </div>
              </div>

              {/* Student list */}
              {isLoadingStudents ? (
                <div className="flex h-[200px] items-center justify-center">
                  <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : students.length === 0 ? (
                <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
                  <Users className="h-12 w-12" />
                  <p className="font-medium">No students found</p>
                  <p className="max-w-xs text-center text-sm">
                    There are no active boarding students assigned to this house.
                  </p>
                </div>
              ) : filteredStudents.length === 0 ? (
                <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
                  <Search className="h-12 w-12" />
                  <p className="text-sm">
                    No students match &quot;{searchQuery}&quot;
                  </p>
                </div>
              ) : (
                <ScrollArea className="h-[400px]">
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Student</TableHead>
                          <TableHead className="hidden sm:table-cell">
                            Dormitory
                          </TableHead>
                          <TableHead className="text-center">Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {filteredStudents.map((student) => {
                          const currentStatus = statusData[student.student_id];
                          return (
                            <TableRow key={student.id}>
                              <TableCell>
                                <div className="font-medium text-sm">
                                  {student.student_name ?? `Student ${student.student_id.slice(0, 8)}`}
                                </div>
                              </TableCell>
                              <TableCell className="hidden text-sm text-muted-foreground sm:table-cell">
                                {student.dormitory_name ?? "--"}
                              </TableCell>
                              <TableCell>
                                <ToggleGroup
                                  type="single"
                                  value={currentStatus || ""}
                                  onValueChange={(value) => {
                                    if (value) {
                                      handleStatusChange(
                                        student.student_id,
                                        value as RollCallEntryStatus
                                      );
                                    }
                                  }}
                                  className="justify-center"
                                >
                                  {ROLL_CALL_STATUS_OPTIONS.map((option) => {
                                    const Icon = option.icon;
                                    const isSelected = currentStatus === option.value;
                                    return (
                                      <ToggleGroupItem
                                        key={option.value}
                                        value={option.value}
                                        aria-label={option.label}
                                        className={`h-7 w-7 p-0 rounded-md ${
                                          isSelected
                                            ? option.selectedClass
                                            : "hover:bg-muted"
                                        }`}
                                        title={option.label}
                                      >
                                        <Icon
                                          className={`h-3.5 w-3.5 ${
                                            isSelected ? "" : "text-muted-foreground"
                                          }`}
                                        />
                                      </ToggleGroupItem>
                                    );
                                  })}
                                </ToggleGroup>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                </ScrollArea>
              )}

              {/* Legend */}
              {students.length > 0 && (
                <div className="flex flex-wrap gap-3 text-xs">
                  {ROLL_CALL_STATUS_OPTIONS.map((option) => {
                    const Icon = option.icon;
                    return (
                      <div key={option.value} className="flex items-center gap-1">
                        <div className={`rounded p-0.5 ${option.bgColor}`}>
                          <Icon className="h-3 w-3 text-white" />
                        </div>
                        <span className="text-muted-foreground">{option.label}</span>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Navigation */}
              <Separator />
              <div className="flex items-center justify-between">
                <Button variant="outline" onClick={() => setStep(1)}>
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back
                </Button>
                <Button
                  onClick={handleSubmit}
                  disabled={isSubmitting || students.length === 0}
                >
                  {isSubmitting ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <ClipboardCheck className="mr-2 h-4 w-4" />
                  )}
                  {isSubmitting ? "Submitting..." : "Submit Roll Call"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

// =========================
// Roll Call Detail Dialog
// =========================

interface RollCallDetailDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  detail: BoardingRollCallDetail | null;
  isLoading: boolean;
}

function RollCallDetailDialog({
  open,
  onOpenChange,
  detail,
  isLoading,
}: RollCallDetailDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Roll Call Details</DialogTitle>
          <DialogDescription>
            {detail
              ? `${formatRollCallType(detail.roll_call_type)} roll call on ${new Date(detail.date).toLocaleDateString("en-GB")}`
              : "Loading roll call details..."}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex h-[200px] items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : detail ? (
          <div className="space-y-6">
            {/* Summary info */}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">House</p>
                <p className="font-medium">{detail.house_name ?? "--"}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Conducted By</p>
                <p className="font-medium">{detail.conducted_by_name ?? "--"}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Type</p>
                <div>{getRollCallTypeBadge(detail.roll_call_type)}</div>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Date</p>
                <p className="font-medium">
                  {new Date(detail.date).toLocaleDateString("en-GB", {
                    weekday: "long",
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </p>
              </div>
              {detail.notes && (
                <div className="space-y-1 sm:col-span-2">
                  <p className="text-sm text-muted-foreground">Notes</p>
                  <p className="text-sm">{detail.notes}</p>
                </div>
              )}
            </div>

            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-md border p-3 text-center">
                <div className="text-2xl font-bold">{detail.total_count}</div>
                <div className="text-xs text-muted-foreground">Total</div>
              </div>
              <div className="rounded-md border bg-green-50 p-3 text-center dark:bg-green-950">
                <div className="text-2xl font-bold text-green-700 dark:text-green-300">
                  {detail.present_count}
                </div>
                <div className="text-xs text-green-600 dark:text-green-400">
                  Present
                </div>
              </div>
              <div className="rounded-md border bg-red-50 p-3 text-center dark:bg-red-950">
                <div className="text-2xl font-bold text-red-700 dark:text-red-300">
                  {detail.absent_count}
                </div>
                <div className="text-xs text-red-600 dark:text-red-400">
                  Absent
                </div>
              </div>
            </div>

            {/* Attendance rate */}
            {detail.total_count > 0 && (
              <div className="rounded-md border p-3">
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Attendance Rate</span>
                  <span className="font-medium">
                    {Math.round((detail.present_count / detail.total_count) * 100)}%
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-green-500 transition-all"
                    style={{
                      width: `${Math.round((detail.present_count / detail.total_count) * 100)}%`,
                    }}
                  />
                </div>
              </div>
            )}

            <Separator />

            {/* Entries list */}
            <div>
              <h4 className="mb-3 text-sm font-medium">
                Student Entries ({detail.entries.length})
              </h4>
              {detail.entries.length > 0 ? (
                <ScrollArea className="h-[300px]">
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Student</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="hidden sm:table-cell">
                            Notes
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detail.entries.map((entry) => (
                          <TableRow key={entry.id}>
                            <TableCell className="font-medium">
                              {entry.student_name ?? `Student ${entry.student_id.slice(0, 8)}`}
                            </TableCell>
                            <TableCell>
                              {getEntryStatusBadge(entry.status)}
                            </TableCell>
                            <TableCell className="hidden max-w-[200px] truncate text-sm text-muted-foreground sm:table-cell">
                              {entry.notes || "--"}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </ScrollArea>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No entries recorded for this roll call.
                </p>
              )}
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
