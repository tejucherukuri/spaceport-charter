import type {
  Booking,
  CreateBookingRequest,
  DashboardResponse,
  Ship,
  ShipUnavailability,
} from "../types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function messageFromBody(body: unknown): string {
  if (typeof body !== "object" || body === null) return "The server returned an invalid response.";

  const detail = (body as Record<string, unknown>).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          return String(item.msg);
        }
        return String(item);
      })
      .join("; ");
  }

  return Object.entries(body)
    .map(([field, errors]) => {
      const text = Array.isArray(errors) ? errors.join(", ") : String(errors);
      return `${field}: ${text}`;
    })
    .join("; ") || "Request failed.";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  const text = await response.text();
  let body: unknown = null;

  if (text) {
    try {
      body = JSON.parse(text) as unknown;
    } catch {
      throw new ApiError("The server returned a non-JSON response.", response.status);
    }
  }
  if (!response.ok) {
    throw new ApiError(messageFromBody(body), response.status);
  }
  return body as T;
}

export function getShips(): Promise<Ship[]> {
  return request<Ship[]>("/ships/");
}

export function getShipUnavailability(
  shipId: number,
  date: string,
): Promise<ShipUnavailability> {
  const query = new URLSearchParams({ date });
  return request<ShipUnavailability>(
    `/ships/${shipId}/unavailability/?${query.toString()}`,
  );
}

export function createBooking(payload: CreateBookingRequest): Promise<Booking> {
  return request<Booking>("/bookings/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getDashboard(from: string, to: string): Promise<DashboardResponse> {
  const query = new URLSearchParams({ from, to });
  return request<DashboardResponse>(`/dashboard/?${query.toString()}`);
}
