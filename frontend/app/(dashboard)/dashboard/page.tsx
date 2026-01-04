import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export const metadata = {
  title: "Dashboard",
};

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <Card className="bg-gradient-to-r from-primary to-primary/80 text-primary-foreground">
        <CardContent className="p-6">
          <h2 className="text-2xl font-bold">Welcome back! 👋</h2>
          <p className="mt-1 text-primary-foreground/80">
            Here&apos;s what&apos;s happening at your school today.
          </p>
        </CardContent>
      </Card>

      {/* Stats Cards */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Total Students", value: "1,234", change: "+12", icon: "👨‍🎓" },
          { label: "Total Staff", value: "85", change: "+3", icon: "👨‍🏫" },
          { label: "Attendance Today", value: "95.2%", change: "+2.1%", icon: "📋" },
          { label: "Fees Collected", value: "GHS 45,230", change: "+8.5%", icon: "💰" },
        ].map((stat) => (
          <Card key={stat.label}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <span className="text-2xl">{stat.icon}</span>
                <span className="rounded-full bg-green-100 px-2 py-1 text-xs font-medium text-green-600">
                  {stat.change}
                </span>
              </div>
              <p className="mt-4 text-3xl font-bold">{stat.value}</p>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: "Add Student", icon: "➕👨‍🎓", href: "/students/new" },
              { label: "Mark Attendance", icon: "✅", href: "/attendance/mark" },
              { label: "Record Payment", icon: "💳", href: "/finance/payments/new" },
              { label: "Generate Report", icon: "📄", href: "/reports/new" },
            ].map((action) => (
              <Button
                key={action.label}
                variant="outline"
                className="h-auto flex-col gap-2 p-4"
                asChild
              >
                <a href={action.href}>
                  <span className="text-xl">{action.icon}</span>
                  <span>{action.label}</span>
                </a>
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Recent Activity */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Students</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[
                { name: "Ama Serwaa", class: "Class 6A", date: "Today" },
                { name: "Kofi Mensah", class: "Class 5B", date: "Yesterday" },
                { name: "Abena Osei", class: "Class 4A", date: "2 days ago" },
              ].map((student) => (
                <div
                  key={student.name}
                  className="flex items-center justify-between border-b pb-3 last:border-0"
                >
                  <div>
                    <p className="font-medium">{student.name}</p>
                    <p className="text-sm text-muted-foreground">{student.class}</p>
                  </div>
                  <span className="text-sm text-muted-foreground">{student.date}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Payments</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[
                { name: "Kweku Appiah", amount: "GHS 1,500", status: "Paid" },
                { name: "Efua Mensah", amount: "GHS 800", status: "Partial" },
                { name: "Yaw Boateng", amount: "GHS 2,000", status: "Paid" },
              ].map((payment) => (
                <div
                  key={payment.name}
                  className="flex items-center justify-between border-b pb-3 last:border-0"
                >
                  <div>
                    <p className="font-medium">{payment.name}</p>
                    <p className="text-sm text-muted-foreground">{payment.amount}</p>
                  </div>
                  <span
                    className={`rounded-full px-2 py-1 text-xs font-medium ${
                      payment.status === "Paid"
                        ? "bg-green-100 text-green-600"
                        : "bg-yellow-100 text-yellow-600"
                    }`}
                  >
                    {payment.status}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
