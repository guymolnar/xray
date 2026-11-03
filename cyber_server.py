import hashlib
import socket
import threading
import tkinter as tk
from tkinter import Label, scrolledtext, Toplevel, Listbox, Button
from constants import IP, PORT, MAX_SESSIONS_PER_USER
from db_manager import DatabaseManager
from create_tables import create_all_tables, populate_media_menu, ensure_users_schema, repair_media_paths
from hide_png import DataHider
from decode_png import ImageExtractor
from datetime import datetime
from PIL import Image, ImageTk
import os
import pygame
import time
from encrypt import Encryption, hash_password, verify_password, derive_user_id 

# so paths keep working after the project is copied to another machine.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Server:
    def __init__(self):
        # Initialize database connection
        self.db_manager = DatabaseManager("localhost", "root", "mysql", "mysql")
        create_all_tables(self.db_manager)
        ensure_users_schema(self.db_manager)
        repair_media_paths(self.db_manager)
        populate_media_menu(self.db_manager)
        
        # Initialize encryption
        self.encryptor = Encryption()
        
        # Initialize GUI components
        self.root = tk.Tk()
        self.root.withdraw()
        self.log_text = None
        self.client_listbox = None
        self.status_label = None
        self.bg_image = None
        self._clients_lock = threading.Lock() 
        self.client_details_images = {}
        self.connected_clients = {} #a dict for connected clients, key is client_id, value is a dict with ip, port, and since

    def play_audio(self):
        pygame.mixer.init()
        pygame.mixer.music.load(os.path.join(BASE_DIR, "ACDC.mp3"))
        pygame.mixer.music.play()

    def update_gui_log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.yview(tk.END)

    def update_client_list(self):
        """
        Redraw the client table: every user from `users`, tagged
        ONLINE/offline against self.connected_clients, with upload stats.
        `users` row layout: username, password_hash, user_id, last_seen,
        ddos_status, total_sent_media, total_files_uploaded,
        files_with_hidden_data, total_files_decoded.
        """
        if not self.client_listbox:
            return

        self.client_listbox.delete(0, tk.END)

        all_users = self.db_manager.get_all_rows("users")
        with self._clients_lock:
            online_ids = {str(cid) for cid in self.connected_clients}

        if self.status_label:
            self.status_label.config(
                text=f"Connected now: {len(online_ids)}    Total clients: {len(all_users)}"
            )

        if not all_users:
            self.client_listbox.insert(tk.END, "-- No clients registered --")
            return

        header = f"{'ID':<12}{'USER':<15}{'STATUS':<10}{'UPLOADED':<10}{'W/HIDDEN':<10}{'DECODED':<9}LAST SEEN"
        self.client_listbox.insert(tk.END, header)
        self.client_listbox.insert(tk.END, "-" * len(header))

        for row in all_users:
            username = row[0]
            client_id = row[2]
            last_seen = row[3]
            total_files_uploaded = row[6] or 0
            files_with_hidden_data = row[7] or 0
            total_decoded = row[8] or 0
            status = "ONLINE" if str(client_id) in online_ids else "offline"
            self.client_listbox.insert(
                tk.END,
                f"{str(client_id):<12}{str(username):<15}{status:<10}"
                f"{total_files_uploaded:<10}{files_with_hidden_data:<10}{total_decoded:<9}{last_seen}"
            )

    def _poll_client_list(self):
        """Refresh the client table on a timer so the counters stay live."""
        self.update_client_list()
        self.root.after(2000, self._poll_client_list)   

    def show_client_details(self, client_id):
        client_data = self.db_manager.get_rows_with_value("users", "user_id", client_id)
        if not client_data:
            return
        client = client_data[0]

        details_window = Toplevel()
        details_window.title(f"Client {client_id} Details")
        details_window.geometry("400x400")

        # Create and store image reference in the window itself to prevent garbage collection
        bg_image = ImageTk.PhotoImage(Image.open(os.path.join(BASE_DIR, "logo_cyber.jpeg")))
        bg_label = Label(details_window, image=bg_image)
        bg_label.image = bg_image  # Keep a reference to prevent garbage collection
        bg_label.place(relwidth=1, relheight=1)

        with self._clients_lock:
            sessions = self.connected_clients.get(client[2], [])
        online = bool(sessions)

        details = [
            f"Username: {client[0]}",
            f"ID: {client[2]}",
            f"Last Seen: {client[3]}",
            f"Total Actions: {client[5]}",
            f"Files Uploaded: {client[6]}",
            f"Files With Hidden Data: {client[7]}",
            f"Files Decoded: {client[8]}",
            f"Connection: {'CONNECTED NOW' if online else 'OFFLINE'}",
        ]

        if online:
            # IP/port aren't persisted (see create_tables.py), but while a
            # session is actually live its address is right here in memory.
            details.append(f"Active sessions: {len(sessions)}/{MAX_SESSIONS_PER_USER}")
            details.append(f"Oldest session since: {min(s['since'] for s in sessions)}")
            for i, s in enumerate(sessions, start=1):
                details.append(f"  session {i}: {s['ip']}:{s['port']} since {s['since']}")

        for detail in details:
            lbl = Label(details_window, text=detail, fg='white', bg='black')
            lbl.pack(anchor="w", padx=10, pady=2)

        history_button = Button(details_window, text="History", command=lambda: self.show_client_history(client_id), bg='gray', fg='white')
        history_button.pack(pady=10)

    def show_client_history(self, client_id):
        history_window = Toplevel()
        history_window.title(f"Client {client_id} - History")
        history_window.geometry("600x400")

        # Create and store image reference in the window itself
        bg_image = ImageTk.PhotoImage(Image.open(os.path.join(BASE_DIR, "logo_cyber.jpeg")))
        bg_label = Label(history_window, image=bg_image)
        bg_label.image = bg_image  # Keep a reference to prevent garbage collection
        bg_label.place(relwidth=1, relheight=1)

        history_label = Label(history_window, text=f"Client {client_id} Image History", font=("Arial", 12, "bold"), fg="white", bg="black")
        history_label.pack(pady=5)

        image_listbox = Listbox(history_window, height=15, width=80, bg="black", fg="white", selectbackground="gray")
        image_listbox.pack(padx=10, pady=5, expand=True, fill="both")

        images = self.db_manager.get_rows_with_value("decrypted_media", "user_id", client_id)

        if not images:
            image_listbox.insert(tk.END, "No images found for this client.")
        else:
            image_paths = [img[2] for img in images]
            for path in image_paths:
                image_listbox.insert(tk.END, path)

            def open_selected_image(event):
                selected_index = image_listbox.curselection()
                if selected_index:
                    selected_path = image_paths[selected_index[0]]
                    if not os.path.isabs(selected_path):
                        selected_path = os.path.join(BASE_DIR, selected_path)
                    os.system(f'"{selected_path}"')

            image_listbox.bind("<Double-Button-1>", open_selected_image)

    def handle_client(self, client_socket):
        client_id = 'unknown'
        my_session = None
        client_ip, client_port = client_socket.getpeername()

        try:
            authenticated = False
            while not authenticated:
                action   = self.encryptor.receive_encrypted_message(client_socket)
                username = self.encryptor.receive_encrypted_message(client_socket)
                password = self.encryptor.receive_encrypted_message(client_socket)

                existing = self.db_manager.get_rows_with_value("users", "username", username)

                if action == "REGISTER":
                    if existing:
                        self.encryptor.send_encrypted_message(client_socket, "ERROR: user already exists")
                    else:
                        self.db_manager.insert_row(
                            "users", "(username, password_hash, user_id)", "(%s, %s, %s)",
                            (username, hash_password(password), derive_user_id(username))
                        )
                        self.encryptor.send_encrypted_message(client_socket, "OK REGISTERED (now log in)")
                    # stay in the loop - the user still has to LOGIN

                elif action == "LOGIN":
                    if not existing:
                        self.encryptor.send_encrypted_message(client_socket, "ERROR: no such user, register first")
                    elif not verify_password(password, existing[0][1]):
                        self.encryptor.send_encrypted_message(client_socket, "ERROR: wrong password")
                    else:
                        uid = existing[0][2]
                        with self._clients_lock:
                            over_limit = len(self.connected_clients.get(uid, [])) >= MAX_SESSIONS_PER_USER
                            if not over_limit:
                                my_session = {"ip": client_ip, "port": client_port, "since": datetime.now()}
                                self.connected_clients.setdefault(uid, []).append(my_session)
                        if over_limit:
                            self.encryptor.send_encrypted_message(client_socket, f"ERROR: this account already has {MAX_SESSIONS_PER_USER} active sessions")
                        else:
                            self.encryptor.send_encrypted_message(client_socket, "OK LOGIN")
                            client_id = uid
                            authenticated = True

                else:
                    self.encryptor.send_encrypted_message(client_socket, "ERROR: unknown action")

            row = self.db_manager.get_rows_with_value("users", "user_id", client_id)[0]

            self.db_manager.update_row("users", "user_id", client_id, ["last_seen"], [datetime.now()])
            if row[3] is None:
                self.encryptor.send_encrypted_message(client_socket, "WELCOME TO MASKER SERVER!")
                client_status = "NEW"
            else:
                self.encryptor.send_encrypted_message(client_socket, "WELCOME BACK")
                client_status = "EXISTING"

            
            self.update_gui_log(f"Client {client_id} connected - Status: {client_status}")
            self.update_client_list()

            while True:
                self.encryptor.send_encrypted_message(client_socket, "\n1: Hide Data\n2: Decode Data\n3: Logout")
                option = self.encryptor.receive_encrypted_message(client_socket)

                if option == "1":
                    hider = DataHider(client_socket, self.db_manager, client_id)
                    result = hider.run()
                elif option == "2":
                    extractor = ImageExtractor(client_socket, self.db_manager, client_id)
                    media_id, media_type, path = extractor.run()
                elif option == "3":
                    self.update_gui_log(f"Client {client_id} disconnected.")
                    break
                else:
                    self.encryptor.send_encrypted_message(client_socket, "Invalid option.")
        except Exception as e:
            self.update_gui_log(f"Error handling client {client_id}: {e}")
        finally:
            with self._clients_lock:
                sessions = self.connected_clients.get(client_id)
                if sessions and my_session in sessions:
                    sessions.remove(my_session)
                    if not sessions:
                        del self.connected_clients[client_id]

            client_socket.close()
            self.update_client_list()

    def start_server(self):
        server_socket = socket.socket()
        server_socket.bind((IP, PORT))
        server_socket.listen()
        self.update_gui_log("Server started...")
        while True:
            client_socket, _ = server_socket.accept()
            threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()

    def create_gui(self):
        self.play_audio()
        
        # Create splash screen
        splash = Toplevel()
        splash.geometry("400x400")
        splash.overrideredirect(True)
        splash.update_idletasks()
        x = (splash.winfo_screenwidth()  - 400) // 2
        y = (splash.winfo_screenheight() - 400) // 2
        splash.geometry(f"400x400+{x}+{y}")

        logo = Image.open(os.path.join(BASE_DIR, "tonystark.jpg")).resize((400, 400))
        logo_photo = ImageTk.PhotoImage(logo)
        label = Label(splash, image=logo_photo)
        label.image = logo_photo  # keep reference
        label.place(x=0, y=0, relwidth=1, relheight=1)

        Label(splash, text="MASKER 2.0", font=("Consolas", 30, "bold"),
              fg="#4fd1c5", bg="black").place(relx=0.5, rely=0.10, anchor="center")
        Label(splash, text="Guy Molnar", font=("Segoe UI", 13),
              fg="white", bg="black").place(relx=0.5, rely=0.21, anchor="center")

        splash.update()
        time.sleep(3)
        splash.destroy()

        # Destroy the initial withdrawn root and create a new one
        self.root.destroy()
        self.root = tk.Tk()
        self.root.title("Server GUI")
        self.root.geometry("500x500")

        # Load and keep reference to background image
        self.bg_image = ImageTk.PhotoImage(Image.open(os.path.join(BASE_DIR, "tonystark.jpg")))
        bg_label = Label(self.root, image=self.bg_image)
        bg_label.place(relwidth=1, relheight=1)

        # Create scrolled text for logs
        self.log_text = scrolledtext.ScrolledText(self.root, state=tk.DISABLED, wrap=tk.WORD, height=10, bg='black', fg='white')
        self.log_text.pack(expand=True, fill='both', padx=10, pady=5)

        # Create clients label
        Label(self.root, text="MASKER Customers", font=("Arial", 14, "bold"), fg="white", bg="black").pack(pady=5)
        self.status_label = Label(self.root, text="", font=("Arial", 10), fg="white", bg="black")
        self.status_label.pack(pady=2)
        # Create client listbox
        self.client_listbox = Listbox(self.root, bg='black', fg='white')
        self.client_listbox.pack(expand=True, fill='both', padx=10, pady=5)
        self.client_listbox.bind("<Double-Button-1>", lambda e: self._open_selected_client())
        # Start server in a separate thread
        threading.Thread(target=self.start_server, daemon=True).start()
        self._poll_client_list()
        self.root.mainloop()

    def _open_selected_client(self): #double clicking an empty row crashes so we check
        sel = self.client_listbox.curselection()
        if not sel:
            return
        text = self.client_listbox.get(sel[0]).strip()
        first_token = text.split()[0] if text else ""
        if not first_token.isdigit():   # header row, divider, or the "no clients" line
            return
        self.show_client_details(first_token)
        
if __name__ == "__main__":
    server = Server()
    server.create_gui()