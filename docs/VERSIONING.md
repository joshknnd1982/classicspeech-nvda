# ClassicSpeech versioning and CI artifact identity

## Workflow triggers

The `Verify and package ClassicSpeech` workflow runs on pull requests, pushes to `main`, and manual workflow dispatches. Every completed run without an explicit release version produces a unique date-and-run artifact.

## Generated numeric version

Every GitHub Actions workflow run generates the package manifest version:

```text
YYYYMMDD.RUN
```

For example, workflow run 16 on UTC date 2026-07-24 installs as version:

```text
20260724.16
```

The source `manifest.ini` deliberately uses the neutral `0.0.0` placeholder. During packaging, `scripts/package_addon.py` replaces that value **inside the `.nvda-addon` archive only**. The checked-out source manifest is never changed.

This uses two numeric components because current NVDA Add-on Store logic compares side-loaded add-on versions only when it can parse two or three integers. The date component preserves chronological order; the GitHub Actions run component makes every workflow artifact unique, including multiple runs on one day.

## Artifact names

An artifact includes the generated installed version and the source commit:

```text
ClassicSpeech-20260724.16-gddf21ae.nvda-addon
```

- `20260724.16` is the version shown by NVDA after installation.
- `gddf21ae` identifies the source commit used by the workflow.
- The `.sha256` sidecar has the same basename.

Git tags and GitHub releases may still carry human-facing labels such as `RC` or `stable`, but they do not change the numeric installed version.

## Release builds

For an official release, run the workflow manually and fill in **Release version** with a numeric version such as `4.0.0` or `4.0.1`. That value is written into the package manifest and its artifact name is simply:

```text
ClassicSpeech-4.0.0.nvda-addon
```

Leave **Release version** blank for all ordinary main, pull-request, and manual test builds. Those continue to use the generated UTC-date-and-run version.

## What's new in the manifest

Every build carries the current release's What's new in the manifest's `changelog`, a field NVDA 2026.1 added. NVDA's Add-on Store shows it, converted from Markdown, when you choose **What's new** for the add-on, and the Add-on Store's submission check copies it into the store listing. NVDA 2025.1 through 2025.3 ignore the field.

The changelog is the `## What's new` section of the release notes named by `RELEASE_NOTES` in `scripts/package_addon.py`, up to the next heading of level one or two. For each release:

1. write `docs/RELEASE-<version>.md` with a `## What's new` section;
2. point `RELEASE_NOTES` at it;
3. run `python scripts/package_addon.py --sync-changelog`, which writes that section into `manifest.ini` as a triple-quoted value.

Packaging stops when the manifest's changelog is missing or is not that section. A release version, the **Release version** above or `--version` given to the script, must also be the version of `RELEASE_NOTES`, so a release can't carry an older release's What's new. Date-and-run builds skip only that last check.
