import api from "./client.js";

export async function getUploadValidation(uploadId) {
  const { data } = await api.get(`/api/uploads/${uploadId}/validation`);
  return data;
}