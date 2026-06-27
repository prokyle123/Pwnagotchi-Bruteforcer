# Updating the GitHub Repository

This release migrates the repository from the legacy plugin filename `bruteforce.py` to the currently deployed filename `Bruteforcer.py`. The capitalization matters because the Pwnagotchi configuration uses `main.plugins.Bruteforcer.*`.

## Files to publish

From this release package, add or replace:

```text
Bruteforcer.py
README.md
CHANGELOG.md
config.example.toml
extras/fan_control_telemetry.py
docs/UPGRADING.md
docs/GITHUB_UPDATE.md
LICENSE
.gitignore
```

Delete the old root-level `bruteforce.py` after the new `Bruteforcer.py` has been added. Keeping both can confuse users and may lead to two similarly named Pwnagotchi plugin configurations.

## Option A: Update through the GitHub website

1. Open your repository in a browser.
2. Open `bruteforce.py`, use the `...` menu, and choose **Delete file**. Commit the deletion with:

   ```text
   chore: remove legacy lowercase plugin filename
   ```

3. Select **Add file → Upload files**.
4. Drag in the files listed above. Preserve the `docs/` and `extras/` folders.
5. Commit the upload with:

   ```text
   release: BruteForcer v3.3.0 Command Center and Mutator Lab
   ```

6. On the repository home page, choose **Releases → Draft a new release**.
7. Create tag `v3.3.0`, title it `BruteForcer v3.3.0`, and use the v3.3.0 section of `CHANGELOG.md` as the release notes.
8. Optionally upload the release ZIP as an asset so users can download a verified package.

## Option B: Update with Git from a computer

```bash
git clone https://github.com/prokyle123/Pwnagotchi-Bruteforcer.git
cd Pwnagotchi-Bruteforcer

# Copy the release-package files into this checkout, preserving folders.
# Then remove the legacy filename.
git rm bruteforce.py

git add Bruteforcer.py README.md CHANGELOG.md config.example.toml LICENSE .gitignore docs extras

git commit -m "release: BruteForcer v3.3.0 Command Center and Mutator Lab"
git tag -a v3.3.0 -m "BruteForcer v3.3.0"
git push origin main --tags
```

## Verify the repository after publishing

Check these items in the GitHub file browser:

- `Bruteforcer.py` exists at the repository root.
- `bruteforce.py` is gone.
- `README.md` renders correctly.
- `CHANGELOG.md` includes v3.3.0.
- `config.example.toml` uses the `main.plugins.Bruteforcer.*` prefix.
- Documentation links open correctly.

## Suggested release notes

```text
BruteForcer v3.3.0 brings the Command Center and Mutator Lab into one GitHub-ready release. Highlights include offline-friendly dashboard pages, Capture Intelligence, reports, measured WPS telemetry, system and fan telemetry, resource awareness, crash-aware job tracking, capture-quality grading, queue controls, and an expanded, capped Mutator Lab. Existing installs should follow docs/UPGRADING.md and preserve the case-sensitive Bruteforcer.py filename plus the main.plugins.Bruteforcer.* config prefix.
```
