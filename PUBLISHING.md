# Publishing SCANsat-GPU to CKAN

This fork ships as its own CKAN mod (`identifier: SCANsat-GPU`) that **provides** and
**conflicts** with `SCANsat`, i.e. a drop-in substitute you install *instead of* stock SCANsat.

CKAN does not host files. You host the download (GitHub Releases), and submit one small metadata
file (`SCANsat-GPU.netkan`) to the NetKAN repo; a bot follows it to your release, reads the KSP-AVC
`SCANsat.version` inside for the version + KSP compatibility, and generates the CKAN entry.

## One-time facts
- License: **BSD-3-clause** (see `LICENSE.txt`; the bundled part models are explicitly cleared for
  redistribution in derivative works with credit).
- Base: SCANsat **21.1** (`dev`); this fork stamps **21.1.1** (`SCANsat.version.props`). Bump the
  `PATCH` there for each new fork release.
- Target: KSP **1.12.5** (min 1.12.3, from `SCANsat/SCANsat.csproj`).

## Each release
1. **Build + package:**
   ```powershell
   .\build-release.ps1            # or -KspRoot <path to a KSP 1.12.5 install with the Managed DLLs>
   ```
   Produces `dist\SCANsat-GPU-21.1.1.zip` (GameData/SCANsat/... with the built DLLs + rebuilt
   `scan_shaders.scan` bundle) and `dist\SCANsat.version`.
   - Reminder: if you changed the shader, **rebuild the Unity asset bundle first**
     (Unity 2019.4.18f1 -> `SCANsat -> Build All Bundles`) and commit `scan_shaders.scan`, else the
     zip ships the old bundle.
   - Sanity check: drop the zip's `GameData/` into a clean KSP and confirm it loads
     (`[SCANsat] All SCANsat asset bundles loaded`).
2. **Tag + GitHub Release:**
   ```powershell
   git tag v21.1.1 ; git push origin v21.1.1
   ```
   Create a Release on that tag; **attach both** `SCANsat-GPU-21.1.1.zip` and `SCANsat.version`.
3. **Submit to CKAN (first release only; later releases are auto-detected by the bot):**
   - Fork `KSP-CKAN/NetKAN`, add `NetKAN/SCANsat-GPU.netkan` (copy of the one in this repo), open a PR.
   - Before submitting, open the current `SCANsat.netkan` in `KSP-CKAN/CKAN-meta` and copy its exact
     `depends`/`recommends`/`suggests` into yours so the fork matches upstream.
   - Optional: validate locally with `netkan.exe SCANsat-GPU.netkan` (from KSP-CKAN's NetKAN releases).

## Notes
- Maintainers may prefer you upstream the RAM fix to `KSPModStewards/SCANsat` rather than list a
  shadowing fork. As of the fork point, upstream's last commit was 2026-04-29 (light maintenance),
  so a PR there may sit a while.
- Easier alternative to the NetKAN PR: upload the zip to **SpaceDock** and enable its "index on CKAN"
  option, which feeds CKAN for you.
