# MyPass (Demo)

A desktop password vault and password generator built with Python and Tkinter.

> ## ⚠️ Demo only. Not secure.
> This demo stores accounts and passwords as **plain JSON with no encryption or hashing**.
> **Do not use real passwords.** A hardened, encrypted version is coming.

## What it does

- Create an account and log in
- Save website / username / password entries to a personal vault
- Generate random passwords (adjustable length, uppercase, digits, symbols) using Python's `secrets` module
- Search, reveal, copy, and delete saved entries

## Known limitations (demo)

- Account passwords and vault entries are saved in plain text (`users_demo.json`, `vault_demo.json`)
- Security questions are collected at signup but account recovery is not implemented yet
- No login attempt limits
- Not independently security audited

## Coming in the secure version

- Salted password hashing / key derivation
- Encrypted vault file
- Login attempt lockout
- Account recovery

