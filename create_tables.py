from db_manager import DatabaseManager
import os

def create_all_tables(db_manager):
    """
    Create all necessary tables for the application using DatabaseManager instance.

    Args:
        db_manager: An initialized DatabaseManager instance
    """
    # `users` holds both identity (username/password) and per-user stats.
    # There used to be a separate `clients` table for the stats side, but
    # every client is always exactly one authenticated user (1:1, joined on
    # user_id/client_id) - splitting that into two tables just meant an
    # extra JOIN for no benefit. No client_ip/client_port here either: a
    # client's *current* address only matters while it's actually
    # connected, and that already lives in Server.connected_clients (an
    # in-memory dict of ip/port/since per user_id) - persisting it to the
    # DB would only ever be stale the moment a client disconnects or the
    # server restarts.
    db_manager.create_table(
        "users",
        "(username VARCHAR(255) PRIMARY KEY, "
        "password_hash VARCHAR(100), "   # salted form: "<32-hex salt>$<64-hex sha256>" = 97 chars
        "user_id INT UNIQUE, "
        "last_seen DATETIME, "
        "ddos_status BOOLEAN DEFAULT FALSE, "
        "total_sent_media INT DEFAULT 0, "
        "total_files_uploaded INT DEFAULT 0, "
        "files_with_hidden_data INT DEFAULT 0, "
        "total_files_decoded INT DEFAULT 0)"
    )

    db_manager.create_table(
        "decrypted_media",
        "(user_id VARCHAR(255), media_type_id INT, path_to_decrypted_media VARCHAR(255))"
    )

    db_manager.create_table(
        "media_menu",
        "(id_media INT PRIMARY KEY, image_path VARCHAR(255), audio_path VARCHAR(255), video_path VARCHAR(255))"
    )

def ensure_users_schema(db_manager):
    """
    Bring the `users` table up to the current merged schema.

    Handles three states, all idempotent so this is safe to call on every
    startup regardless of which one applies:
      1. An already-merged `users` table that's just missing a newer
         column - added via ALTER TABLE.
      2. A database that still has a separate `clients` table (from an
         earlier version of this project) - its data is copied into the
         matching `users` row (client_id == user_id) and `clients` is
         dropped.
      3. Either table still carrying `client_ip`/`client_port` from an
         even older version that persisted the client's last known
         address - those columns are dropped outright and the data
         discarded. IP/port is only tracked for the duration of a live
         connection now, in Server.connected_clients; there's nothing to
         migrate it into.

    Args:
        db_manager: An initialized DatabaseManager instance
    """
    cursor = db_manager.conn.cursor()

    columns = {
        "last_seen": "DATETIME",
        "ddos_status": "BOOLEAN DEFAULT FALSE",
        "total_sent_media": "INT DEFAULT 0",
        "total_files_uploaded": "INT DEFAULT 0",
        "files_with_hidden_data": "INT DEFAULT 0",
        "total_files_decoded": "INT DEFAULT 0",
    }
    cursor.execute("SHOW COLUMNS FROM users")
    existing = {row[0] for row in cursor.fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
            print(f"users: added column {name}")
    db_manager.conn.commit()

    cursor.execute("SHOW TABLES LIKE 'clients'")
    if cursor.fetchone():
        cursor.execute(
            "SELECT client_id, last_seen, ddos_status, total_sent_media, "
            "total_files_uploaded, files_with_hidden_data, total_files_decoded "
            "FROM clients"
        )
        rows = cursor.fetchall()
        for (cid, last_seen, ddos, sent, uploaded, hidden, decoded) in rows:
            cursor.execute(
                "UPDATE users SET last_seen=%s, ddos_status=%s, total_sent_media=%s, "
                "total_files_uploaded=%s, files_with_hidden_data=%s, "
                "total_files_decoded=%s WHERE user_id=%s",
                (last_seen, ddos, sent, uploaded, hidden, decoded, cid)
            )
        db_manager.conn.commit()
        cursor.execute("DROP TABLE clients")
        db_manager.conn.commit()
        print(f"Migrated {len(rows)} row(s) from legacy `clients` table into `users` and dropped it.")

    for col in ("client_ip", "client_port"):
        if col in existing:
            cursor.execute(f"ALTER TABLE users DROP COLUMN {col}")
            print(f"users: dropped column {col} (IP/port is no longer persisted)")
    db_manager.conn.commit()

def populate_media_menu(db_manager):
    """
    Populate the media_menu table with predefined data if it's empty.

    Args:
        db_manager: An initialized DatabaseManager instance
    """
    predefined_media = [
        (1, "poke.jpg", None, None),
        (2, "logo_cyber.jpeg", None, None),
        (3, "mizperamon1.png", None, None),
    ]

    existing_rows = db_manager.get_all_rows("media_menu")
    if not existing_rows:
        for media in predefined_media:
            db_manager.insert_row(
                "media_menu",
                "(id_media, image_path, audio_path, video_path)",
                "(%s, %s, %s, %s)",
                media
            )
def repair_media_paths(db_manager):
    """Rewrite any absolute / machine-specific media path to a bare filename."""
    for id_media, img, aud, vid in db_manager.get_all_rows("media_menu"):
        for col, val in (("image_path", img), ("audio_path", aud), ("video_path", vid)):
            if val and (os.path.isabs(val) or ":" in val or val.startswith("\\\\")):
                db_manager.update_row("media_menu", "id_media", id_media,
                                      [col], [os.path.basename(val)])
