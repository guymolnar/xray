import socket
import os
import random
from PIL import Image
from constants import IP, PORT, CHUNK_SIZE
from encrypt import Encryption

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Client:
    def __init__(self):
        self.decrypted_list_paths = [

        ]
        self.usual_images = [
            os.path.join(BASE_DIR, "poke.jpg"),
            os.path.join(BASE_DIR, "logo_cyber.jpeg"),
            os.path.join(BASE_DIR, "mizperamon1.png")
        ]
        self.client_socket = None
        self.encryptor = Encryption()

    def connect_to_server(self):
        try:
            self.client_socket = socket.socket()
            self.client_socket.connect((IP, PORT))
            print("Connected to server")
        except Exception as e:
            print(f"Error connecting to server: {e}")
            self.client_socket = None


    def authenticate(self):
        while True:
            print("\n1: Register\n2: Login")
            choice = input("Choose: ").strip()
            username = input("Username: ").strip()
            password = input("Password: ").strip()

            action = "REGISTER" if choice == "1" else "LOGIN" if choice == "2" else None
            if not action:
                print("Invalid choice.")
                continue

            self.encryptor.send_encrypted_message(self.client_socket, action)
            self.encryptor.send_encrypted_message(self.client_socket, username)
            self.encryptor.send_encrypted_message(self.client_socket, password)

            response = self.encryptor.receive_encrypted_message(self.client_socket)
            print(response)

            if response.startswith("OK LOGIN"):
                welcome = self.encryptor.receive_encrypted_message(self.client_socket)
                print(welcome)
                return True


    def receive_menu(self):
        try:
            menu = self.encryptor.receive_encrypted_message(self.client_socket)
            print("\nOptions from server:\n")
            print(menu)
            return menu
        except Exception as e:
            print(f"Error receiving menu: {e}")
            return None

    def handle_hide_option(self):
        print("\nYou chose to hide data.")
        
        # Receive media menu
        media_menu = self.encryptor.receive_encrypted_message(self.client_socket)
        if "No media options available." in media_menu:
            print("No media options available to hide data. Returning to menu.")
            return

        print("\nAvailable media to hide data in:\n")
        print(media_menu)

        # Select media and inform server
        selected_media_id = input("Choose a media id to hide data in: ").strip()
        self.encryptor.send_encrypted_message(self.client_socket, selected_media_id)

        # The server is now blocked waiting for us to send a size + the file
        # (DataHider.run() already started on its side), so from here on we
        # must not return without sending something - retry locally instead
        # of bailing out, or the server hangs forever waiting for data.
        print("\nFiles you can hide:")
        for i, path in enumerate(self.usual_images, start=1):
            print(f"{i}: {path}")
        while True:
            choice = input("Choose a file to hide (number): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(self.usual_images):
                data_to_hide_path = self.usual_images[int(choice) - 1]
                break
            print("Invalid choice, try again.")
        print("Data to hide:", data_to_hide_path)


        if not os.path.exists(data_to_hide_path):
            print("File to hide does not exist. Returning to menu.")
            return

        # Read binary file content
        with open(data_to_hide_path, "rb") as file:
            data_to_hide = file.read()

        # Send file size (encrypted)
        self.encryptor.send_encrypted_message(self.client_socket, str(len(data_to_hide)))

        # Send file content (raw, encrypted now)
        self.encryptor.send_encrypted_message(self.client_socket, data_to_hide)

        # Receive server response (encrypted)
        response = self.encryptor.receive_encrypted_message(self.client_socket)
        print(response)

        hidden_media_path = response.split("in ")[-1].strip()
        if os.path.exists(hidden_media_path):
            self.decrypted_list_paths.append(hidden_media_path)
            try:
                img = Image.open(hidden_media_path)
                img.show()
            except Exception as e:
                print(f"Error opening the hidden media: {e}")

    def handle_decode_option(self):
        # By the time we get here the server has already dispatched into
        # ImageExtractor.run() (option "2" was sent in run() before this was
        # called) and is blocked waiting for a size + the file. So just like
        # handle_hide_option, we must not return here without sending
        # something - retry locally instead of bailing out on a bad number.
        print("\nFiles you can try to decode:")
        for i, path in enumerate(self.decrypted_list_paths, start=1):
            print(f"{i}: {path}")

        while True:
            choice = input("Choose a file to decode (number): ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(self.decrypted_list_paths):
                media_path = self.decrypted_list_paths[int(choice) - 1]
                break
            print("Invalid choice, try again.")
        print("File chosen:", media_path)

        if not os.path.exists(media_path):
            print("File does not exist. Returning to menu.")
            return

        with open(media_path, "rb") as file:
            data = file.read()

        # Send length encrypted
        self.encryptor.send_encrypted_message(self.client_socket, str(len(data)))

        # Send raw binary data (encrypted)
        self.encryptor.send_encrypted_message(self.client_socket, data)

        # Receive results
        num_images = int(self.encryptor.receive_encrypted_message(self.client_socket))
        print(f"Found {num_images} hidden images.")

        for i in range(num_images):
            image_size = int(self.encryptor.receive_encrypted_message(self.client_socket))
            self.encryptor.send_encrypted_message(self.client_socket, "ACK")

            image_data = b''
            while len(image_data) < image_size:
                image_data += self.encryptor.receive_encrypted_message(self.client_socket, binary=True)

            decoded_file_path = f"decoded_image_{i + 1}.jpg"
            with open(decoded_file_path, "wb") as file:
                file.write(image_data)

            print(f"Decoded image saved at {decoded_file_path}")
            if os.path.exists(decoded_file_path):
                try:
                    img = Image.open(decoded_file_path)
                    img.show()
                except Exception as e:
                    print(f"Error opening the decoded image: {e}")

    def run(self):
        self.connect_to_server()
        if not self.client_socket:
            return

        if not self.authenticate():  
            return

        while True:
            menu = self.receive_menu()
            if not menu:
                break
            
            while True:
                option = input("Choose an option (1, 2, or 3): ")
                if option == "2" and not self.decrypted_list_paths:
                    print("Nothing to decode yet - hide a file first.")
                    continue
                break

            print("Chosen option:", option)
            self.encryptor.send_encrypted_message(self.client_socket, option)

            if option == "1":
                self.handle_hide_option()
            elif option == "2":
                self.handle_decode_option()
            elif option == "3":
                print("Logging out...")
                break
            else:
                print("Invalid option chosen.")

        self.client_socket.close()

if __name__ == "__main__":
    client = Client()
    client.run()