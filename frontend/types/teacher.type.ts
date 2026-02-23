/**
 * SIMS Plus - Teacher Portal Type Definitions
 *
 * Types for the teacher-facing portal (Sprint 15-16). These types match the
 * Pydantic schemas defined in backend/app/schemas/teacher.py. The backend
 * schemas are the source of truth -- these types MUST stay aligned with them.
 */

// =========================
// Teacher Profile
// =========================

/**
 * TeacherProfile is a frontend-only type. The backend has no dedicated
 * /teacher/profile endpoint -- the profile page will reuse the dashboard
 * endpoint or derive profile from the session. Kept for UI convenience.
 */
export interface TeacherProfile {
  id: string;
  staff_id: string;
  user_id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  photo_url: string | null;
  job_title: string;
  department: string | null;
  is_head_teacher: boolean;
  is_class_teacher: boolean;
  class_teacher_section_id: string | null;
  class_teacher_section_name: string | null;
  class_teacher_class_name: string | null;
}

export interface TeacherProfileUpdate {
  phone?: string;
  photo_url?: string;
}

// =========================
// Dashboard Types
// =========================

/**
 * Matches backend schema: TeacherDashboard
 * Fields: teacher_name, staff_id, total_classes, total_subjects,
 * total_students, classes, subjects, today_schedule, pending_tasks
 */
export interface TeacherDashboardData {
  teacher_name: string;
  staff_id: string;
  total_classes: number;
  total_subjects: number;
  total_students: number;
  classes: TeacherClassSummary[];
  subjects: TeacherSubjectSummary[];
  today_schedule: UpcomingLesson[];
  pending_tasks: PendingTask[];
}

/**
 * Matches backend schema: TeacherSubjectSummary
 */
export interface TeacherSubjectSummary {
  subject_id: string;
  subject_name: string;
  class_count: number;
}

/**
 * Matches backend schema: UpcomingLesson
 */
export interface UpcomingLesson {
  timetable_id: string;
  class_name: string;
  section_name: string | null;
  subject_name: string;
  day_of_week: number;
  period_number: number;
  start_time: string;
  end_time: string;
  room: string | null;
}

/**
 * Matches backend schema: PendingTask
 */
export interface PendingTask {
  task_type: string;
  description: string;
  count: number;
  link_context: Record<string, unknown> | null;
}

// =========================
// Schedule Types
// =========================

/**
 * Matches backend schema: ScheduleEntry
 */
export interface TeacherScheduleEntry {
  id: string;
  class_id: string;
  class_name: string;
  section_id: string | null;
  section_name: string | null;
  subject_id: string | null;
  subject_name: string | null;
  day_of_week: number;
  period_number: number;
  start_time: string;
  end_time: string;
  room: string | null;
}

/**
 * Matches backend schema: DaySchedule
 */
export interface TeacherScheduleDay {
  day_of_week: number;
  day_name: string;
  entries: TeacherScheduleEntry[];
}

/**
 * Matches backend schema: WeekSchedule
 * Note: Backend only returns { days }. No teacher_name, academic_year, term,
 * or total_periods fields.
 */
export interface TeacherWeeklySchedule {
  days: TeacherScheduleDay[];
}

// =========================
// Class Types (teacher view)
// =========================

/**
 * Matches backend schema: TeacherClassSummary
 * Note: Backend does NOT return subject_id, subject_name, subject_code,
 * or periods_per_week. It returns class assignments with student counts.
 */
export interface TeacherClassSummary {
  class_id: string;
  class_name: string;
  section_id: string | null;
  section_name: string | null;
  student_count: number;
  is_class_teacher: boolean;
}

/**
 * Matches backend schema: ClassOverview
 * Note: Backend returns subjects as a TeacherSubjectSummary[] list,
 * not a single subject_id/subject_name/subject_code.
 */
export interface TeacherClassDetail {
  class_id: string;
  class_name: string;
  section_id: string | null;
  section_name: string | null;
  student_count: number;
  subjects: TeacherSubjectSummary[];
  is_class_teacher: boolean;
}

/**
 * Matches backend schema: ClassStudentListResponse
 */
export interface TeacherClassStudentListResponse {
  students: TeacherStudentSummary[];
  total: number;
}

/**
 * Matches backend schema: ClassStudentItem
 */
export interface TeacherStudentSummary {
  id: string;
  student_id: string;
  first_name: string;
  last_name: string;
  middle_name: string | null;
  gender: string;
  photo_url: string | null;
  status: string;
}

/**
 * TeacherStudentDetail is a frontend-only type. The backend has no dedicated
 * /teacher/classes/{classId}/students/{studentId} detail endpoint. The student
 * detail page will compose data from the class student list and notes endpoints.
 * Kept for UI convenience.
 */
export interface TeacherStudentDetail {
  id: string;
  student_id: string;
  first_name: string;
  last_name: string;
  middle_name: string | null;
  date_of_birth: string;
  gender: string;
  photo_url: string | null;
  class_name: string;
  section_name: string | null;
  status: string;
  guardians: TeacherStudentGuardian[];
  attendance_summary: TeacherStudentAttendanceSummary;
  subject_scores: TeacherStudentSubjectScore[];
  recent_notes: TeacherNoteItem[];
}

export interface TeacherStudentGuardian {
  name: string;
  relationship: string;
  phone: string;
  email: string | null;
  is_primary: boolean;
}

export interface TeacherStudentAttendanceSummary {
  total_days: number;
  present: number;
  absent: number;
  late: number;
  excused: number;
  rate: number;
}

export interface TeacherStudentSubjectScore {
  subject_id: string;
  subject_name: string;
  ca_score: number | null;
  ca_max: number;
  exam_score: number | null;
  exam_max: number;
  total: number | null;
  grade: string | null;
  position: number | null;
}

// =========================
// Attendance Types (teacher view)
// =========================

export type TeacherAttendanceStatus = "present" | "absent" | "late" | "excused" | "sick";

/**
 * Matches backend schema: StudentAttendanceSummary
 */
export interface TeacherStudentAttendanceRecord {
  student_id: string;
  student_name: string;
  days_present: number;
  days_absent: number;
  days_late: number;
  total_days: number;
  attendance_percentage: number | null;
}

/**
 * Matches backend schema: ClassAttendanceSummary
 */
export interface TeacherClassAttendanceSummary {
  class_id: string;
  class_name: string;
  section_id: string | null;
  section_name: string | null;
  total_students: number;
  present_today: number;
  absent_today: number;
  late_today: number;
  attendance_percentage: number | null;
  students: TeacherStudentAttendanceRecord[];
}

/**
 * Frontend-only types for the attendance marking UI.
 * Attendance marking is handled by the existing /attendance module endpoints,
 * not the teacher portal. These types are kept for the attendance page's
 * local state management.
 */
export interface TeacherAttendanceStudent {
  student_id: string;
  student_number: string;
  first_name: string;
  last_name: string;
  gender: string;
  photo_url: string | null;
  status: TeacherAttendanceStatus | null;
  remarks: string | null;
}

export interface TeacherAttendanceSection {
  section_id: string;
  section_name: string;
  class_id: string;
  class_name: string;
  date: string;
  is_marked: boolean;
  total_students: number;
  present: number;
  absent: number;
  late: number;
  students: TeacherAttendanceStudent[];
}

export interface TeacherAttendanceMark {
  student_id: string;
  status: TeacherAttendanceStatus;
  remarks?: string;
}

export interface TeacherBulkAttendanceSubmit {
  section_id: string;
  date: string;
  records: TeacherAttendanceMark[];
}

export interface TeacherBulkAttendanceResult {
  created: number;
  updated: number;
  failed: number;
  errors: { student_id: string; error: string }[];
}

// =========================
// Grading Types (teacher view)
// =========================

/**
 * Matches backend schema: PendingScoreEntry
 */
export interface TeacherPendingScoreEntry {
  exam_id: string;
  exam_name: string;
  exam_subject_id: string;
  subject_id: string;
  subject_name: string;
  class_id: string;
  class_name: string;
  section_id: string | null;
  section_name: string | null;
  max_score: number;
  total_students: number;
  scores_entered: number;
  status: string;
}

/**
 * Matches backend schema: ScoreEntryItem (request body)
 */
export interface TeacherScoreEntryItem {
  student_id: string;
  score: number | null;
  is_absent: boolean;
  teacher_remark?: string;
}

/**
 * Matches backend schema: BulkScoreEntryRequest
 */
export interface TeacherBulkScoreEntryRequest {
  scores: TeacherScoreEntryItem[];
}

/**
 * Matches backend schema: ScoreEntryResult
 */
export interface TeacherScoreEntryResult {
  student_id: string;
  success: boolean;
  error: string | null;
  grade: string | null;
  grade_remark: string | null;
}

/**
 * Matches backend schema: BulkScoreEntryResponse
 */
export interface TeacherBulkScoreEntryResponse {
  total: number;
  successful: number;
  failed: number;
  results: TeacherScoreEntryResult[];
}

/**
 * Matches backend schema: StudentGradeSummary
 */
export interface TeacherStudentGradeSummary {
  student_id: string;
  student_name: string;
  exam_score: number | null;
  exam_grade: string | null;
  ca_average: number | null;
  total_score: number | null;
  grade: string | null;
  grade_remark: string | null;
}

/**
 * Matches backend schema: ClassGradeSummary
 */
export interface TeacherClassGradeSummary {
  class_id: string;
  class_name: string;
  subject_id: string;
  subject_name: string;
  term_id: string;
  term_name: string;
  students: TeacherStudentGradeSummary[];
  class_average: number | null;
  highest_score: number | null;
  lowest_score: number | null;
  total_students: number;
}

/**
 * Frontend-only types kept for score entry page local state and the
 * grading list page. These types are used by pages that will be updated
 * to work with the actual backend endpoints.
 */
export interface TeacherGradingSubject {
  class_id: string;
  class_name: string;
  section_id: string | null;
  section_name: string | null;
  subject_id: string;
  subject_name: string;
  subject_code: string;
  student_count: number;
  has_exam: boolean;
  exam_status: string | null;
  ca_count: number;
  scores_entered: boolean;
}

export interface TeacherScoreEntry {
  student_id: string;
  student_number: string;
  first_name: string;
  last_name: string;
  score: number | null;
  is_absent: boolean;
  remark: string | null;
}

export interface TeacherScoreSheet {
  exam_subject_id: string;
  subject_name: string;
  subject_code: string;
  class_name: string;
  section_name: string | null;
  max_score: number;
  pass_mark: number;
  status: string;
  students: TeacherScoreEntry[];
}

export interface TeacherScoreSave {
  exam_subject_id: string;
  scores: {
    student_id: string;
    score: number | null;
    is_absent: boolean;
    remark?: string;
  }[];
}

export interface TeacherScoreSaveResult {
  total: number;
  successful: number;
  failed: number;
  results: TeacherScoreEntryResult[];
}

// =========================
// Notes Types (teacher view)
// =========================

export type TeacherNoteType = "positive" | "concern" | "information" | "action_required";

/**
 * Matches backend schema: TeacherNoteResponse
 */
export interface TeacherNoteItem {
  id: string;
  student_id: string;
  student_name: string | null;
  subject_id: string | null;
  subject_name: string | null;
  note_type: string;
  content: string;
  is_visible_to_parent: boolean;
  parent_acknowledged: boolean;
  parent_acknowledged_at: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Matches backend schema: TeacherNoteCreate
 */
export interface TeacherNoteCreate {
  student_id: string;
  subject_id?: string;
  note_type: TeacherNoteType;
  content: string;
  is_visible_to_parent?: boolean;
}

/**
 * Matches backend schema: TeacherNoteListResponse
 */
export interface TeacherNoteListResponse {
  notes: TeacherNoteItem[];
  total: number;
}

// =========================
// Reports Types (teacher view)
// =========================

/**
 * Matches backend schema: ReportCommentResponse
 */
export interface TeacherReportComment {
  id: string;
  student_id: string;
  student_name: string | null;
  term_id: string;
  academic_year_id: string;
  class_teacher_comment: string | null;
  head_teacher_comment: string | null;
  class_teacher_signed: boolean;
  head_teacher_signed: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * Matches backend schema: ReportCommentListResponse
 */
export interface TeacherReportCommentListResponse {
  comments: TeacherReportComment[];
  total: number;
}

/**
 * Matches backend schema: ReportCommentCreate
 */
export interface TeacherClassTeacherCommentCreate {
  class_teacher_comment: string;
}

/**
 * Matches backend schema: HeadTeacherCommentCreate
 */
export interface TeacherHeadTeacherCommentCreate {
  head_teacher_comment: string;
}

// =========================
// Lesson Plan Types
// =========================

/**
 * Matches backend schema: LessonPlanResponse
 */
export interface TeacherLessonPlan {
  id: string;
  teacher_id: string;
  class_id: string;
  class_name: string | null;
  subject_id: string;
  subject_name: string | null;
  date: string;
  period: number | null;
  topic: string;
  objectives: string | null;
  resources: string | null;
  activities: string | null;
  notes: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

/**
 * Matches backend schema: LessonPlanListResponse
 */
export interface TeacherLessonPlanListResponse {
  plans: TeacherLessonPlan[];
  total: number;
}

/**
 * Matches backend schema: LessonPlanCreate
 */
export interface TeacherLessonPlanCreate {
  class_id: string;
  subject_id: string;
  date: string;
  period?: number;
  topic: string;
  objectives?: string;
  resources?: string;
  activities?: string;
  notes?: string;
}

/**
 * Matches backend schema: LessonPlanUpdate
 */
export interface TeacherLessonPlanUpdate {
  topic?: string;
  objectives?: string;
  resources?: string;
  activities?: string;
  notes?: string;
  status?: string;
}

// =========================
// Communication Types
// =========================

/**
 * Matches backend schema: ClassBroadcastRequest
 */
export interface TeacherClassBroadcastRequest {
  title: string;
  content: string;
  class_id: string;
  priority?: "normal" | "important" | "urgent";
}

/**
 * Matches backend schema: ClassBroadcastResponse
 */
export interface TeacherClassBroadcastResponse {
  announcement_id: string;
  message: string;
}

// =========================
// Head Teacher Types
// =========================

/**
 * Matches backend schema: TeacherPerformanceItem
 */
export interface TeacherPerformanceItem {
  staff_id: string;
  teacher_name: string;
  total_classes: number;
  total_subjects: number;
  total_students: number;
  lesson_plans_created: number;
  lesson_plans_taught: number;
  scores_entered: number;
  scores_pending: number;
  notes_created: number;
  reports_signed: number;
}

/**
 * Matches backend schema: TeacherPerformanceSummary
 */
export interface TeacherPerformanceSummary {
  total_teachers: number;
  teachers: TeacherPerformanceItem[];
  overall_lesson_plan_completion: number | null;
  overall_score_entry_completion: number | null;
}

/**
 * Frontend-only types kept for the head teacher overview page.
 * The backend has no /teacher/head-teacher/overview endpoint. This page
 * will need to be reimplemented to use /teacher/head-teacher/performance
 * or composed from multiple endpoints.
 */
export interface HeadTeacherOverview {
  school_name: string;
  total_students: number;
  total_staff: number;
  total_classes: number;
  attendance_rate_today: number | null;
  attendance_rate_week: number | null;
  classes: HeadTeacherClassSummary[];
}

export interface HeadTeacherClassSummary {
  class_id: string;
  class_name: string;
  section_count: number;
  student_count: number;
  class_teacher_name: string | null;
  attendance_rate: number | null;
  average_score: number | null;
}

/**
 * Frontend-only type. Kept for the head teacher performance page.
 * The backend /teacher/head-teacher/performance endpoint actually returns
 * TeacherPerformanceSummary (teacher-centric metrics, not class-centric).
 * This page will need to be updated to display teacher performance data
 * in a future iteration.
 */
export interface HeadTeacherPerformanceData {
  class_id: string;
  class_name: string;
  subjects: {
    subject_name: string;
    average: number;
    highest: number;
    lowest: number;
    pass_rate: number;
  }[];
  overall_average: number;
  class_size: number;
}

// =========================
// Notification Types (teacher view)
// =========================

/**
 * Frontend-only types. The backend has no /teacher/notifications endpoint.
 * These are kept for the notifications page which will need to be connected
 * to a general notifications API or removed in a future iteration.
 */
export interface TeacherNotification {
  id: string;
  title: string;
  message: string;
  type: "info" | "success" | "warning" | "error";
  category: string;
  is_read: boolean;
  created_at: string;
  link: string | null;
}

export interface TeacherNotificationList {
  items: TeacherNotification[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  unread_count: number;
}
