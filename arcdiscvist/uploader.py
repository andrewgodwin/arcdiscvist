import json
import os
import subprocess


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
        subprocess.check_output(
            [
                "gpg",
                "--symmetric",
                "--batch",
                "--yes",
                "--passphrase",
                self.config["s3"]["passphrase"],
                "-o",
                self.encrypted_path,
                self.volume_path,
            ]
        )

    def upload(self):
        """
        Uploads the volume. Returns the Glacier ID.
        """
        subprocess.check_call(
            [
                "aws",
                "s3",
                "cp",
                "--storage-class",
                "DEEP_ARCHIVE",
                self.encrypted_path,
                "s3://%s/%s"
                % (self.config["s3"]["bucket"], os.path.basename(self.encrypted_path)),
            ]
        )
        os.unlink(self.encrypted_path)
        return "%s/%s" % (
            self.config["s3"]["bucket"],
            os.path.basename(self.encrypted_path),
        )
