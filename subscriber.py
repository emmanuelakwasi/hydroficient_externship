import json
import signal
import sys
from datetime import datetime, timezone
import paho.mqtt.client as mqtt



BROKER_HOST = "localhost"          # Must match publisher's broker
BROKER_PORT = 1883
TOPIC       = "hydroficient/grandmarina/sensors/main-building/readings"
CLIENT_ID   = "GM-SUBSCRIBER-01"


# ── Formatting helpers ────────────────────────────────────────────────────────

def _pressure_bar(inlet: float, outlet: float, width: int = 20) -> str:
    """Simple ASCII bar scaled to 0-100 PSI."""
    filled = int((inlet / 100) * width)
    return f"[{'█' * filled}{'░' * (width - filled)}]"

def _alert(inlet: float, outlet: float, flow: float) -> str:
    """Return a warning tag if values look anomalous."""
    warnings = []
    if inlet < 70 or inlet > 95:
        warnings.append("⚠ PRESSURE")
    if flow < 30 or flow > 55:
        warnings.append("⚠ FLOW")
    diff = abs(inlet - outlet)
    if diff > 15:
        warnings.append("⚠ DIFFERENTIAL")
    return "  " + "  ".join(warnings) if warnings else ""


# ── MQTT callbacks ────────────────────────────────────────────────────────────

_reading_count = 0   # how many messages this subscriber has received

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected to broker at {BROKER_HOST}:{BROKER_PORT}")
        client.subscribe(TOPIC, qos=1)
        print(f"Subscribed to: {TOPIC}")
        print("=" * 55)
        print(f"{'#':>4}  {'Inlet':>7}  {'Outlet':>7}  {'Flow':>9}  Timestamp")
        print("-" * 55)
    else:
        print(f"Connection failed (rc={rc}). Is the broker running?")


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"\nUnexpected disconnect (rc={rc}).")


def on_message(client, userdata, msg):
    global _reading_count
    _reading_count += 1

    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"  [!] Could not parse message: {exc}")
        return

    # Pull fields with safe defaults
    counter  = payload.get("counter",  _reading_count)
    sensors  = payload.get("sensors",  {})
    ts_raw   = payload.get("timestamp", "")
    inlet    = sensors.get("inlet_pressure_psi",  0.0)
    outlet   = sensors.get("outlet_pressure_psi", 0.0)
    flow     = sensors.get("flow_rate_gpm",        0.0)

    # Friendly local timestamp
    try:
        ts_utc  = datetime.strptime(ts_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        ts_disp = ts_utc.astimezone().strftime("%H:%M:%S")
    except ValueError:
        ts_disp = ts_raw or "—"

    alert = _alert(inlet, outlet, flow)
    bar   = _pressure_bar(inlet, outlet)

    print(
        f"[{counter:>3}]  "
        f"{inlet:>6.1f}  "
        f"{outlet:>6.1f}  "
        f"{flow:>8.1f}  "
        f"{ts_disp}"
        f"{alert}"
    )
    # Detailed block every 10 readings
    if counter % 10 == 0:
        diff = round(inlet - outlet, 1)
        print(f"\n        Pressure bar {bar}  Δ={diff} PSI\n")


def on_subscribe(client, userdata, mid, granted_qos):
    pass  # Confirmation handled in on_connect


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    client = mqtt.Client(client_id=CLIENT_ID, protocol=mqtt.MQTTv311)
    client.on_connect   = on_connect
    client.on_disconnect = on_disconnect
    client.on_message   = on_message
    client.on_subscribe = on_subscribe

    def handle_shutdown(sig, frame):
        print(f"\n\nSubscriber stopped. Total readings received: {_reading_count}")
        client.loop_stop()
        client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT,  handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print("=" * 55)
    print("  Water Sensor MQTT Subscriber")
    print(f"  Device:  {CLIENT_ID}")
    print(f"  Broker:  {BROKER_HOST}:{BROKER_PORT}")
    print("=" * 55)

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    except ConnectionRefusedError:
        print(f"\n[ERROR] Could not reach broker at {BROKER_HOST}:{BROKER_PORT}.")
        print("  → Make sure your MQTT broker (e.g. Mosquitto) is running.")
        sys.exit(1)

    client.loop_forever()   # Blocking; handles reconnects automatically


if __name__ == "__main__":
    main()
    