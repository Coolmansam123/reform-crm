"""
One-shot: generate a VAPID keypair for the Phase 3 push-notifications feature.

Run once, copy the printed values into THREE environment configs:
  1. .env (local dev)
  2. Coolify -> field_rep app env vars
  3. Modal secret 'outreach-hub' env (so the Modal cron / hub can also send)

After updating env, redeploy hub + field_rep so the new keys take effect.

Usage:
    pip install cryptography
    python execution/generate_vapid_keys.py
"""
import base64
import sys

try:
    from cryptography.hazmat.primitives.asymmetric import ec
except ImportError:
    print("Missing 'cryptography'. Install with: pip install cryptography")
    sys.exit(1)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def main():
    private_key = ec.generate_private_key(ec.SECP256R1())
    priv_value = private_key.private_numbers().private_value
    priv_bytes = priv_value.to_bytes(32, "big")
    pub_numbers = private_key.public_key().public_numbers()
    pub_bytes = b"\x04" + pub_numbers.x.to_bytes(32, "big") + pub_numbers.y.to_bytes(32, "big")

    print("─" * 64)
    print("VAPID keypair (P-256, base64url, no padding)")
    print("─" * 64)
    print()
    print(f"VAPID_PUBLIC_KEY={b64url(pub_bytes)}")
    print(f"VAPID_PRIVATE_KEY={b64url(priv_bytes)}")
    print(f"VAPID_SUBJECT=mailto:techops@reformchiropractic.com")
    print()
    print("Copy the three lines above into:")
    print("  • .env (local)")
    print("  • Coolify env vars for the field_rep app")
    print("  • Modal secret used by the hub")
    print()
    print("Then redeploy both apps. Subscriptions made before the keypair")
    print("changes will be silently invalidated and will need to re-subscribe.")


if __name__ == "__main__":
    main()
