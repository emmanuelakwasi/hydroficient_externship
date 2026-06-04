import paho.mqtt.client as mqtt
import ssl

try:
    MQTT_CLIENT_ARGS = {"callback_api_version": mqtt.CallbackAPIVersion.VERSION1}
except AttributeError:
    MQTT_CLIENT_ARGS = {}

client = mqtt.Client(client_id="rogue-device", **MQTT_CLIENT_ARGS)
client.tls_set(ca_certs="certs/ca.pem")

try:
    client.connect("localhost", 8883, keepalive=60)
    print("ERROR: Connection should have been rejected!")
except Exception as e:
    print(f"SUCCESS: Connection rejected: {e}")