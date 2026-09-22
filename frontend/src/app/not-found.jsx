import Link from "next/link";

import Icon from "@/components/ui/Icon";

export default function NotFound() {
  return (
    <div className="empty" style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
      <div>
        <div className="ei">
          <Icon name="search" />
        </div>
        <h3>Page not found</h3>
        <p>The page you are looking for does not exist.</p>
        <Link href="/" className="btn btn-primary mt16">
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
