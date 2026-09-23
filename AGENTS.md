# ClassicSpeech for NVDA — Agent Guide

## Scope and source of truth

- Active repository: `classicspeech-nvda`.
- Project roadmap/spec: `../spec.docx`.
- New work belongs in this repository, on a focused Git branch from `main`.
- Do not create independent repository copies, branch-named source folders, or a new `vNN` source folder for ordinary feature work. The historical/versioned folders outside this repository are reference material, not active workspaces.
- Use a separate managed Git worktree only when explicitly needed for a long-lived parallel experiment or comparison.
- After a pull request is merged, remove its temporary worktree and delete its unneeded local branch. Run `git worktree list` first so an active worktree is never removed accidentally.
- Preserve important build artifacts through GitHub Releases or `Classic Speech Historical` before removing a worktree. Generated `dist` output is not source history.

## Delivery boundaries

- ClassicSpeech is an NVDA add-on. Do not modify NVDA core or the installed NVDA baseline unless Tim explicitly requests a separately scoped NVDA-core experiment.
- Keep changes narrow and preserve native NVDA behavior unless the specification explicitly changes it.
- Preserve native literal/review/caret/Say All behavior. Do not route ordinary document text through ClassicSpeech processing without a defined, tested requirement.
- Speech and Sound Schemes (`_speech_core/schemes`) are that kind of defined requirement: they may mark NVDA speech only for items a user configured, and NVDA's output must stay unchanged when nothing is configured (`tests/classic_speech_schemes_harness.py`).
- Each speech and sound scheme is a folder under `ClassicSpeech/Schemes` in NVDA's configuration folder (`_speech_core/schemes/store.py`). Tests that use scheme folders must set `store._ROOT_OVERRIDE` to a temporary folder, never NVDA's real configuration.
- ClassicSpeech's own settings are saved in `ClassicSpeech/settings.ini`, never in nvda.ini (`_speech_core/settings_file.py`). Tests that touch that folder must set `nvda_settings_backup._CONFIG_FOLDER_OVERRIDE` to a temporary folder.
- Change NVDA's own settings only through `nvda_settings_backup.set_nvda_setting` or `recording_nvda_change`, so Reset All ClassicSpeech Settings and removal (`installTasks.py`) can put them back. A synthesizer loaded only to speak or edit a scheme voice must go through `keep_settings_out_of_nvda_config`, so its settings never become the user's NVDA voice settings.
- Voice profile and scheme voices push a temporary, unnamed profile onto NVDA's configuration while they speak (`voice_profile_overlay.py`, `voice_profile_trigger.py`). Such a trigger must stay out of the way of NVDA's settings. It does nothing while `gui.shouldConfigProfileTriggersBeSuspended()` is true, except for a preview. On exit it carries NVDA's writes into the real configuration, apart from the overlay's own voice settings. ClassicSpeech's settings dialogs set `shouldSuspendConfigProfileTriggers = True`, as NVDA's do (`tests/classic_speech_settings_safety_harness.py`).
- `installTasks.py` removes ClassicSpeech's settings only when the add-on is removed, never when a new version replaces it. It loads `nvda_settings_backup.py` on its own, so that module must not import other ClassicSpeech modules.
- Update checks (`_speech_core/update_check.py`) use the GitHub repository in the manifest `url`. Tests must never reach the network.
- Speech-path code must not walk `obj.parent` chains for the focus; use `_speech_core/focus_ancestry.py`, which reads NVDA's cached focus ancestors (`tests/classic_speech_latency_harness.py`).
- A dialog's default button is the one Enter presses after a change in another control (`_speech_core/dialog_helpers.py`). Windows push buttons, wx, WinForms, Qt and Office make whichever button has focus the default, so never report a focused button's default state as the dialog's: standard dialogs answer `DM_GETDEFID`, NVDA's wx dialogs their own default item (not wx's temporary default), and other dialogs what was seen while focus was on another control. Window-handle calls go through `win32_default_button.get_api()`, which only a running NVDA turns on; tests install fakes (`tests/classic_speech_default_button_harness.py`).
- The appearance check (`_speech_core/default_button_appearance.py`) reads screen pixels only for NVDA+E, never for focus speech, and only when nothing else names a default button. It names a button only when that button alone is colored, and says so; with the Screen Curtain on it asks the user to turn the curtain off.
- The token editor owns speech-token ordering and placement. Text Processing owns reporting/filtering transformations; do not move token-placement policy into it.
- `sequence_merger.py` was removed after an audit confirmed it had no active dependents. Do not reintroduce sequence-merging behavior without a defined, tested requirement.

## Accessibility and settings

- The target user is visually impaired. Prefer native NVDA controls, keyboard-complete workflows, stable labels, and screen-reader-friendly feedback.
- Follow existing settings-dialog transaction behavior: Apply, OK, Cancel, Close, reload, and external configuration save must leave persisted and runtime state coherent.
- Do not replace an NVDA accessibility-enhanced control with a raw wx equivalent without explicit approval.
- Never open a modal dialog (a message box or `ShowModal`) from code that runs inside NVDA's core pump, such as a script or a `queueHandler.queueFunction` callback. NVDA's pump doesn't re-enter, so NVDA freezes and can't even speak the dialog; the Reset All ClassicSpeech Settings confirmation did this. Open it with `wx.CallAfter`, as `GlobalPlugin._outside_nvda_core` does (`tests/classic_speech_settings_removal_harness.py`).
- `doc/en/readme.html` is the user guide NVDA opens from the Add-on Store's Help action. Update it with every user-facing change; `tests/classic_speech_user_guide_harness.py` checks that it covers every command, default gesture and settings page.

## Validation

- Read the relevant specification and trace existing code/tests before editing.
- Add or extend focused harness coverage before changing subtle speech-filter, settings, or routing behavior.
- At minimum, compile changed Python files and run the relevant project harnesses/tests.
- Static tests do not prove speech behavior: clearly distinguish them from a live NVDA validation. Never restart NVDA automatically.
- ClassicSpeech runs on NVDA's bundled Python, which lacks some standard library modules; 1.05 failed to load because it imported `filecmp`. Runtime code may import only modules NVDA ships, which `tests/classic_speech_runtime_imports_harness.py` checks.
- Before a release candidate, run the project packaging and archive-member checks; report the exact output path and checksum.
- Every release carries its What's new in the `changelog` of `manifest.ini`, the field NVDA 2026.1 added and shows from the Add-on Store's **What's new** action. The changelog is the `## What's new` section of the release notes `RELEASE_NOTES` names in `scripts/package_addon.py`. Write that section for each release, point `RELEASE_NOTES` at the new notes, and run `python scripts/package_addon.py --sync-changelog`. Packaging refuses a missing or stale changelog, and a release version whose notes `RELEASE_NOTES` isn't (`tests/classic_speech_packaging_harness.py`). Keep the section user-facing, and use only what NVDA's Python-Markdown converts without extensions: headings, lists, emphasis, code and links, but no tables, fenced code blocks, `"""` or `%(`.

## Scratchpad and live validation

- Work in the Git checkout, not directly in the NVDA scratchpad.
- Deploy to scratchpad only when Tim explicitly requests a working/runtime build. Make a timestamped backup, compare source with deployed files, compile the deployed entry points, and do not restart NVDA automatically.
- Preserve the installed NVDA baseline. Scratchpad testing and installed-add-on testing must not be mixed in one trial.

## Git hygiene

- Check `git status` and the active branch before editing.
- Do not commit, push, rebase, force-push, or rewrite history unless Tim explicitly requests it.
- Keep unrelated working-tree changes untouched and report them separately.
- Do not place secrets, logs, runtime backups, or generated artifacts under version control.

## Information placement

- Put stable, repository-specific rules in this file.
- Put reusable cross-project procedures in a Hermes skill.
- Keep personal preferences, account details, and temporary task state out of this repository.
