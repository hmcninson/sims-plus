"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import {
  Upload,
  FileText,
  Download,
  Trash2,
  Loader2,
  File,
  Image,
  FileType,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";

import {
  getStudentDocuments,
  uploadStudentDocument,
  deleteStudentDocument,
  getDocumentDownloadUrl,
} from "@/actions/students.action";
import type { StudentDocumentResponse } from "@/types";

const DOCUMENT_TYPES = [
  { value: "birth_certificate", label: "Birth Certificate" },
  { value: "medical_record", label: "Medical Record" },
  { value: "report_card", label: "Report Card" },
  { value: "transfer_letter", label: "Transfer Letter" },
  { value: "leaving_certificate", label: "Leaving Certificate" },
  { value: "passport_photo", label: "Passport Photo" },
  { value: "immunization_record", label: "Immunization Record" },
  { value: "nhis_card", label: "NHIS Card" },
  { value: "birth_cert_copy", label: "Birth Cert. Copy" },
  { value: "other", label: "Other" },
] as const;

const ACCEPTED_FILE_TYPES = ".pdf,.doc,.docx,.jpg,.jpeg,.png,.webp";
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

const uploadSchema = z.object({
  document_type: z.string().min(1, "Document type is required"),
  title: z.string().min(1, "Title is required").max(200, "Title too long"),
  notes: z.string().max(500, "Notes too long").optional(),
});

type UploadFormValues = z.infer<typeof uploadSchema>;

function getDocTypeLabel(type: string): string {
  const found = DOCUMENT_TYPES.find((dt) => dt.value === type);
  return found ? found.label : type.replace(/_/g, " ");
}

function getDocTypeBadgeColor(type: string): string {
  const colors: Record<string, string> = {
    birth_certificate: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    medical_record: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    report_card: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    transfer_letter: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
    leaving_certificate: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
    passport_photo: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400",
    immunization_record: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  };
  return colors[type] || "bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400";
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(mimeType: string) {
  if (mimeType.startsWith("image/")) return Image;
  if (mimeType === "application/pdf") return FileType;
  return File;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

interface StudentDocumentsProps {
  studentId: string;
}

export function StudentDocuments({ studentId }: StudentDocumentsProps) {
  const [documents, setDocuments] = useState<StudentDocumentResponse[]>([]);
  const [totalSize, setTotalSize] = useState(0);
  const [loading, setLoading] = useState(true);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<StudentDocumentResponse | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isDownloading, setIsDownloading] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filterType, setFilterType] = useState<string>("all");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const form = useForm<UploadFormValues>({
    resolver: zodResolver(uploadSchema),
    defaultValues: { document_type: "", title: "", notes: "" },
  });

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    const typeFilter = filterType !== "all" ? filterType : undefined;
    const result = await getStudentDocuments(studentId, typeFilter);
    if (result.success && result.data) {
      setDocuments(result.data.documents);
      setTotalSize(result.data.total_size_bytes);
    } else {
      toast.error(result.error || "Failed to load documents");
    }
    setLoading(false);
  }, [studentId, filterType]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > MAX_FILE_SIZE) {
      toast.error("File too large. Maximum size is 10MB.");
      return;
    }

    setSelectedFile(file);
    // Auto-fill title from filename if empty
    if (!form.getValues("title")) {
      const nameWithoutExt = file.name.replace(/\.[^.]+$/, "");
      form.setValue("title", nameWithoutExt);
    }
  };

  const handleUpload = async (values: UploadFormValues) => {
    if (!selectedFile) {
      toast.error("Please select a file to upload");
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("document_type", values.document_type);
    formData.append("title", values.title);
    if (values.notes) formData.append("notes", values.notes);

    const result = await uploadStudentDocument(studentId, formData);
    if (result.success) {
      toast.success("Document uploaded successfully");
      setUploadDialogOpen(false);
      setSelectedFile(null);
      form.reset();
      if (fileInputRef.current) fileInputRef.current.value = "";
      fetchDocuments();
    } else {
      toast.error(result.error || "Failed to upload document");
    }
  };

  const handleDownload = async (doc: StudentDocumentResponse) => {
    setIsDownloading(doc.id);
    const result = await getDocumentDownloadUrl(studentId, doc.id);
    if (result.success && result.data) {
      window.open(result.data.download_url, "_blank");
    } else {
      toast.error(result.error || "Failed to get download link");
    }
    setIsDownloading(null);
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    const result = await deleteStudentDocument(studentId, deleteTarget.id);
    if (result.success) {
      toast.success("Document deleted successfully");
      setDeleteTarget(null);
      fetchDocuments();
    } else {
      toast.error(result.error || "Failed to delete document");
    }
    setIsDeleting(false);
  };

  return (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Documents
          </CardTitle>
          <CardDescription>
            {documents.length} document{documents.length !== 1 ? "s" : ""}
            {totalSize > 0 && ` (${formatFileSize(totalSize)} total)`}
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <Select value={filterType} onValueChange={setFilterType}>
            <SelectTrigger className="w-full sm:w-[160px]">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              {DOCUMENT_TYPES.map((dt) => (
                <SelectItem key={dt.value} value={dt.value}>
                  {dt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" onClick={() => setUploadDialogOpen(true)}>
            <Upload className="h-4 w-4 mr-2" />
            Upload
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-16 w-full rounded-lg" />
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-12">
            <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
              <FileText className="h-7 w-7 text-muted-foreground" />
            </div>
            <h3 className="font-semibold mb-1">No Documents</h3>
            <p className="text-muted-foreground mb-4">
              Upload student documents such as birth certificates, medical records, and report cards.
            </p>
            <Button variant="outline" onClick={() => setUploadDialogOpen(true)}>
              <Upload className="h-4 w-4 mr-2" />
              Upload Document
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {documents.map((doc) => {
              const FileIcon = getFileIcon(doc.mime_type);
              return (
                <div
                  key={doc.id}
                  className="flex items-center gap-3 p-3 rounded-lg border hover:bg-accent/50 transition-colors"
                >
                  <div className="rounded-lg bg-muted p-2.5 shrink-0">
                    <FileIcon className="h-5 w-5 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{doc.title}</p>
                    <div className="flex flex-wrap items-center gap-2 mt-1">
                      <Badge variant="secondary" className={`text-xs border-0 ${getDocTypeBadgeColor(doc.document_type)}`}>
                        {getDocTypeLabel(doc.document_type)}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {formatFileSize(doc.file_size)}
                      </span>
                      <span className="text-xs text-muted-foreground hidden sm:inline">
                        {formatDate(doc.created_at)}
                      </span>
                    </div>
                    {doc.notes && (
                      <p className="text-xs text-muted-foreground mt-1 truncate">
                        {doc.notes}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => handleDownload(doc)}
                      disabled={isDownloading === doc.id}
                    >
                      {isDownloading === doc.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Download className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      onClick={() => setDeleteTarget(doc)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>

      {/* Upload Dialog */}
      <Dialog
        open={uploadDialogOpen}
        onOpenChange={(open) => {
          setUploadDialogOpen(open);
          if (!open) {
            setSelectedFile(null);
            form.reset();
            if (fileInputRef.current) fileInputRef.current.value = "";
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upload Document</DialogTitle>
            <DialogDescription>
              Upload a document for this student. Max file size: 10MB.
            </DialogDescription>
          </DialogHeader>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleUpload)} className="space-y-4">
              {/* File Input */}
              <div className="space-y-2">
                <label className="text-sm font-medium">File</label>
                <div className="flex items-center gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept={ACCEPTED_FILE_TYPES}
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full justify-start"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <Upload className="h-4 w-4 mr-2" />
                    {selectedFile ? selectedFile.name : "Choose file..."}
                  </Button>
                  {selectedFile && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="shrink-0"
                      onClick={() => {
                        setSelectedFile(null);
                        if (fileInputRef.current) fileInputRef.current.value = "";
                      }}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
                {selectedFile && (
                  <p className="text-xs text-muted-foreground">
                    {formatFileSize(selectedFile.size)}
                  </p>
                )}
              </div>

              <FormField
                control={form.control}
                name="document_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Document Type</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select type" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {DOCUMENT_TYPES.map((dt) => (
                          <SelectItem key={dt.value} value={dt.value}>
                            {dt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Title</FormLabel>
                    <FormControl>
                      <Input placeholder="Document title" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="notes"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Notes (optional)</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Any additional notes..."
                        rows={2}
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setUploadDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={!selectedFile || form.formState.isSubmitting}
                >
                  {form.formState.isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    "Upload"
                  )}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Document</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete <strong>{deleteTarget?.title}</strong>?
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
