# ClassicSpeech 1.04

ClassicSpeech 1.04 adds a user guide that opens from NVDA's Add-on Store, and a command that opens it. It also fixes Reset this item in Voice Profiles.

Supported NVDA versions: 2025.1 through 2026.2.

## New features

### User guide

ClassicSpeech now has a user guide that covers every setting and command. To open it:

1. Press NVDA+N to open the NVDA menu, then choose Tools, then Add-on Store.
2. On the **Installed add-ons** tab, move to ClassicSpeech.
3. Press the Applications key or Shift+F10, then choose **Help**.

The guide opens in your web browser. Its headings follow the ClassicSpeech dialogs, so you can move through it with H in browse mode.

### Command that opens the user guide

A new Input Gestures command in the ClassicSpeech category, **Opens the ClassicSpeech user guide**, opens the same guide. It has no default gesture. To assign one, open NVDA menu → Preferences → Input gestures.

## Fixes

In **Voice Profiles → Document and web formatting**, **Reset this item** removed the item's sound as well as its voice, although that page doesn't show sounds, which are set in Speech and Sound Schemes. It now removes only the voice. In Speech and Sound Schemes, Reset this item still removes both.

## Installation

1. Download `ClassicSpeech-1.04.nvda-addon`.
2. Open it from Windows Explorer and accept NVDA's installation prompt. It replaces your current ClassicSpeech.
3. Restart NVDA when prompted.

## Verification

* Full local harness gate, including the new `classic_speech_user_guide_harness.py`. It checks that the guide lists every command, default gesture and settings page.
* The packaged manifest passes NVDA 2026.2's add-on manifest validation, and the package contains `doc/en/readme.html`, the file the Add-on Store's Help action opens.
* Live NVDA testing has not been done yet. Please check that Help opens the guide from the Add-on Store, and that the new command opens it after you assign a gesture.
