// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
import type { CoreComponent } from "../api/admin-api";

type Tone = "green" | "yellow" | "red";

export const STATUS_VIEW: Readonly<Record<CoreComponent["status"], { label: string; tone: Tone }>> = {
  up: { label: "Hoạt động", tone: "green" },
  degraded: { label: "Suy giảm", tone: "yellow" },
  down: { label: "Ngừng", tone: "red" },
};

export const FACT_LABELS_VI: Readonly<Record<string, string>> = {
  version: "Phiên bản",
  db_size_mb: "Dung lượng CSDL (MB)",
  realm: "Realm",
  readiness: "Sẵn sàng",
  routes: "Số route",
  upstreams: "Số upstream",
  leader: "Master",
  bucket: "Bucket",
  bucket_reachable: "Bucket truy cập được",
  engine: "Engine",
  pending: "Đang chờ",
  failed: "Lỗi",
  oldest_pending_age_s: "Chờ lâu nhất (giây)",
  last_processed_at: "Xử lý gần nhất",
  head_seq: "Bản ghi cuối",
  error: "Lỗi",
};

export function factValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "boolean") return value ? "có" : "không";
  return String(value);
}

/** ISO timestamp from the API as a short local date-time; unparseable input is shown as is. */
export function shortDateTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString("vi-VN");
}
