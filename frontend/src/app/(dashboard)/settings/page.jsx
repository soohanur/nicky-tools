import NotificationsCard from "@/components/dashboard/NotificationsCard";
import WorkerConfigCard from "@/components/dashboard/WorkerConfigCard";

export const metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <section>
      <div className="grid two-col">
        <WorkerConfigCard />
        <NotificationsCard />
      </div>
    </section>
  );
}
