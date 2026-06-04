""

import json
import signal
import sys
from datetime import datetime, timezone
import paho.mqtt.client as mqtt



BROKER_HOST = "localhost"
BROKER_PORT = 1883
TOPIC       = "hydroficient/grandmarina/#"   # Wildcard — all Grand Marina topics
CLIENT_ID   = "GM-DASHBOARD-01"


DIVIDER      = "─" * 40
WIDE_DIVIDER = "=" * 60

def print_header():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(WIDE_DIVIDER)
    print("  GRAND MARINA WATER MONITORING DASHBOARD")
    print(f"  Connected at: {now}")
    print(WIDE_DIVIDER)
    print()

def print_reading(payload: dict, topic: str):
    """Print a single sensor reading in dashboard format."""
    sensors   = payload.get("sensors", {})
    location  = payload.get("location",  "unknown")
    device_id = payload.get("device_id", "unknown")
    timestamp = payload.get("timestamp", "—")
    counter   = payload.get("counter",   "—")

    inlet  = sensors.get("inlet_pressure_psi",  None)
    outlet = sensors.get("outlet_pressure_psi", None)
    flow   = sensors.get("flow_rate_gpm",        None)

    print(DIVIDER)
    print(f"  Location:  {location}")
    print(f"  Device ID: {device_id}")
    print(f"  Time:      {timestamp}")
    print(f"  Count:     #{counter}")
    print(DIVIDER)

    if inlet is not None:
        print(f"  Pressure (upstream):   {inlet:>6.1f} PSI")
    if outlet is not None:
        print(f"  Pressure (downstream): {outlet:>6.1f} PSI")
    if flow is not None:
        print(f"  Flow rate:             {flow:>6.1f} gal/min")
    if inlet is not None and outlet is not None:
        diff = round(inlet - outlet, 1)
        print(f"  Pressure differential: {diff:>6.1f} PSI")

    # Warn on anomalous values
    alerts = []
    if inlet  is not None and (inlet  < 70 or inlet  > 95):  alerts.append("⚠  Inlet pressure out of range")
    if outlet is not None and (outlet < 60 or outlet > 90):  alerts.append("⚠  Outlet pressure out of range")
    if flow   is not None and (flow   < 30 or flow   > 55):  alerts.append("⚠  Flow rate out of range")
    if inlet  is not None and outlet is not None and abs(inlet - outlet) > 15:
        alerts.append("⚠  High pressure differential")
    if alerts:
        print()
        for a in alerts:
            print(f"  {a}")

    print()


# ── MQTT callbacks ────────────────────────────────────────────────────────────

_message_count = 0

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(TOPIC, qos=1)
        print_header()
        print(f"  Subscribed to: {TOPIC}")
        print(f"  Waiting for sensor data…\n")
    else:
        codes = {1: "Bad protocol", 2: "Bad client ID", 3: "Server unavailable",
                 4: "Bad credentials", 5: "Not authorised"}
        print(f"Connection failed: {codes.get(rc, f'rc={rc}')}")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"\n[!] Unexpected disconnect (rc={rc}). Reconnecting…")

def on_message(client, userdata, msg):
    global _message_count
    _message_count += 1

    # Attempt JSON parse — handle non-JSON gracefully
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        print(DIVIDER)
        print(f"  [Non-JSON message on {msg.topic}]")
        print(f"  Raw: {msg.payload[:120]}")
        print()
        return

    # If it looks like a sensor reading, display it
    if "sensors" in payload:
        print_reading(payload, msg.topic)
    else:
        # Generic formatted dump for other message types
        print(DIVIDER)
        print(f"  Topic:   {msg.topic}")
        for key, value in payload.items():
            print(f"  {key:<12} {value}")
        print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv311)
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    client.on_message    = on_message

    def handle_shutdown(sig, frame):
        print(f"\n\nDashboard stopped. Total messages received: {_message_count}")
        client.loop_stop()
        client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT,  handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    except ConnectionRefusedError:
        print(f"\n[ERROR] Could not reach broker at {BROKER_HOST}:{BROKER_PORT}.")
        print("  → Make sure your MQTT broker (e.g. Mosquitto) is running.")
        sys.exit(1)

    client.loop_forever()


if __name__ == "__main__":
    main()