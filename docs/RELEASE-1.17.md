# ClassicSpeech 1.17

ClassicSpeech 1.17 makes NVDA say "unread" again as you move to an unread message in Microsoft Outlook.

Supported NVDA versions: 2025.1 through 2026.2.

## What's new

* In Microsoft Outlook's message list, an unread message starts with "unread" again as you move to it, as it does in NVDA without ClassicSpeech. With ClassicSpeech, NVDA read the message without it, and said "unread" only when it read the whole message a second time, which you seldom heard because you had already moved on.
* The same goes for everything else NVDA gets from Outlook about a message: "replied", "replied all", "forwarded", "has attachment", "high importance", "low importance" and "meeting request".
* NVDA no longer reads a message a second time just to add "unread".

## Details

### What you hear

Arrowing through the Inbox, or pressing Delete to go to the next message:

* 1.16: "From Contoso News, Subject Morning headlines, Received 6:31 AM, Size 97 KB, row 214, 214 of 230", then, if you waited, "unread From Contoso News, Subject Morning headlines, ..." once more.
* 1.17: "unread From Contoso News, Subject Morning headlines, Received 6:31 AM, Size 97 KB, row 214, 214 of 230".

### Why it happened

NVDA gets a message's status, such as "unread", by asking Outlook about the selected message as it builds the announcement, and leaves the status out, without a word, when Outlook doesn't answer. Right after the selection moves, Outlook doesn't always answer. In the log a tester sent, with ClassicSpeech and the JAWS Migration Assistant running, NVDA asked at that moment for every message, and only Outlook's next name change, about 80 ms later, brought "unread", in a second reading of the whole message. Without the add-ons, NVDA asked a little sooner and usually got an answer, though its own log misses "unread" now and then too.

### What ClassicSpeech does now

For the message you move to, ClassicSpeech waits for Outlook's answer before NVDA builds the announcement, for up to three tenths of a second. In the tester's log Outlook answered well within that. If Outlook doesn't answer in time, you hear the message as before, without its status, and ClassicSpeech doesn't wait again until Outlook answers, so a busy Outlook doesn't slow every message down. There is nothing to set. The user guide has a new section, Microsoft Outlook's message list.

NVDA's debug log now says how long Outlook took to answer, or that it didn't answer, and why.

## Installation

Use **Check for Updates...** in the ClassicSpeech menu (NVDA menu → Preferences → ClassicSpeech). Or download `ClassicSpeech-1.17.nvda-addon`, open it from Windows Explorer and accept NVDA's installation prompt. Restart NVDA when prompted. Your settings are kept.

## Verification

* Full local harness gate: every harness passes. `tests/classic_speech_outlook_messages_harness.py` builds a message row the way NVDA does, with NVDA's own property caching from `baseObject.py` and NVDA 2026.2's way of asking Outlook, and a fake Outlook that turns calls away for a while. Without the fix it fails with exactly what the log shows: the announcement without "unread", then a second reading with it.
* It also checks the limit and the pause after it, that only the focused message waits, that nothing waits before NVDA has Outlook's object model, Outlook Extended's rows, and that a name built on another thread is never kept for NVDA's next announcement.
* These changes have passed the automated tests but have not yet been tried live in NVDA with Outlook.
