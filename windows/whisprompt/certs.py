"""Self-signed CA + server certificate generation.

iOS Safari only allows microphone access in a secure context, so the PWA must
be served over HTTPS. We generate a local CA once, let the user install/trust
it on the iPhone (downloaded from the plain-HTTP helper page), and sign a
server cert covering the machine's current LAN IPs.
"""
import datetime
import ipaddress
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from .config import CERTS_DIR

CA_KEY = CERTS_DIR / "ca.key"
CA_CERT = CERTS_DIR / "ca.crt"
SERVER_KEY = CERTS_DIR / "server.key"
SERVER_CERT = CERTS_DIR / "server.crt"


def get_lan_ips() -> list[str]:
    """Return non-loopback IPv4 addresses, best (default-route) first."""
    ips: list[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no packet is actually sent
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    return ips or ["127.0.0.1"]


def _new_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _write_key(path: Path, key: rsa.RSAPrivateKey) -> None:
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )


def _load_key(path: Path) -> rsa.RSAPrivateKey:
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def _ensure_ca() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    if CA_KEY.exists() and CA_CERT.exists():
        return _load_key(CA_KEY), x509.load_pem_x509_certificate(CA_CERT.read_bytes())

    key = _new_key()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "WhisPrompt Local CA")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False, content_commitment=False,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=True, crl_sign=True,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    _write_key(CA_KEY, key)
    CA_CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return key, cert


def _cert_covers(cert: x509.Certificate, ips: list[str]) -> bool:
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        covered = {str(ip) for ip in san.get_values_for_type(x509.IPAddress)}
        now = datetime.datetime.now(datetime.timezone.utc)
        return set(ips) <= covered and cert.not_valid_after_utc > now + datetime.timedelta(days=7)
    except x509.ExtensionNotFound:
        return False


def ensure_certs() -> tuple[Path, Path]:
    """Return (server_cert, server_key) paths, regenerating if IPs changed."""
    CERTS_DIR.mkdir(parents=True, exist_ok=True)
    ca_key, ca_cert = _ensure_ca()
    ips = get_lan_ips()

    if SERVER_KEY.exists() and SERVER_CERT.exists():
        existing = x509.load_pem_x509_certificate(SERVER_CERT.read_bytes())
        if _cert_covers(existing, ips):
            return SERVER_CERT, SERVER_KEY

    key = _new_key()
    san_entries: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.DNSName(socket.gethostname()),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
    ]
    san_entries += [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips]

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "WhisPrompt Server")]))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=820))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False
        )
        .sign(ca_key, hashes.SHA256())
    )
    _write_key(SERVER_KEY, key)
    SERVER_CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return SERVER_CERT, SERVER_KEY
