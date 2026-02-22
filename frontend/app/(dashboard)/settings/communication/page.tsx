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
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  MessageSquare,
  Mail,
  Phone,
  CheckCircle,
  AlertCircle,
} from "lucide-react";

export const metadata = {
  title: "Communication Settings | SIMS Plus",
};

export default function CommunicationSettingsPage() {
  return (
    <div className="space-y-6">
      {/* SMS Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            SMS Configuration
          </CardTitle>
          <CardDescription>
            Configure SMS gateway for sending notifications to parents.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Phone className="h-5 w-5 text-primary" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-medium">Hubtel SMS</p>
                  <Badge variant="outline" className="text-green-600 border-green-600">
                    <CheckCircle className="mr-1 h-3 w-3" />
                    Connected
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  125 SMS credits remaining
                </p>
              </div>
            </div>
            <Button variant="outline" size="sm">
              Configure
            </Button>
          </div>

          <div className="space-y-2">
            <Label htmlFor="senderId">Sender ID</Label>
            <Input
              id="senderId"
              placeholder="e.g., PRESEC"
              defaultValue="SIMSPLUS"
              maxLength={11}
            />
            <p className="text-xs text-muted-foreground">
              This name appears as the sender. Max 11 characters, no spaces.
            </p>
          </div>

          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label className="text-base">Send attendance alerts via SMS</Label>
              <p className="text-sm text-muted-foreground">
                Automatically notify parents when student is marked absent.
              </p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label className="text-base">Send fee reminders via SMS</Label>
              <p className="text-sm text-muted-foreground">
                Send payment reminders before due dates.
              </p>
            </div>
            <Switch defaultChecked />
          </div>
        </CardContent>
      </Card>

      {/* Email Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Mail className="h-5 w-5" />
            Email Configuration
          </CardTitle>
          <CardDescription>
            Configure email settings for sending notifications.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                <Mail className="h-5 w-5 text-muted-foreground" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-medium">SMTP Server</p>
                  <Badge variant="secondary">
                    <AlertCircle className="mr-1 h-3 w-3" />
                    Not configured
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  Configure your SMTP settings to send emails
                </p>
              </div>
            </div>
            <Button size="sm">
              Setup
            </Button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="fromEmail">From Email</Label>
              <Input
                id="fromEmail"
                type="email"
                placeholder="noreply@school.edu.gh"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fromName">From Name</Label>
              <Input
                id="fromName"
                placeholder="School Name"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="replyTo">Reply-To Email</Label>
            <Input
              id="replyTo"
              type="email"
              placeholder="info@school.edu.gh"
            />
            <p className="text-xs text-muted-foreground">
              Replies to automated emails will be sent here.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Email Templates */}
      <Card>
        <CardHeader>
          <CardTitle>Email Templates</CardTitle>
          <CardDescription>
            Customize email templates for different notifications.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="emailSignature">Email Signature</Label>
            <Textarea
              id="emailSignature"
              placeholder="Enter your email signature..."
              rows={4}
              defaultValue={`Best regards,
The School Administration
Tel: +233 XX XXX XXXX`}
            />
          </div>

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm">
              Edit Welcome Email
            </Button>
            <Button variant="outline" size="sm">
              Edit Fee Reminder
            </Button>
            <Button variant="outline" size="sm">
              Edit Report Card
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Notification Preferences */}
      <Card>
        <CardHeader>
          <CardTitle>Default Notification Preferences</CardTitle>
          <CardDescription>
            Set default notification settings for all parents.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label className="text-base">Report card notifications</Label>
              <p className="text-sm text-muted-foreground">
                Notify parents when report cards are published.
              </p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label className="text-base">Event announcements</Label>
              <p className="text-sm text-muted-foreground">
                Send notifications about school events and activities.
              </p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label className="text-base">Weekly digest</Label>
              <p className="text-sm text-muted-foreground">
                Send weekly summary of student activities to parents.
              </p>
            </div>
            <Switch />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
