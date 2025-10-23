"""API key encryption utilities using Fernet symmetric encryption"""
from cryptography.fernet import Fernet
import hashlib
import os
import logging

logger = logging.getLogger(__name__)


class KeyEncryption:
    """Handles encryption and decryption of API keys"""

    def __init__(self):
        encryption_key = os.getenv("API_KEY_ENCRYPTION_KEY")

        if not encryption_key:
            # Generate new encryption key on first run
            encryption_key = Fernet.generate_key().decode()
            logger.warning(
                f"⚠️ Generated new encryption key. Add to .env file:\n"
                f"API_KEY_ENCRYPTION_KEY={encryption_key}"
            )

        self.fernet = Fernet(encryption_key.encode())

    def encrypt(self, plain_key: str) -> str:
        """
        Encrypt an API key

        Args:
            plain_key: Plain text API key

        Returns:
            Encrypted key as string
        """
        return self.fernet.encrypt(plain_key.encode()).decode()

    def decrypt(self, encrypted_key: str) -> str:
        """
        Decrypt an API key

        Args:
            encrypted_key: Encrypted API key

        Returns:
            Plain text API key
        """
        return self.fernet.decrypt(encrypted_key.encode()).decode()

    @staticmethod
    def hash_key(plain_key: str) -> str:
        """
        Generate SHA256 hash of API key for lookup

        Args:
            plain_key: Plain text API key

        Returns:
            SHA256 hash as hex string
        """
        return hashlib.sha256(plain_key.encode()).hexdigest()
