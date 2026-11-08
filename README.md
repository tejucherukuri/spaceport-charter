# Spaceport Charter System

Welcome, dispatcher. The Pacific Spaceport runs a small fleet of charter ships, and the booking process has — until now — involved a clipboard, a whiteboard, and a great deal of shouting. Your job is to build the replacement.

## What to build

A small full-stack application with two screens:

1. **Charter a Ship.** A user picks a ship and a date, sees which time slots are unavailable, and books an available slot.
2. **Fleet Manager Dashboard.** A view of all bookings across the fleet, organized by ship.

There is no authentication. Assume bookings carry a `pilotName` (free-text) so the manager view has something to display.

## The rules

- **No overlapping bookings.** Two bookings for the same ship cannot overlap.
- **Refueling buffer.** Consecutive bookings on the same ship must be separated by at least 30 minutes of refueling time.
- **Operating hours.** The spaceport is open from **6:00 AM to 10:00 PM Central Time**, every day. Bookings must fall entirely within operating hours.

The unavailable-time information shown on the booking screen must come from a backend endpoint. Do not compute it on the client by fetching the full bookings list.

## Data model (minimum)

- **Ship**: `id`, `name`
- **Booking**: `id`, `shipId`, `pilotName`, `startTime`, `endTime`

You may add fields as you see fit.

## Seed data

The repo includes `seed.py`, which prints a JSON object with the starting fleet and a year of existing bookings:

```
python seed.py > seed.json
```

Load it into your database however you like.

The starting fleet:

```json
[
  { "id": 1, "name": "USS Wanderer" },
  { "id": 2, "name": "Nostromo" },
  { "id": 3, "name": "Serenity" },
  { "id": 4, "name": "Rocinante" },
  { "id": 5, "name": "Millennium Falcon" }
]
```

## Stack

- **Frontend:** React.
- **Backend:** Python — Django or FastAPI is a good starting point, but feel free to use a framework you're more comfortable with.
- **Database:** your choice.
- **Everything else:** your call — frameworks, libraries, project structure, API shape.

## Submission

Push your work to a public GitHub repository and send us the link.

## AI usage

Using AI tools is permitted and expected. We don't care whether you used them; we care that you can explain and justify every decision in your submission. On the technical call we'll ask why your code is the way it is — be ready to walk through it as if you wrote every line yourself.

## Time

Aim for **2–3 hours**. If you find yourself going significantly over, stop and make a note of what you'd do next — we'd rather see a focused, working submission than an exhausted one.

We'll review your code beforehand and discuss it with you on a follow-up call, where we'll ask about your decisions and may request a small modification live. Build something you'll be comfortable walking us through.

Good luck, dispatcher. The fleet is waiting.
