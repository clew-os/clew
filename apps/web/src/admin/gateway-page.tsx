// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
import { useGatewayOverview } from "../api/admin-api";
import { AdminQueryBoundary } from "./admin-query-boundary";
import { Card, PageTitle } from "../components/ui-primitives";

const th = "px-2 py-1 font-semibold";
const td = "px-2 py-1 align-top";

/** APISIX routes and upstreams. Plugin names only: their configuration (secrets) never reaches the browser. */
export function GatewayPage() {
  const overview = useGatewayOverview();
  return (
    <>
      <PageTitle hint="Route và upstream đang chạy trong APISIX (Clew chỉ đọc, không thay đổi gì). Chỉ hiển thị tên plugin, không hiển thị cấu hình.">Cổng API</PageTitle>
      <AdminQueryBoundary query={overview}>
        {(data) => (
          <div className="space-y-4">
            <Card title={`Route (${data.routes.length})`}>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-lg">
                  <thead><tr><th className={th}>Mã</th><th className={th}>Đường dẫn</th><th className={th}>Ưu tiên</th><th className={th}>Upstream</th><th className={th}>Plugin</th></tr></thead>
                  <tbody>
                    {data.routes.map((r) => (
                      <tr key={r.id} className="border-t border-slate-200">
                        <td className={`${td} font-mono`}>{r.id}</td>
                        <td className={`${td} break-all font-mono`}>{r.uris.join(", ")}</td>
                        <td className={td}>{r.priority}</td>
                        <td className={`${td} font-mono`}>{r.upstream_id ?? "-"}</td>
                        <td className={`${td} font-mono`}>{r.plugins.join(", ") || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
            <Card title={`Upstream (${data.upstreams.length})`}>
              <table className="w-full text-left text-lg">
                <thead><tr><th className={th}>Mã</th><th className={th}>Nút</th></tr></thead>
                <tbody>
                  {data.upstreams.map((u) => (
                    <tr key={u.id} className="border-t border-slate-200">
                      <td className={`${td} font-mono`}>{u.id}</td><td className={`${td} font-mono`}>{u.nodes.join(", ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          </div>
        )}
      </AdminQueryBoundary>
    </>
  );
}
