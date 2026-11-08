import { formatMinute } from "../time";

interface BookingFormProps {
  pilotName: string;
  onPilotNameChange: (value: string) => void;
  selectedMinute: number | null;
  durationMinutes: number;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  submitting: boolean;
}

export function BookingForm({
  pilotName,
  onPilotNameChange,
  selectedMinute,
  durationMinutes,
  onSubmit,
  submitting,
}: BookingFormProps) {
  return (
    <form onSubmit={onSubmit} className="booking-form">
      <label className="field pilot-field">
        <span>Pilot name</span>
        <input
          value={pilotName}
          onChange={(event) => onPilotNameChange(event.target.value)}
          maxLength={100}
          autoComplete="name"
          placeholder="e.g. Han Solo"
          required
        />
      </label>

      {selectedMinute !== null && (
        <p className="booking-summary">
          Selected: <strong>{formatMinute(selectedMinute)}–{formatMinute(selectedMinute + durationMinutes)} CT</strong>
        </p>
      )}

      <button
        className="primary-button"
        type="submit"
        disabled={submitting || selectedMinute === null || !pilotName.trim()}
      >
        {submitting ? "Confirming booking…" : "Book this slot"}
      </button>
    </form>
  );
}
