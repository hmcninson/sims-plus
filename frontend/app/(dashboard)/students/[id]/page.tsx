"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Calendar,
  Edit,
  Mail,
  MapPin,
  Phone,
  User,
  Users,
  Heart,
  AlertTriangle,
  Droplet,
  FileText,
  BookOpen,
  Home,
  Copy,
  Check,
  MoreHorizontal,
  Printer,
  Trash2,
  CreditCard,
  ClipboardList,
  GraduationCap,
  Clock,
  Building,
  Briefcase,
  Shield,
  ChevronRight,
  UserCircle,
  IdCard,
  TrendingUp,
  CalendarDays,
  AlertCircle,
  Camera,
  Loader2,
  FilePlus2,
  Award,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Progress } from "@/components/ui/progress";

import { getStudent, deleteStudent, updateStudent, unlinkGuardian } from "@/actions/students.action";
import { uploadStudentPhoto } from "@/actions/media.action";
import type { StudentWithGuardians, StudentGuardianLink } from "@/types";
import { AddNotesDialog } from "./add-notes-dialog";
import { AddGuardianDialog } from "./add-guardian-dialog";
import { LinkGuardianDialog } from "./link-guardian-dialog";

// Helper functions
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatDateLong(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function calculateAge(dateOfBirth: string): number {
  const dob = new Date(dateOfBirth);
  const today = new Date();
  let age = today.getFullYear() - dob.getFullYear();
  const monthDiff = today.getMonth() - dob.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
    age--;
  }
  return age;
}

function calculateEnrollmentDuration(admissionDate: string): string {
  const admission = new Date(admissionDate);
  const today = new Date();
  const years = today.getFullYear() - admission.getFullYear();
  const months = today.getMonth() - admission.getMonth();

  if (years === 0) {
    if (months <= 0) return "Less than a month";
    return `${months} month${months > 1 ? "s" : ""}`;
  }
  if (months < 0) {
    return `${years - 1} year${years - 1 !== 1 ? "s" : ""}, ${12 + months} month${12 + months !== 1 ? "s" : ""}`;
  }
  return `${years} year${years !== 1 ? "s" : ""}${months > 0 ? `, ${months} month${months !== 1 ? "s" : ""}` : ""}`;
}

function getStatusConfig(status: string) {
  const config: Record<string, { label: string; color: string; bgColor: string; icon: typeof Check }> = {
    active: {
      label: "Active",
      color: "text-green-700 dark:text-green-400",
      bgColor: "bg-green-100 dark:bg-green-900/30",
      icon: Check
    },
    inactive: {
      label: "Inactive",
      color: "text-gray-700 dark:text-gray-400",
      bgColor: "bg-gray-100 dark:bg-gray-900/30",
      icon: AlertCircle
    },
    graduated: {
      label: "Graduated",
      color: "text-blue-700 dark:text-blue-400",
      bgColor: "bg-blue-100 dark:bg-blue-900/30",
      icon: GraduationCap
    },
    transferred: {
      label: "Transferred",
      color: "text-yellow-700 dark:text-yellow-400",
      bgColor: "bg-yellow-100 dark:bg-yellow-900/30",
      icon: ArrowLeft
    },
    withdrawn: {
      label: "Withdrawn",
      color: "text-red-700 dark:text-red-400",
      bgColor: "bg-red-100 dark:bg-red-900/30",
      icon: AlertCircle
    },
    suspended: {
      label: "Suspended",
      color: "text-orange-700 dark:text-orange-400",
      bgColor: "bg-orange-100 dark:bg-orange-900/30",
      icon: AlertTriangle
    },
  };
  return config[status] || config.inactive;
}

function getRelationshipLabel(relationship: string): string {
  const labels: Record<string, string> = {
    father: "Father",
    mother: "Mother",
    guardian: "Guardian",
    grandfather: "Grandfather",
    grandmother: "Grandmother",
    uncle: "Uncle",
    aunt: "Aunt",
    sibling: "Sibling",
    other: "Other",
  };
  return labels[relationship] || relationship;
}

// Copy to clipboard component
function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success(`${label} copied to clipboard`);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleCopy}>
            {copied ? (
              <Check className="h-3 w-3 text-green-500" />
            ) : (
              <Copy className="h-3 w-3 text-muted-foreground" />
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p>Copy {label}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// Loading skeleton
function ProfileSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header skeleton */}
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-32" />
        </div>
      </div>

      {/* Hero skeleton */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row gap-6">
            <Skeleton className="h-32 w-32 rounded-full mx-auto md:mx-0" />
            <div className="flex-1 space-y-4">
              <Skeleton className="h-8 w-64" />
              <Skeleton className="h-4 w-48" />
              <div className="flex gap-2">
                <Skeleton className="h-6 w-20" />
                <Skeleton className="h-6 w-24" />
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="space-y-2">
                    <Skeleton className="h-4 w-16" />
                    <Skeleton className="h-5 w-24" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Content skeleton */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6">
          <Skeleton className="h-48 w-full rounded-lg" />
          <Skeleton className="h-32 w-full rounded-lg" />
        </div>
        <div className="lg:col-span-2">
          <Skeleton className="h-96 w-full rounded-lg" />
        </div>
      </div>
    </div>
  );
}

// Info item component
function InfoItem({
  icon: Icon,
  label,
  value,
  copyable = false
}: {
  icon: typeof User;
  label: string;
  value: string;
  copyable?: boolean;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="rounded-lg bg-muted p-2">
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <div className="flex items-center gap-1">
          <p className="font-medium truncate">{value}</p>
          {copyable && <CopyButton text={value} label={label} />}
        </div>
      </div>
    </div>
  );
}

// Quick action card
function QuickAction({
  icon: Icon,
  title,
  description,
  href,
  disabled = false,
}: {
  icon: typeof CreditCard;
  title: string;
  description: string;
  href?: string;
  disabled?: boolean;
}) {
  const content = (
    <Card className={`transition-all hover:shadow-md ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:border-primary"}`}>
      <CardContent className="p-4 flex items-center gap-4">
        <div className="rounded-lg bg-primary/10 p-3">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium">{title}</p>
          <p className="text-xs text-muted-foreground truncate">{description}</p>
        </div>
        <ChevronRight className="h-4 w-4 text-muted-foreground" />
      </CardContent>
    </Card>
  );

  if (disabled || !href) {
    return content;
  }

  return <Link href={href}>{content}</Link>;
}

export default function StudentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const studentId = params.id as string;

  const [student, setStudent] = useState<StudentWithGuardians | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [notesDialogOpen, setNotesDialogOpen] = useState(false);
  const [guardianDialogOpen, setGuardianDialogOpen] = useState(false);
  const [linkGuardianDialogOpen, setLinkGuardianDialogOpen] = useState(false);
  const [unlinkGuardianDialog, setUnlinkGuardianDialog] = useState<{
    open: boolean;
    guardianId: string;
    guardianName: string;
  }>({ open: false, guardianId: "", guardianName: "" });
  const [isDeleting, setIsDeleting] = useState(false);
  const [isUnlinkingGuardian, setIsUnlinkingGuardian] = useState(false);
  const [isUploadingPhoto, setIsUploadingPhoto] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchStudent = async () => {
    setLoading(true);
    setError(null);
    const result = await getStudent(studentId);
    if (result.success && result.data) {
      setStudent(result.data);
    } else {
      setError(result.error || "Failed to load student");
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchStudent();
  }, [studentId]);

  const handleDelete = async () => {
    setIsDeleting(true);
    const result = await deleteStudent(studentId);
    if (result.success) {
      toast.success("Student deleted successfully");
      router.push("/students");
    } else {
      toast.error(result.error || "Failed to delete student");
    }
    setIsDeleting(false);
    setDeleteDialogOpen(false);
  };

  const handlePrint = () => {
    window.print();
  };

  const handleUnlinkGuardian = async () => {
    if (!unlinkGuardianDialog.guardianId) return;

    setIsUnlinkingGuardian(true);
    const result = await unlinkGuardian(studentId, unlinkGuardianDialog.guardianId);

    if (result.success) {
      toast.success("Guardian removed successfully");
      setUnlinkGuardianDialog({ open: false, guardianId: "", guardianName: "" });
      fetchStudent();
    } else {
      toast.error(result.error || "Failed to remove guardian");
    }
    setIsUnlinkingGuardian(false);
  };

  const handlePhotoUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ["image/png", "image/jpeg", "image/webp"];
    if (!allowedTypes.includes(file.type)) {
      toast.error("Invalid file type. Please upload PNG, JPEG, or WEBP.");
      return;
    }

    // Validate file size (2MB max)
    if (file.size > 2 * 1024 * 1024) {
      toast.error("File too large. Maximum size is 2MB.");
      return;
    }

    setIsUploadingPhoto(true);

    const formData = new FormData();
    formData.append("file", file);

    const uploadResult = await uploadStudentPhoto(studentId, formData);

    if (uploadResult.success && uploadResult.data) {
      // Update student with new photo URL
      const updateResult = await updateStudent(studentId, {
        photo_url: uploadResult.data.url,
      });

      if (updateResult.success) {
        toast.success("Photo updated successfully");
        fetchStudent(); // Refresh student data
      } else {
        toast.error(updateResult.error || "Failed to update student photo");
      }
    } else {
      toast.error(uploadResult.error || "Failed to upload photo");
    }

    setIsUploadingPhoto(false);
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  if (loading) {
    return <ProfileSkeleton />;
  }

  if (error || !student) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/students">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <h1 className="text-2xl font-bold">Student Not Found</h1>
        </div>
        <Card>
          <CardContent className="py-16 text-center">
            <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
              <User className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Unable to Load Student</h3>
            <p className="text-muted-foreground mb-6">{error || "The student record could not be found."}</p>
            <Button asChild>
              <Link href="/students">Back to Students</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const fullName = student.middle_name
    ? `${student.first_name} ${student.middle_name} ${student.last_name}`
    : `${student.first_name} ${student.last_name}`;

  const initials = `${student.first_name[0]}${student.last_name[0]}`.toUpperCase();
  const statusConfig = getStatusConfig(student.status);
  const StatusIcon = statusConfig.icon;

  // Calculate profile completion
  const profileFields = [
    student.email,
    student.phone,
    student.address,
    student.date_of_birth,
    student.class_id,
    student.guardians?.length,
    student.blood_group,
  ];
  const completedFields = profileFields.filter(Boolean).length;
  const profileCompletion = Math.round((completedFields / profileFields.length) * 100);

  return (
    <div className="space-y-6 print:space-y-4">
      {/* Hidden file input for photo upload */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handlePhotoUpload}
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
      />

      {/* Breadcrumb with student name */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 print:hidden">
        <div className="flex items-center gap-2 text-sm">
          <Link href="/students" className="text-muted-foreground hover:text-foreground transition-colors">
            Students
          </Link>
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium truncate max-w-[250px]">{fullName}</span>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handlePrint}>
            <Printer className="h-4 w-4 mr-2" />
            Print
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href={`/students/${studentId}/edit`}>
              <Edit className="h-4 w-4 mr-2" />
              Edit
            </Link>
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="icon" className="h-9 w-9">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link href={`/students/${studentId}/edit`}>
                  <Edit className="h-4 w-4 mr-2" />
                  Edit Student
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handlePrint}>
                <Printer className="h-4 w-4 mr-2" />
                Print Profile
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-red-600"
                onClick={() => setDeleteDialogOpen(true)}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete Student
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Hero Card */}
      <Card className="overflow-hidden">
        <div className="h-24 bg-gradient-to-r from-primary/20 via-primary/10 to-transparent print:hidden" />
        <CardContent className="relative px-6 pb-6 -mt-12 print:mt-0 print:pt-6">
          <div className="flex flex-col md:flex-row gap-6 items-start">
            {/* Avatar with Photo Upload */}
            <div className="relative group">
              {student.photo_url ? (
                // Use native img for S3 images to avoid Radix loading issues
                <div className="h-28 w-28 rounded-full border-4 border-background shadow-lg overflow-hidden bg-muted">
                  <img
                    src={student.photo_url}
                    alt={fullName}
                    className="h-full w-full object-cover"
                    onError={(e) => {
                      console.error('Image failed to load:', student.photo_url);
                      // Hide broken image and show fallback
                      e.currentTarget.style.display = 'none';
                      const fallback = e.currentTarget.nextElementSibling;
                      if (fallback) (fallback as HTMLElement).style.display = 'flex';
                    }}
                  />
                  <div className="hidden h-full w-full items-center justify-center text-3xl font-semibold bg-primary/10 text-primary">
                    {initials}
                  </div>
                </div>
              ) : (
                <Avatar className="h-28 w-28 border-4 border-background shadow-lg">
                  <AvatarFallback className="text-3xl font-semibold bg-primary/10 text-primary">
                    {initials}
                  </AvatarFallback>
                </Avatar>
              )}
              {/* Photo upload overlay */}
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploadingPhoto}
                className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-full opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer disabled:cursor-not-allowed print:hidden"
              >
                {isUploadingPhoto ? (
                  <Loader2 className="h-6 w-6 text-white animate-spin" />
                ) : (
                  <Camera className="h-6 w-6 text-white" />
                )}
              </button>
            </div>

            {/* Main Info */}
            <div className="flex-1 space-y-3">
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <h1 className="text-2xl font-bold">{fullName}</h1>
                  <Badge className={`${statusConfig.bgColor} ${statusConfig.color} border-0`}>
                    <StatusIcon className="h-3 w-3 mr-1" />
                    {statusConfig.label}
                  </Badge>
                  {student.is_boarder && (
                    <Badge variant="outline">
                      <Home className="h-3 w-3 mr-1" />
                      Boarder
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <code className="text-sm text-muted-foreground bg-muted px-2 py-0.5 rounded font-mono">
                    {student.student_id}
                  </code>
                  <CopyButton text={student.student_id} label="Student ID" />
                </div>
              </div>

              {/* Quick Stats Row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-2">
                <div>
                  <p className="text-xs text-muted-foreground">Age</p>
                  <p className="font-semibold">{calculateAge(student.date_of_birth)} years</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Gender</p>
                  <p className="font-semibold capitalize">{student.gender}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Class</p>
                  <p className="font-semibold">
                    {student.class_name || "Not Assigned"}
                    {student.section_name && <span className="text-muted-foreground font-normal"> ({student.section_name})</span>}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Guardians</p>
                  <p className="font-semibold">{student.guardians?.length || 0} linked</p>
                </div>
              </div>

              {/* Profile Completion */}
              <div className="pt-2 print:hidden">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-muted-foreground">Profile Completion</span>
                  <span className="font-medium">{profileCompletion}%</span>
                </div>
                <Progress value={profileCompletion} className="h-1.5" />
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column */}
        <div className="space-y-6">
          {/* Personal Information Card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <UserCircle className="h-4 w-4" />
                Personal Information
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <InfoItem
                icon={Calendar}
                label="Date of Birth"
                value={`${formatDate(student.date_of_birth)} (${calculateAge(student.date_of_birth)} yrs)`}
              />
              <InfoItem
                icon={User}
                label="Gender"
                value={student.gender.charAt(0).toUpperCase() + student.gender.slice(1)}
              />
              {student.blood_group && (
                <InfoItem
                  icon={Droplet}
                  label="Blood Group"
                  value={student.blood_group}
                />
              )}
              {student.ghana_card_number && (
                <InfoItem
                  icon={IdCard}
                  label="Ghana Card"
                  value={student.ghana_card_number}
                  copyable
                />
              )}
              {student.nhis_number && (
                <InfoItem
                  icon={Shield}
                  label="NHIS Number"
                  value={student.nhis_number}
                  copyable
                />
              )}
            </CardContent>
          </Card>

          {/* Enrollment Information Card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <GraduationCap className="h-4 w-4" />
                Enrollment
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {student.admission_date && (
                <>
                  <InfoItem
                    icon={CalendarDays}
                    label="Admission Date"
                    value={formatDate(student.admission_date)}
                  />
                  <InfoItem
                    icon={Clock}
                    label="Duration"
                    value={calculateEnrollmentDuration(student.admission_date)}
                  />
                </>
              )}
              {student.admission_number && (
                <InfoItem
                  icon={FileText}
                  label="Admission Number"
                  value={student.admission_number}
                  copyable
                />
              )}
              {student.class_name && (
                <InfoItem
                  icon={BookOpen}
                  label="Current Class"
                  value={student.class_name + (student.section_name ? ` (${student.section_name})` : "")}
                />
              )}
              <InfoItem
                icon={Home}
                label="Student Type"
                value={student.is_boarder ? "Boarding Student" : "Day Student"}
              />
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <div className="space-y-3 print:hidden">
            <h3 className="text-sm font-medium text-muted-foreground px-1">Quick Actions</h3>
            <QuickAction
              icon={CreditCard}
              title="View Fees"
              description="Check fee status and payments"
              href={`/finance/invoices?q=${encodeURIComponent(student.student_id)}`}
            />
            <QuickAction
              icon={FilePlus2}
              title="Generate Invoice"
              description="Create invoice for this student"
              href={`/finance/invoices/generate?student_id=${studentId}`}
            />
            <QuickAction
              icon={Award}
              title="Scholarships"
              description="View scholarships and awards"
              href={`/students/${studentId}/scholarships`}
            />
            <QuickAction
              icon={ClipboardList}
              title="Attendance"
              description="View attendance records"
              disabled
            />
            <QuickAction
              icon={TrendingUp}
              title="Academic Progress"
              description="Grades and assessments"
              disabled
            />
          </div>
        </div>

        {/* Right Column - Tabs */}
        <div className="lg:col-span-2">
          <Tabs defaultValue="contact" className="space-y-4">
            <TabsList className="grid w-full grid-cols-4 print:hidden">
              <TabsTrigger value="contact">Contact</TabsTrigger>
              <TabsTrigger value="guardians">
                Guardians
                {student.guardians && student.guardians.length > 0 && (
                  <Badge variant="secondary" className="ml-1.5 h-5 px-1.5">
                    {student.guardians.length}
                  </Badge>
                )}
              </TabsTrigger>
              <TabsTrigger value="medical">Medical</TabsTrigger>
              <TabsTrigger value="notes">Notes</TabsTrigger>
            </TabsList>

            {/* Contact Tab */}
            <TabsContent value="contact" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Contact Information</CardTitle>
                  <CardDescription>Student and family contact details</CardDescription>
                </CardHeader>
                <CardContent>
                  {student.email || student.phone || student.address ? (
                    <div className="grid gap-6 sm:grid-cols-2">
                      {student.email && (
                        <div className="flex items-start gap-3">
                          <div className="rounded-lg bg-blue-100 dark:bg-blue-900/30 p-2">
                            <Mail className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">Email Address</p>
                            <a href={`mailto:${student.email}`} className="font-medium text-primary hover:underline">
                              {student.email}
                            </a>
                          </div>
                        </div>
                      )}
                      {student.phone && (
                        <div className="flex items-start gap-3">
                          <div className="rounded-lg bg-green-100 dark:bg-green-900/30 p-2">
                            <Phone className="h-4 w-4 text-green-600 dark:text-green-400" />
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">Phone Number</p>
                            <a href={`tel:${student.phone}`} className="font-medium text-primary hover:underline">
                              {student.phone}
                            </a>
                          </div>
                        </div>
                      )}
                      {(student.address || student.city || student.region) && (
                        <div className="flex items-start gap-3 sm:col-span-2">
                          <div className="rounded-lg bg-orange-100 dark:bg-orange-900/30 p-2">
                            <MapPin className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                          </div>
                          <div>
                            <p className="text-xs text-muted-foreground">Address</p>
                            <p className="font-medium">
                              {[student.address, student.city, student.region].filter(Boolean).join(", ")}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <div className="mx-auto w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
                        <Mail className="h-5 w-5 text-muted-foreground" />
                      </div>
                      <p className="text-muted-foreground">No contact information available</p>
                      <Button variant="outline" size="sm" className="mt-3" asChild>
                        <Link href={`/students/${studentId}/edit?step=contact`}>
                          Add Contact Info
                        </Link>
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Primary Guardian Quick View */}
              {student.guardians && student.guardians.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Primary Guardian</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {(() => {
                      const primary = student.guardians.find(g => g.is_primary) || student.guardians[0];
                      return (
                        <div className="flex items-center gap-4">
                          <Avatar className="h-12 w-12">
                            <AvatarImage src={primary.guardian.photo_url || undefined} />
                            <AvatarFallback>
                              {primary.guardian.first_name[0]}{primary.guardian.last_name[0]}
                            </AvatarFallback>
                          </Avatar>
                          <div className="flex-1">
                            <p className="font-medium">
                              {primary.guardian.first_name} {primary.guardian.last_name}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {getRelationshipLabel(primary.relationship)}
                            </p>
                          </div>
                          <div className="text-right">
                            <a href={`tel:${primary.guardian.phone}`} className="text-sm text-primary hover:underline flex items-center gap-1">
                              <Phone className="h-3 w-3" />
                              {primary.guardian.phone}
                            </a>
                          </div>
                        </div>
                      );
                    })()}
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Guardians Tab */}
            <TabsContent value="guardians">
              <Card>
                <CardHeader className="flex flex-row items-start justify-between">
                  <div>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Users className="h-4 w-4" />
                      Guardians & Emergency Contacts
                    </CardTitle>
                    <CardDescription>
                      People authorized to pick up and make decisions for this student
                    </CardDescription>
                  </div>
                  {student.guardians && student.guardians.length > 0 && (
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setLinkGuardianDialogOpen(true)}
                      >
                        Link Existing
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setGuardianDialogOpen(true)}
                      >
                        Add New
                      </Button>
                    </div>
                  )}
                </CardHeader>
                <CardContent>
                  {student.guardians && student.guardians.length > 0 ? (
                    <div className="space-y-4">
                      {student.guardians.map((link: StudentGuardianLink) => (
                        <div
                          key={link.id}
                          className="relative flex flex-col sm:flex-row sm:items-start gap-4 p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
                        >
                          {link.is_primary && (
                            <Badge className="absolute -top-2 left-4 bg-primary">Primary</Badge>
                          )}
                          {/* Remove button */}
                          <Button
                            variant="ghost"
                            size="icon"
                            className="absolute top-2 right-2 h-8 w-8 text-muted-foreground hover:text-destructive"
                            onClick={() =>
                              setUnlinkGuardianDialog({
                                open: true,
                                guardianId: link.guardian.id,
                                guardianName: `${link.guardian.first_name} ${link.guardian.last_name}`,
                              })
                            }
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                          <Avatar className="h-14 w-14 border-2 border-muted">
                            <AvatarImage
                              src={link.guardian.photo_url || undefined}
                              alt={`${link.guardian.first_name} ${link.guardian.last_name}`}
                            />
                            <AvatarFallback className="text-lg">
                              {link.guardian.first_name[0]}
                              {link.guardian.last_name[0]}
                            </AvatarFallback>
                          </Avatar>

                          <div className="flex-1 space-y-2">
                            <div>
                              <p className="font-semibold text-lg">
                                {link.guardian.first_name} {link.guardian.last_name}
                              </p>
                              <p className="text-sm text-muted-foreground">
                                {getRelationshipLabel(link.relationship)}
                                {link.guardian.occupation && ` • ${link.guardian.occupation}`}
                              </p>
                            </div>

                            <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                              <a href={`tel:${link.guardian.phone}`} className="flex items-center gap-1.5 text-primary hover:underline">
                                <Phone className="h-3.5 w-3.5" />
                                {link.guardian.phone}
                              </a>
                              {link.guardian.phone_secondary && (
                                <a href={`tel:${link.guardian.phone_secondary}`} className="flex items-center gap-1.5 text-muted-foreground hover:text-primary">
                                  <Phone className="h-3.5 w-3.5" />
                                  {link.guardian.phone_secondary}
                                </a>
                              )}
                              {link.guardian.email && (
                                <a href={`mailto:${link.guardian.email}`} className="flex items-center gap-1.5 text-muted-foreground hover:text-primary">
                                  <Mail className="h-3.5 w-3.5" />
                                  {link.guardian.email}
                                </a>
                              )}
                            </div>

                            {(link.guardian.workplace || link.guardian.work_phone) && (
                              <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
                                {link.guardian.workplace && (
                                  <span className="flex items-center gap-1.5">
                                    <Building className="h-3.5 w-3.5" />
                                    {link.guardian.workplace}
                                  </span>
                                )}
                                {link.guardian.work_phone && (
                                  <span className="flex items-center gap-1.5">
                                    <Briefcase className="h-3.5 w-3.5" />
                                    {link.guardian.work_phone}
                                  </span>
                                )}
                              </div>
                            )}

                            <div className="flex flex-wrap gap-2 pt-1">
                              {link.is_emergency_contact && (
                                <Badge variant="destructive" className="text-xs">
                                  <AlertTriangle className="h-3 w-3 mr-1" />
                                  Emergency Contact
                                </Badge>
                              )}
                              {link.can_pickup && (
                                <Badge variant="secondary" className="text-xs">
                                  <Check className="h-3 w-3 mr-1" />
                                  Can Pick Up
                                </Badge>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-12">
                      <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
                        <Users className="h-7 w-7 text-muted-foreground" />
                      </div>
                      <h3 className="font-semibold mb-1">No Guardians Linked</h3>
                      <p className="text-muted-foreground mb-4">
                        Add guardian information for emergency contacts and pickup authorization.
                      </p>
                      <div className="flex justify-center gap-2">
                        <Button variant="outline" onClick={() => setLinkGuardianDialogOpen(true)}>
                          Link Existing Guardian
                        </Button>
                        <Button onClick={() => setGuardianDialogOpen(true)}>
                          Add New Guardian
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Medical Tab */}
            <TabsContent value="medical">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Heart className="h-4 w-4" />
                    Medical Information
                  </CardTitle>
                  <CardDescription>
                    Health records, allergies, and medical conditions
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {student.blood_group || student.medical_conditions || student.allergies ? (
                    <div className="space-y-6">
                      {student.blood_group && (
                        <div className="flex items-center gap-4 p-4 rounded-lg bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900">
                          <div className="rounded-full bg-red-100 dark:bg-red-900/50 p-3">
                            <Droplet className="h-6 w-6 text-red-600 dark:text-red-400" />
                          </div>
                          <div>
                            <p className="text-sm text-muted-foreground">Blood Group</p>
                            <p className="text-2xl font-bold text-red-600 dark:text-red-400">{student.blood_group}</p>
                          </div>
                        </div>
                      )}

                      {student.medical_conditions && (
                        <div>
                          <div className="flex items-center gap-2 mb-3">
                            <div className="rounded-lg bg-yellow-100 dark:bg-yellow-900/30 p-1.5">
                              <AlertTriangle className="h-4 w-4 text-yellow-600 dark:text-yellow-400" />
                            </div>
                            <h4 className="font-medium">Medical Conditions</h4>
                          </div>
                          <div className="bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-900 rounded-lg p-4">
                            <p className="whitespace-pre-wrap">{student.medical_conditions}</p>
                          </div>
                        </div>
                      )}

                      {student.allergies && (
                        <div>
                          <div className="flex items-center gap-2 mb-3">
                            <div className="rounded-lg bg-orange-100 dark:bg-orange-900/30 p-1.5">
                              <AlertCircle className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                            </div>
                            <h4 className="font-medium">Allergies</h4>
                          </div>
                          <div className="bg-orange-50 dark:bg-orange-950/20 border border-orange-200 dark:border-orange-900 rounded-lg p-4">
                            <p className="whitespace-pre-wrap">{student.allergies}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center py-12">
                      <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
                        <Heart className="h-7 w-7 text-muted-foreground" />
                      </div>
                      <h3 className="font-semibold mb-1">No Medical Information</h3>
                      <p className="text-muted-foreground mb-4">
                        Add blood group, medical conditions, and allergy information.
                      </p>
                      <Button variant="outline" asChild>
                        <Link href={`/students/${studentId}/edit?step=health`}>
                          Add Medical Info
                        </Link>
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Notes Tab */}
            <TabsContent value="notes">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    Additional Notes
                  </CardTitle>
                  <CardDescription>
                    General notes and remarks about the student
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {student.notes ? (
                    <div className="space-y-3">
                      <div className="bg-muted/50 rounded-lg p-4 border">
                        <p className="whitespace-pre-wrap">{student.notes}</p>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setNotesDialogOpen(true)}
                      >
                        <Edit className="h-4 w-4 mr-2" />
                        Edit Notes
                      </Button>
                    </div>
                  ) : (
                    <div className="text-center py-12">
                      <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
                        <FileText className="h-7 w-7 text-muted-foreground" />
                      </div>
                      <h3 className="font-semibold mb-1">No Notes Added</h3>
                      <p className="text-muted-foreground mb-4">
                        Add any additional information or remarks about this student.
                      </p>
                      <Button variant="outline" onClick={() => setNotesDialogOpen(true)}>
                        Add Notes
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>

      {/* Add Notes Dialog */}
      <AddNotesDialog
        studentId={studentId}
        studentName={fullName}
        currentNotes={student.notes}
        open={notesDialogOpen}
        onOpenChange={setNotesDialogOpen}
        onSuccess={fetchStudent}
      />

      {/* Add Guardian Dialog */}
      <AddGuardianDialog
        studentId={studentId}
        studentName={fullName}
        open={guardianDialogOpen}
        onOpenChange={setGuardianDialogOpen}
        onSuccess={fetchStudent}
      />

      {/* Link Existing Guardian Dialog */}
      <LinkGuardianDialog
        studentId={studentId}
        studentName={fullName}
        existingGuardianIds={student.guardians?.map((g) => g.guardian.id) || []}
        open={linkGuardianDialogOpen}
        onOpenChange={setLinkGuardianDialogOpen}
        onSuccess={fetchStudent}
      />

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Student Record</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{fullName}</strong>? This action cannot be undone
              and will permanently remove all associated data including guardians links and academic records.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? "Deleting..." : "Delete Student"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Remove Guardian Confirmation Dialog */}
      <AlertDialog
        open={unlinkGuardianDialog.open}
        onOpenChange={(open) =>
          setUnlinkGuardianDialog((prev) => ({ ...prev, open }))
        }
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Guardian</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove <strong>{unlinkGuardianDialog.guardianName}</strong> as
              a guardian for this student? This will only remove the link between them - the guardian
              record will not be deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleUnlinkGuardian}
              disabled={isUnlinkingGuardian}
            >
              {isUnlinkingGuardian ? "Removing..." : "Remove Guardian"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
