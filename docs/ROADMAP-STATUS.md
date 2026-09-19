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
- **Speech and Sound Schemes**: per-item sounds and voices for object roles, states, window classes, document formatting and web elements, with named schemes.

The 1.02 baseline passed the local harness gate and a wxPython build of the new dialogs. It still requires live NVDA validation of the items listed in `RELEASE-1.02.md`. 1.03 changes only the manifest's author credits. 1.04 adds the user guide and the command that opens it. 1.05 keeps each scheme in its own folder and shares schemes and voice profiles as files. 1.06 fixes loading in NVDA: the 1.05 build imported a module NVDA does not include, and was never published. 1.07 keeps ClassicSpeech settings in `ClassicSpeech/settings.ini`, restores NVDA's settings on reset and removal, stops scheme voices from changing NVDA voice settings, and checks GitHub for updates. 1.08 keeps NVDA settings changed while a voice profile overlay is active, pauses voice overlays while settings dialogs are open, and fixes Cancel in Web / Browse Mode Settings. 1.09 stops Reset All ClassicSpeech Settings from freezing NVDA: its Yes/No question opened inside NVDA's core event queue. 1.10 makes a Speech and Sound Scheme item's voice and sound follow the text it describes in every reading mode: NVDA is asked for the formatting the configured items need, every speech sequence of one reading command carries the formatting and elements it starts inside, and marked document text is passed through unchanged.

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
| `RELEASE-1.10.md` | Current release notes, packaged with the add-on. |
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
