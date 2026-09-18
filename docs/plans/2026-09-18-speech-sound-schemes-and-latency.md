# ClassicSpeech 1.02: latency, edit fields, Mouse voice, Speech and Sound Schemes

## Problems

1. **Latency (bug).** With the speech hook enabled, arrowing through Windows Explorer lists, the Run
   dialog's Browse window and other file dialogs is sluggish. The NVDA 2026.2 debug log shows
   550–600 ms between `filter input` and `Speaking` for each list item in the Browse dialog, 20–50 ms
   in Explorer and 120–140 ms per Tab in Chromium.
   * `_insert_focused_default_button_token` computed the dialog default button for *every* focus
     sequence before checking that focus was a button. In a file dialog the scan found no explicit
     default, cached an empty name, and therefore rescanned up to 250 descendants (cross-process)
     on every keypress.
   * Several helpers walked `obj.parent` for 8–20 levels per sequence (focus context, menu hints,
     dialog detection, position container). In Explorer (UIA) and Chromium (IA2) each level creates a
     new NVDAObject across processes.
   * Every settings getter re-normalized the entire ClassicSpeech config section.
2. **Edit field contents (by design, now optional).** `apply_value_suppression_rules` dropped the
   current line of an edit field on focus unless text was selected. A merged container sequence
   (for example Chrome's `tool bar` + address bar) was also classified as one object, losing the
   field name, role and contents.
3. **Mouse voice (feature).** Mouse feedback used the Review profile.
4. **Document and web formatting voices plus Speech and Sound Schemes (feature).** Per-item voices
   and WAV sounds for NVDA document-formatting attributes, document/web elements, object roles,
   object states and window classes, similar to the JAWS Speech and Sounds Manager.

## What does not change

* Native NVDA speech when no scheme item is configured: tagging wrappers return NVDA's own output.
* Braille, say-all ordering, Quick Nav, caret and review behavior.
* The selected NVDA synthesizer. A scheme item may name another synthesizer; NVDA's own
  configuration-profile trigger mechanism loads it for that item's speech only and restores the
  active synthesizer afterwards.

## Design

* `focus_ancestry.py` reads NVDA's cached `api.getFocusAncestors()` instead of walking parents and
  memoizes ancestor role keys until focus changes. Default-button detection only runs for focused
  buttons, caches negative results per dialog and skips list/tree/table/document subtrees.
* Verbosity gains a per-profile **Read edit field contents when focused** option (default on).
  A held container that is not followed by an item is spoken as its own native utterance.
* Voice Profiles gains **Mouse** and **Document and web formatting** categories.
* Speech and Sound Schemes (`_speech_core/schemes`):
  * `catalog.py` – every item and the categories that organize them.
  * `store.py` – JSON persistence in `classicSpeech.schemeData`, transactional editing.
  * `tagging.py` – wrappers around NVDA speech generation (`getPropertiesSpeech`,
    `getObjectPropertiesSpeech`, `getControlFieldSpeech`, `getFormatFieldSpeech`,
    `getTextInfoSpeech`) that add marker commands only while speech-bound output is generated.
  * `runtime.py` – converts markers to `WaveFileCommand`, inline prosody commands or configuration
    profile triggers inside the ClassicSpeech filter; strips any remaining markers.

## Validation

* New harness `tests/classic_speech_schemes_harness.py` and additions to existing harnesses.
* Full harness gate and packaging checks.
* Live NVDA validation by the user (Explorer, Run → Browse, edit fields, mouse, documents and web).

## Rollback

Each change is isolated behind a module or setting; disabling Speech and Sound Schemes returns
native output, and the speech hook master switch still disables all ClassicSpeech processing.
