import base64
import hashlib

SECRET_KEY = b"FlightTracker_RPi_SecretKey_2026"

def encrypt_password(plain_text: str) -> str:
    """Encrypts a password string using SHA-256 XOR stream cipher with Base64 prefix."""
    if not plain_text:
        return ""
    key = hashlib.sha256(SECRET_KEY).digest()
    data = plain_text.encode("utf-8")
    cipher_bytes = bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
    return "enc:" + base64.b64encode(cipher_bytes).decode("utf-8")


def decrypt_password(cipher_text: str) -> str:
    """Decrypts an encrypted password string, falling back to plaintext for backward compatibility."""
    if not cipher_text:
        return ""
    if not cipher_text.startswith("enc:"):
        # Backwards compatibility for unencrypted plain text passwords
        return cipher_text
    try:
        raw_b64 = cipher_text[4:]
        cipher_bytes = base64.b64decode(raw_b64.encode("utf-8"))
        key = hashlib.sha256(SECRET_KEY).digest()
        plain_bytes = bytes([b ^ key[i % len(key)] for i, b in enumerate(cipher_bytes)])
        return plain_bytes.decode("utf-8")
    except Exception as e:
        print(f"[Security] Decryption error: {e}")
        return cipher_text
