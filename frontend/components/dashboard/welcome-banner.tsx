"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Users,
  UserPlus,
  ClipboardCheck,
  GraduationCap,
  Trophy,
} from "lucide-react";

interface WelcomeBannerProps {
  firstName: string;
  totalStudents: string;
  attendanceRate: string;
  collectionRate: string;
}

export function WelcomeBanner({
  firstName,
  totalStudents,
  attendanceRate,
  collectionRate,
}: WelcomeBannerProps) {
  return (
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
            Track attendance, manage students, and monitor your school&apos;s
            performance all in one place.
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
                <p className="text-sm font-medium text-white">{totalStudents}</p>
                <p className="text-xs text-slate-400">Students</p>
              </div>
            </div>

            {/* Floating card 2 */}
            <div className="absolute left-0 top-12 flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 p-3 backdrop-blur-sm">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/20">
                <GraduationCap className="h-5 w-5 text-blue-400" />
              </div>
              <div>
                <p className="text-sm font-medium text-white">{attendanceRate}</p>
                <p className="text-xs text-slate-400">Attendance</p>
              </div>
            </div>

            {/* Floating card 3 */}
            <div className="absolute bottom-0 right-8 flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 p-3 backdrop-blur-sm">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-500/20">
                <Trophy className="h-5 w-5 text-amber-400" />
              </div>
              <div>
                <p className="text-sm font-medium text-white">{collectionRate}</p>
                <p className="text-xs text-slate-400">Collection</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
