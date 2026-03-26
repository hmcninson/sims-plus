import { GESReport } from "./GESReport";
import { CambridgeReport } from "./CambridgeReport";
import { AmericanReport } from "./AmericanReport";
import { IBReport } from "./IBReport";
import { FrenchReport } from "./FrenchReport";
import { MontessoriReport } from "./MontessoriReport";
import type { ReportViewProps } from "./types";
import type { CurriculumType } from "@/types/curriculum.type";

interface ReportCardContentProps extends ReportViewProps {
  /**
   * Override which report view to render.
   * If not provided, uses the profile's curriculum_type.
   */
  overrideCurriculumType?: CurriculumType;
}

/**
 * Switch component that dispatches to the correct curriculum-specific
 * report card view based on the profile's curriculum type.
 *
 * This is a display-only component -- it renders data, not edit forms.
 */
export function ReportCardContent({
  report,
  profile,
  config,
  curriculumData,
  overrideCurriculumType,
}: ReportCardContentProps) {
  const curriculumType = overrideCurriculumType || profile?.curriculum_type || "ges";

  const viewProps: ReportViewProps = {
    report,
    profile,
    config,
    curriculumData,
  };

  switch (curriculumType) {
    case "ges":
      return <GESReport {...viewProps} />;

    case "cambridge":
    case "edexcel":
      return <CambridgeReport {...viewProps} />;

    case "american":
      return <AmericanReport {...viewProps} />;

    case "ib":
      return <IBReport {...viewProps} />;

    case "french":
      return <FrenchReport {...viewProps} />;

    case "montessori":
      return <MontessoriReport {...viewProps} />;

    case "custom":
      // Custom profiles fall back to GES layout as the most generic option
      return <GESReport {...viewProps} />;

    default:
      // Unknown curriculum types fall back to GES layout
      return <GESReport {...viewProps} />;
  }
}
