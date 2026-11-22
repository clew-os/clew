// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
import type { Shipment } from "@clew/api-client";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useDisposeShipment } from "../../api/mutations";
import { Button, Field, inputClass } from "../../components/ui-primitives";
import { ViolationBanner } from "../../components/violation-banner";

const MAX_REASON = 500;

/** QA records that a held shipment's food was destroyed. Held food is never released (P3: 120-minute hold limit). */
export function DisposeShipmentPanel(props: { shipment: Shipment }) {
  const dispose = useDisposeShipment();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");
  const [localError, setLocalError] = useState<string>();

  // A refusal (e.g. 409: someone else already disposed it) means the card may be stale: reload it.
  function refreshAfterError() {
    setConfirming(false);
    void queryClient.invalidateQueries();
  }

  function review() {
    const trimmed = reason.trim();
    if (!trimmed) return setLocalError("Nhập lý do hủy.");
    if (trimmed.length > MAX_REASON) return setLocalError(`Lý do tối đa ${MAX_REASON} ký tự.`);
    setLocalError(undefined);
    setConfirming(true);
  }

  if (!open) {
    return (
      <div className="mt-4">
        <Button variant="danger" onClick={() => setOpen(true)}>
          Ghi nhận hủy
        </Button>
      </div>
    );
  }

  return (
    <div className="mt-4 space-y-3 rounded-xl bg-red-50 p-3">
      <p className="text-lg text-red-900">
        Thức ăn bị giữ không bao giờ được xuất lại (quá giới hạn giữ nóng 120 phút). Ghi nhận việc tiêu hủy chuyến {props.shipment.code}.
      </p>
      <Field label="Lý do hủy (bắt buộc)">
        <input
          className={inputClass}
          value={reason}
          maxLength={MAX_REASON}
          disabled={confirming}
          onChange={(e) => {
            setReason(e.target.value);
            dispose.reset();
          }}
        />
      </Field>
      {localError && (
        <p role="alert" className="text-lg font-semibold text-red-800">
          {localError}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        {confirming ? (
          <>
            <span className="text-lg font-semibold">Xác nhận đã hủy chuyến {props.shipment.code}? Không thể hoàn tác.</span>
            <Button
              variant="danger"
              busy={dispose.isPending}
              onClick={() => dispose.mutate({ shipmentId: props.shipment.id, reason: reason.trim() }, { onError: refreshAfterError })}
            >
              Xác nhận hủy
            </Button>
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              Quay lại
            </Button>
          </>
        ) : (
          <>
            <Button variant="danger" onClick={review}>
              Tiếp tục
            </Button>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Đóng
            </Button>
          </>
        )}
      </div>
      <ViolationBanner error={dispose.error} title="Hệ thống từ chối ghi nhận hủy" />
    </div>
  );
}
