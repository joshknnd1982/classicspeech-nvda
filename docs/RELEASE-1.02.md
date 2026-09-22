# ClassicSpeech 1.02

ClassicSpeech 1.02 fixes speech lag in Windows Explorer and file dialogs, restores edit field contents on focus, and adds a Mouse voice profile, per-item voices for document formatting and web elements, and Speech and Sound Schemes.

Supported NVDA versions: 2025.1 through 2026.2.

## What's new

* Speech in Windows Explorer and in Open and Save dialogs is quick again: ClassicSpeech no longer searches a dialog for its default button on every key press.
* Tabbing into an edit field reads its current line, or "blank" when it is empty, as NVDA does. **Read edit field contents when focused**, on the Verbosity page, turns this off for a verbosity profile.
* An address bar and similar fields keep their name when NVDA announces a tool bar just before them.
* **Voice Profiles** has two new categories: **Mouse**, for speech from mouse tracking, and **Document and web formatting**, for a voice on any formatting or web element NVDA reports.
* **Speech and Sound Schemes**, in the ClassicSpeech menu, works like the JAWS Speech and Sounds Manager: give object types, states, window classes, document formatting and web elements a sound, a voice or both, and keep them in named schemes.

## Fixes

### Faster speech in Windows Explorer and file dialogs

With the speech hook enabled, arrowing through files in Windows Explorer, the Run dialog's **Browse** window and other Open or Save dialogs was slow. An NVDA log showed 550 to 600 milliseconds of ClassicSpeech work before each file name was spoken in the Browse window.

There were two causes:

* ClassicSpeech looked for the dialog's default button on every focus change, before checking whether focus was on a button. In a file dialog the search found no default button, so it searched again on the next key press, reading up to 250 accessibility objects each time.
* Several checks walked up to 20 parent objects on every speech sequence. In Explorer and web browsers, each step creates a new cross-process accessibility object.

ClassicSpeech now:

* looks for a default button only when focus is on a button;
* remembers "no default button" for each dialog for ten seconds, while NVDA+E still searches again on request;
* skips file lists, trees, tables and documents when it searches;
* reads NVDA's own cached list of the focus's ancestors;
* stops re-checking its whole configuration section each time it reads a setting.

### Edit field contents are read on focus

Tabbing into an edit field now speaks its current line, or "blank" when the field is empty, as NVDA does natively. Earlier versions deliberately spoke only selected text.

To change this, open **General Settings → Verbosity** and use **Read edit field contents when focused**. Like position announcements, the setting is kept separately for each verbosity profile, and it is on for every profile by default.

### Address bar and similar fields keep their name

When NVDA announced a tool bar immediately before an edit field, for example with Ctrl+L in Chrome, ClassicSpeech merged the two announcements and dropped the field's name, role and text. The tool bar is now spoken on its own, followed by the full field announcement.

## New features

### Mouse voice profile

**Voice Profiles** now has a **Mouse** category. It is used for speech from NVDA's mouse tracking when you move a physical mouse or touchpad. Mouse speech used the Review profile before.

### Document and web formatting voices

**Voice Profiles** now has a **Document and web formatting** category. It lists every option from NVDA's Document Formatting panel, grouped the same way:

* Font and text formatting;
* specific font names, font sizes and style names (for example Heading 1 or Quote);
* Document information;
* Pages and spacing;
* Table information;
* Elements, and landmarks and regions.

Choose an item, check **Use a custom voice for this item**, and set any voice setting your synthesizer offers. The voice is used for the announcement, for example "bold" or "heading level 2", and for the text itself: the bold words, the heading or the link.

An item can also use a different synthesizer. NVDA then has to load that synthesizer each time the item is spoken, which adds a noticeable delay. The active synthesizer is the fastest choice.

NVDA's Document Navigation panel has only the paragraph style option, which produces no announcement, so it has no item.

### Speech and Sound Schemes

**NVDA menu → Preferences → ClassicSpeech → Speech and Sound Schemes...** works like the JAWS Speech and Sounds Manager. You can:

* choose a WAV sound for any object type (control type), object state, window class, unknown object, unlabeled graphic, document formatting option or web element;
* choose whether the sound plays in addition to the spoken announcement or instead of it;
* give any of those items a custom voice;
* keep several named schemes (New, Copy, Rename, Delete), and switch between them in the dialog or with a gesture.

The dialog has a search box, a **List** filter that shows only the items you changed, and a category tree. Each item's name in the tree says what is set, for example "Bold (sound, voice)" or "Link (sound only)". **Add font name**, **Add font size**, **Add style name** and **Add window class** add your own entries. The window class offered is the one from the object you were on before opening the dialog.

Sounds and voices apply to focus changes, object navigation, the review cursor, say all, browse mode, and the physical mouse. An item without a sound or voice keeps NVDA's normal speech.

New Input Gestures commands, with no default gestures, are in the ClassicSpeech category:

* Opens ClassicSpeech Speech and Sound Schemes
* Turns ClassicSpeech speech and sound schemes on or off
* Switches to the next ClassicSpeech speech and sound scheme

## Installation

1. Download `ClassicSpeech-1.02.nvda-addon`.
2. Open it from Windows Explorer and accept NVDA's installation prompt.
3. Restart NVDA when prompted.

## Verification

* Full local harness gate, including the new `classic_speech_latency_harness.py` and `classic_speech_schemes_harness.py`.
* The Speech and Sound Schemes and Voice Profiles dialogs were built and exercised with real wxPython and stand-in NVDA modules. That covered choosing sounds, voices on the active synthesizer and on another synthesizer, previews, search, the customized-items filter, custom entries, named schemes, Apply, OK and Cancel.
* Live NVDA testing has not been done yet. Please check Explorer and the Run → Browse dialog, edit fields, the Mouse profile, formatting voices in Word or a web page, and a few scheme sounds.
