# Windows Code Signing

Code signing is required to reduce SmartScreen warnings for `amulet_app.exe`.

## Requirements
- A valid OV or EV code-signing certificate in PFX format.
- Certificate password.

## GitHub Secrets
Set these repository secrets:
- `WINDOWS_SIGN_CERT_BASE64`: base64-encoded bytes of the `.pfx` file.
- `WINDOWS_SIGN_CERT_PASSWORD`: password for the certificate.
- `WINDOWS_SIGN_TIMESTAMP_URL` (optional): RFC3161 timestamp URL.

If `WINDOWS_SIGN_TIMESTAMP_URL` is not set, the workflow defaults to:
- `http://timestamp.digicert.com`

## Encode PFX as Base64 (PowerShell)
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("C:\\path\\to\\codesign.pfx")) | Set-Clipboard
```

## What the Workflow Signs
- `dist/Amulet/amulet_app.exe`
- `dist/Amulet/amulet_app_debug.exe`

Signing is optional in CI and only runs when signing secrets are present.
