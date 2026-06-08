# TURN Server Setup for CHAIN

## Overview

TURN (Traversal Using Relays around NAT) servers are required for reliable WebRTC calls across different networks. When direct peer-to-peer connections fail (e.g., both users behind restrictive NAT/firewalls), TURN relays the media stream.

## Recommended: Coturn

### Installation

```bash
# Ubuntu/Debian
sudo apt-get install coturn

# macOS
brew install coturn
```

### Basic Configuration

Create `/etc/turnserver.conf`:

```ini
listening-port=3478
tls-listening-port=5349
fingerprint
realm=chain-app.com
user=chain-turn:your-strong-password
total-quota=100
bp-addr-quota=20
stale-nonce
no-multicast-peers
```

### Running

```bash
turnserver -c /etc/turnserver.conf
```

## CHAIN Environment Variables

```bash
# .env
STUN_SERVER_URL=stun:stun.l.google.com:19302
TURN_SERVER_URL=turn:your-server.com:3478
TURN_USERNAME=chain-turn
TURN_PASSWORD=your-strong-password
```

For multiple TURN servers (comma-separated):

```bash
TURN_SERVER_URL=turn:turn1.example.com:3478,turn:turn2.example.com:3478
```

## Verification

Run the check script:

```bash
PYTHONPATH=. python3 scripts/check_phase36_turn.py
```

## How CHAIN Uses ICE

The `webrtc_turn_service.py` module generates ICE config dynamically:

```python
from services.webrtc_turn_service import get_webrtc_ice_config
config = get_webrtc_ice_config()
# Returns: { "iceServers": [...], "iceTransportPolicy": "all", "iceCandidatePoolSize": 10 }
```

The config includes:
- Google's public STUN server (default)
- Your TURN server with UDP/TCP fallback
- Multiple TURN server support
- Automatic TCP fallback URLs

## Security

- TURN credentials are never exposed in source code
- ICE config is generated at runtime from environment variables
- No secrets in frontend templates
