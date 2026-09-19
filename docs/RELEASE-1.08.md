# ClassicSpeech 1.08

ClassicSpeech 1.08 fixes two ways settings could be lost: Cancel in Web / Browse Mode Settings, and NVDA settings changed while a voice profile's voice was speaking.

Supported NVDA versions: 2025.1 through 2026.2.

## Fixes

### Cancel in Web / Browse Mode Settings works

Cancel, Escape and closing the Web / Browse Mode Settings dialog were meant to put back the settings you had when you opened the dialog, or when you last pressed Apply. For NVDA's own browse mode and web element settings, they failed with an error and put nothing back, and the rest of the dialog's settings weren't put back either. Now each NVDA setting the dialog changes is put back exactly as it was stored, in the configuration profile the dialog changed, and each part of the dialog is put back even if another part fails.

### NVDA settings changed while a voice profile's voice speaks are kept

When a voice profile category or a scheme item uses another voice or synthesizer, ClassicSpeech gives NVDA a temporary configuration profile for as long as that speech lasts. NVDA stores any setting changed during that time in the newest profile. So a setting changed while that voice was still speaking, with the OK button of a settings dialog or a toggle command, disappeared when the voice finished. Now:

* While a settings dialog of NVDA or ClassicSpeech, or the NVDA menu, is open, voice profiles and scheme voices that use another voice or synthesizer speak with your own NVDA voice. NVDA treats its own configuration profiles the same way, so the settings you change there, including your voice settings in NVDA's Speech settings, are saved as you set them. Preview still uses the profile's voice. Profiles that change only rate, pitch or volume still apply.
* A setting changed anywhere else while such a voice is speaking is kept when the voice finishes. The temporary profile's own voice settings still go away with it.
* ClassicSpeech's own changes to NVDA settings go straight to the configuration NVDA saves.

## Installation

Use **Check for Updates...** in the ClassicSpeech menu (NVDA menu → Preferences → ClassicSpeech) in ClassicSpeech 1.07. Or download `ClassicSpeech-1.08.nvda-addon`, open it from Windows Explorer and accept NVDA's installation prompt. Restart NVDA when prompted. Your settings are kept.

## Verification

* Full local harness gate: every harness passes, including new tests for Cancel, for settings changed while a voice profile speaks, and for voice switching while settings dialogs are open.
* Both fixes were also run against NVDA 2026.2's own configuration manager. The Cancel that raised "Value must be a section" now restores. A setting changed while a voice profile overlay was active is now in nvda.ini after saving, where before it was lost.
* Every module ClassicSpeech imports was checked against the `library.zip` of the NVDA 2026.2 installed on the test computer.
* Live NVDA testing has not been done yet. Please check that Check for Updates in 1.07 finds and installs 1.08. Then give a voice profile category another voice, change an NVDA setting in NVDA's settings dialog, and check that it is kept.
