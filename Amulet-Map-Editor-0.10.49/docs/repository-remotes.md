# Repository Remotes (Development Record)

Recorded: 2026-03-03

## Purpose

This file records the current GitHub remote layout used for development and public releases.

## Current Remotes

- `origin`: private/dev history repo  
  `https://github.com/Thecoolwolf2017/amulet.git`
- `public`: public release repo  
  `https://github.com/Thecoolwolf2017/amulet-map-editor-public.git`

## Branch Tracking

- Local `main` is currently tracking `public/main`.

If needed, switch tracking back to `origin/main`:

```powershell
git branch --set-upstream-to=origin/main main
```

## Recommended Push Workflow

- Push current development branch to private repo:

```powershell
git push origin main
```

- Push public-ready branch to public repo:

```powershell
git push public main
```

- Push release tags to public repo:

```powershell
git push public --tags
```

## Public Release Repo

- Public launch repository URL:
  `https://github.com/Thecoolwolf2017/amulet-map-editor-public`
