"use client";

import InputFileCard from "@/components/dashboard/InputFileCard";
import ProgressCard from "@/components/dashboard/ProgressCard";
import StatsCard from "@/components/dashboard/StatsCard";
import Alert from "@/components/ui/Alert";
import { useJob } from "@/hooks/useJob";

// Controls: upload + lifecycle + progress on the left, live stats on the right.
export default function ControlsPage() {
  const { error, setError } = useJob();
  return (
    <section>
      {error && <Alert onClose={() => setError("")}>{error}</Alert>}
      <div className="grid two-col" style={{ alignItems: "stretch" }}>
        <div className="grid" style={{ gap: 18 }}>
          <InputFileCard />
          <ProgressCard />
        </div>
        <StatsCard />
      </div>
    </section>
  );
}
