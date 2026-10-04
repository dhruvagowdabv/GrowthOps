import api from "./client.js";

export async function getOverview(uploadId) {
  const { data } = await api.get("/api/analytics/overview", { params: uploadId ? { upload_id: uploadId } : {} });
  return data;
}
export async function getRelationships(uploadIds) {
  const { data } = await api.get("/api/analytics/relationships", {
    params: uploadIds?.length ? { upload_ids: uploadIds } : {},
    paramsSerializer: { indexes: null },
  });
  return data;
}