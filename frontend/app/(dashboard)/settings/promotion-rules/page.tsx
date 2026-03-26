import { Suspense } from "react";

import { PromotionRulesPage } from "./promotion-rules-page";
import PromotionRulesLoading from "./loading";

export default function Page() {
  return (
    <Suspense fallback={<PromotionRulesLoading />}>
      <PromotionRulesPage />
    </Suspense>
  );
}
