"use client";

/**
 * SIMS Plus - Teacher Profile Page
 *
 * Shows the teacher's profile information and allows editing
 * of phone number. Photo upload is referenced but delegated
 * to the media upload endpoint.
 */

import { useEffect, useState, useTransition } from "react";
import {
  AlertCircle,
  Loader2,
  Save,
  User,
  Phone,
  Mail,
  Briefcase,
  Building2,
  BookOpen,
  Star,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { getTeacherProfile, updateTeacherProfile } from "@/actions/teacher.action";
import type { TeacherProfile } from "@/types/teacher.type";
import { getInitials } from "@/lib/format";
import { toast } from "sonner";

export default function TeacherProfilePage() {
  const [profile, setProfile] = useState<TeacherProfile | null>(null);
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    async function load() {
      const result = await getTeacherProfile();
      if (result.success) {
        setProfile(result.data);
        setPhone(result.data.phone || "");
      } else {
        setError(result.error);
      }
      setLoading(false);
    }
    load();
  }, []);

  const handleSave = () => {
    startTransition(async () => {
      const result = await updateTeacherProfile({ phone: phone.trim() });
      if (result.success) {
        setProfile(result.data);
        toast.success("Profile updated");
      } else {
        toast.error(result.error);
      }
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error || "Failed to load profile"}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Profile</h1>
        <p className="text-muted-foreground">View and update your profile information</p>
      </div>

      {/* Profile Header */}
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center gap-4">
            <Avatar className="h-20 w-20">
              <AvatarFallback className="bg-primary/10 text-primary text-2xl">
                {getInitials(`${profile.first_name} ${profile.last_name}`)}
              </AvatarFallback>
            </Avatar>
            <div>
              <h2 className="text-xl font-bold">
                {profile.first_name} {profile.last_name}
              </h2>
              <p className="text-muted-foreground">{profile.job_title}</p>
              <div className="flex gap-2 mt-2">
                <Badge variant="outline">{profile.staff_id}</Badge>
                {profile.is_head_teacher && (
                  <Badge variant="default">Head Teacher</Badge>
                )}
                {profile.is_class_teacher && (
                  <Badge variant="secondary" className="gap-1">
                    <Star className="h-3 w-3" />
                    Class Teacher
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Contact Information */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Contact Information</CardTitle>
          <CardDescription>Your contact details</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Mail className="h-3.5 w-3.5 text-muted-foreground" />
              Email
            </Label>
            <Input value={profile.email} disabled className="bg-muted" />
            <p className="text-[10px] text-muted-foreground">
              Email cannot be changed. Contact admin for updates.
            </p>
          </div>

          <div className="space-y-2">
            <Label className="flex items-center gap-2">
              <Phone className="h-3.5 w-3.5 text-muted-foreground" />
              Phone Number
            </Label>
            <Input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+233 XX XXX XXXX"
            />
          </div>

          <Button onClick={handleSave} disabled={isPending} size="sm">
            {isPending ? (
              <>
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="h-3.5 w-3.5 mr-1" />
                Save Changes
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Employment Details (read-only) */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Employment Details</CardTitle>
          <CardDescription>Your employment information (read-only)</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Briefcase className="h-3.5 w-3.5" />
              Job Title
            </div>
            <span className="text-sm font-medium">{profile.job_title}</span>
          </div>
          <Separator />
          {profile.department && (
            <>
              <div className="flex items-center justify-between py-2">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Building2 className="h-3.5 w-3.5" />
                  Department
                </div>
                <span className="text-sm font-medium">{profile.department}</span>
              </div>
              <Separator />
            </>
          )}
          <div className="flex items-center justify-between py-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <User className="h-3.5 w-3.5" />
              Staff ID
            </div>
            <span className="text-sm font-medium">{profile.staff_id}</span>
          </div>
          {profile.is_class_teacher && profile.class_teacher_class_name && (
            <>
              <Separator />
              <div className="flex items-center justify-between py-2">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <BookOpen className="h-3.5 w-3.5" />
                  Class Teacher For
                </div>
                <span className="text-sm font-medium">
                  {profile.class_teacher_class_name}
                  {profile.class_teacher_section_name
                    ? ` - ${profile.class_teacher_section_name}`
                    : ""}
                </span>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
