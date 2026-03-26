import type { TermReportWithDetails, SubjectResult } from "@/types";
import type {
  CurriculumProfile,
  ReportCardConfig,
  CurriculumReportData,
} from "@/types/curriculum.type";

export interface ReportViewProps {
  report: TermReportWithDetails;
  profile: CurriculumProfile;
  config?: ReportCardConfig;
  curriculumData?: CurriculumReportData;
}
