// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
import type { UseQueryResult } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AdminQueryBoundary } from "./admin-query-boundary";

const q = (state: object) => state as unknown as UseQueryResult<string>;

describe("AdminQueryBoundary", () => {
  it("keeps the last data and shows a warning when only the refetch failed", () => {
    const html = renderToStaticMarkup(
      <AdminQueryBoundary query={q({ isError: true, isPending: false, data: "DATA-OLD" })}>{(d) => <p>{d}</p>}</AdminQueryBoundary>,
    );
    expect(html).toContain("DATA-OLD");
    expect(html).toContain("Không làm mới được dữ liệu");
  });

  it("shows plain data without warning when healthy", () => {
    const html = renderToStaticMarkup(
      <AdminQueryBoundary query={q({ isError: false, isPending: false, data: "DATA" })}>{(d) => <p>{d}</p>}</AdminQueryBoundary>,
    );
    expect(html).toContain("DATA");
    expect(html).not.toContain("Không làm mới");
  });

  it("falls back to the loading state before any data", () => {
    const html = renderToStaticMarkup(
      <AdminQueryBoundary query={q({ isError: false, isPending: true, data: undefined })}>{(d) => <p>{d}</p>}</AdminQueryBoundary>,
    );
    expect(html).toContain("Đang tải dữ liệu");
  });
});
