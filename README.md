# Hydroficient IoT Cyber Defense

**IoT Cybersecurity Externship** | Grand Marina Hotel Water Monitoring System  
*January – March 2026*

---

## Overview

Hydroficient is a practical exploration of how to secure an IoT water monitoring system from the ground up. The project simulates a real hotel facility — the Grand Marina — where pressure sensors and flow meters report live data across three zones: the main building, pool & spa, and kitchen & laundry.

The work progresses across seven iterations, each adding a new security layer. By the end, the system defends against eavesdropping, unauthorized device access, message tampering, and replay attacks — all demonstrable in real time through a live dashboard.

---

## The Problem

Unencrypted MQTT is the default for many IoT deployments. A device on the same network can subscribe to any topic, inject fabricated readings, or silently replay old messages to mask an incident. For a critical utility system like water management, this isn't a theoretical risk — it's a direct path to false sensor data reaching operations staff.

This project treats that threat model seriously and builds toward a hardened deployment.

---

## Security Architecture

The system applies three distinct layers of defense, each addressing a different attack surface:

### Layer 1 — Transport Encryption (TLS)
One-way TLS encrypts all MQTT traffic between devices and the broker. The broker presents a signed certificate; clients verify it against a trusted CA. This closes the wire to passive eavesdroppers.

### Layer 2 — Device Identity (Mutual TLS)
mTLS requires every device to present its own signed certificate before the broker will accept a connection. Anonymous clients and rogue devices are rejected at the handshake. Each device certificate encodes the device's physical location in its Common Name, so the broker knows exactly which zone it's talking to.

Certificate hierarchy:
```
Hydroficient IoT CA  (4096-bit RSA, self-signed, 10-year validity)
├── Broker Certificate         → Mosquitto MQTT broker
├── device-001                 → HYDROLOGIC-MainBuilding-001
├── device-002                 → HYDROLOGIC-PoolSpa-002
└── device-003                 → HYDROLOGIC-Kitchen-003
```

### Layer 3 — Message Integrity & Replay Defense
Even a trusted, authenticated device could be compromised or impersonated at the application layer. Every published message carries three controls validated on the subscriber side:

| Control | Mechanism | Defends Against |
|---|---|---|
| Signature | HMAC-SHA256 over sorted JSON payload | Tampering, injection |
| Freshness | ISO 8601 timestamp, 30-second window | Stale message replay |
| Ordering | Per-device sequence counter | Duplicate/replay delivery |

Validation is fail-fast: a single failed check drops the message and logs the reason.

---

## Project Progression

| Stage | What Was Added |
|---|---|
| Projects 3–4 | Basic MQTT publisher/subscriber + one-way TLS |
| Project 5 | Mutual TLS — broker enforces client certificates |
| Project 6 | HMAC signatures, timestamp freshness, sequence counters |
| Project 7 | Real-time security dashboard with WebSocket bridge |

---

## Attack Simulation

The project includes purpose-built attack tools to verify that defenses actually hold.

**`attack_simulator.py`** runs a three-phase demonstration:
1. **Eavesdropping** — subscribe to all topics using a valid cert (succeeds — encryption doesn't restrict reads, mTLS does)
2. **Data Injection** — publish fabricated sensor readings with an invalid HMAC (blocked at signature check)
3. **Replay Attack** — re-send previously captured messages (blocked at timestamp or sequence check)

**`replay_attacker.py`** gives finer control:
```
# Capture 5 legitimate messages
python replay_attacker.py --mode capture --count 5

# Replay them immediately (blocked by sequence counter)
python replay_attacker.py --mode replay

# Replay after 60 seconds (blocked by timestamp)
python replay_attacker.py --mode replay-delayed --delay 60

# Replay with modified sensor values (blocked by HMAC)
python replay_attacker.py --mode replay-modified
```

**`identity_tester.py`** walks through four mTLS scenarios:
- Valid certificate signed by the project CA → accepted
- No client certificate → rejected at handshake
- Certificate signed by a different CA → rejected (chain verification)
- Expired certificate → rejected

---

## Real-Time Dashboard

`subscriber_dashboard.py` bridges the MQTT stream to a browser via WebSocket. The dashboard displays live pressure, flow rate, and valve position per zone, alongside a running security event log — blocked attacks appear immediately with color and shake animations.

```
# Start the full stack
mosquitto -c mosquitto_mtls.conf -v
python publisher_defended.py
python subscriber_dashboard.py        # opens http://localhost:8000 automatically
```

---

## Running the System

**Prerequisites**
```
pip install paho-mqtt cryptography websockets
```
You'll also need [Mosquitto](https://mosquitto.org/) installed and available on your PATH.

**Generate certificates**
```
python generate_client_certs.py
```
This creates the CA, broker certificate, and one signed certificate per device under `certs/`.

**Basic secured run (mTLS only)**
```
mosquitto -c mosquitto_mtls.conf -v
python publisher_mtls.py
python subscriber_mtls.py
```

**Full defended run (HMAC + replay protection)**
```
mosquitto -c mosquitto_mtls.conf -v
python publisher_defended.py
python subscriber_defended.py
```

**With dashboard + live attack demo**
```
# Terminal 1
mosquitto -c mosquitto_mtls.conf -v

# Terminal 2
python publisher_defended.py

# Terminal 3
python subscriber_dashboard.py

# Terminal 4 (watch the dashboard react)
python attack_simulator.py
```

**Performance benchmarking**
```
python mtls_benchmark.py --mode connection --trials 20
python mtls_benchmark.py --mode latency --count 50
```
In testing, mTLS added roughly 5–15% latency overhead compared to one-way TLS — a negligible cost for the authentication guarantee it provides.

---

## Sensor Data

Three monitored zones, each with simulated realistic baselines:

| Zone | Inlet PSI | Outlet PSI | Flow Rate |
|---|---|---|---|
| Main Building | ~82 | ~77 | ~41 gal/min |
| Pool & Spa | ~68 | ~63 | ~35 gal/min |
| Kitchen & Laundry | ~90 | ~85 | ~28 gal/min |

Each message includes gate/valve position, a device-local timestamp, and a sequence number.

---

## Tech Stack

- **Python 3.7+** — primary language
- **paho-mqtt** — MQTT client (compatible with 1.x and 2.0+ API)
- **cryptography** — X.509 certificate generation and signing
- **hmac / hashlib** — HMAC-SHA256 message authentication
- **asyncio + websockets** — async WebSocket bridge for the dashboard
- **Mosquitto** — MQTT broker

---

## Key Takeaways

Working through this project made concrete a few things that are easy to accept as abstract theory:

- TLS secures the wire but says nothing about who the device is. mTLS closes that gap.
- Message-level controls are necessary even after transport security — a compromised endpoint can still inject or replay over an encrypted channel.
- Replay attacks are subtle. A message that was valid minutes ago is not valid now, and the system has to enforce that explicitly.
- Threat simulation is part of the build. Writing the attacker and the defender in the same codebase forces clarity about what exactly each defense covers.

---

## Externship

**Hydroficient IoT Cyber Defense Externship**  
Completed January – March 2025
