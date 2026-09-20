# ClassicSpeech 1.11

ClassicSpeech 1.11 makes every item in Speech and Sound Schemes do what you configured, wherever it appears.

Supported NVDA versions: 2025.1 through 2026.2.

## Fixes

### An item is heard in every reading mode

A sound or voice set for a formatting option or a web element was only heard when moving word by word with Control and the arrow keys. Reading the same text character by character, line by line with the arrow keys, by sentence, by paragraph or with say all gave NVDA's ordinary voice, and the change went unnoticed. This was most obvious in LibreOffice.

Three separate causes have been fixed.

* **NVDA was not asked for the formatting.** NVDA fetches only the formatting it has been told to announce, and looks no further than the first character of the range it is speaking. A word is its own range, so moving word by word happened to work; a line, a sentence, a paragraph or a say all chunk was described with the formatting of its first character only. ClassicSpeech now asks NVDA for exactly the formatting the configured items need. Your NVDA Document Formatting settings are not changed, and NVDA's own announcements are built from your settings, so NVDA says exactly what you told it to say. Turning off **Font attributes** and giving underlined text a voice now does what it sounds like: the voice changes and nothing is announced.
* **A spelled character lost its formatting.** NVDA speaks a single character in a speech sequence of its own, after the one holding the character's formatting. That second sequence had no formatting, so reading character by character never changed the voice. Every sequence of one reading command now starts with the formatting and elements it is inside, which also covers say all, where NVDA joins several sequences into one.
* **The marked text could be reordered.** When a line held more than one piece of formatting, ClassicSpeech's own speech processing could merge or reorder the fragments, so an item's voice landed on the wrong words or was lost. Document text a scheme item speaks is now passed to NVDA exactly as NVDA built it.

### A voice your synthesizer cannot hear is applied a different way

A voice that changed only the rate, the pitch or the volume was sent to the synthesizer as one of NVDA's inline speech commands. A synthesizer acts only on the commands it lists as supported and silently ignores the rest: BestSpeech, for example, acts on pitch and ignores rate and volume. An item whose voice changed the rate or the volume was therefore never heard on such a synthesizer, however it was configured.

ClassicSpeech now checks what the synthesizer will act on. When an inline command would be ignored, the item uses the same configuration-profile overlay as a ClassicSpeech Voice Profile, which sets the values you chose on the synthesizer itself. The same applies when NVDA's saved value for that setting is zero, which leaves no offset that can express your value.

### An item's voice keeps applying inside an element

Reading by character or word inside a heading, a link, a list or a table asks NVDA for extra detail, and NVDA then leaves out the elements the cursor was already inside. A voice set for those elements stopped at the first word. ClassicSpeech now remembers the elements containing the cursor, so the voice continues for as long as you are inside the element and ends when you leave it.

### A sound set for formatting or an element is played

A WAV sound set for a formatting option or an element was only played where NVDA announced it. With that announcement turned off, the sound was never heard. The sound is now played where the formatting or the element begins in the text, once per run, and is not repeated when a character is spelled.

### Items that could never do anything

Every one of the items in the tree view was checked against NVDA's own control types, and the ones that could never be reached were fixed.

* **Object states.** NVDA never speaks some of the states it knows about: it drops Focusable, Checkable and Selectable always, and Visited outside a link, among others. A sound or voice for one of those did nothing at all. An object's states are now marked on the object itself, so the item applies to any object in that state whether or not NVDA has a word for it. An object's type still comes first, so a scheme for "check box" keeps winning over one for "checked". A negated state such as "not checked" is unchanged: it stays with NVDA's announcement, which is the only place the absence of a state means anything.
* **Style changes (any style)**, **Text color changes** and **Background color changes** are listed as applying to the text that has them, but only the announcement was ever marked. They now apply to the text as well.

## Notes

* Nothing changes for an item you have not configured, and nothing changes when Speech and Sound Schemes are turned off.
* Asking NVDA to look for formatting changes after the cursor costs a little more work in some documents. ClassicSpeech asks for it only when a scheme item describes a run of text.
* A voice applied through the overlay takes effect at a speech boundary, so it can add a very short pause where the formatting starts. A voice the synthesizer can act on inline, such as a pitch change on BestSpeech, keeps speech flowing as before.
* A pitch, rate or volume change is relative to your own setting. If NVDA's pitch for your synthesizer is already near the bottom of its range, a small value for an item is a small change; choose a value further from your own, or a different voice, if you want it to stand out.

## Installation

Use **Check for Updates...** in the ClassicSpeech menu (NVDA menu → Preferences → ClassicSpeech). Or download `ClassicSpeech-1.11.nvda-addon`, open it from Windows Explorer and accept NVDA's installation prompt. Restart NVDA when prompted. Your settings are kept.

## Verification

* Full local harness gate: every harness passes.
* `tests/classic_speech_scheme_items_harness.py` is new. It loads NVDA's own `controlTypes`, so it builds the tree view the user really sees — 333 entries in 13 branches, 310 of them distinct — and checks every item twice: that ClassicSpeech can mark it while NVDA builds speech, and that the mark is turned into both the voice and the sound the user configured. Items whose voice covers text or a whole object must be marked as a range or an object, not only on an announcement that NVDA may never make.
* `tests/classic_speech_schemes_harness.py` gained tests for the reading modes, for a synthesizer that acts on pitch alone, for a saved setting of zero, and for object states.
* The causes were traced in NVDA 2026.2's own `speech.speech.getTextInfoSpeech`, `textInfos.offsets.OffsetsTextInfo.getTextWithFields`, `controlTypes.processAndLabelStates` and `appModules.soffice`, and reproduced before anything was changed.
* Live NVDA testing has not been done yet for this build. In LibreOffice, please underline part of a line and make another part bold, give each a voice that is clearly different from yours, then read that line with the Down arrow, the same words with Control and the arrow keys, character by character with the arrow keys, and with say all. Each item's voice should be heard on its own words every time, and on those words only.
