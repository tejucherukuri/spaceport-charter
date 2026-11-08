import { useEffect, useState } from "react";

import { getDashboard } from "./api/client";
import { addDays, formatDateTime, todayInCentral } from "./time";
import type { DashboardResponse } from "./types";

export function DashboardPage() {
  const [from, setFrom] = useState(todayInCentral);
  const [to, setTo] = useState(() => addDays(todayInCentral(), 14));
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!from || !to) {
      setDashboard(null);
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);
    getDashboard(from, to)
      .then((response) => {
        if (active) setDashboard(response);
      })
      .catch((reason: unknown) => {
        if (active) {
          setDashboard(null);
          setError(reason instanceof Error ? reason.message : "Unable to load bookings.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [from, to]);

  const selectPreset = (daysBack: number, daysForward: number) => {
    const today = todayInCentral();
    setFrom(addDays(today, daysBack));
    setTo(addDays(today, daysForward));
  };

  return (
    <section className="dashboard-page" aria-labelledby="dashboard-heading">
      <div className="section-heading">
        <p className="eyebrow">FLEET OPERATIONS</p>
        <h2 id="dashboard-heading">Fleet manager</h2>
        <p>Review upcoming and recent bookings across the fleet.</p>
      </div>

      <div className="dashboard-controls">
        <label className="field">
          <span>From <small>Central date</small></span>
          <input
            type="date"
            value={from}
            onChange={(event) => setFrom(event.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>Through <small>inclusive</small></span>
          <input
            type="date"
            value={to}
            min={from || undefined}
            onChange={(event) => setTo(event.target.value)}
            required
          />
        </label>
        <div className="date-presets" aria-label="Dashboard date presets">
          <button type="button" onClick={() => selectPreset(0, 14)}>Next 2 weeks</button>
          <button type="button" onClick={() => selectPreset(-30, 0)}>Past 30 days</button>
        </div>
      </div>

      {loading && <p className="muted" role="status">Loading fleet bookings…</p>}
      {error && <p className="notice error-message" role="alert">{error}</p>}

      {dashboard && (
        <div className="dashboard-results">
          <p className="range-summary">
            {dashboard.from} through {dashboard.to} ·{" "}
            {dashboard.ships.reduce((total, ship) => total + ship.bookings.length, 0)} booking(s)
          </p>
          {dashboard.ships.map((ship) => (
            <section className="ship-bookings" key={ship.id} aria-labelledby={`ship-${ship.id}`}>
              <div className="ship-bookings-heading">
                <h3 id={`ship-${ship.id}`}>{ship.name}</h3>
                <span>{ship.bookings.length} booking{ship.bookings.length === 1 ? "" : "s"}</span>
              </div>
              {ship.bookings.length === 0 ? (
                <p className="empty-state">No bookings for this ship in the selected range.</p>
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">Pilot</th>
                        <th scope="col">Start (Central)</th>
                        <th scope="col">End (Central)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ship.bookings.map((booking) => (
                        <tr key={booking.id}>
                          <td>{booking.pilotName}</td>
                          <td>{formatDateTime(booking.startTime)}</td>
                          <td>{formatDateTime(booking.endTime)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          ))}
        </div>
      )}
    </section>
  );
}
