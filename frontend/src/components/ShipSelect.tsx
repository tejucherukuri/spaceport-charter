import type { Ship } from "../types";

interface ShipSelectProps {
  ships: Ship[];
  value: number | null;
  onChange: (shipId: number) => void;
  disabled?: boolean;
}

export function ShipSelect({ ships, value, onChange, disabled }: ShipSelectProps) {
  return (
    <label className="field">
      <span>Ship</span>
      <select
        value={value ?? ""}
        onChange={(event) => onChange(Number(event.target.value))}
        disabled={disabled || ships.length === 0}
        required
      >
        <option value="" disabled>Select a ship</option>
        {ships.map((ship) => (
          <option value={ship.id} key={ship.id}>{ship.name}</option>
        ))}
      </select>
    </label>
  );
}
