import { api } from "./api";
import type {
  PaginatedResponse,
  BulkImportResult,
  Location,
  Organization,
  Commodity,
  Port,
  OilField,
  GasField,
  Pipeline,
  Refinery,
  PowerPlant,
  StorageFacility,
  StrategicPetroleumReserve,
  ImportCorridor,
  ShippingRoute,
  Supplier,
  EntityRelationship,
  InfrastructureEvent,
  CapacityRecord,
} from "../types/energy";

const ENERGY_BASE = "/api/v1/energy";

export async function fetchEntities<T>(
  table: string,
  params?: Record<string, string | number | boolean | undefined>,
): Promise<PaginatedResponse<T>> {
  const response = await api.get<PaginatedResponse<T>>(`${ENERGY_BASE}/${table}`, { params });
  return response.data;
}

export async function fetchEntity<T>(
  table: string,
  uuid: string,
): Promise<T> {
  const response = await api.get<T>(`${ENERGY_BASE}/${table}/${uuid}`);
  return response.data;
}

export async function createEntity(
  table: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const response = await api.post(`${ENERGY_BASE}/${table}`, body);
  return response.data;
}

export async function updateEntity(
  table: string,
  uuid: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const response = await api.put(`${ENERGY_BASE}/${table}/${uuid}`, body);
  return response.data;
}

export async function patchEntity(
  table: string,
  uuid: string,
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const response = await api.patch(`${ENERGY_BASE}/${table}/${uuid}`, body);
  return response.data;
}

export async function deleteEntity(
  table: string,
  uuid: string,
): Promise<Record<string, unknown>> {
  const response = await api.delete(`${ENERGY_BASE}/${table}/${uuid}`);
  return response.data;
}

export async function fetchEntityRelationships(
  table: string,
  uuid: string,
): Promise<EntityRelationship[]> {
  const response = await api.get<EntityRelationship[]>(`${ENERGY_BASE}/${table}/${uuid}/relationships`);
  return response.data;
}

export async function createRelationship(
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const response = await api.post(`${ENERGY_BASE}/relationships`, body);
  return response.data;
}

export async function fetchNetworkGraph(limit = 500): Promise<{ relationships: EntityRelationship[] }> {
  const response = await api.get<{ relationships: EntityRelationship[] }>(
    `${ENERGY_BASE}/graph/network`,
    { params: { limit } },
  );
  return response.data;
}

export async function fetchEntityEvents(
  table: string,
  uuid: string,
): Promise<InfrastructureEvent[]> {
  const response = await api.get<InfrastructureEvent[]>(`${ENERGY_BASE}/${table}/${uuid}/events`);
  return response.data;
}

export async function createEvent(
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const response = await api.post(`${ENERGY_BASE}/events`, body);
  return response.data;
}

export async function fetchEntityHistory(
  table: string,
  uuid: string,
): Promise<CapacityRecord[]> {
  const response = await api.get<CapacityRecord[]>(`${ENERGY_BASE}/${table}/${uuid}/history`);
  return response.data;
}

export async function recordCapacity(
  body: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const response = await api.post(`${ENERGY_BASE}/history`, body);
  return response.data;
}

export async function bulkImport(
  file: File,
): Promise<BulkImportResult> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await api.post<BulkImportResult>(`${ENERGY_BASE}/bulk/import`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export async function bulkExport(): Promise<Record<string, unknown[]>> {
  const response = await api.get<Record<string, unknown[]>>(`${ENERGY_BASE}/bulk/export`);
  return response.data;
}

export type {
  Location,
  Organization,
  Commodity,
  Port,
  OilField,
  GasField,
  Pipeline,
  Refinery,
  PowerPlant,
  StorageFacility,
  StrategicPetroleumReserve,
  ImportCorridor,
  ShippingRoute,
  Supplier,
  EntityRelationship,
  InfrastructureEvent,
  CapacityRecord,
  PaginatedResponse,
  BulkImportResult,
};
