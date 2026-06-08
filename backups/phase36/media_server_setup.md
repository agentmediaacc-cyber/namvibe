# Media Server Setup for CHAIN Live Streaming

## Overview

CHAIN supports three media server backends for production live streaming:

1. **LiveKit** (recommended) — WebRTC-native, supports broadcasting, recording, transcoding
2. **MediaMTX** — lightweight RTSP/RTMP/HLS/WebRTC server
3. **Custom RTMP** — any RTMP-compatible server (nginx-rtmp, etc.)

## Quick Start: LiveKit (Recommended)

### Installation

```bash
# Download LiveKit server
curl -sSL https://get.livekit.io | bash

# Run
lk-server --config lk.yaml
```

### Configuration

```yaml
# lk.yaml
port: 7880
rtc:
  tcp_port: 7881
  udp_port: 7882
redis:
  address: localhost:6379
```

### CHAIN Environment

```bash
# .env
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
```

## MediaMTX

```bash
docker run --rm -it -p 8554:8554 -p 8888:8888 -p 1935:1935 bluenviron/mediamtx
```

```bash
# .env
MEDIA_SERVER_URL=localhost:8888
```

## Custom RTMP Server (nginx-rtmp)

```bash
# Use nginx with rtmp module
RTMP_SERVER_URL=rtmp://your-server.com/live
```

## Verification

```bash
PYTHONPATH=. python3 scripts/check_phase36_media.py
```

## How CHAIN Uses Media Servers

The `media_server_service.py` module detects available backends and returns capability flags:

```python
from services.media_server_service import is_live_streaming_ready
status = is_live_streaming_ready()
# Returns:
# {
#   "status": "ready" | "partial" | "missing",
#   "backends": ["livekit"],
#   "capabilities": { broadcast, webrtc_broadcast, recording, ... }
# }
```

## Capabilities by Backend

| Backend | Broadcast | WebRTC | RTMP | Recording | Transcoding |
|---------|-----------|--------|------|-----------|-------------|
| LiveKit | ✓ | ✓ | ✓ | ✓ | ✓ |
| MediaMTX | ✓ | ✓ | ✓ | ✓ | |
| RTMP | ✓ | | ✓ | | |
