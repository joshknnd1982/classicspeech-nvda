# ClassicSpeech 1.07

ClassicSpeech 1.07 keeps all of its settings in its own file, puts NVDA back the way it was when you reset or remove ClassicSpeech, stops scheme voices from changing your NVDA voice settings, and can check GitHub for updates.

Supported NVDA versions: 2025.1 through 2026.2.

## Fixes

### Removing ClassicSpeech removes all of its settings

Removing ClassicSpeech in the Add-on Store used to leave its settings behind: its voice profiles, verbosity profiles and other settings stayed in nvda.ini, and NVDA settings it had changed stayed changed. Now, when NVDA restarts after you remove ClassicSpeech, ClassicSpeech:

* puts back each NVDA setting it changed, with the value it had before ClassicSpeech first changed it;
* deletes every ClassicSpeech setting, voice profile and speech and sound scheme.

Updating ClassicSpeech to a newer version keeps your settings. This works for removing 1.07 and later: install 1.07 before you remove ClassicSpeech.

### Scheme voices no longer change your NVDA voice settings

A scheme item that speaks with another synthesizer, or a voice you edited for another synthesizer in Speech and Sound Schemes, could be saved as your NVDA voice settings for that synthesizer. Pressing Apply in Voice Profiles while a preview was speaking could also save the preview's voice as your NVDA voice. Neither happens now. If a synthesizer sounds different from what you chose in NVDA, choose it and check its voice settings with NVDA+Control+V.

## New

### ClassicSpeech keeps its settings in its own file

Every ClassicSpeech setting is now in `%APPDATA%\nvda\ClassicSpeech\settings.ini`, next to the Schemes folder, instead of in the `[classicSpeech]` section of nvda.ini. The first time 1.07 starts, it moves your settings there, and the next time NVDA saves its configuration, the section leaves nvda.ini. Nothing else changes: ClassicSpeech settings are still saved when NVDA saves its configuration, and Revert to saved configuration (NVDA+Control+R) reloads them.

The ClassicSpeech folder also holds `nvda-settings-backup.json`, the list of NVDA settings ClassicSpeech changed, with the values they had before.

If you go back to ClassicSpeech 1.06 or earlier, it doesn't read settings.ini, so it starts with its default settings.

### Reset All ClassicSpeech Settings

NVDA menu → Preferences → ClassicSpeech → **Reset All ClassicSpeech Settings...** deletes every ClassicSpeech setting and puts back the NVDA settings ClassicSpeech changed, in your normal configuration and in configuration profiles. ClassicSpeech asks you to confirm first, then saves NVDA's configuration. A setting you changed later in NVDA's own settings keeps your value. The **Resets all ClassicSpeech settings and restores the NVDA settings it changed** command has no gesture until you assign one.

Versions before 1.07 didn't record NVDA's earlier values. For the Object presentation options their verbosity profiles and Speak hotkeys set, a reset puts NVDA's defaults back.

### Check for updates

NVDA menu → Preferences → ClassicSpeech → **Check for Updates...** checks the [releases page](https://github.com/joshknnd1982/classicspeech-nvda/releases) for a newer ClassicSpeech. If there is one, choose **Download and install**: ClassicSpeech downloads it, checks it against its published checksum, and hands it to NVDA's usual add-on installation, which asks you to confirm and offers to restart NVDA. Your settings are kept.

With **Check for ClassicSpeech updates automatically** on the Advanced page of General Settings (checked by default), ClassicSpeech checks once a day, shortly after NVDA starts, and speaks up only when there is an update. The **Checks for ClassicSpeech updates** command has no gesture until you assign one.

### User guide

The guide's new sections, **Updating ClassicSpeech** and **Where ClassicSpeech keeps its settings**, describe where every ClassicSpeech setting is kept, which NVDA settings ClassicSpeech changes, how to reset or remove ClassicSpeech, and how to remove the settings an older version left behind. To open the guide, go to the Add-on Store's **Installed add-ons** tab, select ClassicSpeech, open the context menu and choose **Help**.

## Installation

1. Download `ClassicSpeech-1.07.nvda-addon`.
2. Open it from Windows Explorer and accept NVDA's installation prompt. It replaces ClassicSpeech 1.06.
3. Restart NVDA when prompted.

The first time 1.07 starts, your ClassicSpeech settings move from nvda.ini to `%APPDATA%\nvda\ClassicSpeech\settings.ini`.

## Verification

* Full local harness gate: every harness passes, including new tests for the settings file, the backup and restore of NVDA settings, removal, updates and the voice fixes.
* The settings file, the backup and the reset were also run against NVDA 2026.2's own configuration manager: saving, reverting, a named configuration profile, and the reset.
* Every module ClassicSpeech imports was checked against the `library.zip` of the NVDA 2026.2 installed on the test computer.
* Live NVDA testing has not been done yet. Please check that your settings are unchanged after the update, then try Reset All ClassicSpeech Settings, Check for Updates, and removing ClassicSpeech.
