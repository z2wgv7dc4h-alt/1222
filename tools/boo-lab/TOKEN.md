# Token I need to push

GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained**.

- Resource owner: `z2wgv7dc4h-alt`
- Repository access: **Only select repositories** → create empty public `boo-lab` first, then select it
- Permissions → Repository:
  - **Contents: Read and write**
  - Metadata: Read (forced)
- Expiration: 7 days is enough
- No Actions, no Admin, no Secrets, no Delete

Classic `repo` tokens work but they can see every repo. Do not send those.

Paste the `github_pat_…` in chat once. After push I will not store it. Revoke it when the push lands.
