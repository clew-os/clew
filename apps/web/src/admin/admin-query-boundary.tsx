// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { QueryBoundary } from "../components/query-boundary";

/** True when the last background refresh failed but earlier data is still available. */
export const isStale = (query: Pick<UseQueryResult, "isError" | "data">): boolean => query.isError && query.data !== undefined;

/**
 * Like QueryBoundary, but a failed background refetch keeps the last data on screen with a small
 * warning instead of replacing the whole page with an error (admin pages poll continuously).
 */
export function AdminQueryBoundary<T>(props: { query: UseQueryResult<T>; children: (data: T) => ReactNode }) {
  const { query } = props;
  if (query.data === undefined) return <QueryBoundary query={query}>{props.children}</QueryBoundary>;
  return (
    <>
      {isStale(query) && (
        <p role="status" className="mb-3 rounded-lg bg-yellow-50 p-2 text-base text-yellow-900">
          Không làm mới được dữ liệu, đang hiển thị dữ liệu lần cập nhật trước.
        </p>
      )}
      {props.children(query.data)}
    </>
  );
}
