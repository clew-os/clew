// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { CoreComponent } from "../api/admin-api";
import { CoreStatusView } from "./core-status-view";

const base = { service_kind: "platform", latency_ms: 12, facts: {}, console_url: null, secondary_console_url: null } as const;

const COMPONENTS: CoreComponent[] = [
  { ...base, key: "postgres", label: "PostgreSQL", status: "up", facts: { version: "PostgreSQL 17.12" } },
  { ...base, key: "outbox", label: "Outbox + worker", status: "degraded", facts: { failed: 2 } },
  { ...base, key: "flowable", label: "Flowable", status: "down", facts: { error: "ConnectError: refused" } },
  { ...base, key: "keycloak", label: "Keycloak", status: "up", console_url: "http://localhost:9081/auth/admin/clew/console/" },
];

describe("CoreStatusView", () => {
  const html = renderToStaticMarkup(<CoreStatusView components={COMPONENTS} />);

  it("renders one card per component with a status badge", () => {
    for (const c of COMPONENTS) expect(html).toContain(c.label);
    expect(html).toMatch(/status-postgres[^>]*><span[^>]*bg-green-100[^>]*>Hoạt động/);
    expect(html).toMatch(/status-outbox[^>]*><span[^>]*bg-yellow-100[^>]*>Suy giảm/);
    expect(html).toMatch(/status-flowable[^>]*><span[^>]*bg-red-100[^>]*>Ngừng/);
  });

  it("shows latency, facts and the error of a failed probe", () => {
    expect(html).toContain("Độ trễ: 12 ms");
    expect(html).toContain("PostgreSQL 17.12");
    expect(html).toContain("ConnectError: refused");
  });

  it("links to the native console only where one exists, opening in a new tab", () => {
    expect(html.match(/Mở bảng quản trị gốc/g)).toHaveLength(1);
    expect(html).toContain('href="http://localhost:9081/auth/admin/clew/console/" target="_blank" rel="noreferrer"');
  });

  it("explains that native consoles only open on the server machine", () => {
    expect(html).toContain("127.0.0.1");
    expect(html).toContain("localhost:9333");
    expect(html).toContain("localhost:8888");
  });
});
