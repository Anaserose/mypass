# MyPass

An offline desktop password vault and password generator built with Python and Tkinter. Your vault is encrypted on your own machine, and the app has no network code.

## Features

- Local accounts, each with its own encrypted vault
- Password generator (length, uppercase, digits, symbols) using Python's `secrets` module
- Search, reveal, copy, and delete saved entries
- Clipboard is cleared 30 seconds after copying
- Recovery passphrase in case you forget your master password
- Login lockout after 5 failed attempts

## How the encryption works

- Each account gets one random **vault key** at registration. It encrypts the vault with Fernet (AES-128-CBC + HMAC-SHA256).
- The vault key is never stored on its own. It is saved twice, each copy encrypted ("wrapped") under a different key:
  1. a key derived from your **master password**
  2. a key derived from your **recovery passphrase**
- Keys are derived with PBKDF2-HMAC-SHA256 (390,000 iterations) and a random per-account salt.
- Your master password and recovery passphrase are never stored. Logging in re-derives the key and tries to unlock the vault key.
- Files are saved atomically (temp file, then swap) so a crash can't leave a half-written vault.

## Known limitations

- **The recovery passphrase is a second way into your vault.** Anyone who copies your `data/` folder can guess it offline with no attempt limit, so choose a long, unique one. Recovery is also case insensitive.
- **Lockout only protects the app's login screen.** Someone with copies of your files can skip the app, so a strong master password is your real protection.
- Account emails are stored unencrypted in `data/users.json`.
- The vault is decrypted in memory while you're logged in.
- If you forget **both** your password and your passphrase, your data cannot be recovered.

## Run it

Requires Python 3.8+ with Tkinter (included with most Python installs; on Linux install `python3-tk`).

```bash
pip install -r requirements.txt
python main.py
```

Your data is stored locally in a `data/` folder next to `main.py` and is never uploaded anywhere.

## History

The original unencrypted demo is preserved at the `v0.1-demo` tag.

## Roadmap

- Argon2id or scrypt instead of PBKDF2
- Random recovery code instead of a passphrase
- Auto-lock after idle time
- Stricter file permissions on data files
- Unit tests for the crypto functions
- Import / export
