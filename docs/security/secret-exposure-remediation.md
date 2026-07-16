# Secret Exposure Remediation

Status: remediation complete for current tree; historical cleanup still required if repository policy demands removal from reachable history.

This branch previously contained credential-like values in tracked environment example and backup files. Those values have been removed from the tracked tree and replaced with placeholders, but some reachable commits still contain the original backup snapshots.

## Remediation scope

- Remove real or live-looking credential values from tracked files.
- Keep only placeholder examples in committed documentation.
- Stop tracking environment backup snapshots that are not intended as source-controlled artifacts.
- Add a deterministic secret-safety contract to prevent reintroduction.

## Findings summary

- `backups/phase21/env.bak`, `backups/phase23/env.bak`, and `backups/phase26/env.bak` contained real-looking credential material.
- The same backup snapshots are reachable in history through the commits that last touched them.
- Documentation examples and local defaults were converted to placeholder form.
- The tracked-tree secret-safety contract now passes on the current branch state.

## Rotation checklist

- Neon database credentials: verify externally in the database provider dashboard.
- Supabase service-role key: verify externally in the Supabase dashboard.
- Redis / Upstash token: verify externally in the Redis provider dashboard.
- LiveKit API secret: verify externally in the LiveKit control plane.
- TURN credential: verify externally in the TURN service configuration.
- OAuth client secrets: verify externally in the OAuth provider dashboard.
- Flask / JWT / session secrets: rotate locally and redeploy.

## Reachable history

- Earliest reachable exposure for the backup snapshots: `ba9a3519d53753003eac537d299f58ce9908bb6f`
- Latest reachable exposure for the backup snapshots: `5b74c2bd8f718e350c6eac8bf1f8ea62f7505ef7`
- Branches or tags containing the exposure: any ref that still reaches those commits, including the current feature branch history before rewrite.

## Current-tree verification

- `scripts/test_tracked_secret_safety.py` passes.
- The current tracked tree no longer contains backup environment snapshots.
- Placeholder documentation and local defaults remain intentionally non-secret.

## History cleanup guidance

If repository policy requires removal of the historical backup snapshots, perform a coordinated cleanup:

1. Rotate the credential first.
2. Stop collaborators from pushing the affected branches.
3. Rewrite history with `git filter-repo` to remove the exposed value or file.
4. Force-push only in the coordinated maintenance window permitted by repository policy.
5. Require all collaborators to re-clone or reset to the rewritten history.

## Verification

- Run `python3 scripts/test_tracked_secret_safety.py`.
- Run the release test suite.
- Confirm the working tree contains no tracked secret-bearing files.
