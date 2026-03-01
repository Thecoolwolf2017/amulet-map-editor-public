# Windows Code Signing

Code signing is required to reduce SmartScreen warnings for `amulet_app.exe`.

## Default (No-Cost) Mode
The CI workflow can generate a temporary self-signed certificate automatically when
no signing secrets are provided.

This is free and signs binaries for integrity, but SmartScreen trust/reputation
benefits are limited versus publicly trusted OV/EV certificates.

## Optional Trusted-Certificate Mode
To use your own certificate instead of self-signed, set these repository secrets:
- `WINDOWS_SIGN_CERT_BASE64`: base64-encoded bytes of your `.pfx` file.
- `WINDOWS_SIGN_CERT_PASSWORD`: password for your certificate.
- `WINDOWS_SIGN_TIMESTAMP_URL` (optional): RFC3161 timestamp URL.

If `WINDOWS_SIGN_TIMESTAMP_URL` is not set, the workflow defaults to:
- `http://timestamp.digicert.com`

## Encode PFX as Base64 (PowerShell)
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\\path\\to\\codesign.pfx")) | Set-Clipboard
```

## What the Workflow Signs
- `dist/Amulet/amulet_app.exe`

Signing runs in CI on Windows builds. It uses trusted-cert secrets when available,
otherwise it falls back to a generated self-signed certificate.
