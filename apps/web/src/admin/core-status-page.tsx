// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
import { useCoreStatus } from "../api/admin-api";
import { PageTitle } from "../components/ui-primitives";
import { AdminQueryBoundary } from "./admin-query-boundary";
import { CoreStatusView } from "./core-status-view";

export function CoreStatusPage() {
  const status = useCoreStatus();
  return (
    <>
      <PageTitle hint="Tình trạng các thành phần lõi, tự làm mới mỗi 10 giây.">Lõi hệ thống</PageTitle>
      <AdminQueryBoundary query={status}>{(components) => <CoreStatusView components={components} />}</AdminQueryBoundary>
    </>
  );
}
