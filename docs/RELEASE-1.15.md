# ClassicSpeech 1.15

ClassicSpeech 1.15 makes NVDA+E, and the "default" that focus speech adds, name a dialog's real default button: the button Enter presses after you change something in one of the dialog's other controls.

Supported NVDA versions: 2025.1 through 2026.2.

## What's new

* **NVDA+E** names the dialog's real default button, even while focus is on another button. On Cancel in a file dialog you now hear "Default button Open", no longer "Default button Cancel".
* In NVDA's settings dialogs, NVDA+E says OK, which Enter presses from any control. It used to name a button such as **Change...** once Tab had passed over it.
* The Open and Save As dialogs of LibreOffice, Notepad and most other programs report their default button, including a split button such as **Open**, which used to give "No default button". So do message boxes, property sheets and other standard Windows dialogs.
* ClassicSpeech also finds the default button in other programs' dialogs, such as LibreOffice's own dialogs and Microsoft Office's, and in web forms: the button Enter presses in a form's edit fields.
* Some programs make whichever button has focus their default. There, ClassicSpeech remembers the dialog's default button from when focus was in another control. If it can't know, you hear, for example, "No default button known. Enter presses Cancel".
* When neither Windows nor the program reports a default button, ClassicSpeech looks at the dialog's buttons on the screen, as a sighted person would. If exactly one button is filled or outlined in the accent color, you hear, for example, "Default button Save, by appearance". While NVDA's Screen Curtain is on, ClassicSpeech can't see the buttons and asks you to turn the Screen Curtain off.
* With **Announce default button in dialogs** checked, focus speech adds "default" only for the dialog's real default button, now also a split button ("Open, default, split button"), and never for a button that is the default only while it has focus.

## Details

### What the default button is

The default button is the one Enter presses after you type in an edit field, move a slider or check a box in a dialog. Pressing Enter while focus is on a button still presses that button; NVDA+E tells you what Enter does from the dialog's other controls.

1.14 and earlier reported whichever button had focus when you pressed NVDA+E on a button. They also remembered the first answer for the whole dialog, so a wrong answer stayed until the dialog closed.

### NVDA's settings dialogs

NVDA's settings dialogs press OK when you press Enter in any of their controls. ClassicSpeech now reports OK there, wherever focus is. In other NVDA and ClassicSpeech dialogs it reports the button the dialog itself names as its default. The wx toolkit NVDA is built with treats a focused button as the default for as long as it has focus, and 1.14 took that button for the dialog's default: after Tab passed over **Change...** on the Speech page, NVDA+E said "Default button Change..." from the pitch slider.

### Standard Windows dialogs

Open and Save As, message boxes, property sheets and most classic Windows dialogs keep their default button themselves, and Windows tells ClassicSpeech which one it is whatever has focus. The Open button of a file dialog is often a split button, with a menu of other ways to open the file; it counts as a button now.

### Other programs

Many programs make the focused button the default for as long as it has focus: programs built with Windows Forms, wxWidgets, Delphi or Qt, and Microsoft Office's dialogs. While you are on another button, the dialog's own default can't be read. ClassicSpeech remembers it from when focus was in another control of the dialog. If focus has only been on buttons since the dialog opened, NVDA+E says which button Enter presses now, for example "No default button known. Enter presses Cancel". Move to an edit field or another control and press NVDA+E again.

LibreOffice's own dialogs, and web pages, report their default button whatever has focus. In a web form, the default button is the button Enter presses in the form's edit fields, usually its first submit button; ClassicSpeech finds it when the browser reports it.

### By appearance

Some dialogs, such as the ones in many Windows 11 apps and web pages, don't report a default button at all, but draw it differently: filled with the accent color, or with an accent-colored border. When nothing else names a default button, NVDA+E compares the dialog's buttons on the screen and names one only if it alone is colored while the others are gray, white or black: "Default button Save, by appearance".

* A colored border counts only while focus is not on a button, because Windows also draws the focused button with one.
* A button under the mouse pointer is never chosen, because pointing at a button can color it too.
* Unavailable buttons and a dialog behind another window are left out.
* ClassicSpeech only compares the colors; nothing is saved.
* The check needs the dialog on the screen. While NVDA's Screen Curtain is on, you hear "No default button found. Turn off Screen Curtain so ClassicSpeech can check how the buttons look." The Screen Curtain is turned on and off with NVDA+Control+Escape, or on the Privacy and Security page of NVDA's settings.
* Focus speech never uses this check.

### Announce default button in dialogs

With this option checked on the Misc page, focus speech says "default" only for the button NVDA+E would name, and only when ClassicSpeech knows it for sure. A split button is announced as "Open, default, split button". The word "default" can now be translated.

## Installation

Use **Check for Updates...** in the ClassicSpeech menu (NVDA menu → Preferences → ClassicSpeech). Or download `ClassicSpeech-1.15.nvda-addon`, open it from Windows Explorer and accept NVDA's installation prompt. Restart NVDA when prompted. Your settings are kept.

## Verification

* Full local harness gate: every harness passes. The new `tests/classic_speech_default_button_harness.py` covers NVDA's settings dialogs and other wx dialogs, the Windows file dialog with its split Open button, property sheets and nested dialogs, programs that give the focused button the default, LibreOffice, Qt, Office, UI Automation and web form dialogs, the appearance check, and the Screen Curtain message. On Windows it also checks, with a real dialog that is never shown, that Windows keeps naming the dialog's default button while another button has focus.
* These changes have passed the automated tests but have not yet been tried live in NVDA.
