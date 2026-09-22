import Icon from "@/components/ui/Icon";
import { site } from "@/data/site";

// Compact brand shown above the form on small screens (.ac-brand).
export default function AuthBrand() {
  return (
    <div className="ac-brand">
      <span className="mark">
        <Icon name="spider" />
      </span>
      {site.name}
    </div>
  );
}
