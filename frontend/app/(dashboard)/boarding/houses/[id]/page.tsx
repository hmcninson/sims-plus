import { Metadata } from "next";
import { getHouse, getDormitories } from "@/actions/boarding.action";
import { HouseDetailView } from "./house-detail";

export const metadata: Metadata = {
  title: "House Detail",
};

interface Props {
  params: Promise<{ id: string }>;
}

export default async function HouseDetailPage({ params }: Props) {
  const { id } = await params;

  const [houseResult, dormitoriesResult] = await Promise.all([
    getHouse(id),
    getDormitories({ houseId: id }),
  ]);

  const house = houseResult.success ? houseResult.data! : null;
  const dormitories = dormitoriesResult.success ? dormitoriesResult.data!.items : [];

  if (!house) {
    return (
      <div className="flex h-[400px] flex-col items-center justify-center gap-4">
        <p className="text-lg font-semibold">House not found</p>
        <p className="text-muted-foreground">{houseResult.error || "Unable to load house details"}</p>
      </div>
    );
  }

  return <HouseDetailView house={house} initialDormitories={dormitories} />;
}
