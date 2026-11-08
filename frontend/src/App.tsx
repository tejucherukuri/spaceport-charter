import { useState } from "react";
import { BookingPage } from "./BookingPage";
import { DashboardPage } from "./DashboardPage";
import "./App.css";

function App() {
  const [activePage, setActivePage] = useState<"booking" | "dashboard">("booking");

  return (
    <main className="app-shell">
      <header className="app-header">
        <p className="eyebrow">PACIFIC SPACEPORT</p>
        <h1>Charter Control</h1>
        <p className="intro">Fleet bookings, coordinated in Central Time.</p>
      </header>
      <nav className="primary-nav" aria-label="Main navigation">
        <button
          type="button"
          className={activePage === "booking" ? "active" : ""}
          aria-current={activePage === "booking" ? "page" : undefined}
          onClick={() => setActivePage("booking")}
        >
          Charter a ship
        </button>
        <button
          type="button"
          className={activePage === "dashboard" ? "active" : ""}
          aria-current={activePage === "dashboard" ? "page" : undefined}
          onClick={() => setActivePage("dashboard")}
        >
          Fleet manager
        </button>
      </nav>
      {activePage === "booking" ? <BookingPage /> : <DashboardPage />}
    </main>
  );
}

export default App;
