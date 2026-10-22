"""Called only by the installer: output is captured, never logged."""
import base64
import hashlib
import json
from pathlib import Path
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

root = Path(__file__).resolve().parent
envelope = json.loads((root / 'enrollment.enc.json').read_text())
if envelope.get('algorithm') != 'RSA-OAEP-SHA256':
    raise ValueError('Unexpected enrollment format')
private = serialization.load_pem_private_key((root / 'receiver-private.pem').read_bytes(), password=None)
fingerprint = hashlib.sha256(private.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).hexdigest()
if envelope.get('recipient_spki_sha256') != fingerprint or private.key_size != 3072:
    raise ValueError('Enrollment belongs to another device')
plain = private.decrypt(base64.b64decode(envelope['ciphertext'], validate=True), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
data = json.loads(plain)
if (data.get('control_url') != 'https://175.178.16.90/r-link'
        or not isinstance(data.get('expires_at'), int) or data['expires_at'] <= time.time()
        or not isinstance(data.get('enrollment_token'), str) or not 20 <= len(data['enrollment_token']) <= 256
        or not isinstance(data.get('device'), str) or not 1 <= len(data['device']) <= 80):
    raise ValueError('Invalid or expired device enrollment')
print(json.dumps(data))
