from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os
from typing import Tuple
import base64
from fastapi import HTTPException

class EncryptionManager:
    def __init__(self):
        # Get encryption key from environment variable
        self.encryption_key = os.getenv("ENCRYPTION_KEY")
        if not self.encryption_key:
            raise ValueError("ENCRYPTION_KEY environment variable not set")
        
        # Convert the key from base64 to bytes if it's stored as base64
        try:
            self.encryption_key = base64.b64decode(self.encryption_key)
        except:
            # If not base64, assume it's already in bytes format
            if isinstance(self.encryption_key, str):
                self.encryption_key = self.encryption_key.encode()
        
        # Ensure key is 32 bytes (256 bits) for AES-256
        if len(self.encryption_key) != 32:
            raise ValueError("Encryption key must be 32 bytes (256 bits)")

    def encrypt_data(self, data: bytes) -> Tuple[bytes, bytes, bytes]:
        """
        Encrypt data using AES-GCM.
        Returns (encrypted_data, iv, tag)
        """
        try:
            # Generate a random 12-byte IV
            iv = os.urandom(12)
            
            # Create AES-GCM cipher
            aesgcm = AESGCM(self.encryption_key)
            
            # Encrypt the data
            encrypted_data = aesgcm.encrypt(iv, data, None)
            
            # Split the result into ciphertext and tag
            # The last 16 bytes are the authentication tag
            ciphertext = encrypted_data[:-16]
            tag = encrypted_data[-16:]
            
            return ciphertext, iv, tag
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error encrypting data: {str(e)}"
            )

    def decrypt_data(self, encrypted_data: bytes, iv: bytes, tag: bytes) -> bytes:
        """
        Decrypt data using AES-GCM.
        """
        try:
            # Create AES-GCM cipher
            aesgcm = AESGCM(self.encryption_key)
            
            # Combine ciphertext and tag
            encrypted_data_with_tag = encrypted_data + tag
            
            # Decrypt the data
            decrypted_data = aesgcm.decrypt(iv, encrypted_data_with_tag, None)
            
            return decrypted_data
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error decrypting data: {str(e)}"
            )

# Create a singleton instance
encryption_manager = EncryptionManager() 