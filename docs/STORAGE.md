# Storage — AICP Workstation Layout and Rules

> Authoritative reference for what goes where on this machine, why, and how to add or migrate storage.
> Lives in the AICP repo because AICP runs the workloads that consume storage tiers (weight serving, caches, routing telemetry). Brain-side cross-reference: `wiki/spine/references/operator-workstation-storage-tiering.md`.

## Summary

Three storage tiers, one hard rule, one procedure. The hard rule — **the WSL VDisk itself (`/` on `/dev/sdc`) never contains model weights or large caches** — supersedes any other decision. Every other choice below exists to make that rule easy to follow.

## Tier taxonomy

| Tier | Physical | WSL access | Typical latency | Use for |
|---|---|---|---|---|
| **T0 — Hyperfast NVMe** | D:\ (WD_BLACK SN770 Gen4 NVMe, behind PCIe 3.0 x4 on this X299 board) | Dedicated VHDX mounted as native ext4 block device (`/dev/sdX` → `/mnt/models`) | ~2.8–3.2 GB/s seq read, no 9P tax | Active model weights, inference working set, hot caches, anything mmap'd by a serving process |
| **T1 — SATA SSD RAID 0** | H:\ (Intel RAID 0 of 2× SATA SSDs, 1.9TB, local — confirmed via `Get-PhysicalDisk` 2026-04-23) | 9P passthrough at `/mnt/h/...`, OR native ext4 via VHDX on H:\ (e.g. `/mnt/dev-envs`) | ~500–1000 MB/s native VHDX (SATA stripe ceiling); ~0.5–1 GB/s via 9P | Weight archives, staging downloads, datasets, dedicated dev VHDXs (venvs, sources, build caches) |
| **T2 — Cold archive** | F:\ (3.7TB, personal archive drive) | 9P at `/mnt/f/...` | USB/HDD class | Long-term backups, non-LLM data |
| **OFF-LIMITS** | `/dev/sdc` (WSL root `/`), `/mnt/c`, `/mnt/s` (Docker) | — | — | **Never** holds model weights, large caches, or datasets. Not `/home`, not `/root`, not anywhere inside the WSL root filesystem. |

### The hard rule, stated precisely

> Any file larger than ~500MB that is not required to be inside the Linux system itself (glibc, kernel modules, core utils, user shell config) belongs on a dedicated mount (T0/T1/T2), never on the WSL root VDisk.

Rationale: WSL VDisks (VHDX on the Windows host) grow as used and — absent `sparseVhd=true`, and imperfectly even with it — do not cleanly return space to the host. `.wslconfig` on this machine has `sparseVhd=true` set, which helps but does not absolve careless writes.

### Bandwidth reality on THIS machine (2026-04-23)

The X299 Skylake-X platform tops out at PCIe 3.0. Every NVMe slot is capped at PCIe 3.0 x4 ≈ 3.5 GB/s theoretical, ~3 GB/s practical. A PLX PCIe switch in the x16 slot splits to x8 aggregate maximum — 2× NVMe in RAID 0 through PLX would cap near 5–6 GB/s theoretical, not the 14–15 GB/s a modern Z790 board would enable. **Design the placement logic around ~3 GB/s NVMe, not manufacturer spec sheets.**

Future upgrade target: MSI Z790 Gaming Pro WiFi + 12–14th gen Intel + DDR5 + 2× NVMe RAID 0. Migration section below.

## Current physical state (verified 2026-04-23)

| Device | Size | FS | UUID | Mount | Status |
|---|---|---|---|---|---|
| `/dev/sdc` | 1007GB | ext4 | `ed9fcb8b…` | `/` (WSL root) | **System — no model data here** |
| `/dev/sdf` | 541GB | ext4, label `models` | `0011b353-25b2-4414-842b-e88506a1970b` | `/mnt/models` | **T0 — active** |
| `/dev/sdb` | 16GB | swap | `e51bef1e…` | [SWAP] | active swap |
| `/dev/sda` | 0GB | (empty ext4) | — | unmounted | placeholder / unknown origin |
| `/dev/sdd` | 256GB | ext4 | `3255683f…` | unmounted | unknown contents — inspect before reusing |
| `/dev/sde` | 0GB | (empty ext4) | — | unmounted | placeholder / unknown origin |

Windows drive map:

| Win | Disk# | Media | Size | Free | WSL path | Role |
|---|---|---|---|---|---|---|
| C:\ | 1 | Intel RAID 0 SATA SSD | 465G | 211G | `/mnt/c` | Windows system — OFF-LIMITS |
| D:\ | 2 | **WD_BLACK SN770 NVMe** | 932G | 672G before VHDX | `/mnt/d` + hosts `D:\vdisks\models.vhdx` | T0 NVMe host for VHDX files |
| F:\ | 3 | SABRENT USB (HDD class) | 3.7T | 433G | `/mnt/f` | T2 personal archive |
| H:\ | 0 | **Intel RAID 0 of 2× SATA SSDs** (local, NOT network) | 1.9T | 1.7T | `/mnt/h` + hosts `H:\vdisks\dev-envs.vhdx` | T1 SATA RAID 0 — dev VHDXs, cold weights, staging |
| S:\ | 4 | PCIE SSD (via USB adapter) | 233G | 96G | `/mnt/s` | Docker reserved — OFF-LIMITS |

`.wslconfig` at `C:\Users\Jean\.wslconfig`:

```ini
[wsl2]
memory=48GB
processors=8
swap=16GB
localhostForwarding=true
dnsTunneling=true

[experimental]
sparseVhd=true
autoMemoryReclaim=gradual
```

## What goes where — concrete placements

| Data | Tier | Path |
|---|---|---|
| K2.6 Q2 GGUF weights (340GB) when re-downloaded | T0 | `/mnt/models/kimi-k2-6-q2/` |
| LocalAI model weights (LLM GGUFs, SD, clip, whisper, TTS voices) | T0 | `/mnt/models/localai/models/` (symlinked from `<repo>/models`) |
| LocalAI backend build context (CUDA llama-cpp, whisper, piper, SD) | T0 | `/mnt/models/localai/backends/` (symlinked from `<repo>/backends`) |
| KTransformers venv | T1-on-NAS-VHDX | `/mnt/dev-envs/ktransformers-env/` (dedicated VHDX `H:\vdisks\dev-envs.vhdx`, native ext4) |
| KTransformers source | T1-on-NAS-VHDX | `/mnt/dev-envs/ktransformers-src/` |
| KTransformers weights/caches working set | T0 | `/mnt/models/kt-cache/` |
| AirLLM offload tier | T0 | `/mnt/models/airllm-cache/` |
| LoRA / fine-tune adapters (hot-swap) | T0 | `/mnt/models/adapters/` |
| Inventory manifest (E010-M004) | T0 | `/mnt/models/.inventory.json` |
| Cold weight archives (idle variants) | T1 | `/mnt/h/models-cold/<model>/` |
| Download staging (big HF pulls) | T1 | `/mnt/h/models-cold/downloads/<model>/` |
| Datasets at rest | T1 | `/mnt/h/datasets/<name>/` |
| Personal backups | T2 | `/mnt/f/Backups/...` |
| Python venvs for AICP itself, repo sources | WSL root is OK (small) | `~/.venvs/`, `~/devops-expert-local-ai/` (keep under a few GB each — large deps belong on a dedicated VHDX) |

### Symlink pattern for files historically co-located with the repo

LocalAI's `docker-compose.yaml` uses `./models:/models` as a bind mount and `./backends` as Docker build context. Both are kept on T0 at `/mnt/models/localai/` with symlinks at the repo root for backwards compatibility:

```
<repo>/models    -> /mnt/models/localai/models      (bind mount target, follows symlink)
<repo>/backends  -> /mnt/models/localai/backends    (docker build context, follows symlink)
```

Both paths are gitignored so the symlinks don't show up in git. Docker bind mounts and BuildKit both follow host-side symlinks.

## Hard don'ts

1. **Never download model weights, datasets >500MB, or caches to `~/` or any path inside `/`.** The target path must resolve via `df -T` to a non-root mount (ideally `/mnt/models` for active, `/mnt/h/...` for cold).
2. **Never use `sudo rm -rf` on a mount you haven't verified with `mount | grep <path>`.** The 2026-04-23 incident happened partly because emergency-deleting the wrong VDisk became the fastest path out of a jam.
3. **Never run `hf download` / `aria2c` / `git lfs` without an explicit `--local-dir` pointing at a dedicated mount.** The default CWD or `~/.cache/huggingface` is a trap — those resolve to `/` and fill the WSL root.
4. **Never `wsl --mount --vhd` a VHDX file on a network share.** All current drive letters on this machine are local storage (confirmed 2026-04-23 via `Get-PhysicalDisk` — D:\ NVMe, H:\ local SATA RAID 0, C:\ local SATA RAID 0, F:\ USB, S:\ USB). If a future drive letter is ever SMB-mapped, VHDX-on-it will fail HCS ACL checks.
5. **Never edit `/etc/fstab` without `nofail`** on any non-root mount. Boot must never block on a missing VDisk.
6. **Never skip the `takeown` + `icacls` sequence** when creating a new VHDX — the `wsl --mount --vhd` HCS/E_ACCESSDENIED error has a root cause, and the fix is documented below.
7. **Never start a download ≥100MB without explicit operator authorization** — even if space appears to exist. See memory `feedback_never_unauthorized_large_disk_writes.md`.

## Creating a new dedicated VDisk (authoritative procedure)

Source: `wiki/log/2026-04-23-vhdx-attach-procedure-and-hcs-fix.md` + `2026-04-23-e010-m002-mount-complete.md`. The `takeown`/`icacls` block is the load-bearing step — skipping it produces `Wsl/Service/AttachDisk/MountVhd/HCS/E_ACCESSDENIED` even as Administrator.

### Step 1 — Windows side (elevated PowerShell)

```powershell
# Adjust SIZE_GB and path for the intended purpose
$VHD  = "D:\vdisks\<name>.vhdx"          # or H:\vdisks\<name>.vhdx if H: is local RAID (NOT SMB)
$SIZE = 550GB                             # dynamic — only consumes as used

New-VHD -Path $VHD -SizeBytes $SIZE -Dynamic

takeown /F $VHD
icacls $VHD /reset
icacls $VHD /grant "$(whoami):(F)"
icacls $VHD /grant "NT VIRTUAL MACHINE\Virtual Machines:(F)"
icacls $VHD /grant "SYSTEM:(F)"
icacls $VHD /grant "Administrators:(F)"

wsl --mount --vhd $VHD --bare
```

### Step 2 — WSL side

```bash
lsblk -b                                   # identify new /dev/sdX (usually next free letter)

DEV=/dev/sdX                               # set to the device from lsblk
MOUNT=/mnt/<name>                          # e.g. /mnt/models, /mnt/dev-envs

sudo mkfs.ext4 -L <name> $DEV
sudo mkdir -p $MOUNT
sudo mount $DEV $MOUNT

UUID=$(sudo blkid -s UUID -o value $DEV)
echo "UUID=$UUID $MOUNT ext4 defaults,nofail,x-systemd.device-timeout=10s 0 2" | sudo tee -a /etc/fstab

# Verify fstab works
sudo umount $MOUNT && sudo mount -a && df -h $MOUNT

# Make user-writable
sudo chown $(id -u):$(id -g) $MOUNT
touch $MOUNT/.mount-ok
```

### Step 3 — Persistence across reboots

`wsl --mount --vhd` is one-shot. It does NOT survive `wsl --shutdown` by itself. To auto-re-attach:

**Option A — Windows Task Scheduler (recommended)**

Create a scheduled task in Task Scheduler:
- Trigger: *At log on of Jean*
- Action: `powershell.exe -NoProfile -WindowStyle Hidden -Command "wsl --mount --vhd 'D:\vdisks\<name>.vhdx' --bare"`
- Settings: Run only when user is logged on, highest privileges, start a new instance if already running.

**Option B — Manual re-mount after each `wsl --shutdown`**

Run the `wsl --mount --vhd` line from Step 1 in elevated PowerShell. Fastest to set up, most brittle.

## Stale `/etc/fstab` cleanup

If you destroy a VDisk (e.g., via Hyper-V Manager or `Remove-VHD`), remove its entry from `/etc/fstab` the same day. `nofail` prevents boot failure but the stale line is tech debt that confuses future sessions. The 2026-04-23 stale entry for UUID `564e3456…` lived for hours after its VDisk was gone and cost investigation time.

## Migration procedure (future Z790 + 2× NVMe RAID 0)

When the new platform lands, T0 migrates from single-NVMe-VHDX to a larger, faster mount. The data layout stays identical — only the underlying device changes.

1. **Provision the new target**:
   - If RAID 0 is via Windows Storage Spaces → create the pool, expose as a new drive letter (e.g., `R:\`), create `R:\vdisks\models.vhdx`.
   - If RAID 0 is via motherboard/controller → the BIOS presents one volume; same VHDX approach on the new letter.
   - Size generously (1.5–2TB dynamic given the larger model ambitions).
2. **Benchmark with `fio`** before any migration — new target must clear ~5 GB/s sustained to justify the move.
3. **Attach the new VHDX** per the Step 1 procedure above; it gets a new `/dev/sdX` letter.
4. **Stop consumers** (`kt-serve`, AICP, any process with an open mmap on `/mnt/models`).
5. **Atomic data move**: `rsync -aHAX --info=progress2 /mnt/models/ /mnt/models-new/` followed by a sanity diff (`diff -rq /mnt/models /mnt/models-new`).
6. **Flip `/etc/fstab`**: replace the old UUID with the new one, same mount point.
7. **Detach and retire** the old VHDX only after the new mount is proven in production for at least one work cycle. Keep the old VHDX file offline as rollback for 1–2 weeks.
8. **Update this doc** with the new device, UUID, and measured `fio` numbers.
9. **Update the brain doc** (`wiki/spine/references/operator-workstation-storage-tiering.md`) with the new disk row.

## Benchmarking commands

```bash
# Seq read (the honest NVMe-vs-9P comparison)
fio --name=seq-read --rw=read --bs=1M --size=4G \
    --iodepth=16 --numjobs=1 --direct=1 \
    --filename=/mnt/models/.fio-$$ --group_reporting
rm /mnt/models/.fio-*

# Random 4K (the MoE expert fetch pattern)
fio --name=rand4k --rw=randread --bs=4K --size=1G \
    --iodepth=32 --numjobs=4 --direct=1 \
    --filename=/mnt/models/.fio-$$ --group_reporting
rm /mnt/models/.fio-*

# Repeat against /mnt/h and /mnt/d for the 9P tax comparison.
```

Log results with date + hardware context in `wiki/log/<date>-storage-benchmark.md`.

## Disk cleanup checklist (when clearing space)

In order — cheap, reversible first:

1. `journalctl --vacuum-size=500M` (system logs)
2. Docker: `docker system prune -a` (reclaim Docker space on `/mnt/s`)
3. `~/.cache/huggingface/hub/` → purge downloaded snapshots you can re-download
4. `~/.cache/pip/`, `~/.cache/uv/`, `~/.cache/pypoetry/`
5. `/tmp/*`, `/var/tmp/*`
6. Old venvs in `~/.venvs/` or project-local `.venv/` that are no longer active
7. `/mnt/models/airllm-cache/`, `/mnt/models/kt-cache/` — rebuild on next run
8. Archived model weights in `/mnt/h/models-cold/` — keep only current generation

**Never** as a first move: `rm -rf /mnt/models` or any emergency deletion of a dedicated mount. Investigate first.

## References

- Brain authoritative tiering doc: `wiki/spine/references/operator-workstation-storage-tiering.md`
- VHDX attach procedure + HCS fix: `wiki/log/2026-04-23-vhdx-attach-procedure-and-hcs-fix.md`
- E010-M002 completion log: `wiki/log/2026-04-23-e010-m002-mount-complete.md`
- Persistent operator rules (memory): `feedback_never_unauthorized_large_disk_writes.md`, `feedback_storage_tiers_and_wsl_vdisk_rule.md`
