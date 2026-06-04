import argparse
import ssl
import time
import datetime
import os
import tempfile
import paho.mqtt.client as mqtt

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

# Configuration
BROKER = "localhost"
PORT = 8883
CA_CERT = "certs/ca.pem"
CA_KEY = "certs/ca-key.pem"
CLIENT_CERT = "certs/device-001.pem"
CLIENT_KEY = "certs/device-001-key.pem"

try:
    MQTT_CLIENT_ARGS = {"callback_api_version": mqtt.CallbackAPIVersion.VERSION1}
except AttributeError:
    MQTT_CLIENT_ARGS = {}


def try_connect(ca_certs, certfile=None, keyfile=None, label=""):
    connected = []
    failed = []

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            connected.append(True)
        else:
            failed.append(rc)

    client = mqtt.Client(client_id=f"identity-tester-{label}", **MQTT_CLIENT_ARGS)
    client.on_connect = on_connect

    try:
        if certfile and keyfile:
            client.tls_set(
                ca_certs=ca_certs,
                certfile=certfile,
                keyfile=keyfile,
                tls_version=ssl.PROTOCOL_TLS_CLIENT
            )
        else:
            client.tls_set(
                ca_certs=ca_certs,
                tls_version=ssl.PROTOCOL_TLS_CLIENT
            )

        client.connect(BROKER, PORT, keepalive=10)
        client.loop_start()
        time.sleep(2)
        client.loop_stop()
        client.disconnect()

        if connected:
            return True, None
        else:
            return False, "Connection refused by broker (rc != 0)"

    except ssl.SSLError as e:
        return False, f"[SSL] {e}"
    except Exception as e:
        return False, str(e)


def generate_wrong_ca_cert():
    """Generate a brand new CA and sign a client cert with it — unknown to the broker."""
    # New rogue CA key
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    ca_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Rogue CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Rogue Org"),
    ])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256(), default_backend())
    )

    # Client cert signed by rogue CA
    client_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    client_cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "rogue-device")]))
        .issuer_name(ca_name)
        .public_key(client_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .sign(ca_key, hashes.SHA256(), default_backend())
    )

    # Write to temp files
    tmp_dir = tempfile.mkdtemp()
    ca_path = os.path.join(tmp_dir, "rogue-ca.pem")
    cert_path = os.path.join(tmp_dir, "rogue-client.pem")
    key_path = os.path.join(tmp_dir, "rogue-client-key.pem")

    with open(ca_path, "wb") as f:
        f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
    with open(cert_path, "wb") as f:
        f.write(client_cert.public_bytes(serialization.Encoding.PEM))
    with open(key_path, "wb") as f:
        f.write(client_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()
        ))

    return ca_path, cert_path, key_path


def generate_expired_cert():
    """Generate a cert signed by the real CA but with expiry in the past."""
    with open(CA_CERT, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    with open(CA_KEY, "rb") as f:
        ca_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

    client_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    expired_cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "expired-device")]))
        .issuer_name(ca_cert.subject)
        .public_key(client_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=730))
        .not_valid_after(datetime.datetime.utcnow() - datetime.timedelta(days=365))  # expired 1 year ago
        .sign(ca_key, hashes.SHA256(), default_backend())
    )

    tmp_dir = tempfile.mkdtemp()
    cert_path = os.path.join(tmp_dir, "expired-client.pem")
    key_path = os.path.join(tmp_dir, "expired-client-key.pem")

    with open(cert_path, "wb") as f:
        f.write(expired_cert.public_bytes(serialization.Encoding.PEM))
    with open(key_path, "wb") as f:
        f.write(client_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()
        ))

    return cert_path, key_path


def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(success, error):
    if success:
        print("  Result:  ✓ CONNECTED")
        print("  Status:  SUCCESS — legitimate device accepted")
    else:
        print("  Result:  ✗ REJECTED")
        print(f"  Error:   {error}")


# ── Scenario A ───────────────────────────────────────────────
def test_correct():
    print_header("Scenario A: Correct Client Certificate")
    print("  Device:  HYDROLOGIC-MainBuilding-001")
    print("  Cert:    certs/device-001.pem (valid, signed by our CA)")
    print("  Expect:  CONNECTION ACCEPTED\n")

    success, error = try_connect(CA_CERT, CLIENT_CERT, CLIENT_KEY, label="correct")
    print_result(success, error)

    print("\n  Explanation:")
    print("  The device presents a certificate signed by the trusted CA.")
    print("  The broker verifies the chain and grants access.")


# ── Scenario B ───────────────────────────────────────────────
def test_no_cert():
    print_header("Scenario B: No Client Certificate")
    print("  Device:  rogue-device (no certificate)")
    print("  Cert:    None — only CA cert provided")
    print("  Expect:  CONNECTION REJECTED\n")

    success, error = try_connect(CA_CERT, certfile=None, keyfile=None, label="nocert")
    print_result(success, error)

    print("\n  Explanation:")
    print("  require_certificate true means the broker demands a client cert.")
    print("  The TLS handshake fails before the connection is even established.")
    print("  Network access alone is not enough.")


# ── Scenario C ───────────────────────────────────────────────
def test_wrong_ca():
    print_header("Scenario C: Certificate from Wrong CA")
    print("  Device:  rogue-device (cert signed by unknown CA)")
    print("  Cert:    Generated on-the-fly by a rogue CA")
    print("  Expect:  CONNECTION REJECTED\n")

    rogue_ca, rogue_cert, rogue_key = generate_wrong_ca_cert()

    # Client uses our real CA to verify server, but presents rogue client cert
    success, error = try_connect(CA_CERT, rogue_cert, rogue_key, label="wrongca")
    print_result(success, error)

    print("\n  Explanation:")
    print("  The broker only trusts certificates signed by certs/ca.pem.")
    print("  The rogue cert was signed by a different CA the broker has never seen.")
    print("  Unlike Scenario B (no cert), here a cert IS presented — but it fails")
    print("  chain verification. The broker rejects it as untrusted.")


# ── Scenario D ───────────────────────────────────────────────
def test_expired():
    print_header("Scenario D: Expired Certificate")
    print("  Device:  expired-device (cert expired 1 year ago)")
    print("  Cert:    Signed by real CA, but validity window is in the past")
    print("  Expect:  CONNECTION REJECTED\n")

    expired_cert, expired_key = generate_expired_cert()

    success, error = try_connect(CA_CERT, expired_cert, expired_key, label="expired")
    print_result(success, error)

    print("\n  Explanation:")
    print("  The cert IS signed by the trusted CA — the chain is valid.")
    print("  But TLS also checks the validity period (not_valid_after).")
    print("  An expired cert is rejected even if it was once legitimate.")
    print("  This matters for IoT: if certs never expire, a stolen cert")
    print("  from a decommissioned device remains valid forever.")


# ── Main ─────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="mTLS Identity Attack Simulator")
    parser.add_argument("--mode", required=True,
                        choices=["test-correct", "test-no-cert", "test-wrong-ca", "test-expired"],
                        help="Which scenario to run")
    args = parser.parse_args()

    if args.mode == "test-correct":
        test_correct()
    elif args.mode == "test-no-cert":
        test_no_cert()
    elif args.mode == "test-wrong-ca":
        test_wrong_ca()
    elif args.mode == "test-expired":
        test_expired()

    print("\n" + "=" * 60 + "\n")