"""Ensure a self-signed TLS cert for LAN HTTPS (camera / getUserMedia)."""

from __future__ import annotations

import argparse
import ipaddress
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _lan_ipv4_addresses() -> list[str]:
    addresses: list[str] = ["127.0.0.1"]
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip and ip not in addresses and not ip.startswith("127."):
                addresses.append(ip)
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and ip not in addresses:
                addresses.append(ip)
    except OSError:
        pass
    return addresses


def ensure_lan_tls(cert_dir: Path) -> tuple[Path, Path]:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError as exc:
        raise SystemExit(
            "LAN HTTPS requires the 'cryptography' package. "
            "Install with: pip install cryptography"
        ) from exc

    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / "cert.pem"
    key_path = cert_dir / "key.pem"
    if cert_path.is_file() and key_path.is_file():
        return cert_path, key_path

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "MTG Collection LAN"),
    ])
    san_names: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
    ]
    for ip_text in _lan_ipv4_addresses():
        try:
            san_names.append(x509.IPAddress(ipaddress.ip_address(ip_text)))
        except ValueError:
            continue

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(san_names), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "lan_tls",
    )
    args = parser.parse_args()
    cert_path, key_path = ensure_lan_tls(args.dir)
    print(cert_path)
    print(key_path)


if __name__ == "__main__":
    main()
