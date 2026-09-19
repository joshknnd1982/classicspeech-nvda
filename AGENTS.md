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
- `installTasks.py` removes ClassicSpeech's settings only when the add-on is removed, never when a new version replaces it. It loads `nvda_settings_backup.py` on its own, so that module must not import other ClassicSpeech modules.
- Speech-path code must not walk `obj.parent` chains for the focus; use `_speech_core/focus_ancestry.py`, which reads NVDA's cached focus ancestors (`tests/classic_speech_latency_harness.py`).
- The token editor owns speech-token ordering and placement. Text Processing owns reporting/filtering transformations; do not move token-placement policy into it.
- `sequence_merger.py` was removed after an audit confirmed it had no active dependents. Do not reintroduce sequence-merging behavior without a defined, tested requirement.

## Accessibility and settings

- The target user is visually impaired. Prefer native NVDA controls, keyboard-complete workflows, stable labels, and screen-reader-friendly feedback.
- Follow existing settings-dialog transaction behavior: Apply, OK, Cancel, Close, reload, and external configuration save must leave persisted and runtime state coherent.
- Do not replace an NVDA accessibility-enhanced control with a raw wx equivalent without explicit approval.
- `doc/en/readme.html` is the user guide NVDA opens from the Add-on Store's Help action. Update it with every user-facing change; `tests/classic_speech_user_guide_harness.py` checks that it covers every command, default gesture and settings page.

## Validation

- Read the relevant specification and trace existing code/tests before editing.
- Add or extend focused harness coverage before changing subtle speech-filter, settings, or routing behavior.
- At minimum, compile changed Python files and run the relevant project harnesses/tests.
- Static tests do not prove speech behavior: clearly distinguish them from a live NVDA validation. Never restart NVDA automatically.
- ClassicSpeech runs on NVDA's bundled Python, which lacks some standard library modules; 1.05 failed to load because it imported `filecmp`. Runtime code may import only modules NVDA ships, which `tests/classic_speech_runtime_imports_harness.py` checks.
- Before a release candidate, run the project packaging and archive-member checks; report the exact output path and checksum.

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
