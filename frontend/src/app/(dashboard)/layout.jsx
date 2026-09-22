import Shell from "@/components/layout/Shell";

export const metadata = {
  title: "Dashboard",
};

// Every dashboard page shares the rail + app bar and the current-job state.
export default function DashboardLayout({ children }) {
  return <Shell title="Scraply Dashboard">{children}</Shell>;
}
