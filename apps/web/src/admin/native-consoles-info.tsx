// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
import { Card } from "../components/ui-primitives";

/** Where the native admin consoles live and why their links only work on the server machine. */
export function NativeConsolesInfo() {
  return (
    <Card title="Bảng quản trị gốc của từng dịch vụ">
      <ul className="list-disc space-y-1 pl-6 text-lg">
        <li>
          Keycloak (người dùng, vai trò, tổ chức khách hàng, phiên, sự kiện): <code>http://localhost:9081/auth/admin/clew/console/</code>
        </li>
        <li>
          SeaweedFS master (cụm, volume): <code>http://localhost:9333/</code>, filer (tệp): <code>http://localhost:8888/</code>{" "}
          — đóng mặc định vì không có đăng nhập; chỉ mở khi bảo trì bằng <code>make admin-tools-open</code>, xong thì{" "}
          <code>make admin-tools-close</code>.
        </li>
      </ul>
      <p className="mt-3 rounded-lg bg-slate-100 p-3 text-base text-slate-700">
        Các bảng này chỉ lắng nghe trên 127.0.0.1 nên chỉ mở được trên chính máy chủ chạy hệ thống, không mở được từ máy khác trong mạng.
        Đăng nhập Keycloak bằng cùng tài khoản quản trị hệ thống.
      </p>
    </Card>
  );
}
