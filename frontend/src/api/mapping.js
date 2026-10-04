import api from "./client.js";

export async function getUploadMapping(uploadId) {
  const { data } = await api.get(`/api/uploads/${uploadId}/mapping`);
  return data;
}