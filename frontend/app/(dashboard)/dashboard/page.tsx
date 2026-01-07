import Link from "next/link";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Users,
  UserCog,
  ClipboardCheck,
  Wallet,
  TrendingUp,
  TrendingDown,
  UserPlus,
  Calendar,
  ArrowRight,
  Clock,
  CheckCircle2,
  AlertCircle,
  GraduationCap,
  Trophy,
} from "lucide-react";
import { getInitials } from "@/lib/format";
import { getCurrentUser } from "@/actions/auth.action";

export const metadata = {
  title: "Dashboard",
};

// Stats data - would come from API in real app
const stats = [
  {
    title: "Total Students",
    value: "1,234",
    change: "+12",
    changeType: "positive" as const,
    icon: Users,
    href: "/students",
  },
  {
    title: "Total Staff",
    value: "85",
    change: "+3",
    changeType: "positive" as const,
    icon: UserCog,
    href: "/staff",
  },
  {
    title: "Today's Attendance",
    value: "95.2%",
    change: "+2.1%",
    changeType: "positive" as const,
    icon: ClipboardCheck,
    href: "/attendance",
  },
  {
    title: "Fees Collected",
    value: "GHS 45,230",
    change: "-8.5%",
    changeType: "negative" as const,
    icon: Wallet,
    href: "/finance",
  },
];

// Recent students - would come from API
const recentStudents = [
  { name: "Ama Serwaa", class: "Class 6A", date: "Today", status: "active" },
  { name: "Kofi Mensah", class: "Class 5B", date: "Yesterday", status: "active" },
  { name: "Abena Osei", class: "Class 4A", date: "2 days ago", status: "active" },
  { name: "Kwame Asante", class: "Class 3B", date: "3 days ago", status: "pending" },
];

// Recent payments - would come from API
const recentPayments = [
  { name: "Kweku Appiah", amount: "GHS 1,500", status: "paid", date: "Today" },
  { name: "Efua Mensah", amount: "GHS 800", status: "partial", date: "Yesterday" },
  { name: "Yaw Boateng", amount: "GHS 2,000", status: "paid", date: "2 days ago" },
  { name: "Akua Nyarko", amount: "GHS 1,200", status: "pending", date: "3 days ago" },
];

// Upcoming events - would come from API
const upcomingEvents = [
  { title: "Mid-Term Exams Begin", date: "Jan 15, 2026", type: "exam" },
  { title: "PTA Meeting", date: "Jan 20, 2026", type: "meeting" },
  { title: "Sports Day", date: "Jan 25, 2026", type: "event" },
];

export default async function DashboardPage() {
  const user = await getCurrentUser();
  const firstName = user?.first_name || "there";

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6 md:p-8">
        {/* Background decoration */}
        <div className="absolute inset-0 bg-grid-white/[0.02]" />
        <div className="absolute -right-20 -top-20 h-60 w-60 rounded-full bg-primary/20 blur-3xl" />
        <div className="absolute -bottom-20 -right-10 h-40 w-40 rounded-full bg-blue-500/20 blur-3xl" />

        <div className="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          {/* Left content */}
          <div className="space-y-3">
            <h1 className="text-2xl font-bold tracking-tight text-white md:text-3xl">
              Welcome back, {firstName}!
            </h1>
            <p className="max-w-md text-slate-300">
              Track attendance, manage students, and monitor your school&apos;s performance
              all in one place. Here&apos;s your overview for today.
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              <Button size="sm" asChild>
                <Link href="/students/new">
                  <UserPlus className="mr-2 h-4 w-4" />
                  Add Student
                </Link>
              </Button>
              <Button size="sm" variant="secondary" asChild>
                <Link href="/attendance/mark">
                  <ClipboardCheck className="mr-2 h-4 w-4" />
                  Mark Attendance
                </Link>
              </Button>
            </div>
          </div>

          {/* Right floating cards decoration */}
          <div className="hidden md:block">
            <div className="relative h-40 w-64">
              {/* Floating card 1 */}
              <div className="absolute right-0 top-0 flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 p-3 backdrop-blur-sm">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-500/20">
                  <Users className="h-5 w-5 text-green-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">1,234</p>
                  <p className="text-xs text-slate-400">Students</p>
                </div>
              </div>

              {/* Floating card 2 */}
              <div className="absolute left-0 top-12 flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 p-3 backdrop-blur-sm">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/20">
                  <GraduationCap className="h-5 w-5 text-blue-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">95.2%</p>
                  <p className="text-xs text-slate-400">Attendance</p>
                </div>
              </div>

              {/* Floating card 3 */}
              <div className="absolute bottom-0 right-8 flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 p-3 backdrop-blur-sm">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-500/20">
                  <Trophy className="h-5 w-5 text-amber-400" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">A+ Grade</p>
                  <p className="text-xs text-slate-400">Top Class</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Link key={stat.title} href={stat.href}>
            <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                    <stat.icon className="h-5 w-5 text-primary" />
                  </div>
                  <Badge
                    variant={stat.changeType === "positive" ? "default" : "destructive"}
                    className="flex items-center gap-1 font-medium"
                  >
                    {stat.changeType === "positive" ? (
                      <TrendingUp className="h-3 w-3" />
                    ) : (
                      <TrendingDown className="h-3 w-3" />
                    )}
                    {stat.change}
                  </Badge>
                </div>
                <div className="mt-4">
                  <p className="text-2xl font-bold">{stat.value}</p>
                  <p className="text-sm text-muted-foreground">{stat.title}</p>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Three column layout */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent Students */}
        <Card className="lg:col-span-1">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <div>
              <CardTitle className="text-base font-semibold">Recent Students</CardTitle>
              <CardDescription>Newly enrolled students</CardDescription>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/students" className="flex items-center gap-1">
                View all
                <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentStudents.map((student, index) => (
                <div
                  key={index}
                  className="flex items-center gap-3"
                >
                  <Avatar className="h-9 w-9">
                    <AvatarFallback className="bg-primary/10 text-primary text-xs">
                      {getInitials(student.name)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{student.name}</p>
                    <p className="text-xs text-muted-foreground">{student.class}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-muted-foreground">{student.date}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Recent Payments */}
        <Card className="lg:col-span-1">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <div>
              <CardTitle className="text-base font-semibold">Recent Payments</CardTitle>
              <CardDescription>Latest fee transactions</CardDescription>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/finance/payments" className="flex items-center gap-1">
                View all
                <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentPayments.map((payment, index) => (
                <div
                  key={index}
                  className="flex items-center gap-3"
                >
                  <div
                    className={`flex h-9 w-9 items-center justify-center rounded-full ${
                      payment.status === "paid"
                        ? "bg-green-100 text-green-600"
                        : payment.status === "partial"
                        ? "bg-yellow-100 text-yellow-600"
                        : "bg-red-100 text-red-600"
                    }`}
                  >
                    {payment.status === "paid" ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : payment.status === "partial" ? (
                      <Clock className="h-4 w-4" />
                    ) : (
                      <AlertCircle className="h-4 w-4" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{payment.name}</p>
                    <p className="text-xs text-muted-foreground">{payment.amount}</p>
                  </div>
                  <Badge
                    variant={
                      payment.status === "paid"
                        ? "default"
                        : payment.status === "partial"
                        ? "secondary"
                        : "destructive"
                    }
                    className="capitalize"
                  >
                    {payment.status}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Upcoming Events */}
        <Card className="lg:col-span-1">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <div>
              <CardTitle className="text-base font-semibold">Upcoming Events</CardTitle>
              <CardDescription>Important dates this month</CardDescription>
            </div>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/calendar" className="flex items-center gap-1">
                View all
                <ArrowRight className="h-3 w-3" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {upcomingEvents.map((event, index) => (
                <div
                  key={index}
                  className="flex items-center gap-3"
                >
                  <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                    <Calendar className="h-4 w-4 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{event.title}</p>
                    <p className="text-xs text-muted-foreground">{event.date}</p>
                  </div>
                  <Badge variant="outline" className="capitalize text-xs">
                    {event.type}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Attendance Overview - Full width */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div>
            <CardTitle className="text-base font-semibold">Attendance Overview</CardTitle>
            <CardDescription>Weekly attendance trends</CardDescription>
          </div>
          <Button variant="outline" size="sm" asChild>
            <Link href="/attendance/reports">View Report</Link>
          </Button>
        </CardHeader>
        <CardContent>
          <div className="flex h-[200px] items-center justify-center rounded-lg border border-dashed">
            <p className="text-sm text-muted-foreground">
              Attendance chart will be displayed here
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
