"use client";

import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { format, addDays, subDays } from "date-fns";
import {
  Loader2,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  Utensils,
  Baby,
  AlertTriangle,
  Sparkles,
  Save,
  Calendar,
  Smile,
  Frown,
  Meh,
  Zap,
  CloudSun,
  ThermometerSun,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar as CalendarPicker } from "@/components/ui/calendar";
import { cn } from "@/lib/utils";

import { StudentCombobox } from "@/components/preschool";
import { getStudents } from "@/actions/students.action";
import {
  getDailyLog,
  createDailyLog,
  updateDailyLog,
} from "@/actions/preschool.action";
import type {
  Class,
  DailyActivityLog,
  DailyActivityLogCreate,
  MoodType,
  MealAmount,
  NapQuality,
  MealEntry,
  Student,
} from "@/types";

interface DailyLogsManagerProps {
  classes: Class[];
}

const MOODS: { value: MoodType; label: string; icon: React.ReactNode; color: string }[] = [
  { value: "happy", label: "Happy", icon: <Smile className="h-4 w-4" />, color: "text-green-600" },
  { value: "excited", label: "Excited", icon: <Zap className="h-4 w-4" />, color: "text-amber-600" },
  { value: "calm", label: "Calm", icon: <CloudSun className="h-4 w-4" />, color: "text-blue-600" },
  { value: "tired", label: "Tired", icon: <Meh className="h-4 w-4" />, color: "text-gray-600" },
  { value: "upset", label: "Upset", icon: <Frown className="h-4 w-4" />, color: "text-red-600" },
  { value: "sick", label: "Sick", icon: <ThermometerSun className="h-4 w-4" />, color: "text-purple-600" },
];

const MEAL_AMOUNTS: { value: MealAmount; label: string; color: string }[] = [
  { value: "none", label: "None", color: "bg-red-100 text-red-800" },
  { value: "little", label: "A Little", color: "bg-amber-100 text-amber-800" },
  { value: "some", label: "Some", color: "bg-yellow-100 text-yellow-800" },
  { value: "most", label: "Most", color: "bg-lime-100 text-lime-800" },
  { value: "all", label: "All", color: "bg-green-100 text-green-800" },
];

const NAP_QUALITIES: { value: NapQuality; label: string }[] = [
  { value: "good", label: "Good" },
  { value: "restless", label: "Restless" },
  { value: "didnt_sleep", label: "Didn't Sleep" },
];

const MEAL_TYPES = ["Breakfast", "Morning Snack", "Lunch", "Afternoon Snack"];

const DEFAULT_ACTIVITIES = [
  "Circle Time",
  "Free Play",
  "Outdoor Play",
  "Arts & Crafts",
  "Music",
  "Story Time",
  "Puzzles",
  "Building Blocks",
  "Dramatic Play",
  "Sensory Play",
];

export function DailyLogsManager({ classes }: DailyLogsManagerProps) {
  // Selection state
  const [selectedClassId, setSelectedClassId] = useState<string>("");
  const [selectedStudentId, setSelectedStudentId] = useState<string>("");
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());

  // Data state
  const [students, setStudents] = useState<Student[]>([]);
  const [existingLog, setExistingLog] = useState<DailyActivityLog | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    arrival_time: "",
    arrival_mood: "" as MoodType | "",
    departure_time: "",
    departure_mood: "" as MoodType | "",
    meals: [] as MealEntry[],
    nap_start: "",
    nap_end: "",
    nap_quality: "" as NapQuality | "",
    diaper_changes: 0,
    potty_successes: 0,
    accidents: 0,
    activities: [] as string[],
    notes: "",
    highlights: "",
  });

  // Loading state
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);
  const [isLoadingLog, setIsLoadingLog] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Fetch students when class changes
  useEffect(() => {
    async function fetchStudents() {
      if (!selectedClassId) {
        setStudents([]);
        setSelectedStudentId("");
        return;
      }

      setIsLoadingStudents(true);
      try {
        const result = await getStudents({
          class_id: selectedClassId,
          page_size: 100,
        });

        if (result.success && result.data) {
          setStudents(
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
        } else {
          setStudents([]);
        }
      } catch {
        setStudents([]);
      } finally {
        setIsLoadingStudents(false);
      }
    }

    fetchStudents();
  }, [selectedClassId]);

  // Fetch existing log when student or date changes
  const fetchLog = useCallback(async () => {
    if (!selectedStudentId) {
      setExistingLog(null);
      resetForm();
      return;
    }

    setIsLoadingLog(true);
    try {
      const dateStr = format(selectedDate, "yyyy-MM-dd");
      const result = await getDailyLog(selectedStudentId, dateStr);

      if (result.success && result.data) {
        setExistingLog(result.data);
        // Populate form with existing data
        setFormData({
          arrival_time: result.data.arrival_time || "",
          arrival_mood: result.data.arrival_mood || "",
          departure_time: result.data.departure_time || "",
          departure_mood: result.data.departure_mood || "",
          meals: result.data.meals || [],
          nap_start: result.data.nap_start || "",
          nap_end: result.data.nap_end || "",
          nap_quality: result.data.nap_quality || "",
          diaper_changes: result.data.diaper_changes || 0,
          potty_successes: result.data.potty_successes || 0,
          accidents: result.data.accidents || 0,
          activities: result.data.activities || [],
          notes: result.data.notes || "",
          highlights: result.data.highlights || "",
        });
      } else {
        setExistingLog(null);
        resetForm();
      }
    } catch {
      setExistingLog(null);
      resetForm();
    } finally {
      setIsLoadingLog(false);
    }
  }, [selectedStudentId, selectedDate]);

  useEffect(() => {
    fetchLog();
  }, [fetchLog]);

  // Reset form
  const resetForm = () => {
    setFormData({
      arrival_time: "",
      arrival_mood: "",
      departure_time: "",
      departure_mood: "",
      meals: [],
      nap_start: "",
      nap_end: "",
      nap_quality: "",
      diaper_changes: 0,
      potty_successes: 0,
      accidents: 0,
      activities: [],
      notes: "",
      highlights: "",
    });
  };

  // Handle meal update
  const updateMeal = (type: string, amount: MealAmount) => {
    setFormData((prev) => {
      const existingMealIndex = prev.meals.findIndex((m) => m.type === type);
      const newMeals = [...prev.meals];

      if (existingMealIndex >= 0) {
        newMeals[existingMealIndex] = { ...newMeals[existingMealIndex], amount };
      } else {
        newMeals.push({ type, amount });
      }

      return { ...prev, meals: newMeals };
    });
  };

  // Get meal amount for a type
  const getMealAmount = (type: string): MealAmount | undefined => {
    return formData.meals.find((m) => m.type === type)?.amount;
  };

  // Toggle activity
  const toggleActivity = (activity: string) => {
    setFormData((prev) => {
      if (prev.activities.includes(activity)) {
        return { ...prev, activities: prev.activities.filter((a) => a !== activity) };
      } else {
        return { ...prev, activities: [...prev.activities, activity] };
      }
    });
  };

  // Handle save
  const handleSave = async () => {
    if (!selectedStudentId) {
      toast.error("Please select a student");
      return;
    }

    setIsSaving(true);
    try {
      const logData: DailyActivityLogCreate = {
        student_id: selectedStudentId,
        log_date: format(selectedDate, "yyyy-MM-dd"),
        arrival_time: formData.arrival_time || undefined,
        arrival_mood: (formData.arrival_mood as MoodType) || undefined,
        departure_time: formData.departure_time || undefined,
        departure_mood: (formData.departure_mood as MoodType) || undefined,
        meals: formData.meals.length > 0 ? formData.meals : undefined,
        nap_start: formData.nap_start || undefined,
        nap_end: formData.nap_end || undefined,
        nap_quality: (formData.nap_quality as NapQuality) || undefined,
        diaper_changes: formData.diaper_changes || undefined,
        potty_successes: formData.potty_successes || undefined,
        accidents: formData.accidents || undefined,
        activities: formData.activities.length > 0 ? formData.activities : undefined,
        notes: formData.notes || undefined,
        highlights: formData.highlights || undefined,
      };

      let result;
      if (existingLog) {
        result = await updateDailyLog(existingLog.id, logData);
      } else {
        result = await createDailyLog(logData);
      }

      if (result.success) {
        toast.success(existingLog ? "Daily log updated" : "Daily log created");
        fetchLog();
      } else {
        toast.error(result.error || "Failed to save daily log");
      }
    } catch {
      toast.error("Failed to save daily log");
    } finally {
      setIsSaving(false);
    }
  };

  // Get selected student
  const selectedStudent = students.find((s) => s.id === selectedStudentId);

  // No classes
  if (classes.length === 0) {
    return (
      <Alert>
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>No Preschool Classes</AlertTitle>
        <AlertDescription>
          There are no preschool classes available. Please create preschool classes first.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Selection Controls */}
      <div className="flex flex-wrap items-end gap-4">
        <div className="w-full sm:w-auto">
          <Label className="mb-1.5 block text-sm font-medium">Class</Label>
          <Select value={selectedClassId} onValueChange={setSelectedClassId}>
            <SelectTrigger className="w-full sm:w-[200px]">
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

        <div className="w-full sm:w-auto">
          <Label className="mb-1.5 block text-sm font-medium">Student</Label>
          <StudentCombobox
            students={students}
            value={selectedStudentId}
            onValueChange={setSelectedStudentId}
            placeholder="Select student..."
            disabled={!selectedClassId}
            isLoading={isLoadingStudents}
          />
        </div>

        {selectedStudentId && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              onClick={() => setSelectedDate(subDays(selectedDate, 1))}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>

            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" className="w-full sm:w-[180px] justify-start gap-2">
                  <Calendar className="h-4 w-4" />
                  {format(selectedDate, "MMM d, yyyy")}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <CalendarPicker
                  mode="single"
                  selected={selectedDate}
                  onSelect={(date) => date && setSelectedDate(date)}
                  initialFocus
                />
              </PopoverContent>
            </Popover>

            <Button
              variant="outline"
              size="icon"
              onClick={() => setSelectedDate(addDays(selectedDate, 1))}
              disabled={selectedDate >= new Date()}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      {/* Daily Log Form */}
      {selectedStudentId ? (
        isLoadingLog ? (
          <div className="flex h-96 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Header with Save Button */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">
                  {selectedStudent?.first_name} {selectedStudent?.last_name}
                </h2>
                <p className="text-sm text-muted-foreground">
                  {format(selectedDate, "EEEE, MMMM d, yyyy")}
                  {existingLog && (
                    <Badge variant="secondary" className="ml-2">
                      Log exists
                    </Badge>
                  )}
                </p>
              </div>
              <Button onClick={handleSave} disabled={isSaving} className="gap-2">
                {isSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                Save Log
              </Button>
            </div>

            <div className="grid gap-6 md:grid-cols-2">
              {/* Arrival & Departure */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Sun className="h-4 w-4 text-amber-500" />
                    Arrival & Departure
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Arrival Time</Label>
                      <Input
                        type="time"
                        value={formData.arrival_time}
                        onChange={(e) =>
                          setFormData({ ...formData, arrival_time: e.target.value })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Arrival Mood</Label>
                      <Select
                        value={formData.arrival_mood}
                        onValueChange={(value) =>
                          setFormData({ ...formData, arrival_mood: value as MoodType })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select..." />
                        </SelectTrigger>
                        <SelectContent>
                          {MOODS.map((mood) => (
                            <SelectItem key={mood.value} value={mood.value}>
                              <div className="flex items-center gap-2">
                                <span className={mood.color}>{mood.icon}</span>
                                {mood.label}
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Departure Time</Label>
                      <Input
                        type="time"
                        value={formData.departure_time}
                        onChange={(e) =>
                          setFormData({ ...formData, departure_time: e.target.value })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Departure Mood</Label>
                      <Select
                        value={formData.departure_mood}
                        onValueChange={(value) =>
                          setFormData({ ...formData, departure_mood: value as MoodType })
                        }
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Select..." />
                        </SelectTrigger>
                        <SelectContent>
                          {MOODS.map((mood) => (
                            <SelectItem key={mood.value} value={mood.value}>
                              <div className="flex items-center gap-2">
                                <span className={mood.color}>{mood.icon}</span>
                                {mood.label}
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Nap Time */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Moon className="h-4 w-4 text-indigo-500" />
                    Nap Time
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Start Time</Label>
                      <Input
                        type="time"
                        value={formData.nap_start}
                        onChange={(e) =>
                          setFormData({ ...formData, nap_start: e.target.value })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>End Time</Label>
                      <Input
                        type="time"
                        value={formData.nap_end}
                        onChange={(e) =>
                          setFormData({ ...formData, nap_end: e.target.value })
                        }
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Sleep Quality</Label>
                    <Select
                      value={formData.nap_quality}
                      onValueChange={(value) =>
                        setFormData({ ...formData, nap_quality: value as NapQuality })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="How did they sleep?" />
                      </SelectTrigger>
                      <SelectContent>
                        {NAP_QUALITIES.map((quality) => (
                          <SelectItem key={quality.value} value={quality.value}>
                            {quality.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </CardContent>
              </Card>

              {/* Meals */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Utensils className="h-4 w-4 text-orange-500" />
                    Meals
                  </CardTitle>
                  <CardDescription>
                    Tap to select how much was eaten
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {MEAL_TYPES.map((mealType) => (
                    <div key={mealType} className="space-y-2">
                      <Label className="text-sm">{mealType}</Label>
                      <div className="flex flex-wrap gap-2">
                        {MEAL_AMOUNTS.map((amount) => {
                          const isSelected = getMealAmount(mealType) === amount.value;
                          return (
                            <Button
                              key={amount.value}
                              type="button"
                              variant="outline"
                              size="sm"
                              className={cn(
                                "h-8",
                                isSelected && amount.color
                              )}
                              onClick={() => updateMeal(mealType, amount.value)}
                            >
                              {amount.label}
                            </Button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>

              {/* Potty/Diaper */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Baby className="h-4 w-4 text-pink-500" />
                    Potty Training / Diaper
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <Label>Diaper Changes</Label>
                      <Input
                        type="number"
                        min="0"
                        value={formData.diaper_changes}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            diaper_changes: parseInt(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Potty Successes</Label>
                      <Input
                        type="number"
                        min="0"
                        value={formData.potty_successes}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            potty_successes: parseInt(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Accidents</Label>
                      <Input
                        type="number"
                        min="0"
                        value={formData.accidents}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            accidents: parseInt(e.target.value) || 0,
                          })
                        }
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Activities */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Sparkles className="h-4 w-4 text-purple-500" />
                  Activities
                </CardTitle>
                <CardDescription>
                  Select activities the child participated in today
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {DEFAULT_ACTIVITIES.map((activity) => {
                    const isSelected = formData.activities.includes(activity);
                    return (
                      <Button
                        key={activity}
                        type="button"
                        variant={isSelected ? "default" : "outline"}
                        size="sm"
                        onClick={() => toggleActivity(activity)}
                      >
                        {activity}
                      </Button>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Notes & Highlights */}
            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Notes</CardTitle>
                  <CardDescription>
                    General notes about the day
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Textarea
                    placeholder="Any additional notes..."
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    rows={4}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Highlights</CardTitle>
                  <CardDescription>
                    Special moments to share with parents
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Textarea
                    placeholder="Something special that happened today..."
                    value={formData.highlights}
                    onChange={(e) => setFormData({ ...formData, highlights: e.target.value })}
                    rows={4}
                  />
                </CardContent>
              </Card>
            </div>
          </div>
        )
      ) : (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <Calendar className="h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-medium">Select a Student</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Choose a class and student to log their daily activities
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
