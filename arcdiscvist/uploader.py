import os
import subprocess
import json


class Uploader:
    """
    Uploads volumes to Glacier.
    """

    def __init__(self, volume_path, config):
        self.volume_path = volume_path
        self.config = config

    @property
    def encrypted_path(self):
        return self.volume_path + ".gpg"

    def encrypt(self):
        """
        Encrypts the volume.
        """
        # Check for encrypted version
        if os.path.isfile(self.encrypted_path):
            raise ValueError("Encrypted file is apparently already present")
        # Encrypt
        subprocess.check_output([
            "gpg",
            "--symmetric",
            "--batch",
            "--yes",
            "--passphrase",
            self.config['glacier']['passphrase'],
            "-o",
            self.encrypted_path,
            self.volume_path,
        ])

    def upload(self):
        """
        Uploads the volume. Returns the Glacier ID.
        """
        aws_output = subprocess.check_output([
            "aws",
            "glacier",
            "upload-archive",
            "--account-id", "-",
            "--vault-name", self.config['glacier']['vault'],
            "--archive-description", os.path.basename(self.encrypted_path),
            "--body", self.encrypted_path,
        ])
        os.unlink(self.encrypted_path)
        return json.loads(aws_output)['archiveId']
