// Thin fetch wrapper: attaches the JWT (if present) and normalizes error
// handling so every page doesn't repeat the same try/fetch/parse boilerplate.
// Deliberately no axios/react-query here — this is the "minimal, functional
// base" layer; swap this out freely, it's a tiny surface.
// Relative by default: the backend serves this app and the API from one
// origin, so "/api" always points at the right server, on any host or port
// (localhost:8080, a tunnel URL, a deployed site). VITE_API_URL only needs
// setting if the API is hosted somewhere else.
const API_URL = import.meta.env.VITE_API_URL || "/api";

function getToken() {
  return localStorage.getItem("token");
}

async function request(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  let data = null;
  try {
    data = await res.json();
  } catch {
    // empty/non-JSON body is fine for some responses
  }

  if (!res.ok) {
    throw new Error((data && data.error) || `Request failed (${res.status})`);
  }
  return data;
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body),
  put: (path, body) => request("PUT", path, body),
};
