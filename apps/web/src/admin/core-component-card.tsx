// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
import type { CoreComponent } from "../api/admin-api";
import { Badge, Card } from "../components/ui-primitives";
import { FACT_LABELS_VI, STATUS_VIEW, factValue } from "./admin-format";

const linkClass = "inline-block text-lg font-semibold text-blue-800 underline";

/** One core component: status badge, latency, small facts, link to its native console. */
export function CoreComponentCard({ component }: { component: CoreComponent }) {
  const view = STATUS_VIEW[component.status];
  const facts = Object.entries(component.facts);
  return (
    <Card
      title={component.label}
      actions={
        <span data-testid={`status-${component.key}`}>
          <Badge tone={view.tone}>{view.label}</Badge>
        </span>
      }
    >
      <p className="mb-2 text-base text-slate-600">Độ trễ: {component.latency_ms} ms</p>
      {facts.length > 0 && (
        <dl className="mb-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-lg">
          {facts.map(([key, value]) => (
            <div key={key} className="contents">
              <dt className="text-slate-600">{FACT_LABELS_VI[key] ?? key}</dt>
              <dd className={`break-all font-mono ${key === "error" ? "text-red-800" : ""}`}>{factValue(value)}</dd>
            </div>
          ))}
        </dl>
      )}
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        {component.console_url && (
          <a className={linkClass} href={component.console_url} target="_blank" rel="noreferrer">
            Mở bảng quản trị gốc
          </a>
        )}
        {component.secondary_console_url && (
          <a className={linkClass} href={component.secondary_console_url} target="_blank" rel="noreferrer">
            Mở bảng quản trị filer
          </a>
        )}
      </div>
    </Card>
  );
}
