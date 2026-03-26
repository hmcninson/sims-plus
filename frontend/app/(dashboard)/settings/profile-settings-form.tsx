"use client";

import { useState, useRef } from "react";
import { Camera, Loader2, Save, X, Shield, Check } from "lucide-react";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { getInitials } from "@/lib/format";
import { updateProfile, uploadAndSaveAvatar } from "@/actions/user.action";

// Role display names and colors
const ROLE_CONFIG: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  platform_admin: { label: "Platform Admin", variant: "destructive" },
  chain_admin: { label: "Chain Admin", variant: "destructive" },
  school_admin: { label: "School Admin", variant: "default" },
  academic_head: { label: "Academic Head", variant: "default" },
  finance_officer: { label: "Finance Officer", variant: "secondary" },
  hr_officer: { label: "HR Officer", variant: "secondary" },
  teacher: { label: "Teacher", variant: "secondary" },
  house_parent: { label: "House Parent", variant: "secondary" },
  parent: { label: "Parent", variant: "outline" },
  student: { label: "Student", variant: "outline" },
};

// Permission category labels
const PERMISSION_CATEGORIES: Record<string, string> = {
  school: "School Management",
  users: "User Management",
  students: "Student Management",
  staff: "Staff Management",
  classes: "Class Management",
  subjects: "Subject Management",
  attendance: "Attendance",
  exams: "Examinations",
  finance: "Finance",
  boarding: "Boarding",
  transport: "Transport",
  reports: "Reports",
};

interface ProfileSettingsFormProps {
  user: {
    id: string;
    email: string;
    first_name: string;
    last_name: string;
    phone?: string;
    role: string;
    avatar_url?: string;
  };
  permissions?: string[];
}

export function ProfileSettingsForm({ user, permissions = [] }: ProfileSettingsFormProps) {
  const [isSaving, setIsSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [formData, setFormData] = useState({
    first_name: user.first_name || "",
    last_name: user.last_name || "",
    email: user.email || "",
    phone: user.phone || "",
    avatar_url: user.avatar_url || "",
  });

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ["image/png", "image/jpeg", "image/webp", "image/gif"];
    if (!allowedTypes.includes(file.type)) {
      toast.error("Invalid file type", {
        description: "Please upload a PNG, JPEG, WebP, or GIF image.",
      });
      return;
    }

    // Validate file size (2MB max)
    if (file.size > 2 * 1024 * 1024) {
      toast.error("File too large", {
        description: "Maximum file size is 2MB.",
      });
      return;
    }

    setIsUploading(true);

    try {
      const formDataUpload = new FormData();
      formDataUpload.append("file", file);

      const result = await uploadAndSaveAvatar(formDataUpload);

      if (result.success && result.data) {
        setFormData((prev) => ({ ...prev, avatar_url: result.data?.avatar_url || "" }));
        toast.success("Photo updated", {
          description: "Your profile photo has been updated successfully.",
        });
      } else {
        toast.error("Upload failed", {
          description: result.error || "Failed to upload photo.",
        });
      }
    } catch {
      toast.error("Upload error", {
        description: "An unexpected error occurred during upload.",
      });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleRemoveAvatar = async () => {
    setIsUploading(true);
    try {
      const result = await updateProfile({ avatar_url: "" });
      if (result.success) {
        setFormData((prev) => ({ ...prev, avatar_url: "" }));
        toast.success("Photo removed", {
          description: "Your profile photo has been removed.",
        });
      } else {
        toast.error("Failed to remove photo", {
          description: result.error || "Please try again.",
        });
      }
    } catch {
      toast.error("Error", {
        description: "An unexpected error occurred.",
      });
    } finally {
      setIsUploading(false);
    }
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSaving(true);

    try {
      const result = await updateProfile({
        first_name: formData.first_name || undefined,
        last_name: formData.last_name || undefined,
        phone: formData.phone || undefined,
      });

      if (result.success) {
        toast.success("Profile Updated", {
          description: "Your profile has been saved successfully.",
        });
      } else {
        toast.error("Update Failed", {
          description: result.error || "Failed to update profile.",
        });
      }
    } catch {
      toast.error("Error", {
        description: "An unexpected error occurred.",
      });
    } finally {
      setIsSaving(false);
    }
  }

  const fullName = `${formData.first_name} ${formData.last_name}`.trim();

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Profile Photo */}
      <Card>
        <CardHeader>
          <CardTitle>Profile Photo</CardTitle>
          <CardDescription>
            Your photo will be visible to other users in your school.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-6">
            <div className="relative">
              <Avatar className="h-20 w-20">
                {formData.avatar_url ? (
                  <AvatarImage src={formData.avatar_url} alt={fullName} />
                ) : null}
                <AvatarFallback className="bg-primary/10 text-primary text-xl">
                  {getInitials(fullName)}
                </AvatarFallback>
              </Avatar>
              {formData.avatar_url && (
                <button
                  type="button"
                  onClick={handleRemoveAvatar}
                  disabled={isUploading}
                  className="absolute -top-1 -right-1 h-6 w-6 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center hover:bg-destructive/90"
                  title="Remove photo"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
              <Button
                type="button"
                size="icon"
                variant="secondary"
                className="absolute -bottom-1 -right-1 h-8 w-8 rounded-full"
                disabled={isUploading}
                onClick={() => fileInputRef.current?.click()}
              >
                {isUploading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Camera className="h-4 w-4" />
                )}
              </Button>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium">Upload a new photo</p>
              <p className="text-xs text-muted-foreground">
                JPG, PNG, WebP or GIF. Max size 2MB.
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                onChange={handleAvatarUpload}
                className="hidden"
                id="avatar-upload"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-2"
                disabled={isUploading}
                onClick={() => fileInputRef.current?.click()}
              >
                {isUploading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  "Upload Photo"
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Personal Information */}
      <Card>
        <CardHeader>
          <CardTitle>Personal Information</CardTitle>
          <CardDescription>Update your personal details here.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="first_name">First Name</Label>
                <Input
                  id="first_name"
                  name="first_name"
                  value={formData.first_name}
                  onChange={handleInputChange}
                  placeholder="Enter first name"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="last_name">Last Name</Label>
                <Input
                  id="last_name"
                  name="last_name"
                  value={formData.last_name}
                  onChange={handleInputChange}
                  placeholder="Enter last name"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <Input
                id="email"
                name="email"
                type="email"
                value={formData.email}
                disabled
                className="bg-muted"
              />
              <p className="text-xs text-muted-foreground">
                Contact support to change your email address.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone">Phone Number</Label>
              <Input
                id="phone"
                name="phone"
                type="tel"
                value={formData.phone}
                onChange={handleInputChange}
                placeholder="+233 XX XXX XXXX"
              />
            </div>

            <div className="flex justify-end pt-4">
              <Button type="submit" disabled={isSaving}>
                {isSaving ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Save className="mr-2 h-4 w-4" />
                    Save Changes
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Role Information */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Role & Permissions
          </CardTitle>
          <CardDescription>
            Your assigned role and access level in this school.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Current Role */}
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <Shield className="h-5 w-5 text-primary" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-medium">Current Role</p>
                  <Badge variant={ROLE_CONFIG[user.role]?.variant || "secondary"}>
                    {ROLE_CONFIG[user.role]?.label || user.role?.replace("_", " ") || "User"}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  Contact your administrator to change your role.
                </p>
              </div>
            </div>
          </div>

          {/* Permissions */}
          {permissions.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-muted-foreground">Your Permissions</h4>
              <div className="grid gap-2 sm:grid-cols-2">
                {(() => {
                  // Group permissions by category
                  const grouped = permissions.reduce((acc, perm) => {
                    const [category] = perm.split(".");
                    if (!acc[category]) acc[category] = [];
                    acc[category].push(perm);
                    return acc;
                  }, {} as Record<string, string[]>);

                  return Object.entries(grouped).map(([category, perms]) => (
                    <div
                      key={category}
                      className="rounded-lg border p-3"
                    >
                      <p className="text-sm font-medium mb-2">
                        {PERMISSION_CATEGORIES[category] || category}
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {perms.map((perm) => {
                          const action = perm.split(".")[1] || perm;
                          return (
                            <span
                              key={perm}
                              className="inline-flex items-center gap-1 rounded-md bg-muted px-2 py-0.5 text-xs"
                            >
                              <Check className="h-3 w-3 text-green-600" />
                              {action}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  ));
                })()}
              </div>
            </div>
          )}

          {permissions.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-4">
              No specific permissions assigned. Contact your administrator for access.
            </p>
          )}
        </CardContent>
      </Card>
    </form>
  );
}
