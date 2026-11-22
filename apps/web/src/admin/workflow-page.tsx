// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
import { useRetryDeadLetterJob, useWorkflowOverview } from "../api/admin-api";
import { AdminQueryBoundary } from "./admin-query-boundary";
import { Button, Card, PageTitle } from "../components/ui-primitives";
import { ViolationBanner } from "../components/violation-banner";
import { shortDateTime } from "./admin-format";

const th = "px-2 py-1 font-semibold";
const td = "px-2 py-1 align-top";

function Empty({ children }: { children: string }) {
  return <p className="text-lg text-slate-600">{children}</p>;
}

/** Process definitions, open tasks, timers and dead-letter jobs of the workflow engine. */
export function WorkflowPage() {
  const overview = useWorkflowOverview();
  const retry = useRetryDeadLetterJob();

  function confirmRetry(jobId: string) {
    if (window.confirm("Thử lại công việc lỗi này? Hệ thống ghi lại thao tác vào nhật ký kiểm toán.")) retry.mutate(jobId);
  }

  return (
    <>
      <PageTitle hint="Trạng thái engine quy trình (Flowable). Công việc lỗi nằm ở danh sách dead-letter.">Quy trình</PageTitle>
      <AdminQueryBoundary query={overview}>
        {(data) => (
          <div className="space-y-4">
            <Card title="Định nghĩa quy trình">
              {data.definitions.length === 0 ? (
                <Empty>Chưa triển khai quy trình nào.</Empty>
              ) : (
                <table className="w-full text-left text-lg">
                  <thead><tr><th className={th}>Khóa</th><th className={th}>Tên</th><th className={th}>Phiên bản</th><th className={th}>Đang chạy</th></tr></thead>
                  <tbody>
                    {data.definitions.map((d) => (
                      <tr key={d.key} className="border-t border-slate-200">
                        <td className={`${td} font-mono`}>{d.key}</td><td className={td}>{d.name ?? "-"}</td>
                        <td className={td}>v{d.version}</td><td className={td}>{d.running_instances}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
            <Card title={`Công việc đang mở (${data.open_tasks.length})`}>
              {data.open_tasks.length === 0 ? <Empty>Không có công việc đang mở.</Empty> : (
                <ul className="space-y-1 text-lg">
                  {data.open_tasks.map((t) => (
                    <li key={t.id}>{t.name ?? t.id} <span className="text-slate-600">- tạo {shortDateTime(t.created)}{t.assignee ? `, giao cho ${t.assignee}` : ""}</span></li>
                  ))}
                </ul>
              )}
            </Card>
            <Card title={`Bộ hẹn giờ (${data.timer_jobs.length})`}>
              {data.timer_jobs.length === 0 ? <Empty>Không có bộ hẹn giờ nào đang chờ.</Empty> : (
                <ul className="space-y-1 text-lg">
                  {data.timer_jobs.map((j) => <li key={j.id}>Đến hạn {shortDateTime(j.due_date)} <span className="font-mono text-base text-slate-600">({j.process_instance_id ?? j.id})</span></li>)}
                </ul>
              )}
            </Card>
            <Card title={`Công việc lỗi - dead-letter (${data.deadletter_jobs.length})`}>
              {data.deadletter_jobs.length === 0 ? <Empty>Không có công việc lỗi.</Empty> : (
                <ul className="space-y-3">
                  {data.deadletter_jobs.map((j) => (
                    <li key={j.id} className="flex flex-wrap items-start justify-between gap-3 rounded-lg bg-red-50 p-3">
                      <div className="min-w-0 text-lg">
                        <p className="font-mono text-base">{j.id} - quy trình {j.process_instance_id ?? "-"} - {shortDateTime(j.created)}</p>
                        <p className="break-words text-red-900">{j.exception_message ?? "Không có thông báo lỗi."}</p>
                      </div>
                      <Button variant="secondary" busy={retry.isPending && retry.variables === j.id} disabled={retry.isPending} onClick={() => confirmRetry(j.id)}>Thử lại</Button>
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
