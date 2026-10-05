"""Synthetic service account keys generated per test run; never real credentials."""

import json
from functools import cache
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

TOKEN_URI = "https://oauth2.googleapis.com/token"


@cache
def _pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()


def service_account_info(**changes: Any) -> dict[str, Any]:
    return {
        "type": "service_account",
        "project_id": "synthetic-project",
        "private_key_id": "synthetic-key-id",
        "private_key": _pem(),
        "client_email": "lumini-synthetic@synthetic-project.iam.gserviceaccount.com",
        "client_id": "000000000000000000000",
        "token_uri": TOKEN_URI,
        **changes,
    }


def service_account_json(**changes: Any) -> str:
    return json.dumps(service_account_info(**changes))
