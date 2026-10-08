import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  timeout: 30000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error?.response?.data?.detail;
    const message = typeof detail === "string" ? detail
      : detail?.message || error?.message || "Something went wrong. Please try again.";
    return Promise.reject(new Error(message));
  },
);

export default api;
