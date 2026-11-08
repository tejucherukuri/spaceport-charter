import { useEffect, useState } from "react";

import {
  ApiError,
  createBooking,
  getShipUnavailability,
  getShips,
} from "./api/client";
import { BookingForm } from "./components/BookingForm";
import { ShipSelect } from "./components/ShipSelect";
import { TimeSlotGrid } from "./components/TimeSlotGrid";
import { centralDateTime, todayInCentral } from "./time";
import type { Ship, ShipUnavailability } from "./types";

const DURATIONS = [60, 90, 120, 180, 240];

function durationLabel(minutes: number): string {
  const hours = minutes / 60;
  return `${hours} ${hours === 1 ? "hour" : "hours"}`;
}

export function BookingPage() {
  const [ships, setShips] = useState<Ship[]>([]);
  const [shipId, setShipId] = useState<number | null>(null);
  const [date, setDate] = useState(todayInCentral);
  const [durationMinutes, setDurationMinutes] = useState(60);
  const [availability, setAvailability] = useState<ShipUnavailability | null>(null);
  const [selectedMinute, setSelectedMinute] = useState<number | null>(null);
  const [pilotName, setPilotName] = useState("");
  const [loadingShips, setLoadingShips] = useState(true);
  const [loadingAvailability, setLoadingAvailability] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getShips()
      .then((fleet) => {
        if (!active) return;
        setShips(fleet);
        setShipId(fleet[0]?.id ?? null);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Unable to load ships.");
      })
      .finally(() => {
        if (active) setLoadingShips(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (shipId === null || !date) {
      setAvailability(null);
      return;
    }

    let active = true;
    setAvailability(null);
    setSelectedMinute(null);
    setLoadingAvailability(true);
    setError(null);
    setConfirmation(null);

    getShipUnavailability(shipId, date)
      .then((result) => {
        if (active) setAvailability(result);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Unable to load availability.");
        }
      })
      .finally(() => {
        if (active) setLoadingAvailability(false);
      });

    return () => {
      active = false;
    };
  }, [shipId, date]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (shipId === null || selectedMinute === null) return;

    setSubmitting(true);
    setError(null);
    setConfirmation(null);
    try {
      const created = await createBooking({
        shipId,
        pilotName: pilotName.trim(),
        startTime: centralDateTime(date, selectedMinute),
        endTime: centralDateTime(date, selectedMinute + durationMinutes),
      });
      const shipName = ships.find((ship) => ship.id === created.shipId)?.name ?? "ship";
      setConfirmation(
        `Booking confirmed for ${created.pilotName} aboard ${shipName}.`,
      );
      setSelectedMinute(null);
      setPilotName("");
    } catch (reason: unknown) {
      if (reason instanceof ApiError && reason.status === 409) {
        setError(`${reason.message} Availability has been refreshed.`);
      } else {
        setError(reason instanceof Error ? reason.message : "Unable to create booking.");
      }
    } finally {
      try {
        const refreshed = await getShipUnavailability(shipId, date);
        setAvailability(refreshed);
      } catch (reason: unknown) {
        setError(
          reason instanceof Error
            ? `Booking request finished, but availability could not be refreshed: ${reason.message}`
            : "Booking request finished, but availability could not be refreshed.",
        );
      }
      setSubmitting(false);
    }
  };

  return (
    <section className="booking-page" aria-labelledby="booking-heading">
      <div className="section-heading">
        <p className="eyebrow">FLIGHT OPERATIONS</p>
        <h2 id="booking-heading">Charter a ship</h2>
        <p>Choose your vessel, plan a departure, and leave time for refueling.</p>
      </div>

      <div className="booking-card">
        <div className="booking-controls">
          <ShipSelect
            ships={ships}
            value={shipId}
            disabled={loadingShips || submitting}
            onChange={setShipId}
          />
          <label className="field">
            <span>Departure date <small>Central Time</small></span>
            <input
              type="date"
              value={date}
              min={todayInCentral()}
              onChange={(event) => setDate(event.target.value)}
              disabled={submitting}
              required
            />
          </label>
          <label className="field">
            <span>Flight duration</span>
            <select
              value={durationMinutes}
              onChange={(event) => {
                setDurationMinutes(Number(event.target.value));
                setSelectedMinute(null);
              }}
              disabled={submitting}
            >
              {DURATIONS.map((minutes) => (
                <option key={minutes} value={minutes}>{durationLabel(minutes)}</option>
              ))}
            </select>
          </label>
        </div>

        <section className="availability-section" aria-labelledby="availability-heading">
          <div className="subsection-heading">
            <h3 id="availability-heading">Departure availability</h3>
            <span className="timezone-badge">UTC−5 / UTC−6 · CT</span>
          </div>
          {loadingAvailability ? (
            <p className="muted" role="status">Checking the fleet schedule…</p>
          ) : availability ? (
            <TimeSlotGrid
              availability={availability}
              durationMinutes={durationMinutes}
              selectedMinute={selectedMinute}
              onSelect={(minute) => {
                setSelectedMinute(minute);
                setError(null);
                setConfirmation(null);
              }}
            />
          ) : (
            <p className="muted">Select a ship and date to load availability.</p>
          )}
        </section>

        <BookingForm
          pilotName={pilotName}
          onPilotNameChange={setPilotName}
          selectedMinute={selectedMinute}
          durationMinutes={durationMinutes}
          onSubmit={handleSubmit}
          submitting={submitting}
        />

        {error && <p className="notice error-message" role="alert">{error}</p>}
        {confirmation && <p className="notice success-message" role="status">{confirmation}</p>}
      </div>
    </section>
  );
}
