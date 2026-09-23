# ClassicSpeech 1.16

ClassicSpeech 1.16 says "selected" when you select an item yourself, for example a file with Control+Space in File Explorer.

Supported NVDA versions: 2025.1 through 2026.2.

## What's new

* Selecting an item with **Control+Space**, such as a file in File Explorer, now says "selected", as NVDA does. With **List item state reporting** on its default, **Say not selected**, ClassicSpeech said only the file's name. Unselecting a file still says "not selected".
* **List item state reporting** now decides only what you hear as you move to items. When you select or unselect the item you're on, you always hear which it became, whatever the option says.
* Selecting an item that has no name used to be silent. It now says "selected".

## Details

### What you hear

In File Explorer, hold Control and press Down Arrow to move without changing the selection, then press Space to select or unselect the file you're on:

* Control+Down Arrow: "report.docx not selected 3 of 12", as before.
* Control+Space: "report.docx selected". 1.15 said only "report.docx".
* Control+Space again: "report.docx not selected", as before.

ClassicSpeech says the item's name with its new state. NVDA on its own says only "selected" or "not selected".

### List item state reporting

This option on the Text Processing page decides which of the two words you hear as you move to list items, tree view items, menu items, and table rows and cells. As you move through a list of files, NVDA itself says "not selected" on a file that isn't selected, and nothing on a file that is. So **Say not selected**, the default, sounds the same as NVDA while you move, and the only word it removed was the "selected" that answers Control+Space.

A selection change is now always spoken in full. What you hear as you move to an item is unchanged, whichever choice you have made.

## Installation

Use **Check for Updates...** in the ClassicSpeech menu (NVDA menu → Preferences → ClassicSpeech). Or download `ClassicSpeech-1.16.nvda-addon`, open it from Windows Explorer and accept NVDA's installation prompt. Restart NVDA when prompted. Your settings are kept.

## Verification

* Full local harness gate: every harness passes. `tests/classic_speech_focus_speech_harness.py` sends the speech NVDA 2026.2 gave File Explorer for Control+Down Arrow and Control+Space through ClassicSpeech's speech filter. `tests/classic_speech_core_harness.py` checks a selection change with every List item state reporting choice, in a list and a tree view, and for an item without a name, and checks that items you move to still follow the option.
* These changes have passed the automated tests but have not yet been tried live in NVDA.
