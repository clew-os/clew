// SPDX-FileCopyrightText: The Clew Authors
// SPDX-License-Identifier: Apache-2.0
import { type ApiError, type Schemas, unwrap } from "@clew/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api-client-instance";

export type CoreComponent = Schemas["CoreComponentOut"];
export type WorkflowOverview = Schemas["WorkflowOverviewOut"];
export type OutboxOverview = Schemas["OutboxOverviewOut"];
export type GatewayOverview = Schemas["GatewayOverviewOut"];

/** Health of every core component; refreshed every 10 s so an outage shows without a reload. */
export const useCoreStatus = () =>
  useQuery({
    queryKey: ["admin-core-status"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/core-status")),
    staleTime: 5_000,
    refetchInterval: 10_000,
  });

export const useWorkflowOverview = () =>
  useQuery({
    queryKey: ["admin-workflow"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/workflow")),
    staleTime: 5_000,
    refetchInterval: 15_000,
  });

export const useOutboxOverview = () =>
  useQuery({
    queryKey: ["admin-outbox"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/outbox")),
    staleTime: 5_000,
    refetchInterval: 15_000,
  });

export const useGatewayOverview = () =>
  useQuery({ queryKey: ["admin-gateway"], queryFn: () => unwrap(api.GET("/api/v1/admin/gateway")), staleTime: 15_000 });

/** Retry mutations refresh only the admin queries they can change (not every cached query of the app). */
function useAdminRetry<TVars>(run: (vars: TVars) => Promise<unknown>, keys: readonly string[]) {
  const queryClient = useQueryClient();
  return useMutation<unknown, ApiError, TVars>({
    mutationFn: run,
    onSuccess: () => Promise.all(keys.map((key) => queryClient.invalidateQueries({ queryKey: [key] }))),
  });
}

export const useRetryDeadLetterJob = () =>
  useAdminRetry(
    (jobId: string) =>
      unwrap(api.POST("/api/v1/admin/workflow/deadletter-jobs/{job_id}/retry", { params: { path: { job_id: jobId } } })),
    ["admin-workflow", "admin-core-status"],
  );

export const useRetryOutboxEvent = () =>
  useAdminRetry(
    (eventId: number) => unwrap(api.POST("/api/v1/admin/outbox/{event_id}/retry", { params: { path: { event_id: eventId } } })),
    ["admin-outbox", "admin-core-status"],
  );
