# Quark Media System - API Contract (Aligned with core-backend)

This document reflects the actual FastAPI routes in `services/core-backend/app/api/routes.py`.
Frontend-only needs are marked as **MISSING IN BACKEND**.

## Base
- API host: `${NEXT_PUBLIC_API_BASE}` (example: `http://localhost:8000`)
- API prefix: `/api/v1` (client appends if not already present)
- Content-Type: `application/json`

## Error Shape
- Errors return HTTP status codes with `{"detail": "..."}`.

## 1) Share Parse
POST `/api/v1/share/parse`

Request:
```
{
  "url": "https://pan.quark.cn/s/xxxx" | "shareCode",
  "passcode": "optional"
}
```

Response (200):
```
{
  "total_count": 10,
  "files": [
    {
      "fid": "...",
      "name": "...",
      "is_dir": false,
      "parent_fid": "...",
      "path": "/...",
      "size": 123456,
      "file_type": 0,
      "share_fid_token": "..."
    }
  ]
}
```

Errors:
- 400/401/404/500 with `detail`

## 2) Media Provision (Queue Transfer)
POST `/api/v1/media/{media_id}/provision`

Path param:
- `media_id`: numeric VirtualMedia id (not TMDB id)

Response (202 accepted):
```
{
  "status": "accepted",
  "message": "Provisioning started"
}
```

Other responses:
- 200 `{ "status": "archived", "physical_path": "/..." }`
- 200 `{ "status": "processing", "message": "Provisioning already in progress" }`
- 404/500 with `detail`

## 3) Tasks
GET `/api/v1/tasks/stats`

Response:
```
{
  "by_status": {
    "pending": 0,
    "processing": 1,
    "completed": 2,
    "failed": 0
  },
  "queue_size": 3,
  "dead_queue_size": 0
}
```

POST `/api/v1/tasks/dead/retry/{media_id}`
```
{ "status": "queued", "message": "Task requeued for retry" }
```

GET `/api/v1/tasks/dead`
```
{ "count": 0, "tasks": [ { ...queued_payload } ] }
```

DELETE `/api/v1/tasks/dead`
```
{ "status": "cleared", "count": 0 }
```

POST `/api/v1/tasks/cookie/update`
```
{ "cookie": "..." }
```
Response:
```
{ "status": "updated", "message": "Cookie updated successfully" }
```

GET `/api/v1/tasks/cookie/validate`
```
{ "valid": true, "message": "Cookie is valid" }
```

## 4) Resources Search (Telegram Aggregation)
GET `/api/v1/resources/search?keyword={keyword}`

Response:
```
{
  "data": [
    {
      "id": "group-id",
      "list": [
        {
          "id": "...",
          "messageId": "...",
          "title": "...",
          "content": "...",
          "pubDate": "...",
          "image": "...",
          "cloudLinks": ["https://pan.quark.cn/s/..."],
          "cloudType": "quark",
          "tags": ["..."],
          "channel": "...",
          "channelId": "..."
        }
      ],
      "channelInfo": {
        "id": "...",
        "name": "...",
        "channelLogo": "...",
        "channelId": "..."
      }
    }
  ]
}
```

GET `/api/v1/resources/channels`

Response:
```
[
  {
    "id": "...",
    "name": "...",
    "channelLogo": "...",
    "channelId": "..."
  }
]
```

Legacy:
- GET `/api/search?keyword={keyword}` (same response shape)

Frontend mapping note:
- `searchQuarkLinks` flattens `cloudLinks` into LinkItem entries.

---

## 5) Home Feed
GET `/api/v1/home`

Response:
```
{
  "favorites": [MediaItem],
  "trending": [MediaItem],
  "updatedAt": "ISO-8601"
}
```

MediaItem:
```
{
  "tmdbId": "string",
  "title": "string",
  "year": "string?",
  "rating": 7.8,
  "posterUrl": "string?",
  "status": "VIRTUAL|MATERIALIZED|PROVISIONING|FAILED",
  "overview": "string?"
}
```

## 6) Media Detail
GET `/api/v1/media/{tmdbId}`

Response:
```
{
  "tmdbId": "string",
  "title": "string",
  "overview": "string?",
  "year": "string?",
  "runtime": "string?",
  "rating": 7.6,
  "genres": ["string"],
  "posterUrl": "string?",
  "backdropUrl": "string?",
  "resources": [ResourceItem]
}
```

ResourceItem:
```
{
  "id": "string",
  "name": "string",
  "size": "string?",
  "status": "VIRTUAL|MATERIALIZED|PROVISIONING|FAILED",
  "updatedAt": "ISO-8601?",
  "webdavPath": "string?",
  "errorMessage": "string?"
}
```

## 7) Save Virtual Link
POST `/api/v1/media/{tmdbId}/links/virtual`

Request:
```
{
  "tmdbId": "string",
  "linkId": "string",
  "title": "string",
  "shareUrl": "string"
}
```

Response:
```
{ "status": "VIRTUAL", "savedAt": "ISO-8601" }
```

## 8) Trigger JIT Provision
POST `/api/v1/media/{tmdbId}/provision`

Request:
```
{
  "tmdbId": "string",
  "linkId": "string",
  "shareUrl": "string?"
}
```

Response:
```
{
  "taskId": "string",
  "status": "pending|processing|completed|failed",
  "tmdbId": "string",
  "linkId": "string?",
  "updatedAt": "ISO-8601",
  "errorMessage": "string?"
}
```

## 9) Task Status
GET `/api/v1/tasks/{taskId}`

Response:
```
{
  "taskId": "string",
  "status": "pending|processing|completed|failed",
  "tmdbId": "string",
  "linkId": "string?",
  "updatedAt": "ISO-8601",
  "errorMessage": "string?",
  "progress": 0.5,
  "resultWebdavUrl": "string?"
}
```

Notes:
- `linkId` or `shareUrl` is used to locate the VirtualMedia row before enqueueing.
