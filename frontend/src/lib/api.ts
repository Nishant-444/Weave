/**
 * Dynamic API Base URL configuration.
 * When VITE_API_URL is configured (e.g. on Vercel pointing to Render/Railway),
 * requests go directly to the deployed backend.
 * In local dev without VITE_API_URL, requests default to '/api' which Vite proxies to localhost:8000.
 */
const RAW_BASE = import.meta.env.VITE_API_URL || "/api";
export const API_BASE_URL = RAW_BASE.replace(/\/+$/, "");

export function apiUrl(endpoint: string): string {
  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  // If base is already '/api' and endpoint starts with '/api', avoid duplicate '/api/api'
  if (API_BASE_URL === "/api" && cleanEndpoint.startsWith("/api/")) {
    return cleanEndpoint;
  }
  return `${API_BASE_URL}${cleanEndpoint}`;
}
