import { formatMinute } from "../time";
import type { ShipUnavailability } from "../types";

const SLOT_INCREMENT_MINUTES = 30;

interface TimeSlotGridProps {
  availability: ShipUnavailability;
  durationMinutes: number;
  selectedMinute: number | null;
  onSelect: (minute: number) => void;
}

function isAvailable(
  minute: number,
  durationMinutes: number,
  availability: ShipUnavailability,
): boolean {
  const endMinute = minute + durationMinutes;
  return endMinute <= availability.closeMinute
    && !availability.unavailable.some(
      (blocked) => minute < blocked.endMinute && endMinute > blocked.startMinute,
    );
}

export function TimeSlotGrid({
  availability,
  durationMinutes,
  selectedMinute,
  onSelect,
}: TimeSlotGridProps) {
  const slots: number[] = [];
  for (
    let minute = availability.openMinute;
    minute < availability.closeMinute;
    minute += SLOT_INCREMENT_MINUTES
  ) {
    slots.push(minute);
  }

  return (
    <>
      {availability.unavailable.length > 0 ? (
        <div className="blocked-list" aria-label="Unavailable time ranges">
          <span className="field-caption">Unavailable (includes refueling buffer)</span>
          <ul>
            {availability.unavailable.map((blocked) => (
              <li key={blocked.start}>
                {formatMinute(blocked.startMinute)} – {formatMinute(blocked.endMinute)}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="muted">No existing blocked times for this date.</p>
      )}

      <p className="field-caption">
        Select a start time · {formatMinute(availability.openMinute)}–{formatMinute(availability.closeMinute)} CT
      </p>
      <div className="slot-grid" role="group" aria-label="Available start times">
        {slots.map((minute) => {
          const available = isAvailable(minute, durationMinutes, availability);
          return (
            <button
              type="button"
              key={minute}
              className={`slot-button${selectedMinute === minute ? " selected" : ""}`}
              disabled={!available}
              aria-pressed={selectedMinute === minute}
              title={available ? undefined : "Unavailable for this duration"}
              onClick={() => onSelect(minute)}
            >
              {formatMinute(minute)}
            </button>
          );
        })}
      </div>
      <div className="slot-legend">
        <span><i className="legend-dot available" /> Available</span>
        <span><i className="legend-dot unavailable" /> Unavailable</span>
      </div>
    </>
  );
}
