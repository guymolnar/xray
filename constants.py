# constants.py
# This file contains constants used across the application.

CHUNK_SIZE = 4096
IP = "127.0.0.1"
PORT = 9921
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "mysql",
    "database": "mysql"
}

JPEG_EOI = b'\xFF\xD9' 
PNG_IEND = b'\x49\x45\x4E\x44\xAE\x42\x60\x82' 
MAX_SESSIONS_PER_USER = 3