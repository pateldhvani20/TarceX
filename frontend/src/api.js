export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export const API_HOST = API_BASE_URL.replace(/^https?:\/\//, "");

export class ApiError extends Error {
  constructor(message, { offline = false, status = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.offline = offline;
    this.status = status;
  }
}

function formatDetail(detail) {
  if (detail == null) {
    return null;
  }

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }

        const location = Array.isArray(item?.loc)
          ? item.loc.filter((part) => part !== "body").join(".")
          : "";
        const message = item?.msg || JSON.stringify(item);
        return location ? `${location}: ${message}` : message;
      })
      .join("; ");
  }

  if (typeof detail === "object") {
    return detail.message || detail.error || JSON.stringify(detail);
  }

  return String(detail);
}

async function request(path, options = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      ...options,
    });
  } catch {
    throw new ApiError(
      `Backend offline — unable to reach ${API_HOST}. Start FastAPI on port 8000 and try again.`,
      { offline: true }
    );
  }

  let data = null;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const message =
      formatDetail(data?.detail) ||
      data?.error ||
      data?.message ||
      `HTTP ${response.status} ${response.statusText || "request failed"}`;

    throw new ApiError(message, {
      offline: false,
      status: response.status,
    });
  }

  return data;
}

export function getHealth() {
  return request("/health");
}

export function getStats() {
  return request("/stats");
}

export function getTransactions() {
  return request("/transactions");
}

export function ingestTransaction(payload) {
  return request("/ingest", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Build a TransactionEvent body that matches backend/schemas.py. */
export function buildIngestPayload(form) {
  const payload = {
    event_id: String(form.event_id || "").trim(),
    timestamp: String(form.timestamp || "").trim(),
    source: String(form.source || "").trim(),
    user_id: String(form.user_id || "").trim(),
    amount: Number(form.amount),
  };

  const optionalFields = [
    "category",
    "description",
    "merchant",
    "status",
    "email",
    "phone",
  ];

  for (const field of optionalFields) {
    const value = form[field];
    if (value != null && String(value).trim() !== "") {
      payload[field] = String(value).trim();
    }
  }

  return payload;
}
