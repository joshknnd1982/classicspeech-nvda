# ClassicSpeech 1.13

ClassicSpeech 1.13 puts each release's notes inside the add-on, where NVDA 2026.1 and later look for them, so NVDA's Add-on Store can tell you what is new.

Supported NVDA versions: 2025.1 through 2026.2.

## What's new

* ClassicSpeech now tells NVDA what is new in each release. In NVDA 2026.1 and later, select ClassicSpeech in the Add-on Store, press the Applications key or Shift+F10, and choose **What's new**. NVDA opens the notes in a window you read in browse mode, like a web page, with buttons to copy them or close the window.
* The Add-on Store offers **What's new** for a version of ClassicSpeech that it lists, so you can read about an update before you install it, and for a copy you installed from the Add-on Store. It doesn't offer it on the Installed add-ons tab for a copy installed from an add-on file, which includes ClassicSpeech's own **Check for Updates...**; for that copy, the update offer shows each release's notes in its **What's new** box before you install.
* NVDA 2025.1 through 2025.3 don't show these notes, and install and run ClassicSpeech as before.
* Nothing else changes: speech, settings, voice profiles and schemes work as they did in 1.12.

## For maintainers: every release carries its What's new

NVDA 2026.1 added a `changelog` field to the add-on manifest for the changes between the previous version and this one. The Add-on Store shows it from **What's new**, converted from Markdown to HTML, and the Add-on Store's submission check copies it into the store listing. From this release on, ClassicSpeech's `manifest.ini` always carries it.

* The changelog is the `## What's new` section of the current release notes, the file `RELEASE_NOTES` names in `scripts/package_addon.py`. The section ends at the next heading of level one or two, so it may have `###` headings of its own.
* `python scripts/package_addon.py --sync-changelog` copies that section into `manifest.ini`.
* Packaging refuses to build when the changelog is missing or is not that section. It also refuses a release version, such as 1.13, unless `RELEASE_NOTES` is that version's notes, so a release can't go out with an older release's What's new. `tests/classic_speech_packaging_harness.py` runs the same check on every pull request, and reads the manifest with NVDA's own manifest rules to prove NVDA sees the changelog exactly as written.
* The changelog can't contain `"""`, which would end it early, or `%(`, which NVDA's manifest reader takes for a reference to another value. NVDA uses Python-Markdown without extensions, so keep to headings, lists, emphasis, code and links: tables and fenced code blocks are not converted.

## Installation

Use **Check for Updates...** in the ClassicSpeech menu (NVDA menu → Preferences → ClassicSpeech). Or download `ClassicSpeech-1.13.nvda-addon`, open it from Windows Explorer and accept NVDA's installation prompt. Restart NVDA when prompted. Your settings are kept.

## Verification

* The manifest was checked against the manifest rules of NVDA 2025.1, 2025.3, 2026.1 and 2026.2, read with ConfigObj 5.0.9 as NVDA reads it. It is valid for every one of them. NVDA 2026.1 and 2026.2 read the changelog exactly as written, and the 2025 versions ignore it.
* The changelog was converted with Python-Markdown 3.10.3, the version NVDA uses for What's new, and becomes the list shown above.
* Full local harness gate: every harness passes. `tests/classic_speech_packaging_harness.py` gained tests for the What's new: that the manifest carries the current release's section, that NVDA's manifest rules read it back unchanged and older NVDA versions still accept the manifest, that packaging keeps it and refuses a stale one, and that a changelog line which looks like a manifest setting stays text.
* No speech code changed. Live NVDA testing of the Add-on Store's **What's new** needs a copy that the Add-on Store lists or installed; a copy installed from the add-on file doesn't have the action.
