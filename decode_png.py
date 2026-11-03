import os
from datetime import datetime
from encrypt import Encryption
from steg import extract, extract_after_marker
from constants import JPEG_EOI, PNG_IEND
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class ImageExtractor:
    """
    A class responsible for receiving a media file from the client,
    extracting hidden JPEG images from it, saving them, and sending them back.
    """

    def __init__(self, client_socket, db_manager, user_id):
        """
        Initializes the extractor with the client's socket, DB manager, and user ID.
        
        """
        self.client_socket = client_socket
        self.db_manager = db_manager
        self.user_id = user_id
        self.found_images = []
        self.encryptor = Encryption()

    def receive_media(self):
        """
        Receives the media file size (encrypted) and raw binary media data from the client.

        :return: binary data of the received media file
        """
        media_size = int(self.encryptor.receive_encrypted_message(self.client_socket))
        media_data = b''

        while len(media_data) < media_size:
            chunk = self.encryptor.receive_encrypted_message(self.client_socket, binary=True)
            if not chunk:
                break
            media_data += chunk

        return media_data

    def save_temp_file(self, data):
        """
        Saves the received media data to a temporary file.

        :param data: binary media data
        :return: path to the temporary file
        """
        temp_path = os.path.join(BASE_DIR, f"temp_{self.user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg")        
        with open(temp_path, "wb") as temp_file:
            temp_file.write(data)
        return temp_path

    def extract_payload(self, stego_path):
        """
        Runs LSB extraction on the received stego image and, if a payload was
        found, writes it to disk and records it in `decrypted_media`.
        """
        with open(stego_path, "rb") as f:
            head = f.read(8)
        is_jpeg = head[:2] == b'\xFF\xD8'

        if is_jpeg:
            payload = extract_after_marker(stego_path, JPEG_EOI)
            print(f"[decode] JPEG stego file ({'found' if payload else 'nothing found'})")
        else:
            payload = extract(stego_path)
            if payload is not None:
                print("[decode] PNG stego file  recovered via real LSB extraction")
            else:
                payload = extract_after_marker(stego_path, PNG_IEND)
                print(f"[decode] PNG stego file no LSB payload")

        if payload is None:
            return

        ext = ".jpg" if is_jpeg else ".png"
        output_file = os.path.join(BASE_DIR, f"hidden_{self.user_id}_1_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}")
        with open(output_file, "wb") as out:
            out.write(payload)

        self.found_images.append(output_file)
        self.db_manager.insert_decrypted_media(self.user_id, 1, os.path.basename(output_file))

    def send_results(self):
        """
        Sends the number of found images to the client,
        then sends each image size (encrypted), waits for "ACK", and sends the image file.
        """
        self.encryptor.send_encrypted_message(self.client_socket, f"{len(self.found_images)}")

        for image_path in self.found_images:
            with open(image_path, "rb") as file:
                data = file.read()
                self.encryptor.send_encrypted_message(self.client_socket, f"{len(data)}")
                ack = self.encryptor.receive_encrypted_message(self.client_socket)
                if ack != "ACK":
                    break
                self.encryptor.send_encrypted_message(self.client_socket, data)

    def run(self):
        """
        Executes the full flow: receive, extract, send back hidden images.

        :return: (media_type_id, media_type, first_output_path) tuple
        """
        media_data = self.receive_media()
        temp_path = self.save_temp_file(media_data)
        self.extract_payload(temp_path)
        self.send_results()
        os.remove(temp_path)

        found = len(self.found_images)
        self.db_manager.increment_user_stats(
            self.user_id, actions=1, uploaded=1, with_hidden=1 if found else 0, decoded=1
        )

        if self.found_images:
            return 1, "image", self.found_images[0]
        else:
            return 0, "image", ""