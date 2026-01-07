import type { ResourceStatus } from "@/lib/api";

const statusStyles: Record<
  ResourceStatus,
  { label: string; className: string }
> = {
  VIRTUAL: { label: "Virtual", className: "badge badge--virtual" },
  MATERIALIZED: { label: "Materialized", className: "badge badge--materialized" },
  PROVISIONING: { label: "Provisioning", className: "badge badge--provisioning" },
  FAILED: { label: "Failed", className: "badge badge--failed" }
};

export function StatusBadge({ status }: { status: ResourceStatus }) {
  const style = statusStyles[status];
  return <span className={style.className}>{style.label}</span>;
}