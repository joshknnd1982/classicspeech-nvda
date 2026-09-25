# ClassicSpeech 1.18

ClassicSpeech 1.18 says a selection change in File Explorer the way JAWS does.

Supported NVDA versions: 2025.1 through 2026.2.

## What's new

* In File Explorer's list of files, **Control+Space** now says it the way JAWS does. When you unselect a file, you hear "not selected" first and then the file's name. When you select a file, you hear just "selected". ClassicSpeech used to say the file's name first, as it does when you move to a file, so "not selected" was easy to miss.
* Everywhere else, such as a list in another program, an Open dialog or File Explorer's navigation pane, you still hear the item's name and then "selected" or "not selected".
* What you hear as you move from file to file hasn't changed, and still follows **List item state reporting**.

## Details

### What you hear

Control+Space on "Jaws files", a folder that is selected because you arrowed to it:

* 1.17: "Jaws files, not selected".
* 1.18: "not selected, Jaws files".

Control+Space again, selecting it:

* 1.17: "Jaws files, selected".
* 1.18: "selected".

### Why

A tester coming from JAWS reported that Control+Space in File Explorer didn't say "selected" or "not selected". NVDA's log showed ClassicSpeech saying "Jaws files, not selected" each time, and the tester said they would rather hear it as JAWS says it. JAWS's File Explorer script (ExplorerFrame.jss, ObjStateChangedEvent) says "Not Selected" and then the item's name when an item is unselected, and only "selected" when it is selected. With the name first, the answer to the key sounded like the announcement of an unselected file you had just moved to.

### What ClassicSpeech does now

NVDA announces a selection change as the new state alone. Since 1.16, ClassicSpeech keeps that state whatever List item state reporting says, and adds the focused item's name in front. When the item is in File Explorer's list of files (the `DirectUIHWND` items view of File Explorer), ClassicSpeech now puts the name after "not selected", and adds no name to "selected". The token editor's order for everything else is unchanged.

## Installation

Use **Check for Updates...** in the ClassicSpeech menu (NVDA menu → Preferences → ClassicSpeech). Or download `ClassicSpeech-1.18.nvda-addon`, open it from Windows Explorer and accept NVDA's installation prompt. Restart NVDA when prompted. Your settings are kept.

## Verification

* Full local harness gate: every harness passes. `tests/classic_speech_core_harness.py` runs ClassicSpeech's speech processing on a focused File Explorer item: "not selected, Jaws files" and "selected" whatever List item state reporting says and whatever the token editor's order, an unnamed item, moving from file to file unchanged, and the name first as before in another program's list, an Open dialog, the desktop and File Explorer's navigation pane.
* These changes have passed the automated tests but have not yet been tried live in NVDA.
