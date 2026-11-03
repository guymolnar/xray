"""
Fires a standard set of SQL-injection-shaped payloads at the LOGIN step
(both as username and as password) against the real running server, over
the real encrypted socket protocol - no shortcuts, no mocking.

For every payload we just log the server's plain response. Since nothing
here is a valid account, every single one should come back as an ordinary
auth failure ("no such user" for the username slot, "wrong password" for
the password slot) with no delay, no leaked data, and no crash. That's
what "bulletproof" looks like in practice: boring, identical error
messages no matter how hostile the input looks.

Usage: start the server (`python cyber_server.py`) first, then run this
in a second terminal:  python test_sqli_resistance.py
"""
import socket
import time
from encrypt import Encryption
from constants import IP, PORT

USERNAME_PAYLOADS = [
    "' OR '1'='1",
    "admin' -- ",
    "' OR 1=1#",
    "x' UNION SELECT 'a','b',1,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL -- ",
    "x' UNION SELECT username,password_hash,user_id,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL FROM users -- ",
    "guy' AND SUBSTRING(password_hash,1,1)='2",
    "' OR SLEEP(5) -- ",
    "'; DROP TABLE users; --",
    "'; DELETE FROM users; --",
    "guy\\'--",
]

PASSWORD_PAYLOADS = [
    "' OR '1'='1",
    "' OR 1=1 -- ",
    "x' UNION SELECT 1 -- ",
    "'; DROP TABLE users; --",
]


def try_login(enc, sock, username, password):
    enc.send_encrypted_message(sock, "LOGIN")
    enc.send_encrypted_message(sock, username)
    enc.send_encrypted_message(sock, password)
    return enc.receive_encrypted_message(sock)


def run():
    enc = Encryption()

    print("=== payload as USERNAME (password is a harmless fixed string) ===")
    for payload in USERNAME_PAYLOADS:
        s = socket.socket()
        s.connect((IP, PORT))
        t0 = time.time()
        resp = try_login(enc, s, payload, "irrelevant")
        elapsed = time.time() - t0
        flag = "OK (safe)" if resp.startswith("ERROR") and elapsed < 2 else "!!! CHECK THIS !!!"
        print(f"[{flag}] {elapsed:5.2f}s  username={payload!r:70}  -> {resp}")
        s.close()

    print("\n=== payload as PASSWORD (username is the real account 'guy') ===")
    for payload in PASSWORD_PAYLOADS:
        s = socket.socket()
        s.connect((IP, PORT))
        t0 = time.time()
        resp = try_login(enc, s, "guy", payload)
        elapsed = time.time() - t0
        flag = "OK (safe)" if resp == "ERROR: wrong password" and elapsed < 2 else "!!! CHECK THIS !!!"
        print(f"[{flag}] {elapsed:5.2f}s  password={payload!r:40}  -> {resp}")
        s.close()

    print("\nIf every line says OK (safe), no payload above changed the query's\n"
          "meaning, leaked another row, delayed the response, or dropped/deleted\n"
          "anything - i.e. the parameterized queries are holding.")


if __name__ == "__main__":
    run()
