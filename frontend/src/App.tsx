import { useEffect, useState } from "react";

import { getShips } from "./api/client";
import type { Ship } from "./types";
import "./App.css";

function App() {
  const [ships, setShips] = useState<Ship[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    getShips()
      .then((fleet) => {
        if (active) setShips(fleet);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Unable to load the fleet.");
        }
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="app-shell">
      <header className="app-header">
        <p className="eyebrow">PACIFIC SPACEPORT</p>
        <h1>Charter Control</h1>
        <p className="intro">Fleet bookings, coordinated in Central Time.</p>
      </header>

      <section className="fleet-preview" aria-labelledby="fleet-heading">
        <h2 id="fleet-heading">Fleet connection check</h2>
        {error ? (
          <p role="alert" className="error-message">{error}</p>
        ) : ships.length === 0 ? (
          <p className="muted">Loading ships…</p>
        ) : (
          <ul>
            {ships.map((ship) => <li key={ship.id}>{ship.name}</li>)}
          </ul>
        )}
      </section>
    </main>
  );
}

export default App;
