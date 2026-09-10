# SwiftShare

Anonymous, encrypted file and text sharing. Upload a file, several files or just some text, and get a short link. The link expires on the schedule you pick, and no account is needed.

The encryption design is the subject of my paper **"Beyond Nonce Uniqueness: A Cryptographic Evaluation of AES-GCM in Secure Anonymous File Sharing Systems"** (ICDSA 2025, Springer). [Read it here](https://doi.org/10.1007/978-3-032-15407-1_26).

## How it works

- **Encryption:** every upload is encrypted on the server with AES-256-GCM, using a fresh random 12-byte nonce, before it is stored. Only ciphertext is kept.
- **Storage:** encrypted files go to an AWS S3 bucket. Each share gets a random 6-character ID.
- **Expiry:** choose delete-after-first-download, 1 hour or 1 day. Once a link has expired, the file is deleted from S3 the next time anyone requests it.
- **Optional password:** you can protect any share with one.
- **Multiple files:** several files, or files plus text, are bundled into one encrypted ZIP.

## Stack

Python, FastAPI, `cryptography` (AESGCM), boto3 and AWS S3, and a plain HTML/CSS/JS front end.

## Run it locally

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```
ENCRYPTION_KEY=<base64 of 32 random bytes>
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=...
S3_BUCKET_NAME=...
```

Generate a key with `python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"`, then start the server:

```bash
uvicorn main:app --reload
```

Then open http://localhost:8000.

## Notes

Share metadata (IDs, expiry times and passwords) is held in memory, so restarting the server invalidates existing links. The files themselves stay encrypted in S3.
