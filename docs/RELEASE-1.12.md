# ClassicSpeech 1.12

ClassicSpeech 1.12 is about being able to hear what you are moving through: the menu NVDA opens when you add an input gesture, and every row of the Speech and Sound Schemes tree. The Hotkeys page now offers its two multiple-choice settings the way NVDA's Document Formatting page offers Spelling or grammar errors.

Supported NVDA versions: 2025.1 through 2026.2.

## What's new

* The keyboard layout menu NVDA opens while you add an input gesture reads the item it opens on. That item used to be silent until you arrowed to the next one.
* Every row of the Speech and Sound Schemes tree is read. Rows named after NVDA's own words, such as "menu" and "selected", were silent.
* The two Hotkeys settings that are several choices, **Speak hotkeys in** and **Which shortcuts to speak**, are lists of checkboxes, the way NVDA's Document Formatting page offers Spelling or grammar errors. Your settings are kept.

## Fixes

### The keyboard layout menu is read when you add an input gesture

When you add a gesture in NVDA's Input Gestures dialog and press the keystroke, NVDA opens a small menu so you can choose which keyboard the gesture belongs to, for example "control+f (desktop keyboard)" or "control+f (keyboard, all layouts)". With ClassicSpeech's speech hook on, the item the menu opened on was silent. Arrowing to the next item read normally, so the menu was usable but its first line had to be guessed at.

ClassicSpeech briefly holds back a bare container fragment such as "tree view" so it can be joined to the item it belongs to. NVDA attaches a cancellation marker to each announcement it builds for a focus event, and its speech manager throws away an utterance whose marker has expired **together with everything still waiting behind it**. Speaking that fragment again after the focus had already moved into the menu therefore took the menu item's announcement down with it.

Three things changed.

* A held fragment is abandoned once the focus has moved on. It described something you have already left, so it is not spoken over what you moved to.
* A held fragment never carries NVDA's cancellation marker into the utterance it is spoken in later, or into the announcement of another object it is merged with. The marker belongs to the announcement NVDA built.
* A fragment that is the focused item's own name is not held at all. A row called "tree view" is a row, not the tree that holds it.

As a last resort, speech for an open menu that ClassicSpeech's own processing leaves with no words at all now falls back to NVDA's own text. A menu you cannot hear is a dead end, so nothing is allowed to empty one.

### Every row of the Speech and Sound Schemes tree is read

The tree in the Speech and Sound Schemes manager is built from NVDA's own vocabulary, so its rows are named after roles and states: "menu", "selected", "tree view", "list", "combo box". ClassicSpeech classified such a row label as the role or state it looks like, and then dropped or moved it, so arrowing onto those rows gave only "1 of 156" or nothing at all. Under **Object types (control types and roles)** the two rows named "menu" were silent, and under **Object states** the row named "selected" was silent.

The first thing spoken for a focused item is that item's own name. ClassicSpeech already protected the name of a focused dialog control, such as a combo box labelled "Style", from being taken for a role; that protection now covers the items inside a dialog too: tree view items, list items, menu items, tabs and table cells. All 346 rows of the tree are checked by `tests/classic_speech_scheme_items_harness.py`.

## Changes

### Hotkeys settings are lists of checkboxes

NVDA presents a setting that is really several independent choices as a labeled list of checkboxes rather than a combo box with one entry per combination: Spelling or grammar errors on the Document Formatting page is Speech, Sound and Braille, each checked on its own. The two Hotkeys settings that worked the older way now match it.

* **Speak hotkeys in** is a list with **Menus** and **Dialogs**. Check both, check one, or clear both to speak no shortcuts at all.
* **Which shortcuts to speak** is a list with **Access keys** and **Command shortcuts**. Clearing both speaks no shortcut.

Arrow to a line and press <kbd>Space</kbd> to change it. NVDA's own accessible check list is used, so the checked state is reported as you move and when you change it. Settings written by earlier versions are read unchanged, and the values ClassicSpeech stores are the same ones earlier versions wrote, so you can move back to an earlier version without losing these settings.

Every check list in ClassicSpeech — the Token Editor, Key Labels, Page Summary element types, Spelling or grammar errors, and now Hotkeys — is built from one shared place, so they all behave the same.

## Notes

* Nothing changes outside the paths above: an item you have not configured, ordinary document reading and NVDA's own speech are untouched.
* **Speak hotkeys in** with nothing checked is the same setting as the old "Off", and clearing both kinds of shortcut is a new way to say the same thing from the other list.
