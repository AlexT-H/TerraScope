const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export async function fetchRankedParcels(payload) {
  const response = await fetch(`${API_BASE_URL}/rank`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

export async function fetchParcel(unitId) {
  const response = await fetch(`${API_BASE_URL}/parcels/${encodeURIComponent(unitId)}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
