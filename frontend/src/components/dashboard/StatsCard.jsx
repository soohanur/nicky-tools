"use client";

import Icon from "@/components/ui/Icon";
import { useJob } from "@/hooks/useJob";
import { formatNumber } from "@/lib/format";

function Stat({ icon, color, label, value, note }) {
  return (
    <div className="card stat">
      <div className="top">
        <span className={`ic ${color}`}>
          <Icon name={icon} />
        </span>
        {label}
      </div>
      <div className="num">{value}</div>
      <div className="note">{note}</div>
    </div>
  );
}

// Six live counters for the current job.
export default function StatsCard() {
  const { stats } = useJob();
  return (
    <div className="card" style={{ display: "flex", flexDirection: "column" }}>
      <div className="card-head">
        <h2>Extraction Stats</h2>
      </div>
      <div className="grid stat-grid" style={{ gridTemplateColumns: "1fr 1fr", gridAutoRows: "1fr", flex: 1 }}>
        <Stat icon="rows" color="ic-blue" label="Total Rows" value={formatNumber(stats.total)} note="in input file" />
        <Stat icon="checkc" color="ic-green" label="Completed" value={formatNumber(stats.processed)} note="rows processed" />
        <Stat icon="pct" color="ic-purple" label="Success Rate" value={`${stats.rate}%`} note="contact found" />
        <Stat icon="phone" color="ic-blue" label="Numbers Found" value={formatNumber(stats.numbers)} note="phone numbers" />
        <Stat icon="phoneoff" color="ic-red" label="Missing Numbers" value={formatNumber(stats.missing)} note="no number" />
        <Stat icon="mail" color="ic-amber" label="Emails" value={formatNumber(stats.emails)} note="email addresses" />
      </div>
    </div>
  );
}
