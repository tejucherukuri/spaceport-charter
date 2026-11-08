const CENTRAL_TIME_ZONE = "America/Chicago";

export function todayInCentral(): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: CENTRAL_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const part = (type: string) => parts.find((value) => value.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function formatMinute(minute: number): string {
  const hour = Math.floor(minute / 60);
  const minutes = String(minute % 60).padStart(2, "0");
  const period = hour < 12 ? "AM" : "PM";
  const displayHour = hour % 12 || 12;
  return `${displayHour}:${minutes} ${period}`;
}

function centralOffsetForDate(date: string): string {
  const [year, month, day] = date.split("-").map(Number);
  const reference = new Date(Date.UTC(year, month - 1, day, 12));
  const zoneName = new Intl.DateTimeFormat("en-US", {
    timeZone: CENTRAL_TIME_ZONE,
    timeZoneName: "longOffset",
  })
    .formatToParts(reference)
    .find((part) => part.type === "timeZoneName")?.value;

  if (!zoneName || zoneName === "GMT") return "+00:00";
  const offset = zoneName.replace("GMT", "");
  return /^[+-]\d{2}:\d{2}$/.test(offset) ? offset : "+00:00";
}

export function centralDateTime(date: string, minute: number): string {
  const hour = String(Math.floor(minute / 60)).padStart(2, "0");
  const minutes = String(minute % 60).padStart(2, "0");
  return `${date}T${hour}:${minutes}:00${centralOffsetForDate(date)}`;
}
