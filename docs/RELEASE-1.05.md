# ClassicSpeech 1.05

ClassicSpeech 1.05 keeps each speech and sound scheme in its own folder, and lets you share schemes and voice profiles as files.

Supported NVDA versions: 2025.1 through 2026.2.

## New features

### Each scheme has its own folder

Speech and Sound Schemes are now folders you can find in File Explorer:

* Each scheme, including Default, is a folder in `%APPDATA%\nvda\ClassicSpeech\Schemes`, in NVDA's user configuration folder.
* A scheme's folder holds `scheme.json`, the scheme's settings, and a `Sounds` folder. When you press OK or Apply, ClassicSpeech copies each sound you chose into that folder, so the scheme keeps working if the original file moves.
* The new **Open schemes folder** button in Speech and Sound Schemes opens the folder in File Explorer.
* Renaming or deleting a scheme renames or deletes its folder when you press OK or Apply.
* Your existing schemes move into folders the first time 1.05 starts.

Fonts, sizes, styles and window classes you add now belong to each scheme. A new scheme starts with the active scheme's added entries.

### Share schemes

* **Export scheme...** saves the active scheme, with its sounds, voices and added entries, in one `.classicspeech-scheme` file. If a sound file is missing, ClassicSpeech lists the sounds it left out.
* **Import scheme...** adds a scheme file someone sent you as a new scheme and makes it active. Press OK or Apply to keep it, or Cancel to discard it.

### Share voice profiles

* **Export voice profiles...** in Voice Profiles saves your voice profiles, for every synthesizer, in one `.classicspeech-voices` file.
* **Import voice profiles...** reads such a file, replacing only the synthesizers and categories it contains. Press OK or Apply to keep them.

Document and web formatting voices are part of a scheme, so they travel with an exported scheme.

The user guide describes all of this. To open it, go to the Add-on Store's **Installed add-ons** tab, select ClassicSpeech, open the context menu and choose **Help**.

## Installation

1. Download `ClassicSpeech-1.05.nvda-addon`.
2. Open it from Windows Explorer and accept NVDA's installation prompt. It replaces your current ClassicSpeech.
3. Restart NVDA when prompted.

## Verification

* Full local harness gate: 495 tests. New tests cover scheme folders, moving existing schemes, renaming and deleting folders, scheme packages (including refusing unsafe package contents), and voice profile files.
* Both dialogs were run with real wxPython. The run covered saving schemes into folders, exporting and importing a scheme and voice profiles through the file choosers, Open schemes folder, and Cancel.
* Live NVDA testing has not been done yet. Please check that your existing schemes still work after the update and appear in the Schemes folder, then try exporting and importing a scheme and your voice profiles.
