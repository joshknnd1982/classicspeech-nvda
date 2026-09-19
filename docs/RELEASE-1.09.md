# ClassicSpeech 1.09

ClassicSpeech 1.09 fixes Reset All ClassicSpeech Settings, which froze NVDA.

Supported NVDA versions: 2025.1 through 2026.2.

## Fixes

### Reset All ClassicSpeech Settings no longer freezes NVDA

Choosing **Reset All ClassicSpeech Settings...** in the ClassicSpeech menu froze NVDA. It stopped speaking, including the question it was asking, and had to be restarted, and nothing was reset. The reset opened its question inside NVDA's core event queue, which does not run again until the question is answered.

Now the question opens the way NVDA opens its own dialogs, so NVDA keeps running and reads it:

* A Yes/No dialog asks "Do you really want to reset all ClassicSpeech settings?" and explains what a reset deletes.
* **Yes** resets. **No**, the default, keeps everything as it is.

The **Resets all ClassicSpeech settings and restores the NVDA settings it changed** command had the same problem and is fixed too. So is one message of **Check for Updates...**, shown only by a copy of ClassicSpeech that doesn't know where its updates are published.

## Installation

Use **Check for Updates...** in the ClassicSpeech menu (NVDA menu → Preferences → ClassicSpeech). Or download `ClassicSpeech-1.09.nvda-addon`, open it from Windows Explorer and accept NVDA's installation prompt. Restart NVDA when prompted. Your settings are kept.

## Verification

* Full local harness gate: every harness passes. New tests check that the reset and update commands never open a dialog inside NVDA's core event queue, and they fail on the 1.08 code.
* The cause was confirmed in the NVDA 2026.2 log: NVDA's main thread was waiting in the reset's message box inside NVDA's core event queue, and NVDA's watchdog reported the freeze.
* Every module ClassicSpeech imports was checked against the `library.zip` of the NVDA 2026.2 installed on the test computer.
* Live NVDA testing has not been done yet. Please choose Reset All ClassicSpeech Settings: NVDA should read the question. Try No first (nothing changes), then Yes.
