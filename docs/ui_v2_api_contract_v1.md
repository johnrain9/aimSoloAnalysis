# UI v2 API Contract v1

Status: Frozen for `TASK-UI-10`
Version: `v1`
Scope: P0 rewritten UI routes in `ui-v2/`

## Goals
- Freeze the payload shape the rewritten frontend will consume for `import`, `summary`, `insights`, `compare`, and `map`.
- Make ready, `not_ready`, and error semantics explicit.
- Preserve existing backend behavior while documenting the fields the rewritten UI depends on.

## Shared Rules
- All successful P0 route payloads are JSON objects.
- `session_id` is a string in API responses.
- Rider-facing units are `imperial` for P0 UI payloads unless a later versioned contract says otherwise.
- Unknown-session responses use:

```json
{
  "error": "unknown_session",
  "session_id": "123",
  "track_direction": "",
  "analytics_version": "0.1.0-local",
  "rider_name": null,
  "bike_name": null
}
```

- Deterministic `not_ready` responses use:

```json
{
  "error": "not_ready",
  "detail": "human-readable explanation",
  "session_id": "123",
  "track_name": "Track Name",
  "direction": "CW",
  "track_direction": "Track Name CW",
  "analytics_version": "0.1.0-local",
  "rider_name": "Rider",
  "bike_name": "Bike"
}
```

## `POST /import`

### Request

```json
{
  "file_path": "/abs/path/to/session.csv"
}
```

`file_path` is optional. If omitted, the API tries to load the most recent stored session from the local DB.

### Success

```json
{
  "session_id": "17",
  "track_name": "Thunderhill",
  "direction": "CW",
  "track_direction": "CW",
  "analytics_version": "0.1.0-local",
  "source": "/abs/path/to/session.csv",
  "rider_name": "Jane Doe",
  "bike_name": "S1000RR"
}
```

### Failure
- HTTP `404`: missing DB fallback or unreadable file path.
- HTTP `400`: invalid file path or CSV parse failure.
- HTTP `500`: persistence or metadata recovery failure.

## `GET /summary/{session_id}`

### Ready Payload

```json
{
  "session_id": "17",
  "track_name": "Thunderhill",
  "direction": "CW",
  "track_direction": "Thunderhill CW",
  "analytics_version": "0.1.0-local",
  "rider_name": "Jane Doe",
  "bike_name": "S1000RR",
  "units": "imperial",
  "cards": [
    {
      "id": "best_lap",
      "label": "Best Lap",
      "value": "1:56.420",
      "delta": "-0.180",
      "trend": "up"
    }
  ],
  "laps": [
    {
      "lap": 7,
      "time": "1:56.420",
      "sector_times": ["0:38.000", "0:39.100", "0:39.320"],
      "is_best": true
    }
  ]
}
```

### Required Fields
- Top-level: `session_id`, `track_name`, `direction`, `track_direction`, `analytics_version`, `units`, `cards`, `laps`
- `cards[]`: `id`, `label`, `value`, `delta`, `trend`
- `laps[]`: `lap`, `time`, `sector_times`, `is_best`

## `GET /insights/{session_id}`

### Ready Payload

```json
{
  "session_id": "17",
  "track_name": "Thunderhill",
  "direction": "CW",
  "track_direction": "Thunderhill CW",
  "analytics_version": "0.1.0-local",
  "rider_name": "Jane Doe",
  "bike_name": "S1000RR",
  "units": "imperial",
  "unit_contract": {
    "system": "imperial",
    "distance": "ft",
    "speed": "mph",
    "time": "s"
  },
  "track_map": {
    "reference_lap": 4,
    "target_lap": 7,
    "track_direction": "Thunderhill CW",
    "reference_points": [[0.0, 0.0, 0.0]],
    "target_points": [[0.0, 0.0, 0.0]],
    "segments": [
      {
        "id": "T3",
        "label": "T3",
        "start_m": 100.0,
        "apex_m": 130.0,
        "end_m": 170.0
      }
    ],
    "units": "imperial",
    "unit_contract": {
      "system": "imperial",
      "distance": "ft",
      "speed": "mph",
      "time": "s"
    }
  },
  "items": [
    {
      "id": "line_inconsistency",
      "rule_id": "line_inconsistency",
      "title": "T3 line consistency",
      "phase": "mid",
      "did": "At T3 (mid phase), line spread is about 3.0 ft wider than reference.",
      "should": "T3: initiate turn-in at about 387 ft lap distance each lap, then hold one apex marker.",
      "because": "Because line variance is elevated (6.2 ft), timing and speed consistency drop through mid.",
      "operational_action": "T3: initiate turn-in at about 387 ft lap distance each lap, then hold one apex marker.",
      "causal_reason": "Because line variance is elevated (6.2 ft), timing and speed consistency drop through mid.",
      "risk_tier": "Primary",
      "risk_reason": "Evidence quality and context support this as a main next-session focus.",
      "data_quality_note": "gps accuracy good (3.3 ft); 10 satellites",
      "uncertainty_note": "High confidence from current telemetry quality.",
      "success_check": "Rider check: repeat the same turn-in and apex marker for the next 3 laps.",
      "did_vs_should": {
        "did": "At T3 (mid phase), line spread is about 3.0 ft wider than reference.",
        "should": "T3: initiate turn-in at about 387 ft lap distance each lap, then hold one apex marker.",
        "because": "Because line variance is elevated (6.2 ft), timing and speed consistency drop through mid.",
        "success_check": "Rider check: repeat the same turn-in and apex marker for the next 3 laps."
      },
      "expected_gain_s": 0.18,
      "experimental_protocol": null,
      "is_primary_focus": true,
      "confidence": 0.8,
      "confidence_label": "high",
      "gain": "+0.180",
      "time_gain_s": 0.18,
      "detail": "At T3 (mid phase), line spread is about 3.0 ft wider than reference.",
      "actions": [],
      "options": [],
      "segment_id": "T3",
      "corner_id": "T3",
      "corner_label": "T3",
      "evidence": {},
      "comparison": "Lap 8 vs best Lap 3",
      "quality_gate": {},
      "gain_trace": {}
    }
  ]
}
```

### Required Insight Fields
- `id`, `rule_id`, `title`, `phase`
- `did`, `should`, `because`, `success_check`
- `risk_tier`, `confidence`, `confidence_label`
- `expected_gain_s`, `gain`, `time_gain_s`
- `detail`, `corner_id`, `corner_label`, `segment_id`
- `evidence`

### Optional Insight Fields
- `experimental_protocol`
- `quality_gate`
- `gain_trace`
- `actions`
- `options`
- `track_map`

### Not-ready Semantics
- `items` is omitted when `error: "not_ready"` is returned.
- UI must render deterministic fallback text instead of crashing.

## `GET /compare/{session_id}`

### Ready Payload

```json
{
  "session_id": "17",
  "track_name": "Thunderhill",
  "direction": "CW",
  "track_direction": "Thunderhill CW",
  "analytics_version": "0.1.0-local",
  "rider_name": "Jane Doe",
  "bike_name": "S1000RR",
  "units": "imperial",
  "unit_contract": {
    "system": "imperial",
    "distance": "ft",
    "speed": "mph",
    "time": "s"
  },
  "comparison": {
    "reference_lap": 4,
    "target_lap": 7,
    "delta_by_segment": [
      {"segment_id": "T1", "delta_s": 0.08}
    ],
    "delta_by_sector": []
  }
}
```

### Query Parameters
- `reference_lap` optional integer
- `target_lap` optional integer

If an explicit lap is not available, API returns deterministic `not_ready`.

## `GET /map/{session_id}`

### Ready Payload

```json
{
  "lap_a": 4,
  "lap_b": 7,
  "track_direction": "Thunderhill CW",
  "points_a": [[0.0, 0.0, 0.0]],
  "points_b": [[0.0, 0.0, 0.0]],
  "session_id": "17",
  "units": "imperial",
  "unit_contract": {
    "system": "imperial",
    "distance": "ft",
    "speed": "mph",
    "time": "s"
  }
}
```

### Required Fields
- `lap_a`, `lap_b`, `track_direction`, `points_a`, `points_b`, `session_id`, `units`, `unit_contract`

## UI Consumption Rules
- `ui-v2` treats API payloads as source of truth when available and falls back to deterministic mock/offline placeholders when not.
- `ui-v2` does not infer missing did-vs-should fields client-side beyond showing structured empty-state copy.
- `ui-v2` should not depend on undocumented backend fields for route rendering.

## Versioning Rule
- Any payload-breaking change for `ui-v2` routes requires a new versioned contract doc and matching frontend-harness update.
