# ClassicSpeech 1.10

ClassicSpeech 1.10 fixes Speech and Sound Schemes in documents: an item's voice and sound now follow the text it describes however you read it.

Supported NVDA versions: 2025.1 through 2026.2.

## Fixes

### A scheme item is heard in every reading mode

A sound or voice set for a formatting option or a web element was only heard when moving word by word with Control and the arrow keys. Reading the same text character by character, line by line with the arrow keys, by sentence, by paragraph or with say all gave NVDA's ordinary voice, and the change went unnoticed. This was most obvious in LibreOffice.

Three separate causes have been fixed.

* **NVDA was not asked for the formatting.** NVDA fetches only the formatting it has been told to announce, and looks no further than the first character of the range it is speaking. A word is its own range, so moving word by word happened to work; a line, a sentence, a paragraph or a say all chunk was described with the formatting of its first character only. ClassicSpeech now asks NVDA for exactly the formatting the configured items need. Your NVDA Document Formatting settings are not changed, and NVDA's own announcements are built from your settings, so NVDA says exactly what you told it to say. Turning off **Font attributes** and giving underlined text a voice now does what it sounds like: the voice changes and nothing is announced.
* **A spelled character lost its formatting.** NVDA speaks a single character in a speech sequence of its own, after the one holding the character's formatting. That second sequence had no formatting, so reading character by character never changed the voice. Every sequence of one reading command now starts with the formatting and elements it is inside, which also covers say all, where NVDA joins several sequences into one.
* **The marked text could be reordered.** When a line held more than one piece of formatting, ClassicSpeech's own speech processing could merge or reorder the fragments, so an item's voice landed on the wrong words or was lost. Document text a scheme item speaks is now passed to NVDA exactly as NVDA built it.

### An item's voice keeps applying inside an element

Reading by character or word inside a heading, a link, a list or a table asks NVDA for extra detail, and NVDA then leaves out the elements the cursor was already inside. A voice set for those elements stopped at the first word. ClassicSpeech now remembers the elements containing the cursor, so the voice continues for as long as you are inside the element and ends when you leave it.

### A sound set for formatting or an element is played

A WAV sound set for a formatting option or an element was only played where NVDA announced it. With that announcement turned off, the sound was never heard. The sound is now played where the formatting or the element begins in the text, once per run, and is not repeated when a character is spelled.

## Notes

* Nothing changes for an item you have not configured, and nothing changes when Speech and Sound Schemes are turned off.
* Asking NVDA to look for formatting changes after the cursor costs a little more work in some documents. ClassicSpeech asks for it only when a scheme item describes a run of text.

## Installation

Use **Check for Updates...** in the ClassicSpeech menu (NVDA menu → Preferences → ClassicSpeech). Or download `ClassicSpeech-1.10.nvda-addon`, open it from Windows Explorer and accept NVDA's installation prompt. Restart NVDA when prompted. Your settings are kept.

## Verification

* Full local harness gate: every harness passes. Ten new tests read the same underlined text by character, word, line, sentence, paragraph and say all through the whole path, from NVDA building the speech to the sequence ClassicSpeech hands back, and they fail on the 1.09 code.
* The causes were traced in NVDA 2026.2's own `speech.speech.getTextInfoSpeech`, `textInfos.offsets.OffsetsTextInfo.getTextWithFields` and `appModules.soffice`, and reproduced against a LibreOffice-shaped document before anything was changed.
* Live NVDA testing has not been done yet. In LibreOffice, please underline part of a line, then read that line with the Down arrow, the same words with Control and the arrow keys, character by character with the arrow keys, and with say all. The item's voice should be heard on the underlined words every time, and on those words only.
