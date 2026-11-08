import { BookingPage } from "./BookingPage";
import "./App.css";

function App() {
  return (
    <main className="app-shell">
      <header className="app-header">
        <p className="eyebrow">PACIFIC SPACEPORT</p>
        <h1>Charter Control</h1>
        <p className="intro">Fleet bookings, coordinated in Central Time.</p>
      </header>
      <BookingPage />
    </main>
  );
}

export default App;
