// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
import { useOutboxOverview, useRetryOutboxEvent } from "../api/admin-api";
import { AdminQueryBoundary } from "./admin-query-boundary";
import { Button, Card, PageTitle } from "../components/ui-primitives";
import { ViolationBanner } from "../components/violation-banner";
import { shortDateTime } from "./admin-format";

function Counter({ label, value, alert = false }: { label: string; value: string | number; alert?: boolean }) {
  return (
    <div className={`rounded-xl p-4 ring-1 ring-slate-200 ${alert ? "bg-red-50 text-red-900" : "bg-white"}`}>
      <p className="text-base text-slate-600">{label}</p>
      <p className="text-3xl font-bold">{value}</p>
    </div>
  );
}

/** Transactional outbox: counts, and failed events that can be pushed back into the queue. */
export function OutboxPage() {
  const overview = useOutboxOverview();
  const retry = useRetryOutboxEvent();

  function confirmRetry(id: number) {
    if (window.confirm("Đưa sự kiện lỗi này trở lại hàng đợi? Hệ thống ghi lại thao tác vào nhật ký kiểm toán.")) retry.mutate(id);
  }

  return (
    <>
      <PageTitle hint="Hàng đợi sự kiện giữa API và worker. Sự kiện lỗi quá số lần thử sẽ dừng cho đến khi được thử lại.">Outbox</PageTitle>
      <AdminQueryBoundary query={overview}>
        {(data) => (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Counter label="Đang chờ" value={data.pending} />
              <Counter label="Đã xử lý" value={data.processed} />
              <Counter label="Lỗi" value={data.failed} alert={data.failed > 0} />
              <Counter label="Chờ lâu nhất (giây)" value={data.oldest_pending_age_s ?? "-"} />
            </div>
            <p className="text-lg text-slate-600">Xử lý gần nhất: {shortDateTime(data.last_processed_at)}</p>
            <Card title={`Sự kiện lỗi gần nhất (${data.failed_events.length})`}>
              {data.failed_events.length === 0 ? (
                <p className="text-lg text-slate-600">Không có sự kiện lỗi.</p>
              ) : (
                <ul className="space-y-3">
                  {data.failed_events.map((e) => (
                    <li key={e.id} className="flex flex-wrap items-start justify-between gap-3 rounded-lg bg-red-50 p-3">
                      <div className="min-w-0 text-lg">
                        <p><span className="font-mono">#{e.id}</span> {e.event_type} - {e.attempts} lần thử - {shortDateTime(e.failed_at)}</p>
                        <p className="break-words text-red-900">{e.last_error ?? "Không có thông báo lỗi."}</p>
                      </div>
                      <Button variant="secondary" busy={retry.isPending && retry.variables === e.id} disabled={retry.isPending} onClick={() => confirmRetry(e.id)}>Thử lại</Button>
                    </li>
                  ))}
                </ul>
              )}
              <ViolationBanner error={retry.error} />
            </Card>
          </div>
        )}
      </AdminQueryBoundary>
    </>
  );
}
