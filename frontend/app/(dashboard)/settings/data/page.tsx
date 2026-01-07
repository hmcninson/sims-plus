import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Database,
  Upload,
  Download,
  Clock,
  HardDrive,
  AlertTriangle,
  FileSpreadsheet,
  Users,
  GraduationCap,
} from "lucide-react";

export const metadata = {
  title: "Data Management | SIMS Plus",
};

const backups = [
  { id: 1, date: "Jan 4, 2026 - 02:00 AM", size: "124 MB", type: "Automatic" },
  { id: 2, date: "Jan 3, 2026 - 02:00 AM", size: "123 MB", type: "Automatic" },
  { id: 3, date: "Jan 2, 2026 - 02:00 AM", size: "122 MB", type: "Automatic" },
  { id: 4, date: "Dec 31, 2025 - 10:30 AM", size: "121 MB", type: "Manual" },
];

const importOptions = [
  {
    title: "Students",
    description: "Import student records from CSV or Excel",
    icon: Users,
    count: "456 records",
  },
  {
    title: "Staff",
    description: "Import staff data from CSV or Excel",
    icon: GraduationCap,
    count: "32 records",
  },
  {
    title: "Classes",
    description: "Import class and section data",
    icon: FileSpreadsheet,
    count: "24 records",
  },
];

export default function DataSettingsPage() {
  return (
    <div className="space-y-6">
      {/* Data Import */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Import Data
          </CardTitle>
          <CardDescription>
            Import data from spreadsheets or other systems.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {importOptions.map((option) => (
              <div
                key={option.title}
                className="flex items-center justify-between rounded-lg border p-4"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                    <option.icon className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="font-medium">{option.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {option.description}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-muted-foreground">
                    {option.count}
                  </span>
                  <Button variant="outline" size="sm">
                    <Upload className="mr-2 h-4 w-4" />
                    Import
                  </Button>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 rounded-lg border border-dashed p-6 text-center">
            <Upload className="mx-auto h-8 w-8 text-muted-foreground" />
            <p className="mt-2 text-sm font-medium">Drop files here or click to upload</p>
            <p className="text-xs text-muted-foreground">
              Supports CSV and Excel files (.csv, .xlsx)
            </p>
            <Button variant="outline" size="sm" className="mt-4">
              Select Files
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Data Export */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            Export Data
          </CardTitle>
          <CardDescription>
            Download your data in various formats.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Button variant="outline" className="justify-start">
              <FileSpreadsheet className="mr-2 h-4 w-4" />
              Export Students (Excel)
            </Button>
            <Button variant="outline" className="justify-start">
              <FileSpreadsheet className="mr-2 h-4 w-4" />
              Export Staff (Excel)
            </Button>
            <Button variant="outline" className="justify-start">
              <FileSpreadsheet className="mr-2 h-4 w-4" />
              Export Finances (Excel)
            </Button>
            <Button variant="outline" className="justify-start">
              <Database className="mr-2 h-4 w-4" />
              Export All Data (JSON)
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Backups */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <HardDrive className="h-5 w-5" />
                Backups
              </CardTitle>
              <CardDescription>
                Automatic backups run daily at 2:00 AM.
              </CardDescription>
            </div>
            <Button size="sm">
              <Download className="mr-2 h-4 w-4" />
              Create Backup
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {backups.map((backup) => (
              <div
                key={backup.id}
                className="flex items-center justify-between rounded-lg border p-4"
              >
                <div className="flex items-center gap-3">
                  <Clock className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="font-medium">{backup.date}</p>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">
                        {backup.size}
                      </span>
                      <Badge variant="secondary" className="text-xs">
                        {backup.type}
                      </Badge>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm">
                    <Download className="mr-2 h-4 w-4" />
                    Download
                  </Button>
                  <Button variant="ghost" size="sm">
                    Restore
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="border-destructive/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-5 w-5" />
            Danger Zone
          </CardTitle>
          <CardDescription>
            Irreversible actions that affect your data.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-destructive/30 p-4">
            <div>
              <p className="font-medium">Reset Demo Data</p>
              <p className="text-sm text-muted-foreground">
                Clear all demo/test data and start fresh.
              </p>
            </div>
            <Button variant="outline" size="sm">
              Reset Data
            </Button>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-destructive/30 p-4">
            <div>
              <p className="font-medium">Delete All Data</p>
              <p className="text-sm text-muted-foreground">
                Permanently delete all school data. This cannot be undone.
              </p>
            </div>
            <Button variant="destructive" size="sm">
              Delete All
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
