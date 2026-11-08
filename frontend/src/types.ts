export interface Ship {
  id: number;
  name: string;
}

export interface Booking {
  id: number;
  shipId: number;
  pilotName: string;
  startTime: string;
  endTime: string;
}

export interface CreateBookingRequest {
  shipId: number;
  pilotName: string;
  /** ISO 8601 timestamp that includes an explicit UTC offset. */
  startTime: string;
  /** ISO 8601 timestamp that includes an explicit UTC offset. */
  endTime: string;
}

export interface UnavailableInterval {
  start: string;
  end: string;
  /** Minutes from Central midnight. */
  startMinute: number;
  /** Minutes from Central midnight. */
  endMinute: number;
}

export interface ShipUnavailability {
  shipId: number;
  date: string;
  timezone: "America/Chicago";
  open: string;
  close: string;
  openMinute: number;
  closeMinute: number;
  refuelBufferMinutes: number;
  unavailable: UnavailableInterval[];
}

export interface DashboardShip extends Ship {
  bookings: Booking[];
}

export interface DashboardResponse {
  from: string;
  to: string;
  ships: DashboardShip[];
}
