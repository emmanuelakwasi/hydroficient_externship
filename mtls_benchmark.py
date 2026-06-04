import argparse
import time
import ssl
import statistics
import paho.mqtt.client as mqtt

# Configuration
TLS_PORT = 8883
MTLS_PORT = 8884
BROKER = "localhost"

CA_CERT = "certs/ca.pem"
CLIENT_CERT = "certs/device-001.pem"
CLIENT_KEY = "certs/device-001-key.pem"

try:
    MQTT_CLIENT_ARGS = {"callback_api_version": mqtt.CallbackAPIVersion.VERSION1}
except AttributeError:
    MQTT_CLIENT_ARGS = {}


def measure_connection_time(port, use_client_cert=False, trial_num=1):
    connected = []

    def on_connect(client, userdata, flags, rc):
        connected.append(rc)

    client = mqtt.Client(client_id=f"benchmark-{port}-{trial_num}", **MQTT_CLIENT_ARGS)
    client.on_connect = on_connect

    if use_client_cert:
        client.tls_set(
            ca_certs=CA_CERT,
            certfile=CLIENT_CERT,
            keyfile=CLIENT_KEY,
            tls_version=ssl.PROTOCOL_TLS_CLIENT
        )
    else:
        client.tls_set(
            ca_certs=CA_CERT,
            tls_version=ssl.PROTOCOL_TLS_CLIENT
        )

    start = time.perf_counter()
    try:
        client.connect(BROKER, port, keepalive=60)
        client.loop_start()
        timeout = time.perf_counter() + 5
        while not connected and time.perf_counter() < timeout:
            time.sleep(0.001)
        elapsed = (time.perf_counter() - start) * 1000
        client.loop_stop()
        client.disconnect()
        if connected and connected[0] == 0:
            return elapsed
        else:
            return None
    except Exception as e:
        print(f"    [ERR] {e}")
        return None


def measure_latency(port, use_client_cert=False, count=50):
    latencies = []
    received = []

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            client.subscribe("benchmark/latency/response")

    def on_message(client, userdata, msg):
        recv_time = time.perf_counter() * 1000
        received.append(recv_time)

    client = mqtt.Client(client_id=f"latency-{port}", **MQTT_CLIENT_ARGS)
    client.on_connect = on_connect
    client.on_message = on_message

    if use_client_cert:
        client.tls_set(
            ca_certs=CA_CERT,
            certfile=CLIENT_CERT,
            keyfile=CLIENT_KEY,
            tls_version=ssl.PROTOCOL_TLS_CLIENT
        )
    else:
        client.tls_set(
            ca_certs=CA_CERT,
            tls_version=ssl.PROTOCOL_TLS_CLIENT
        )

    try:
        client.connect(BROKER, port, keepalive=60)
        client.loop_start()
        time.sleep(0.5)

        for i in range(count):
            send_time = time.perf_counter() * 1000
            client.publish("benchmark/latency/response", payload=str(send_time), qos=1)
            time.sleep(0.05)
            if received:
                latency = received[-1] - send_time
                if 0 < latency < 500:
                    latencies.append(latency)
                received.clear()

        client.loop_stop()
        client.disconnect()
        return latencies
    except Exception as e:
        print(f"    [ERR] {e}")
        return []


def run_connection_benchmark(trials):
    print("=" * 60)
    print("mTLS Benchmark: Connection Time")
    print("=" * 60)
    print(f"Running {trials} connection trials for each mode...\n")

    # One-Way TLS
    print(f"Testing One-Way TLS (port {TLS_PORT})...")
    tls_times = []
    for i in range(trials):
        t = measure_connection_time(TLS_PORT, use_client_cert=False, trial_num=i)
        if t is not None:
            tls_times.append(t)
            print(f"  Trial {i+1}: {t:.1f} ms")
        else:
            print(f"  Trial {i+1}: FAILED")

    print()

    # Mutual TLS
    print(f"Testing Mutual TLS (port {MTLS_PORT})...")
    mtls_times = []
    for i in range(trials):
        t = measure_connection_time(MTLS_PORT, use_client_cert=True, trial_num=i)
        if t is not None:
            mtls_times.append(t)
            print(f"  Trial {i+1}: {t:.1f} ms")
        else:
            print(f"  Trial {i+1}: FAILED")

    print()
    print("=" * 60)
    print("  Connection Time Comparison")
    print("=" * 60)

    if tls_times and mtls_times:
        tls_avg = statistics.mean(tls_times)
        mtls_avg = statistics.mean(mtls_times)
        overhead_ms = mtls_avg - tls_avg
        overhead_pct = (overhead_ms / tls_avg) * 100

        print(f"  Trials: {trials}\n")
        print(f"  One-Way TLS:")
        print(f"    Average: {tls_avg:.1f} ms")
        print(f"    Min: {min(tls_times):.1f} ms | Max: {max(tls_times):.1f} ms")
        print()
        print(f"  Mutual TLS:")
        print(f"    Average: {mtls_avg:.1f} ms")
        print(f"    Min: {min(mtls_times):.1f} ms | Max: {max(mtls_times):.1f} ms")
        print()
        print(f"  Overhead: +{overhead_ms:.1f} ms (+{overhead_pct:.1f}%)")
    else:
        print("  Not enough data. Check broker connections.")

    print("=" * 60)


def run_latency_benchmark(count):
    print("=" * 60)
    print("mTLS Benchmark: Message Latency")
    print("=" * 60)
    print(f"Sending {count} messages for each mode...\n")

    print(f"Testing One-Way TLS (port {TLS_PORT})...")
    print(f"  Connected. Publishing {count} messages...")
    tls_latencies = measure_latency(TLS_PORT, use_client_cert=False, count=count)
    if tls_latencies:
        print(f"  Average latency: {statistics.mean(tls_latencies):.1f} ms")

    print()
    print(f"Testing Mutual TLS (port {MTLS_PORT})...")
    print(f"  Connected. Publishing {count} messages...")
    mtls_latencies = measure_latency(MTLS_PORT, use_client_cert=True, count=count)
    if mtls_latencies:
        print(f"  Average latency: {statistics.mean(mtls_latencies):.1f} ms")

    print()
    print("=" * 60)
    print("  Message Latency Comparison")
    print("=" * 60)

    if tls_latencies and mtls_latencies:
        tls_avg = statistics.mean(tls_latencies)
        mtls_avg = statistics.mean(mtls_latencies)
        overhead_ms = mtls_avg - tls_avg
        overhead_pct = (overhead_ms / tls_avg) * 100 if tls_avg > 0 else 0

        print(f"  Messages: {count}\n")
        print(f"  One-Way TLS:")
        print(f"    Average: {tls_avg:.1f} ms")
        print(f"    Min: {min(tls_latencies):.1f} ms | Max: {max(tls_latencies):.1f} ms")
        print()
        print(f"  Mutual TLS:")
        print(f"    Average: {mtls_avg:.1f} ms")
        print(f"    Min: {min(mtls_latencies):.1f} ms | Max: {max(mtls_latencies):.1f} ms")
        print()
        print(f"  Overhead: +{overhead_ms:.1f} ms (+{overhead_pct:.1f}%)")
    else:
        print("  Not enough data. Check broker connections.")

    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="mTLS Benchmark Tool")
    parser.add_argument("--mode", choices=["connection", "latency"], required=True)
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args()

    if args.mode == "connection":
        run_connection_benchmark(args.trials)
    elif args.mode == "latency":
        run_latency_benchmark(args.count)