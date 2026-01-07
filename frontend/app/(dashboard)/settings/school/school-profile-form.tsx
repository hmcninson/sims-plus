"use client";

import { useState, useRef } from "react";
import { Building2, Mail, Phone, Globe, MapPin, Palette, Save, Loader2, Upload, X, Hash } from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { updateSchoolProfile, updateSchoolBranding, uploadSchoolLogo } from "@/actions/school.action";
import type { SchoolProfile, SchoolProfileUpdate } from "@/types/school.type";

// School type display names
const SCHOOL_TYPE_LABELS: Record<string, string> = {
  basic_preschool: "Basic - Preschool",
  basic_primary: "Basic - Primary",
  basic_jhs: "Basic - Junior High School",
  basic_combined: "Basic - Combined (Primary + JHS)",
  shs: "Senior High School",
  technical: "Technical/Vocational",
  international: "International School",
  special_needs: "Special Needs School",
};

// Ghana regions
const GHANA_REGIONS = [
  "Greater Accra",
  "Ashanti",
  "Western",
  "Central",
  "Eastern",
  "Northern",
  "Upper East",
  "Upper West",
  "Volta",
  "Bono",
  "Bono East",
  "Ahafo",
  "Western North",
  "Oti",
  "North East",
  "Savannah",
] as const;

interface SchoolProfileFormProps {
  initialData: SchoolProfile;
}

export function SchoolProfileForm({ initialData }: SchoolProfileFormProps) {
  const [isSaving, setIsSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [formData, setFormData] = useState({
    motto: initialData.motto || "",
    description: initialData.description || "",
    year_established: initialData.year_established?.toString() || "",
    email: initialData.email || "",
    phone: initialData.phone || "",
    website: initialData.website || "",
    address: initialData.address || "",
    city: initialData.city || "",
    region: initialData.region || "",
    gps_address: initialData.gps_address || "",
    logo_url: initialData.logo_url || "",
    primary_color: initialData.primary_color || "#3b82f6",
    uses_boarding: initialData.uses_boarding || false,
    uses_transport: initialData.uses_transport || false,
    student_id_prefix: initialData.student_id_prefix || "STU",
  });

  const handleInputChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSwitchChange = (name: string, checked: boolean) => {
    setFormData((prev) => ({ ...prev, [name]: checked }));
  };

  const handleRegionChange = (value: string) => {
    setFormData((prev) => ({ ...prev, region: value }));
  };

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ["image/png", "image/jpeg", "image/webp"];
    if (!allowedTypes.includes(file.type)) {
      toast.error("Invalid file type", {
        description: "Please upload a PNG, JPEG, or WebP image.",
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

      const result = await uploadSchoolLogo(formDataUpload);

      if (result.success && result.data) {
        const logoUrl = result.data.url;
        setFormData((prev) => ({ ...prev, logo_url: logoUrl }));

        // Auto-save the logo to the database
        const saveResult = await updateSchoolBranding({ logo_url: logoUrl });
        if (saveResult.success) {
          toast.success("Logo uploaded and saved", {
            description: "Your school logo has been updated successfully.",
          });
        } else {
          toast.warning("Logo uploaded but not saved", {
            description: "Click 'Save Changes' to save your logo.",
          });
        }
      } else {
        toast.error("Upload failed", {
          description: result.error || "Failed to upload logo.",
        });
      }
    } catch {
      toast.error("Upload error", {
        description: "An unexpected error occurred during upload.",
      });
    } finally {
      setIsUploading(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleRemoveLogo = async () => {
    setFormData((prev) => ({ ...prev, logo_url: "" }));

    // Auto-save the removal to the database
    const result = await updateSchoolBranding({ logo_url: "" });
    if (result.success) {
      toast.success("Logo removed", {
        description: "Your school logo has been removed.",
      });
    }
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSaving(true);

    try {
      const updateData: SchoolProfileUpdate = {
        motto: formData.motto || undefined,
        description: formData.description || undefined,
        year_established: formData.year_established
          ? parseInt(formData.year_established, 10)
          : undefined,
        email: formData.email || undefined,
        phone: formData.phone || undefined,
        website: formData.website || undefined,
        address: formData.address || undefined,
        city: formData.city || undefined,
        region: formData.region || undefined,
        gps_address: formData.gps_address || undefined,
        logo_url: formData.logo_url || undefined,
        primary_color: formData.primary_color || undefined,
        uses_boarding: formData.uses_boarding,
        uses_transport: formData.uses_transport,
        student_id_prefix: formData.student_id_prefix || undefined,
      };

      const result = await updateSchoolProfile(updateData);

      if (result.success) {
        toast.success("Profile Updated", {
          description: "School profile has been saved successfully.",
        });
      } else {
        toast.error("Update Failed", {
          description: result.error || "Failed to update school profile.",
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

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* School Identity */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="h-5 w-5" />
            School Identity
          </CardTitle>
          <CardDescription>
            Basic information about your school (some fields are read-only)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>School Name</Label>
              <Input value={initialData.name} disabled className="bg-muted" />
              <p className="text-xs text-muted-foreground">
                Contact support to change your school name
              </p>
            </div>
            <div className="space-y-2">
              <Label>School Code</Label>
              <Input value={initialData.code || "N/A"} disabled className="bg-muted" />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>School Type</Label>
              <Input value={SCHOOL_TYPE_LABELS[initialData.school_type] || initialData.school_type} disabled className="bg-muted" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="year_established">Year Established</Label>
              <Input
                id="year_established"
                name="year_established"
                type="number"
                placeholder="e.g., 1990"
                value={formData.year_established}
                onChange={handleInputChange}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="motto">School Motto</Label>
            <Input
              id="motto"
              name="motto"
              placeholder="Enter school motto"
              value={formData.motto}
              onChange={handleInputChange}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              name="description"
              placeholder="Brief description of your school..."
              className="min-h-[100px]"
              value={formData.description}
              onChange={handleInputChange}
            />
            <p className="text-xs text-muted-foreground">
              A short description that may appear on reports and communications
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Contact Information */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Contact Information
          </CardTitle>
          <CardDescription>
            How parents and others can reach your school
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email Address</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <Input
                  id="email"
                  name="email"
                  type="email"
                  placeholder="school@example.com"
                  className="pl-9"
                  value={formData.email}
                  onChange={handleInputChange}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone">Phone Number</Label>
              <div className="relative">
                <Phone className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                <Input
                  id="phone"
                  name="phone"
                  type="tel"
                  placeholder="+233 XX XXX XXXX"
                  className="pl-9"
                  value={formData.phone}
                  onChange={handleInputChange}
                />
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="website">Website</Label>
            <div className="relative">
              <Globe className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                id="website"
                name="website"
                type="url"
                placeholder="https://www.yourschool.edu.gh"
                className="pl-9"
                value={formData.website}
                onChange={handleInputChange}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Location */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MapPin className="h-5 w-5" />
            Location
          </CardTitle>
          <CardDescription>Physical address of your school</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="address">Street Address</Label>
            <Input
              id="address"
              name="address"
              placeholder="Enter street address"
              value={formData.address}
              onChange={handleInputChange}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="city">City/Town</Label>
              <Input
                id="city"
                name="city"
                placeholder="e.g., Accra"
                value={formData.city}
                onChange={handleInputChange}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="region">Region</Label>
              <Select value={formData.region} onValueChange={handleRegionChange}>
                <SelectTrigger>
                  <SelectValue placeholder="Select region" />
                </SelectTrigger>
                <SelectContent>
                  {GHANA_REGIONS.map((region) => (
                    <SelectItem key={region} value={region}>
                      {region}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="gps_address">Ghana Post GPS Address</Label>
            <Input
              id="gps_address"
              name="gps_address"
              placeholder="e.g., GA-123-4567"
              value={formData.gps_address}
              onChange={handleInputChange}
            />
            <p className="text-xs text-muted-foreground">
              Your digital address from Ghana Post
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Branding */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Palette className="h-5 w-5" />
            Branding
          </CardTitle>
          <CardDescription>Customize your school&apos;s appearance</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-start gap-6">
            <div className="relative flex-shrink-0">
              {formData.logo_url ? (
                <>
                  <img
                    src={formData.logo_url}
                    alt="School Logo"
                    className="h-24 w-24 rounded-lg object-cover border"
                  />
                  <button
                    type="button"
                    onClick={handleRemoveLogo}
                    className="absolute -top-2 -right-2 h-6 w-6 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center hover:bg-destructive/90"
                    title="Remove logo"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </>
              ) : (
                <div className="h-24 w-24 rounded-lg bg-muted flex items-center justify-center border">
                  <Building2 className="h-10 w-10 text-muted-foreground" />
                </div>
              )}
            </div>
            <div className="flex-1 space-y-3">
              <div>
                <Label>School Logo</Label>
                <p className="text-xs text-muted-foreground mt-1">
                  Upload a PNG, JPEG, or WebP image (max 2MB)
                </p>
              </div>
              <div className="flex items-center gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={handleLogoUpload}
                  className="hidden"
                  id="logo-upload"
                />
                <Button
                  type="button"
                  variant="outline"
                  disabled={isUploading}
                  onClick={() => fileInputRef.current?.click()}
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="mr-2 h-4 w-4" />
                      Upload Logo
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="primary_color">Primary Color</Label>
            <div className="flex items-center gap-3">
              <input
                type="color"
                id="primary_color_picker"
                value={formData.primary_color}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, primary_color: e.target.value }))
                }
                className="h-10 w-14 rounded border cursor-pointer"
              />
              <Input
                id="primary_color"
                name="primary_color"
                placeholder="#3b82f6"
                value={formData.primary_color}
                onChange={handleInputChange}
                className="flex-1"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              This color is used in reports and branded materials
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Features */}
      <Card>
        <CardHeader>
          <CardTitle>Features</CardTitle>
          <CardDescription>Enable or disable optional school features</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label className="text-base">Boarding Facilities</Label>
              <p className="text-sm text-muted-foreground">
                Enable if your school has boarding/hostel facilities
              </p>
            </div>
            <Switch
              checked={formData.uses_boarding}
              onCheckedChange={(checked: boolean) =>
                handleSwitchChange("uses_boarding", checked)
              }
            />
          </div>

          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label className="text-base">Transport Services</Label>
              <p className="text-sm text-muted-foreground">
                Enable if your school provides transport services
              </p>
            </div>
            <Switch
              checked={formData.uses_transport}
              onCheckedChange={(checked: boolean) =>
                handleSwitchChange("uses_transport", checked)
              }
            />
          </div>
        </CardContent>
      </Card>

      {/* Academic Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Hash className="h-5 w-5" />
            Academic Settings
          </CardTitle>
          <CardDescription>
            Configure academic-related settings for your school
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="student_id_prefix">Student ID Prefix</Label>
            <div className="relative">
              <Hash className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                id="student_id_prefix"
                name="student_id_prefix"
                placeholder="STU"
                className="pl-9 uppercase"
                maxLength={10}
                value={formData.student_id_prefix}
                onChange={(e) => {
                  // Only allow alphanumeric characters
                  const value = e.target.value.replace(/[^A-Za-z0-9]/g, '').toUpperCase();
                  setFormData((prev) => ({ ...prev, student_id_prefix: value }));
                }}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              This prefix will be used when auto-generating student IDs (e.g., {formData.student_id_prefix || "STU"}-2026-001)
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button type="submit" disabled={isSaving} size="lg">
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
    </form>
  );
}
