"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Save } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
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

import { updateTermReportRemarks } from "@/actions/exams.action";

interface EditRemarksFormProps {
  reportId: string;
  initialData: {
    class_teacher_remark: string;
    headmaster_remark: string;
    conduct_grade: string;
    interest: string;
  };
}

const CONDUCT_GRADES = [
  { value: "Excellent", label: "Excellent" },
  { value: "Very Good", label: "Very Good" },
  { value: "Good", label: "Good" },
  { value: "Satisfactory", label: "Satisfactory" },
  { value: "Needs Improvement", label: "Needs Improvement" },
];

export function EditRemarksForm({ reportId, initialData }: EditRemarksFormProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const [formData, setFormData] = useState({
    class_teacher_remark: initialData.class_teacher_remark,
    headmaster_remark: initialData.headmaster_remark,
    conduct_grade: initialData.conduct_grade,
    interest: initialData.interest,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    startTransition(async () => {
      const result = await updateTermReportRemarks(reportId, {
        class_teacher_remark: formData.class_teacher_remark || undefined,
        headmaster_remark: formData.headmaster_remark || undefined,
        conduct_grade: formData.conduct_grade || undefined,
        interest: formData.interest || undefined,
      });

      if (result.success) {
        toast.success("Remarks updated successfully");
        router.push(`/exams/report-cards/${reportId}`);
        router.refresh();
      } else {
        toast.error("Failed to update remarks", { description: result.error });
      }
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-6">
        {/* Remarks */}
        <Card>
          <CardHeader>
            <CardTitle>Remarks</CardTitle>
            <CardDescription>
              Add teacher and headmaster remarks for this report card.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="class_teacher_remark">Class Teacher's Remark</Label>
              <Textarea
                id="class_teacher_remark"
                placeholder="Enter class teacher's remark..."
                value={formData.class_teacher_remark}
                onChange={(e) =>
                  setFormData({ ...formData, class_teacher_remark: e.target.value })
                }
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="headmaster_remark">Headmaster's Remark</Label>
              <Textarea
                id="headmaster_remark"
                placeholder="Enter headmaster's remark..."
                value={formData.headmaster_remark}
                onChange={(e) =>
                  setFormData({ ...formData, headmaster_remark: e.target.value })
                }
                rows={3}
              />
            </div>
          </CardContent>
        </Card>

        {/* Conduct & Interest */}
        <Card>
          <CardHeader>
            <CardTitle>Conduct & Interests</CardTitle>
            <CardDescription>
              Rate the student's conduct and note their interests or activities.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="conduct_grade">Conduct Grade</Label>
                <Select
                  value={formData.conduct_grade}
                  onValueChange={(value) =>
                    setFormData({ ...formData, conduct_grade: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select conduct grade" />
                  </SelectTrigger>
                  <SelectContent>
                    {CONDUCT_GRADES.map((grade) => (
                      <SelectItem key={grade.value} value={grade.value}>
                        {grade.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="interest">Interest / Activities</Label>
                <Input
                  id="interest"
                  placeholder="e.g., Football, Music, Art"
                  value={formData.interest}
                  onChange={(e) =>
                    setFormData({ ...formData, interest: e.target.value })
                  }
                />
              </div>
            </div>
          </CardContent>
          <CardFooter className="flex justify-end gap-2 border-t pt-6">
            <Button
              type="button"
              variant="outline"
              onClick={() => router.back()}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Save className="mr-2 h-4 w-4" />
              )}
              Save Changes
            </Button>
          </CardFooter>
        </Card>
      </div>
    </form>
  );
}
