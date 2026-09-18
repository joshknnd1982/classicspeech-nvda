# ClassicSpeech 1.06

ClassicSpeech 1.06 fixes the 1.05 test build, which did not load in NVDA, and includes everything built for 1.05.

Supported NVDA versions: 2025.1 through 2026.2.

## Fixes

### ClassicSpeech loads again

The 1.05 test build did not load in NVDA:

* the ClassicSpeech submenu was missing from NVDA menu → Preferences;
* the ClassicSpeech category was missing from Input Gestures;
* ClassicSpeech did not change NVDA's speech.

The NVDA log said "Error importing global plugin classicSpeech" and "No module named 'filecmp'". The new scheme folder code used a Python module that NVDA's built-in copy of Python doesn't include. 1.06 doesn't use it. A new automatic test now checks that ClassicSpeech imports only modules NVDA includes.

## Also in this release

The features built for 1.05, which was never published:

* Each speech and sound scheme is its own folder in `%APPDATA%\nvda\ClassicSpeech\Schemes`, and an **Open schemes folder** button opens it in File Explorer.
* **Export scheme** and **Import scheme** share a scheme, with its sounds and voices, as one `.classicspeech-scheme` file.
* **Export voice profiles** and **Import voice profiles** share voice profiles as one `.classicspeech-voices` file.

The [1.05 release notes](https://github.com/joshknnd1982/classicspeech-nvda/blob/main/docs/RELEASE-1.05.md) and the user guide describe them in detail. To open the guide, go to the Add-on Store's **Installed add-ons** tab, select ClassicSpeech, open the context menu and choose **Help**.

## Installation

1. Download `ClassicSpeech-1.06.nvda-addon`.
2. Open it from Windows Explorer and accept NVDA's installation prompt. It replaces ClassicSpeech 1.05.
3. Restart NVDA when prompted.

The first time 1.06 starts, your speech and sound schemes move into their folders.

## Verification

* Full local harness gate: 498 tests. The new runtime imports test fails on the 1.05 code with exactly the `filecmp` import.
* Every module ClassicSpeech imports was checked against the `library.zip` of the NVDA 2026.2 installed on the test computer.
* Live NVDA testing has not been done yet. Please check that the ClassicSpeech submenu and the Input Gestures category are back, then try the scheme folders and the export and import buttons.
