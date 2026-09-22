import Icon from "@/components/ui/Icon";
import { site } from "@/data/site";

// Left brand panel of the login / register pages (hidden on small screens).
export default function AuthAside({ headline, lead, features }) {
  return (
    <div className="auth-aside">
      <div className="a-brand">
        <span className="mark">
          <Icon name="spider" />
        </span>
        {site.name}
      </div>
      <div className="a-mid">
        <h2>{headline}</h2>
        <p>{lead}</p>
        <div className="feats">
          {features.map((f) => (
            <div key={f.text} className="feat">
              <span className="fk">
                <Icon name={f.icon} />
              </span>
              {f.text}
            </div>
          ))}
        </div>
      </div>
      <div className="tiny" style={{ position: "relative", zIndex: 1, opacity: 0.7 }}>
        &copy; {site.year} {site.company} · {site.version}
      </div>
    </div>
  );
}
