# Masker

A small steganography demo with a server and client.

## What it does
- hides data inside image files
- extracts hidden data from images
- uses AES-encrypted socket communication
- stores user/client data in MySQL

## Requirements
- Python 3
- MySQL running locally
- packages:
  - `mysql-connector-python`
  - `Pillow`
  - `pygame`
  - `pycryptodome`

## Setup
1. Make sure MySQL is running.
2. Check the DB credentials in `constants.py`.
3. Make sure these files exist in the project root:
   - `secret.key`
   - `poke.jpg`
   - `logo_cyber.jpeg`
   - `mizperamon1.png`
   - `tonystark.jpg`
   - `ACDC.mp3`
4. Install dependencies:

```bash
pip install mysql-connector-python Pillow pygame pycryptodome
```

## Run
Start the server:

```bash
python cyber_server.py
```

Then start the client in another terminal:

```bash
python cyber_client.py
```

## Notes
- This project is a prototype and assumes a local MySQL setup.
- The server uses a GUI and may require a desktop environment.
- The app expects the files and DB settings to match the code exactly.
