import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from utils.config import log

def encrypt_symmetric(data):
	try:
		# Generate a random key for AES-GCM (256 bits)
		key = AESGCM.generate_key(bit_length=256)
		# Initialize AES-GCM with the generated key
		aesgcm = AESGCM(key)
		# Generate a random nonce (12 bytes for AES-GCM)
		nonce = os.urandom(12)

		# Encrypt the data
		ciphertext = aesgcm.encrypt(nonce, data, None)

		# Return the ciphertext, nonce, and key
		return ciphertext, nonce, key
	except Exception as e:
		log(f"Error during symmetric encryption: {e}", "error")
		return None, None, None

def encrypt_asymmetric(public_key_bytes, key_format, data):
	try:
		# Load the public key depending on the specified format
		if key_format.lower() == 'pem':
			public_key = serialization.load_pem_public_key(
				public_key_bytes,
				backend=default_backend()
			)
		elif key_format.lower() == 'der' or key_format.lower() == 'spki':
			public_key = serialization.load_der_public_key(
				public_key_bytes,
				backend=default_backend()
			)
		else:
			raise ValueError("Public key format must be 'pem' or 'der'.")

		# Encrypt the data using the public key
		encrypted_data = public_key.encrypt(
			data,
			padding.OAEP(
				mgf=padding.MGF1(algorithm=hashes.SHA256()),
				algorithm=hashes.SHA256(),
				label=None
			)
		)

		# Return the encrypted data
		return encrypted_data
	except Exception as e:
		log(f"Error during asymmetric encryption: {e}", "error")
		return None