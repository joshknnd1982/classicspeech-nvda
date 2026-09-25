# ClassicSpeech current status and documentation index

This document describes the current `main` baseline and indexes the maintained documentation. It is not a release note or authorization to deploy, package, or merge work.

Historical files under `docs/plans/` and the versioned RC notes preserve original design, validation, and release rationale. They do not describe the current development baseline and must not be treated as active task lists.

## Current `main` baseline

The current automated baseline includes:

- organized General Settings panels, including the native **Spoken object details** checklist and revised Intermediate defaults;
- same-synth Voice Profiles and the Preferences → ClassicSpeech entry points;
- Web / Browse Mode custom Browse and Focus mode messages, preserving native NVDA behavior until a message is configured;
- Page Summary, Page Ready, heading-continuity, and supported Edge notification controls;
- unbound Input Gestures entries for General Settings, Web / Browse Mode Settings, Voice Profiles, Speech and Sound Schemes, turning schemes on or off, switching schemes, and opening the user guide;
- a user guide, `doc/en/readme.html`, that NVDA's Add-on Store Help action opens;
- conservative Number Processing that preserves combined digit strings such as `5'5`;
- compatibility coverage for both legacy and current NVDA Braille-input source layouts;
- 1.02 latency fixes for Windows Explorer and file dialogs (cached focus ancestry and a default-button search limited to focused buttons);
- **Read edit field contents when focused** (Verbosity, per profile, on by default);
- the **Mouse** and **Document and web formatting** Voice Profile categories;
- **Speech and Sound Schemes**: per-item sounds and voices for object roles, states, window classes, document formatting and web elements, with named schemes;
- the current release's What's new in the manifest `changelog`, which NVDA 2026.1 and later show from the Add-on Store's **What's new** action, kept equal to the release notes' `## What's new` section by packaging;
- **Give ClassicSpeech messages priority over NVDA speech** (Misc), for every message ClassicSpeech speaks itself;
- the **NVDA sounds** scheme category, which replaces the sounds in NVDA's waves folder with a scheme's sounds;
- the dialog's own default button for **NVDA+E** and **Announce default button in dialogs**, from wx, `DM_GETDEFID`, default push-button styles, reported default states, and, for NVDA+E only, the buttons' appearance on screen;
- **List item state reporting** (Text Processing) for items the user moves to, with a selection change, such as Control+Space, always spoken with its new state, and in File Explorer's list of files spoken as JAWS's ExplorerFrame.jss speaks it;
- a message's status from Outlook, such as "unread", in the focus announcement of Outlook's message list, which waits a bounded time for Outlook's object model.

The 1.02 baseline passed the local harness gate and a wxPython build of the new dialogs. It still requires live NVDA validation of the items listed in `RELEASE-1.02.md`. 1.03 changes only the manifest's author credits. 1.04 adds the user guide and the command that opens it. 1.05 keeps each scheme in its own folder and shares schemes and voice profiles as files. 1.06 fixes loading in NVDA: the 1.05 build imported a module NVDA does not include, and was never published. 1.07 keeps ClassicSpeech settings in `ClassicSpeech/settings.ini`, restores NVDA's settings on reset and removal, stops scheme voices from changing NVDA voice settings, and checks GitHub for updates. 1.08 keeps NVDA settings changed while a voice profile overlay is active, pauses voice overlays while settings dialogs are open, and fixes Cancel in Web / Browse Mode Settings. 1.09 stops Reset All ClassicSpeech Settings from freezing NVDA: its Yes/No question opened inside NVDA's core event queue. 1.11 makes every Speech and Sound Scheme item do what the user configured: an item's voice and sound follow the text they describe in every reading mode (NVDA is asked for the formatting the configured items need, every speech sequence of one reading command carries the formatting and elements it starts inside, and marked document text is passed through unchanged); a voice the synthesizer cannot hear as an inline command uses the same overlay as a Voice Profile; an object's states are marked on the object; every one of the items in the tree view is covered by `classic_speech_scheme_items_harness.py`; and an update offer shows the release notes in a read-only edit box instead of a message box. 1.12 makes the keyboard layout menu NVDA opens while adding an input gesture read its first item (a held container fragment is abandoned once the focus has moved and never carries NVDA's focus cancellation marker into a later utterance, which NVDA drops together with everything queued behind it), makes every row of the Speech and Sound Schemes tree readable by protecting a focused item's own name from role and state classification, and offers the two Hotkeys multiple-choice settings as NVDA-style check lists from one shared control. 1.13 puts each release's What's new in the manifest `changelog` that NVDA 2026.1 added, and packaging refuses a build whose changelog is missing, is not the current release notes' `## What's new` section, or belongs to another release version. 1.14 routes every ClassicSpeech message through `message_priority.speak_message`, which with the new Misc option speaks it at `Spri.NOW` and holds off NVDA's automatic speech cancellation until the message has been spoken or the user presses a key, and adds the NVDA sounds category: `schemes/nvda_sounds.py` wraps `nvwave.playWaveFile` to play a scheme's sound for any file in NVDA's waves folder, and takes over NVDA's start and exit sounds, through NVDA's own option, while a scheme has a start sound. 1.15 reports a dialog's own default button wherever focus is (`dialog_helpers.py`, `win32_default_button.py`): NVDA's wx dialogs through their default item without wx's temporary default, standard Windows dialogs through `DM_GETDEFID`, other Windows toolkits through the default push-button style seen while focus was on another control, and toolkits without a window per button through the default state, trusted on a focused button only in IAccessible2 applications other than Qt. Split buttons count. When nothing else names one, NVDA+E compares the dialog's buttons on screen (`default_button_appearance.py`) and names one only when it alone is colored. 1.16 keeps the state of a list item's selection change, such as Control+Space on a file, whatever List item state reporting says: a state-only "selected" or "not selected" sequence on a focused item is marked as a selection change, and the option applies to the items the user moves to. 1.17 puts an overlay class in front of NVDA's Outlook `UIAGridRow` (`outlook_message_rows.py`): for the focused message it waits, up to 300 ms, until Outlook's object model answers before NVDA builds the name, so the status NVDA reads from Outlook, such as "unread", is in the focus announcement; after a timeout it doesn't wait again until Outlook answers, and it never keeps a name built off NVDA's main thread. 1.18 says a selection change in File Explorer's list of files (a focused list item in `DirectUIHWND` of `explorer`) as JAWS's ExplorerFrame.jss does: "not selected" before the item's name, placed with the token editor's `forceLast`, and "selected" alone; other lists keep the name first.

## Current boundaries

- Virtual-buffer mutation, synthetic structural lines, and replacement of NVDA's native Browse Mode presentation are not ClassicSpeech add-on work. The supported add-on API has no buffer write path. Any future proposal requires a separately approved NVDA-core design.
- Page-ready orientation is distinct from virtual-buffer manipulation. It must remain additive, current-document scoped, and must not change native buffer contents, selection, caret, Quick Nav, braille, Say All, or structural speech.
- Tooltip behavior is intentionally unchanged. Tooltip timing is not exposed because the current speech routes cannot provide reliable full-token timing.
- `sequence_merger.py` was removed after a repository-wide dependency audit found no active source, test, packaging, or documentation dependency. Do not reintroduce sequence-merging behavior without a defined requirement and focused coverage.

## Documentation map

| Document | Role |
| --- | --- |
| `../README.md` | Current user-facing feature, settings-access, safety, and testing overview. |
| `../doc/en/readme.html` | User guide for every setting and command; NVDA's Add-on Store Help opens it. |
| `DEVELOPMENT-WORKFLOW.md` | Source, branch, CI, scratchpad, and live-validation procedure. |
| `VERSIONING.md` | CI artifact and official-release versioning rules. |
| `RELEASE-1.18.md` | Current release notes, packaged with the add-on; their What's new is the manifest changelog. |
| `RELEASE-1.17.md` | 1.17 notes: Outlook's message status, such as "unread", in the focus announcement. |
| `RELEASE-1.16.md` | 1.16 notes: a selection change, such as Control+Space, always says its new state. |
| `RELEASE-1.15.md` | 1.15 notes: a dialog's own default button, found by appearance when nothing reports it. |
| `RELEASE-1.14.md` | 1.14 notes: message priority, NVDA sounds in schemes. |
| `RELEASE-1.13.md` | 1.13 notes: What's new in the manifest changelog. |
| `RELEASE-1.12.md` | 1.12 notes: input gesture menu, Schemes tree rows, Hotkeys check lists. |
| `RELEASE-1.11.md` | 1.11 notes: every Speech and Sound Scheme item, update notes box. |
| `RELEASE-1.09.md` | 1.09 notes: Reset All ClassicSpeech Settings no longer freezes NVDA. |
| `RELEASE-1.08.md` | 1.08 notes: settings kept during voice overlays, Web / Browse Mode Cancel. |
| `RELEASE-1.07.md` | 1.07 notes: settings file, reset and removal, voice leak fixes, update checks. |
| `RELEASE-1.06.md` | 1.06 notes: loading fix; includes the 1.05 scheme folders and sharing. |
| `RELEASE-1.05.md` | 1.05 notes: scheme folders and sharing (built, never published; 1.06 includes it). |
| `RELEASE-1.04.md` | 1.04 release notes: user guide. |
| `RELEASE-1.03.md` | 1.03 release notes: author credits. |
| `RELEASE-1.02.md` | 1.02 release notes: latency fixes, edit fields, Mouse voice, Speech and Sound Schemes. |
| `plans/2026-09-18-speech-sound-schemes-and-latency.md` | 1.02 design: latency fixes, edit fields, Mouse voice, Speech and Sound Schemes. |
| `WEB-BUFFER-LOAD-RESEARCH.md` | Historical NVDA lifecycle research and the no-buffer-mutation boundary. |
| `VOICE-PROFILES-RC-V24.md` | Historical Voice Profiles RC note. |
| `PAGE-ORIENTATION-RC-V25.md` | Historical Page Orientation RC note. |
| `EDGE-NOTIFICATIONS-RC-V26.md` | Historical Edge Notifications RC note. |
| `plans/2026-07-20-web-summary-v0.md` | Historical manual Page Summary design. |
| `plans/2026-07-21-automatic-page-summary-v1.md` | Historical automatic Page Summary design. |
| `plans/2026-07-22-page-orientation-presentation-research.md` | Archived virtual-buffer presentation research; not implementable as an add-on. |
| `plans/2026-07-23-page-load-notifications-v1.md` | Historical Page Ready design. |
| `plans/2026-07-23-edge-notification-controls.md` | Historical Edge notification-controls design. |

When behavior changes, update this status document, the README, and any relevant release note or add-on metadata together. Historical plans and RC notes should be retained for provenance, not duplicated as competing current roadmaps.
