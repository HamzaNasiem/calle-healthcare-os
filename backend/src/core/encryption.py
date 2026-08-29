"""
Encryption Module (AES-256-GCM)
Implements Envelope Encryption for PHI fields.
For local dev, uses a static base64 key. For production, integrates with AWS KMS.
"""
import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.config.settings import settings


class PHIEncryptionService:
    def __init__(self):
        # In production, this would call KMS to get a Data Key
        # For local development, we use the static base64 key
        self._key = self._get_key()

    def _get_key(self) -> bytes:
        if settings.encryption_mode == "local":
            # Check ENCRYPTION_KEY env var first (primary), then local_kms_key_base64 (secondary)
            raw_key = settings.ENCRYPTION_KEY or settings.local_kms_key_base64
            if not raw_key:
                raise ValueError(
                    "ENCRYPTION_KEY environment variable must be set. "
                    "Generate one with: python -c \"import secrets,base64; print(base64.b64encode(secrets.token_bytes(32)).decode())\""
                )
            key = base64.b64decode(raw_key)
            if len(key) != 32:
                raise ValueError("ENCRYPTION_KEY must be exactly 32 bytes (256 bits) when base64-decoded for AES-256")
            return key

        elif settings.encryption_mode == "kms":
            if not settings.local_kms_key_base64:
                raise ValueError("LOCAL_KMS_KEY_BASE64 must contain the KMS-encrypted data key in kms mode")
            
            import boto3
            from botocore.exceptions import ClientError
            
            try:
                kms_client = boto3.client('kms')
                encrypted_key = base64.b64decode(settings.local_kms_key_base64)
                
                # If a CMK ARN is provided, we can optionally pass it, but KMS decrypts automatically based on ciphertext
                decrypt_kwargs = {'CiphertextBlob': encrypted_key}
                if settings.kms_cmk_arn:
                    decrypt_kwargs['KeyId'] = settings.kms_cmk_arn
                    
                response = kms_client.decrypt(**decrypt_kwargs)
                plaintext_key = response['Plaintext']
                
                if len(plaintext_key) != 32:
                    raise ValueError("Decrypted Data Key must be exactly 32 bytes (256 bits) for AES-256")
                return plaintext_key
            except ClientError as e:
                raise ValueError(f"AWS KMS Decryption failed: {str(e)}")
        else:
            raise ValueError(f"Invalid ENCRYPTION_MODE: {settings.encryption_mode}")

    def encrypt(self, plaintext: str | None) -> bytes | None:
        """
        Encrypts plaintext using AES-256-GCM.
        Returns bytes: nonce (12 bytes) + ciphertext + auth tag (16 bytes)
        """
        if plaintext is None:
            return None
        if not isinstance(plaintext, str):
            plaintext = str(plaintext)
        if plaintext == "":
            return b""

        aesgcm = AESGCM(self._key)
        nonce = os.urandom(12)  # 96-bit nonce recommended for GCM
        
        # encrypt() appends the 16-byte authentication tag to the ciphertext
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), associated_data=None)
        
        # Combine nonce and ciphertext
        combined = nonce + ciphertext
        return combined

    def decrypt(self, encrypted_bytes: bytes | None) -> str | None:
        """
        Decrypts bytes: nonce (12 bytes) + ciphertext + auth tag (16 bytes)
        Returns decrypted UTF-8 plaintext string.
        """
        if encrypted_bytes is None:
            return None
        if not isinstance(encrypted_bytes, (bytes, bytearray)):
            return None
        if len(encrypted_bytes) == 0:
            return ""
        if len(encrypted_bytes) < 28:  # 12-byte nonce + 16-byte authentication tag
            return None

        try:
            nonce = encrypted_bytes[:12]
            ciphertext = encrypted_bytes[12:]
            
            aesgcm = AESGCM(self._key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
            
            return plaintext.decode('utf-8')
        except Exception:
            # HIPAA: Never log or leak raw ciphertext or crypto traces
            raise ValueError("Decryption failed: cryptographic validation or key mismatch") from None

# Singleton instance
phi_crypto = PHIEncryptionService()
