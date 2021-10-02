import json
import logging
import os
import subprocess
import tempfile
from typing import Dict, List, Optional

import boto3

from ..archive import Archive
from .base import BaseBackend


class S3Backend(BaseBackend):
    """
    A backend that stores archives on S3 or compatible, encrypted.
    """

    def __init__(
        self,
        key_id: str,
        key_secret: str,
        bucket: str,
        passphrase: Optional[str] = None,
        endpoint: Optional[str] = None,
    ):
        self.key_id = key_id
        self.key_secret = key_secret
        self.bucket = bucket
        self.passphrase = passphrase
        self.endpoint = endpoint

    def __repr__(self):
        return f"S3Backend: {self.bucket} ({self.endpoint})"

    def client(self):
        return boto3.resource(
            "s3",
            aws_access_key_id=self.key_id,
            aws_secret_access_key=self.key_secret,
            endpoint_url=self.endpoint,
        ).Bucket(self.bucket)

    def archive_list(self) -> List[str]:
        """
        Returns the set of available archives based on their meta files
        """
        bucket = self.client()
        results = []
        for item in bucket.objects.all():
            if item.key.endswith(".arcd") and "meta" not in item.key:
                results.append(item.key.split(".", 1)[0])
        return results

    def archive_store(self, root, archive: Archive) -> None:
        # Decide the object names it will end up at
        archive_name = f"{archive.id}.arcd"
        archive_encrypted_name = f"{archive.id}.arcd.gpg"
        meta_name = f"{archive.id}.meta.arcd"
        meta_encrypted_name = f"{archive.id}.meta.arcd.gpg"
        # Write out the archive to a temporary directory
        with tempfile.TemporaryDirectory(prefix="arc-s3-") as tempdir:
            logging.info("Packing archive")
            archive_path = os.path.join(tempdir, archive_name)
            archive_encrypted_path = os.path.join(tempdir, archive_encrypted_name)
            meta_path = os.path.join(tempdir, meta_name)
            meta_encrypted_path = os.path.join(tempdir, meta_encrypted_name)
            archive.pack(root, archive_path)
            # Write out the meta file
            logging.info("Writing meta file")
            with open(meta_path, "w") as file:
                json.dump(archive.to_json(), file)
            # Encrypt it
            if self.passphrase:
                logging.info("Encrypting")
                subprocess.check_output(
                    [
                        "gpg",
                        "--symmetric",
                        "--batch",
                        "--yes",
                        "--passphrase",
                        self.passphrase,
                        "-o",
                        archive_encrypted_path,
                        archive_path,
                    ],
                    stderr=subprocess.STDOUT,
                )
                subprocess.check_output(
                    [
                        "gpg",
                        "--symmetric",
                        "--batch",
                        "--yes",
                        "--passphrase",
                        self.passphrase,
                        "-o",
                        meta_encrypted_path,
                        meta_path,
                    ],
                    stderr=subprocess.STDOUT,
                )
            # Upload it
            logging.info("Uploading")
            if self.passphrase:
                self.client().upload_file(
                    archive_encrypted_path, archive_encrypted_name
                )
                self.client().upload_file(meta_encrypted_path, meta_encrypted_name)
            else:
                self.client().upload_file(archive_path, archive_name)
                self.client().upload_file(meta_path, meta_name)

    def archive_retrieve_meta(self, archive_id: str) -> Dict:
        meta_name = f"{archive_id}.meta.arcd"
        meta_encrypted_name = f"{archive_id}.meta.arcd.gpg"
        # Write out the archive to a temporary directory
        with tempfile.TemporaryDirectory(prefix="arc-s3-") as tempdir:
            logging.info("Downloading meta")
            meta_path = os.path.join(tempdir, meta_name)
            meta_encrypted_path = os.path.join(tempdir, meta_encrypted_name)
            # Download it
            if self.passphrase:
                self.client().download_file(meta_encrypted_name, meta_encrypted_path)
                logging.info("Decrypting meta")
                subprocess.check_output(
                    [
                        "gpg",
                        "--decrypt",
                        "--batch",
                        "--yes",
                        "--passphrase",
                        self.passphrase,
                        "-o",
                        meta_path,
                        meta_encrypted_path,
                    ],
                    stderr=subprocess.STDOUT,
                )
            else:
                self.client().download_file(meta_name, meta_path)
            # Decode its json
            with open(meta_path, "r") as file:
                return json.load(file)

    def archive_retrieve(self, root: str, archive_id: str) -> None:
        # Get archive info
        archive = Archive.from_json(self.archive_retrieve_meta(archive_id))
        archive_name = f"{archive.id}.arcd"
        archive_encrypted_name = f"{archive.id}.arcd.gpg"
        # Write out the archive to a temporary directory
        with tempfile.TemporaryDirectory(prefix="arc-s3-") as tempdir:
            logging.info("Downloading archive")
            archive_path = os.path.join(tempdir, archive_name)
            archive_encrypted_path = os.path.join(tempdir, archive_encrypted_name)
            # Download it
            if self.passphrase:
                self.client().download_file(
                    archive_encrypted_name, archive_encrypted_path
                )
                logging.info("Decrypting archive")
                subprocess.check_output(
                    [
                        "gpg",
                        "--decrypt",
                        "--batch",
                        "--yes",
                        "--passphrase",
                        self.passphrase,
                        "-o",
                        archive_path,
                        archive_encrypted_path,
                    ],
                    stderr=subprocess.STDOUT,
                )
            else:
                self.client().download_file(archive_name, archive_path)
            # Unpack it
            archive.unpack(root, archive_path)
