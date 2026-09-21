# ClassicSpeech 1.14

ClassicSpeech 1.14 lets ClassicSpeech's own messages be heard in full, and lets a speech and sound scheme replace the sounds NVDA itself plays.

Supported NVDA versions: 2025.1 through 2026.2.

## What's new

* **Give ClassicSpeech messages priority over NVDA speech** is a new option on the Misc page of General Settings. When it is checked, the messages ClassicSpeech speaks itself, such as the speech hook loaded message, Page ready and page summaries, are spoken right away, and NVDA's own speech can't cut them off. NVDA's speech follows them. Pressing a key still stops a message, as it stops any speech. The option is off by default.
* Speech and Sound Schemes can replace NVDA's own sounds. The new **NVDA sounds** category lists every sound NVDA plays from its waves folder, named after the event it reports: switching to browse mode or focus mode, auto-suggestions, spelling errors, a logged error, the screen curtain, Remote Access, and NVDA starting and exiting. Give one a WAV file, and NVDA plays yours instead while that scheme is active. Remove it, and NVDA's own sound comes back.
* Your sounds are kept in the scheme's folder, in `%APPDATA%\nvda\ClassicSpeech\Schemes`, and NVDA's own files are never changed. With no NVDA sounds in the active scheme, NVDA plays its sounds as it always has.
* NVDA plays its start sound before add-ons load. While your scheme has a sound for **NVDA starts**, ClassicSpeech turns off NVDA's **Play sounds when starting or exiting NVDA** option and plays the start and exit sounds itself. Removing that sound, or disabling, removing or resetting ClassicSpeech, turns the option back on.

## Details

### Give ClassicSpeech messages priority over NVDA speech

NVDA cuts off whatever is being spoken when something happens that it reports on its own: a new window comes to the front, the mouse moves over a new object, an application reports an event. ClassicSpeech's messages were cut off the same way. The speech hook loaded message is the clearest example: NVDA speaks it while add-ons load, and a moment later reports the focus, which cut the message off.

With the option checked, a ClassicSpeech message:

* is spoken at NVDA's highest speech priority, the one NVDA itself uses for messages that must be heard. It starts at once; speech it interrupts resumes after it, and speech NVDA starts while it plays waits for it;
* can't be cancelled by NVDA's own reactions to events until it has been spoken. The speech NVDA wanted to start instead is spoken after it;
* still stops when you press a key on the keyboard, a key on a braille display, or make a touch gesture, exactly as NVDA's speech does. NVDA exiting, and a configuration profile that loads another synthesizer, also stop it.

The messages are: the speech hook loaded message, Page ready and page summaries (automatic or with NVDA+Shift+U), speech history, the default button (NVDA+E), speech and sound scheme messages, the update and user guide messages, and your own browse mode, focus mode and Microsoft Edge notification messages. The object ClassicSpeech speaks for NVDA+Tab is not a message and speaks as before.

With the option cleared, which is the default, every message is spoken exactly as in 1.13.

### NVDA's own sounds in Speech and Sound Schemes

The **NVDA sounds** category is at the end of the Speech and Sound Schemes tree. Item details names the file NVDA plays for each event and the NVDA option that turns that sound on.

* NVDA starts (start.wav) and NVDA exits (exit.wav): Play sounds when starting or exiting NVDA, in NVDA's General settings.
* Switching to browse mode (browseMode.wav) and Switching to focus mode (focusMode.wav): Audio indication of focus and browse modes, in NVDA's Browse Mode settings.
* Auto-suggestions appear (suggestionsOpened.wav) and Auto-suggestions close (suggestionsClosed.wav): Play a sound when auto-suggestions appear, in NVDA's Object Presentation settings.
* Spelling or grammar error (textError.wav): Play sound for spelling errors while typing, in NVDA's Keyboard settings, and Spelling or grammar errors with Sound, in NVDA's Document Formatting settings.
* Error written to the NVDA log (error.wav): Play a sound for logged errors, in NVDA's Advanced settings.
* Screen curtain turned on (screenCurtainOn.wav) and Screen curtain turned off (screenCurtainOff.wav): Play sound when toggling Screen Curtain.
* Remote Access: connected to control another computer (connected.wav), ready to be controlled (controlled.wav), another computer joined (controlling.wav), disconnected (disconnected.wav), clipboard sent (clipboardPush.wav) and clipboard received (clipboardReceive.wav).

To replace a sound, select it, press **Play sound** to hear NVDA's own, press **Browse for sound...** and choose a WAV file, then press OK or Apply. The file is copied into the scheme's Sounds folder, as for every scheme sound, and only a sound in the Schemes folder replaces one of NVDA's.

* NVDA plays your sound only where it would play its own: if an NVDA option such as Audio indication of focus and browse modes is off, there is no sound for that event.
* If NVDA can't play your file, it plays its own sound instead.
* Turning schemes off, or choosing a scheme that doesn't replace a sound, brings NVDA's own sound back at once.
* These items are sounds, not speech: they have no voice, and they change nothing in what NVDA says.
* When another computer controls this one through Remote Access, NVDA sends it the sounds it plays by their file names. A sound your scheme plays instead is a file only this computer has, so the controlling computer doesn't hear it.

NVDA plays its start sound before any add-on loads, so ClassicSpeech can't replace it at that moment. While the active scheme has a sound for NVDA starts, ClassicSpeech turns off Play sounds when starting or exiting NVDA, records the value it had, and plays the start sound itself as soon as it loads, a moment later than NVDA would. When NVDA exits, or Windows signs out, ClassicSpeech plays the exit sound: yours if the scheme has one, otherwise NVDA's. It turns the option back on when the scheme no longer has a start sound, when schemes are turned off, and when you disable, remove or reset ClassicSpeech. If the option was already off, neither NVDA nor ClassicSpeech plays a start or exit sound.

A scheme with NVDA sounds keeps them when you export and import it.

## Installation

Use **Check for Updates...** in the ClassicSpeech menu (NVDA menu → Preferences → ClassicSpeech). Or download `ClassicSpeech-1.14.nvda-addon`, open it from Windows Explorer and accept NVDA's installation prompt. Restart NVDA when prompted. Your settings are kept.

## Verification

* Full local harness gate: every harness passes. Two new harnesses cover the new features. `tests/classic_speech_message_priority_harness.py` covers speaking with priority, holding off NVDA's automatic cancellations until a message has been spoken, key presses, braille and touch input, NVDA's exit and synthesizer changes still cancelling, the end of a message surviving ClassicSpeech's own speech processing, and that no ClassicSpeech message bypasses the option. `tests/classic_speech_nvda_sounds_harness.py` covers every sound in NVDA master's waves folder, each way NVDA names a sound, missing, unreadable and outside files, the start and exit sounds with NVDA's option, disabling, removing, updating and resetting ClassicSpeech, and the dialog's NVDA sound items.
* These changes have passed the automated tests but have not yet been tried live in NVDA.
