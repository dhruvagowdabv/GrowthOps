import api from "./client.js";

export async function uploadCsv(file, onProgress) {
  const body = new FormData();
  body.append("file", file);
  const { data } = await api.post("/api/uploads", body, {
    onUploadProgress: (event) => {
      if (event.total) onProgress?.(Math.round((event.loaded * 100) / event.total));
    },
  });
  return data;
}
export async function getProfile(id) { return (await api.get(`/api/uploads/${id}/profile`)).data; }
export async function getMapping(id) { return (await api.get(`/api/uploads/${id}/mapping`)).data; }
export async function getValidation(id) { return (await api.get(`/api/uploads/${id}/validation`)).data; }
export async function getUploadAnalytics(id) { return (await api.get(`/api/uploads/${id}/analytics`)).data; }
export async function ingestUpload(id) { return (await api.post(`/api/uploads/${id}/ingest`)).data; }