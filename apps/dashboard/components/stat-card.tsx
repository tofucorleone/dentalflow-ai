import type { LucideIcon } from "lucide-react";

type StatTone =
  | "appointments"
  | "patients"
  | "treatments"
  | "revenue";

type StatCardProps = {
  label: string;
  value: string | number;
  detail: string;
  icon: LucideIcon;
  tone: StatTone;
};

const sparklinePaths: Record<StatTone, string> = {
  appointments:
    "M2 42 L18 47 L34 29 L50 35 L67 17 L84 27 L101 11 L118 3",
  patients:
    "M2 46 L18 20 L34 29 L50 10 L67 19 L84 8 L101 25 L118 3",
  treatments:
    "M2 43 L18 29 L34 37 L50 18 L67 27 L84 10 L101 17 L118 3",
  revenue:
    "M2 47 L18 21 L34 32 L50 11 L67 25 L84 8 L101 18 L118 3",
};

export function StatCard({
  label,
  value,
  detail,
  icon: Icon,
  tone,
}: StatCardProps) {
  return (
    <article className={`stat-card stat-card-${tone}`}>
      <div className="stat-card-top">
        <div className="stat-icon">
          <Icon size={36} strokeWidth={2.1} />
        </div>

        <p>{label}</p>
      </div>

      <div className="stat-card-bottom">
        <div className="stat-card-copy">
          <strong>{value}</strong>
          <span>{detail}</span>
        </div>

        <svg
          className="stat-sparkline"
          viewBox="0 0 120 52"
          aria-hidden="true"
        >
          <path
            className="stat-sparkline-area"
            d={`${sparklinePaths[tone]} L118 52 L2 52 Z`}
          />
          <path
            className="stat-sparkline-line"
            d={sparklinePaths[tone]}
          />
          <circle cx="118" cy="3" r="3" />
        </svg>
      </div>
    </article>
  );
}
