/**
 * SIMS Plus - Multi-Curriculum Type Definitions (Phase 1-3)
 *
 * Types for curriculum profile management, assessment structures,
 * report card configuration, curriculum templates, external exams,
 * predicted grades, credits, and transcripts.
 *
 * All types match backend Pydantic schemas in backend/app/schemas/curriculum.py
 */

// =========================
// Enums / Union Types
// =========================

export type CurriculumType =
  | "ges"
  | "cambridge"
  | "edexcel"
  | "american"
  | "ib"
  | "french"
  | "montessori"
  | "custom";

export type ScoreDisplayMode =
  | "percentage"
  | "grade_only"
  | "grade_and_score"
  | "level"
  | "gpa"
  | "narrative"
  | "mention";

export type AssessmentComponentType =
  | "continuous_assessment"
  | "exam"
  | "class_work"
  | "homework"
  | "midterm"
  | "end_term"
  | "coursework"
  | "controlled_assessment"
  | "external_exam"
  | "practical"
  | "oral"
  | "internal_assessment"
  | "external_assessment"
  | "extended_essay"
  | "tok"
  | "cas"
  | "quiz"
  | "test"
  | "project"
  | "participation"
  | "final"
  | "controle_continu"
  | "epreuve"
  | "observation"
  | "narrative"
  | "portfolio";

export type AcademicCalendarType = "terms" | "semesters" | "quarters";

// =========================
// Curriculum Profile
// =========================

/** Matches CurriculumProfileResponse */
export interface CurriculumProfile {
  id: string;
  name: string;
  curriculum_type: CurriculumType;
  description?: string;
  grading_scale_id?: string;
  academic_calendar_type: AcademicCalendarType;
  periods_per_year: number;
  score_display_mode: ScoreDisplayMode;
  show_position: boolean;
  show_class_average: boolean;
  use_gpa: boolean;
  use_credits: boolean;
  use_criterion_grading: boolean;
  config?: Record<string, unknown>;
  is_default: boolean;
  is_active: boolean;
  school_id?: string;
  created_at: string;
  updated_at: string;
}

/** Matches CurriculumProfileDetailResponse */
export interface CurriculumProfileDetail extends CurriculumProfile {
  assessment_structure?: AssessmentStructure;
  report_config?: ReportCardConfig;
}

/** Matches CurriculumProfileCreate */
export interface CurriculumProfileCreate {
  name: string;
  curriculum_type: CurriculumType;
  description?: string;
  grading_scale_id?: string;
  academic_calendar_type?: AcademicCalendarType;
  periods_per_year?: number;
  score_display_mode?: ScoreDisplayMode;
  show_position?: boolean;
  show_class_average?: boolean;
  use_gpa?: boolean;
  use_credits?: boolean;
  use_criterion_grading?: boolean;
  config?: Record<string, unknown>;
  is_default?: boolean;
}

/** Matches CurriculumProfileUpdate */
export interface CurriculumProfileUpdate {
  name?: string;
  curriculum_type?: CurriculumType;
  description?: string;
  grading_scale_id?: string;
  academic_calendar_type?: AcademicCalendarType;
  periods_per_year?: number;
  score_display_mode?: ScoreDisplayMode;
  show_position?: boolean;
  show_class_average?: boolean;
  use_gpa?: boolean;
  use_credits?: boolean;
  use_criterion_grading?: boolean;
  config?: Record<string, unknown>;
  is_active?: boolean;
}

// =========================
// Assessment Structure
// =========================

/** Matches AssessmentComponentResponse */
export interface AssessmentComponent {
  id: string;
  component_type: AssessmentComponentType;
  name: string;
  weight: number;
  max_score?: number;
  is_external: boolean;
  sequence: number;
  maps_to_ca: boolean;
  maps_to_exam: boolean;
  config?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** Matches AssessmentStructureResponse */
export interface AssessmentStructure {
  id: string;
  curriculum_profile_id: string;
  academic_year_id?: string;
  name: string;
  description?: string;
  is_active: boolean;
  components: AssessmentComponent[];
  created_at: string;
  updated_at: string;
}

/** Matches AssessmentComponentCreate */
export interface AssessmentComponentCreate {
  component_type: AssessmentComponentType;
  name: string;
  weight: number;
  max_score?: number;
  is_external?: boolean;
  sequence?: number;
  maps_to_ca?: boolean;
  maps_to_exam?: boolean;
  config?: Record<string, unknown>;
}

/** Matches AssessmentComponentUpdate (no component_type -- immutable) */
export interface AssessmentComponentUpdate {
  name?: string;
  weight?: number;
  max_score?: number;
  is_external?: boolean;
  sequence?: number;
  maps_to_ca?: boolean;
  maps_to_exam?: boolean;
  config?: Record<string, unknown>;
}

/** Matches AssessmentStructureCreate */
export interface AssessmentStructureCreate {
  name: string;
  description?: string;
  academic_year_id?: string;
  components: AssessmentComponentCreate[];
}

// =========================
// Report Card Config
// =========================

/** Matches ReportCardConfigResponse */
export interface ReportCardConfig {
  id: string;
  curriculum_profile_id: string;
  template_key: string;
  show_position: boolean;
  show_class_average: boolean;
  show_subject_position: boolean;
  show_effort_grade: boolean;
  show_predicted_grades: boolean;
  show_gpa: boolean;
  show_credits: boolean;
  show_honor_roll: boolean;
  show_learner_profile: boolean;
  show_atl_skills: boolean;
  custom_columns?: Record<string, unknown>;
  header_text?: string;
  footer_text?: string;
  created_at: string;
  updated_at: string;
}

/** Matches ReportCardConfigUpdate */
export interface ReportCardConfigUpdate {
  template_key?: string;
  show_position?: boolean;
  show_class_average?: boolean;
  show_subject_position?: boolean;
  show_effort_grade?: boolean;
  show_predicted_grades?: boolean;
  show_gpa?: boolean;
  show_credits?: boolean;
  show_honor_roll?: boolean;
  show_learner_profile?: boolean;
  show_atl_skills?: boolean;
  custom_columns?: Record<string, unknown>;
  header_text?: string;
  footer_text?: string;
}

// =========================
// Template
// =========================

/** Matches CurriculumTemplateInfo */
export interface CurriculumTemplateInfo {
  key: string;
  name: string;
  curriculum_type: CurriculumType;
  description: string;
}

// =========================
// Validation
// =========================

/** Matches ValidateStructureResponse */
export interface ValidateStructureResponse {
  is_valid: boolean;
  total_weight: number;
  message: string;
}

// =========================
// Grade Equivalency
// =========================

/** Matches GradeEquivalencyResponse */
export interface GradeEquivalency {
  id: string;
  source_grading_scale_id: string;
  target_grading_scale_id: string;
  source_grade_id: string;
  target_grade_id: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

/** Matches GradeMapping */
export interface GradeMapping {
  source_grade_id: string;
  target_grade_id: string;
  notes?: string;
}

/** Matches GradeEquivalencyCreate */
export interface GradeEquivalencyCreate {
  source_grading_scale_id: string;
  target_grading_scale_id: string;
  mappings: GradeMapping[];
}

/** Matches GradeConvertRequest */
export interface GradeConvertRequest {
  source_grade_id: string;
  source_grading_scale_id: string;
  target_grading_scale_id: string;
}

// =========================
// Subject Curriculum Mapping
// =========================

/** Matches SubjectCurriculumMappingResponse */
export interface SubjectCurriculumMapping {
  id: string;
  subject_id: string;
  curriculum_profile_id: string;
  external_code?: string;
  external_name?: string;
  level?: string;
  credits?: number;
  coefficient?: number;
  is_hl: boolean;
  grading_scale_id?: string;
  config?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** Matches SubjectCurriculumMappingCreate */
export interface SubjectCurriculumMappingCreate {
  subject_id: string;
  curriculum_profile_id: string;
  external_code?: string;
  external_name?: string;
  level?: string;
  credits?: number;
  coefficient?: number;
  is_hl?: boolean;
  grading_scale_id?: string;
  config?: Record<string, unknown>;
}

/** Matches SubjectCurriculumMappingUpdate */
export interface SubjectCurriculumMappingUpdate {
  external_code?: string;
  external_name?: string;
  level?: string;
  credits?: number;
  coefficient?: number;
  is_hl?: boolean;
  grading_scale_id?: string;
  config?: Record<string, unknown>;
}

// =========================
// Curriculum Report Data
// =========================

export interface CurriculumReportData {
  curriculum_type?: CurriculumType;
  gpa?: number;
  weighted_gpa?: number;
  cumulative_gpa?: number;
  total_credits_earned?: number;
  cumulative_credits?: number;
  honor_roll?: boolean;
  ib_total_points?: number;
  french_mention?: string;
  extra_data?: Record<string, unknown>;
}

// =========================
// External Exam Board
// =========================

/** Matches backend enum: waec, cambridge_international, edexcel, college_board, ibo, other */
export type ExternalExamBoard =
  | "waec"
  | "cambridge_international"
  | "edexcel"
  | "college_board"
  | "ibo"
  | "other";

// =========================
// External Exam Registration
// =========================

/** Matches ExternalExamRegistrationResponse */
export interface ExternalExamRegistration {
  id: string;
  student_id: string;
  exam_board: ExternalExamBoard;
  exam_session: string;
  subjects: Record<string, unknown>[];
  candidate_number?: string;
  center_number?: string;
  registration_status: "pending" | "registered" | "confirmed";
  results?: Record<string, unknown>[];
  registration_date?: string;
  results_date?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

/** Matches ExternalExamSubject (used in create/update payloads) */
export interface ExternalExamSubject {
  subject_code: string;
  subject_name?: string;
  level?: string;
  paper_numbers?: string[];
}

/** Matches ExternalExamRegistrationCreate */
export interface ExternalExamRegistrationCreate {
  student_id: string;
  exam_board: ExternalExamBoard;
  exam_session: string;
  subjects: ExternalExamSubject[];
  candidate_number?: string;
  center_number?: string;
  registration_date?: string;
  notes?: string;
}

/** Matches ExternalExamRegistrationUpdate */
export interface ExternalExamRegistrationUpdate {
  subjects?: ExternalExamSubject[];
  candidate_number?: string;
  center_number?: string;
  registration_status?: "pending" | "registered" | "confirmed";
  registration_date?: string;
  notes?: string;
}

// =========================
// Results Import
// =========================

/** Matches ResultsImportPreview */
export interface ResultsImportPreview {
  total_rows: number;
  matched: number;
  unmatched: number;
  errors: string[];
  preview_rows: Record<string, unknown>[];
}

/** Matches ResultsImportCommit */
export interface ResultsImportCommit {
  imported: number;
  skipped: number;
  errors: string[];
}

// =========================
// Predicted Grades
// =========================

/** Matches PredictedGradeResponse */
export interface PredictedGrade {
  id: string;
  student_id: string;
  subject_id: string;
  subject_name?: string;
  academic_year_id: string;
  term_id?: string;
  predicted_grade?: string;
  target_grade?: string;
  predicted_score?: number;
  predicted_by?: string;
  predicted_at?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

/** Matches PredictedGradeCreate */
export interface PredictedGradeCreate {
  student_id: string;
  subject_id: string;
  academic_year_id: string;
  term_id?: string;
  predicted_grade?: string;
  target_grade?: string;
  predicted_score?: number;
  notes?: string;
}

/** Matches BulkPredictedGradeCreate */
export interface PredictedGradeBulk {
  predictions: PredictedGradeCreate[];
}

// =========================
// Credits & GPA
// =========================

/** Matches StudentCreditResponse */
export interface CreditRecord {
  id: string;
  student_id: string;
  subject_id: string;
  curriculum_profile_id: string;
  academic_year_id: string;
  term_id?: string;
  credits_attempted: number;
  credits_earned: number;
  grade_points?: number;
  weighted_grade_points?: number;
  is_ap: boolean;
  is_honors: boolean;
  created_at: string;
}

/** Matches StudentGPAResponse */
export interface StudentGPA {
  student_id: string;
  curriculum_profile_id: string;
  term_gpa?: number;
  weighted_gpa?: number;
  cumulative_gpa?: number;
  cumulative_weighted_gpa?: number;
  total_credits_attempted: number;
  total_credits_earned: number;
  honor_roll: boolean;
}

/** Matches StudentCreditRecordCreate */
export interface StudentCreditRecordCreate {
  student_id: string;
  subject_id: string;
  curriculum_profile_id: string;
  academic_year_id: string;
  term_id?: string;
  credits_attempted: number;
  credits_earned: number;
  grade_points?: number;
  weighted_grade_points?: number;
  is_ap?: boolean;
  is_honors?: boolean;
}

// =========================
// Transcript
// =========================

/** Matches TranscriptSubjectRecord */
export interface TranscriptSubject {
  subject_name: string;
  subject_code?: string;
  grade?: string;
  credits_attempted: number;
  credits_earned: number;
  grade_points?: number;
  is_ap: boolean;
  is_honors: boolean;
}

/** Matches TranscriptTermRecord */
export interface TranscriptTerm {
  academic_year: string;
  term?: string;
  subjects: TranscriptSubject[];
  term_gpa?: number;
  term_credits_earned: number;
}

/** Matches TranscriptResponse */
export interface TranscriptData {
  student_id: string;
  student_name: string;
  curriculum_profile: string;
  academic_records: TranscriptTerm[];
  cumulative_gpa?: number;
  weighted_gpa?: number;
  total_credits_earned: number;
  graduation_credits_required?: number;
  credits_remaining?: number;
  honors: string[];
  generated_at: string;
}

// =========================
// Montessori Assessment
// =========================

export type MontessoriProgressLevel = "emerging" | "developing" | "practicing" | "mastery";

export interface MontessoriSkill {
  name: string;
  progress_level: MontessoriProgressLevel;
}

export interface MontessoriArea {
  name: string;
  skills: MontessoriSkill[];
  narrative: string;
}

export interface MontessoriWorkSample {
  description: string;
}

export interface MontessoriAssessmentData {
  developmental_areas: MontessoriArea[];
  work_samples: MontessoriWorkSample[];
  goals: string[];
  general_narrative: string;
}

export interface MontessoriAssessmentCreate extends MontessoriAssessmentData {
  student_id: string;
}

export interface MontessoriAssessmentResponse {
  student_id: string;
  student_name: string;
  developmental_areas: MontessoriArea[];
  work_samples: MontessoriWorkSample[];
  goals: string[];
  general_narrative: string;
  updated_at?: string;
}

// =========================
// Dual-Track Report
// =========================

export interface DualTrackSubjectResult {
  subject_name: string;
  subject_code?: string;
  class_score?: number;
  exams_score?: number;
  total_score?: number;
  grade?: string;
  grade_remark?: string;
  subject_position?: number;
  /** International-specific: component scores keyed by component_type */
  component_scores?: Record<string, number>;
  final_score?: number;
  effort_grade?: string;
}

export interface DualTrackComponent {
  name: string;
  weight: number;
  component_type: string;
}

export interface DualTrackReportData {
  ges_results: DualTrackSubjectResult[];
  international_results: DualTrackSubjectResult[];
  international_components: DualTrackComponent[];
  international_curriculum_name: string;
  ges_average?: number;
  ges_position?: number;
  international_average?: number;
  gpa?: number;
  ib_total_points?: number;
}
