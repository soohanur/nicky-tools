import Icon from "@/components/ui/Icon";

// Brand mark: gradient blue tile with the search glyph.
export default function Logo({ className = "rail-logo" }) {
  return (
    <span className={className} aria-hidden="true">
      <Icon name="spider" />
    </span>
  );
}
