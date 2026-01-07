import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { Label } from "@/components/ui/label";

export default function AppearanceSettingsPage() {
  return (
    <div className="space-y-6">
      {/* Theme */}
      <Card>
        <CardHeader>
          <CardTitle>Theme</CardTitle>
          <CardDescription>
            Select your preferred color scheme for the interface.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Color Mode</Label>
            <p className="text-sm text-muted-foreground">
              Choose between light, dark, or system preference.
            </p>
            <ThemeToggle className="mt-3" />
          </div>
        </CardContent>
      </Card>

      {/* Display Preferences */}
      <Card>
        <CardHeader>
          <CardTitle>Display Preferences</CardTitle>
          <CardDescription>
            Customize how information is displayed.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div>
              <p className="font-medium">Compact Mode</p>
              <p className="text-sm text-muted-foreground">
                Display more content with reduced spacing.
              </p>
            </div>
            <span className="text-sm text-muted-foreground">Coming soon</span>
          </div>
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div>
              <p className="font-medium">Date Format</p>
              <p className="text-sm text-muted-foreground">
                Choose your preferred date display format.
              </p>
            </div>
            <span className="text-sm text-muted-foreground">DD/MM/YYYY</span>
          </div>
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div>
              <p className="font-medium">Currency</p>
              <p className="text-sm text-muted-foreground">
                Default currency for financial displays.
              </p>
            </div>
            <span className="text-sm text-muted-foreground">GHS (₵)</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
