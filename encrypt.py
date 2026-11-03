import base64
from Crypto.Cipher import AES
from constants import CHUNK_SIZE
import hashlib, os


def hash_password(password, salt_hex=None):
    """Salted SHA-256. Returns 'saltHex$hashHex' - the same string is stored and used to compare."""
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.sha256(salt + password.encode()).hexdigest()
    return f"{salt.hex()}${digest}"

def verify_password(password, stored):
    """True when `password` reproduces the stored 'saltHex$hashHex' string."""
    salt_hex, _ = stored.split("$")
    return hash_password(password, salt_hex) == stored

def derive_user_id(username):
    """Stable numeric id from SHA-256(username); 7 hex chars stay inside signed INT."""
    return int(hashlib.sha256(username.encode()).hexdigest()[:7], 16)

class Encryption:
    """
    Class for managing encryption and decryption using AES
    
    Documentation: This class is responsible for encrypting and decrypting data using AES-GCM protocol.
    The class uses a fixed key and fixed nonce for simplicity.
    """

    def __init__(self):
        """
        Initialize the encryption class with predefined keys
        
        Documentation: Creates a new encryption object with predefined keys
        """
        key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "secret.key")
        with open(key_path, "rb") as f:
            self.AES_KEY = f.read()
        self.AES_NONCE = b'FixedNonce12'  # 12 bytes

    def encrypt_data(self, data: bytes) -> str:
        """
        Encrypts binary data using AES-GCM
        
        Documentation:
        This function receives binary data and encrypts it using AES-GCM.
        It appends the authentication tag to the ciphertext and returns a base64 encoded string.
        
        Args:
            data (bytes): The binary data to encrypt
            
        Returns:
            str: Base64 encoded encrypted data with authentication tag
        """
        cipher = AES.new(self.AES_KEY, AES.MODE_GCM, nonce=self.AES_NONCE)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        return base64.b64encode(ciphertext + tag).decode()

    def decrypt_data(self, data: str) -> bytes:
        """
        Decrypts a base64 encoded string of encrypted data
        
        Documentation:
        This function receives a base64 encoded string, decodes it, and decrypts using AES-GCM.
        It separates the ciphertext from the authentication tag and verifies the integrity.
        
        Args:
            data (str): Base64 encoded encrypted data with authentication tag
            
        Returns:
            bytes: Decrypted binary data
            
        Raises:
            ValueError: If the authentication tag verification fails
        """
        raw_data = base64.b64decode(data)
        cipher = AES.new(self.AES_KEY, AES.MODE_GCM, nonce=self.AES_NONCE)
        ciphertext, tag = raw_data[:-16], raw_data[-16:]
        return cipher.decrypt_and_verify(ciphertext, tag)

    def send_encrypted_message(self, sock, message):
        """
        Encrypts and sends a message through a socket
        
        Documentation:
        This function encrypts the given message and sends it through the provided socket.
        It first sends the length of the encrypted message as 4 bytes, then the encrypted message.
        
        Args:
            sock: Socket object to send data through
            message (str/bytes): Message to encrypt and send
        """
        if isinstance(message, str):
            message = message.encode()
        encrypted_message = self.encrypt_data(message)
        encrypted_bytes = encrypted_message.encode()
        sock.sendall(len(encrypted_bytes).to_bytes(4, byteorder='big'))  # Send message length (4 bytes)
        sock.sendall(encrypted_bytes)

    def receive_encrypted_message(self, sock, binary=False) -> str:
        """
        Receives and decrypts a message from a socket
        
        Documentation:
        This function receives an encrypted message from the provided socket,
        decrypts it, and returns the original message as a string.
        It first reads 4 bytes to determine the message length, then reads the encrypted message.
        
        Args:
            sock: Socket object to receive data from
            
        Returns:
            str: Decrypted message
            
        Returns empty string if no data is received
        """
        raw_length = sock.recv(4)
        if not raw_length:
            return ""
        message_length = int.from_bytes(raw_length, byteorder='big')
        data = b''
        while len(data) < message_length:
            chunk = sock.recv(min(CHUNK_SIZE, message_length - len(data)))
            if not chunk:
                break
            data += chunk
        decrypted = self.decrypt_data(data.decode())
        return decrypted if binary else decrypted.decode()
# Example usage:
# encryptor = Encryption()
# encryptor.send_encrypted_message(socket_object, "Hello, world!")
# received_message = encryptor.receive_encrypted_message(socket_object)