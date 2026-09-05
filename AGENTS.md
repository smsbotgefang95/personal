# Codex Desktop Instructions

## Local Testing

Whenever working on this project, start a local static development server for testing even if the operator does not explicitly ask for one.

Use this command from the repo root:

```bash
python3 -m http.server 8015
```

Then test pages through the local server instead of opening files directly:

- `http://localhost:8015/`
- `http://localhost:8015/citizenship-interview-prep.html`

If port `8015` is already in use, use the next available port and report the URL. Keep the server running after testing so the operator can continue using it locally. Do not stop the local static development server unless the operator explicitly asks you to stop it.

Current local server note: port `8015` is already in use, so the active local server for this workspace is running at `http://localhost:8016/`. Use that server for local testing unless it stops or becomes unavailable.

## Response Style

When a code change has been made but is not committed or deployed yet, end the response with this sentence as its own final paragraph:

Do you want to deploy the code change?

## Deploy

When the operator says `deploy`, deploy this site to the production server.

### Production Details

- Production SSH alias: `personal-prod`
- Production server: `dev1@217.216.82.144`
- Production checkout: `/home/dev1/personal`
- Production URL: `https://personal.homehomehooray.com`
- The remote server pulls from GitHub using its deploy key.

### Git Workflow Before Deploy

Before running deploy, make sure all intended local changes are committed, merged into `main`, and pushed to GitHub. Uncommitted, unmerged, or unpushed changes will not deploy.

1. Check the current branch and worktree:

   ```bash
   git status
   git branch --show-current
   ```

2. If there are intended changes, commit them.
3. Make sure the changes are on `main`. If working on another branch, merge that branch into `main`.
4. Push `main` to GitHub:

   ```bash
   git push origin main
   ```

Do not deploy until `main` on GitHub contains the changes that should go live.

### Deploy Command

Run:

```bash
ssh personal-prod 'cd /home/dev1/personal && ./deploy.sh'
```

The deploy script is the source of truth for deployment behavior. Do not duplicate its logic in Codex Desktop. Let it pull the latest GitHub changes, sync files into the nginx web root, update nginx, reload nginx, and refresh SSL if needed.

### Verification

After the deploy command finishes, verify the site responds:

```bash
curl -I https://personal.homehomehooray.com
```

Report the deploy result and the HTTP status from the verification request.

Do not stop the local static development server after deployment unless the operator explicitly asks you to stop it.

## Environment Notes

### SSH Setup For New Machines

If `personal-prod` is not configured on the current machine, add this entry to `~/.ssh/config`:

```sshconfig
Host personal-prod
  HostName 217.216.82.144
  User dev1
  IdentityFile ~/.ssh/id_ed25519_personal
  IdentitiesOnly yes
```

Then verify access:

```bash
ssh personal-prod 'pwd && ls /home/dev1/personal'
```

This alias is project-specific. Do not reuse another project's alias, such as `hub-prod`, even if it points to the same server.

### Sudo Setup

The server has limited passwordless sudo configured for `/home/dev1/personal/deploy.sh` through `/etc/sudoers.d/personal-deploy`.

If deploy prompts for a sudo password, the server-side sudoers rule is missing or no longer matches `deploy.sh`. Fix `/etc/sudoers.d/personal-deploy` on the server before retrying unattended deploy.

## Smart Shopping Image Requirements

When adding or replacing food pictures in Smart Shopping, use a square (1:1) image with a genuinely transparent background (alpha channel), no background color, and no colored tile behind the picture. Apply this default without asking the operator to repeat it.
