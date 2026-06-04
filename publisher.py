
import json
import time
import random
import signal
import sys
from datetime import datetime, timezone
import paho.mqtt.client as mqtt





# ── Configuration ────────────────────────────────────────────────────────────

BROKER_HOST = "localhost"          # Change to your broker's hostname/IP
BROKER_PORT = 1883
TOPIC       = "hydroficient/grandmarina/sensors/main-building/readings"
DEVICE_ID   = "GM-HYDROLOGIC-01"
LOCATION    = "main-building"
INTERVAL    = 2                    # seconds between readings

# Baseline sensor values
BASE_INLET_PRESSURE  = 82.0       # PSI
BASE_OUTLET_PRESSURE = 77.0       # PSI
BASE_FLOW            = 41.0       # gal/min



class WaterSensorMQTT:
    """Simulates a water sensor and publishes readings via MQTT."""

    def __init__(self, device_id: str, location: str, broker_host: str, broker_port: int = 1883):
        self.device_id   = device_id
        self.location    = location
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.counter     = 0
        self._connected  = False

        self.client = mqtt.Client(client_id=device_id, protocol=mqtt.MQTTv311)
        self.client.on_connect    = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish    = self._on_publish



    def _on_connect(self, client, userdata, flags, rc):
        codes = {
            0: "Connected successfully",
            1: "Incorrect protocol version",
            2: "Invalid client identifier",
            3: "Server unavailable",
            4: "Bad username or password",
            5: "Not authorised",
        }
        if rc == 0:
            self._connected = True
            print(f"Broker: {codes.get(rc, 'Unknown')}")
        else:
            print(f"Connection failed: {codes.get(rc, f'rc={rc}')}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            print(f"Unexpected disconnect (rc={rc}). Reconnecting…")

    def _on_publish(self, client, userdata, mid):
        pass  # Acknowledged by broker

    # ── Sensor simulation ─────────────────────────────────────────────────────

    def _read_sensors(self) -> dict:
        """Generate a realistic sensor reading with small random variation."""
        def vary(base, spread=1.5):
            return round(base + random.uniform(-spread, spread), 1)

        return {
            "inlet_pressure_psi":  vary(BASE_INLET_PRESSURE),
            "outlet_pressure_psi": vary(BASE_OUTLET_PRESSURE),
            "flow_rate_gpm":       vary(BASE_FLOW, spread=2.0),
        }

    def _build_payload(self) -> dict:
        self.counter += 1
        sensors = self._read_sensors()
        return {
            "device_id":  self.device_id,
            "location":   self.location,
            "counter":    self.counter,
            "timestamp":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sensors":    sensors,
            "units": {
                "pressure": "PSI",
                "flow":     "gal/min",
            },
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def connect(self):
        print(f"Connecting to broker at {self.broker_host}:{self.broker_port} …")
        self.client.connect(self.broker_host, self.broker_port, keepalive=60)
        self.client.loop_start()
        time.sleep(1)  # Give the network loop time to handshake

    def publish_reading(self, topic: str) -> dict:
        payload = self._build_payload()
        result  = self.client.publish(topic, json.dumps(payload), qos=1)
        result.wait_for_publish()
        return payload

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    sensor = WaterSensorMQTT(
        device_id   = DEVICE_ID,
        location    = LOCATION,
        broker_host = BROKER_HOST,
        broker_port = BROKER_PORT,
    )

    # Graceful shutdown on Ctrl-C
    def handle_shutdown(sig, frame):
        print(f"\n\nShutting down after {sensor.counter} readings. Goodbye!")
        sensor.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT,  handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

   
    print(f"Starting device: {DEVICE_ID}")
    print(f"Location:        {LOCATION}")
    print(f"Publishing to:   {TOPIC}")
    print(f"Interval:        {INTERVAL} seconds")
    print("-" * 40)

    sensor.connect()

    while True:
        payload = sensor.publish_reading(TOPIC)
        s = payload["sensors"]
        print(
            f"[{payload['counter']}] "
            f"Pressure: {s['inlet_pressure_psi']}/{s['outlet_pressure_psi']} PSI, "
            f"Flow: {s['flow_rate_gpm']} gal/min"
        )
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()