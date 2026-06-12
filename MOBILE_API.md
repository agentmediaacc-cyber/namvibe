# NamVibe Mobile API v1 Documentation

## Base URL
`https://your-domain.com/api/v1`

## Authentication
Use Bearer Token in the `Authorization` header:
`Authorization: Bearer <access_token>`

Or use session-based auth (Web-only).

## Endpoints

### Auth
- `POST /auth/login`: Login with email/password.
- `POST /auth/register`: Register new account.

### Feed
- `GET /feed/`: Get ranked feed. Supports `limit` and `offset`.

### Reels
- `GET /reels/`: List public reels.
- `GET /reels/<id>`: Get single reel.
- `POST /reels/upload`: Upload video (multipart/form-data).
- `POST /reels/<id>/view`: Record a view.
- `POST /reels/<id>/like`: Like a reel.

### Messages
- `GET /messages/threads`: List active threads.
- `GET /messages/threads/<id>`: Get messages in a thread.
- `POST /messages/send`: Send a message.
- `POST /messages/threads/<id>/seen`: Mark thread as seen.

### Notifications
- `GET /notifications/`: List notifications.
- `GET /notifications/unread-count`: Get unread count.
- `POST /notifications/read-all`: Mark all read.

### Live
- `GET /live/rooms`: List active live rooms.
- `GET /live/rooms/<id>`: Get room details.

## Realtime (Socket.IO)
- **Connect**: Send access token or session cookie.
- **Events**:
  - `join_thread`: `{"thread_id": "..."}`
  - `leave_thread`: `{"thread_id": "..."}`
  - `join_live_room`: `{"room_id": "..."}`
  - `typing_start`: `{"thread_id": "..."}`
  - `presence_heartbeat`: No payload.

## Error Format
```json
{
  "success": false,
  "error": {
    "code": "error_code",
    "message": "Human readable message"
  }
}
```

## Pagination
Standard `limit` and `offset` query parameters.

## Rate Limits
- 60 messages/min
- 30 uploads/hour
- 10 login attempts/min
