from datetime import datetime
from encrypt import Encryption
from steg import embed, append_after_marker
from constants import JPEG_EOI, PNG_IEND
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class DataHider:
    """
    A class to handle the process of receiving data from a client and hiding it in a base media file.
    """

    def __init__(self, client_socket, db_manager, user_id):
        """
        Initializes the DataHider with necessary resources.
        
        """
        self.client_socket = client_socket
        self.db_manager = db_manager
        self.user_id = user_id
        self.encryptor = Encryption()

    def fetch_media_menu(self):
        """
        Retrieves the media menu from the database and sends it to the client.

        :return: The selected media item as a row (tuple), or None if there's no available media.
        """
        media_menu = self.db_manager.get_all_rows("media_menu")
        if not media_menu:
            self.encryptor.send_encrypted_message(self.client_socket, "No media options available.")
            return None

        menu_str = "\n".join([f"{item[0]}: {item[1] or item[2] or item[3]}" for item in media_menu])
        self.encryptor.send_encrypted_message(self.client_socket, menu_str)

        selected_id = self.encryptor.receive_encrypted_message(self.client_socket)
        return next(item for item in media_menu if str(item[0]) == selected_id)

    def receive_data_to_hide(self):
        """
        Receives the size and the actual binary data from the client.

        :return: The binary data sent by the client.
        """
        size = int(self.encryptor.receive_encrypted_message(self.client_socket))
        data = b''
        while len(data) < size:
            chunk = self.encryptor.receive_encrypted_message(self.client_socket, binary=True)
            if not chunk:
                break
            data += chunk
        return data

    def create_hidden_file(self, media_path, data_to_hide):
        """
        Combines the base media with the hidden data and saves it to a new file.

        :param media_path: The path to the base media file.
        :param data_to_hide: The binary data to hide.
        :return: The path to the output file.
        """
        ext = os.path.splitext(media_path)[1].lower()

        if ext in (".jpg", ".jpeg"):
            output_path = os.path.join(BASE_DIR, f"hidden_{self.user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg")
            print(f"[hide] {os.path.basename(media_path)} is JPEG -> using append-after-EOI")
            return append_after_marker(media_path, data_to_hide, output_path, JPEG_EOI)

        output_path = os.path.join(BASE_DIR, f"hidden_{self.user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
        try:
            result = embed(media_path, data_to_hide, output_path)
            print(f"[hide] {os.path.basename(media_path)} is PNG -> used real LSB embedding")
            return result
        except ValueError as e:
            print(f"[hide] {os.path.basename(media_path)} is PNG but LSB capacity too small ({e}) -> falling back to append-after-IEND")
            return append_after_marker(media_path, data_to_hide, output_path, PNG_IEND)

    def run(self):
        """
        The main method that orchestrates the hiding process.

        :return: Tuple with (media_id, media_type_id, output_path)
        """
        selected_media = self.fetch_media_menu()
        if not selected_media:
            return

        data_to_hide = self.receive_data_to_hide()

        media_path = selected_media[1]
        if not os.path.isabs(media_path):
            media_path = os.path.join(BASE_DIR, media_path)
        output_path = self.create_hidden_file(media_path, data_to_hide)

        self.db_manager.insert_decrypted_media(self.user_id, 1, os.path.basename(output_path))
        self.db_manager.increment_user_stats(self.user_id, actions=1, uploaded=1, with_hidden=1)

        self.encryptor.send_encrypted_message(self.client_socket, f"Data successfully hidden in {output_path}")
        return selected_media[0], 1, output_path