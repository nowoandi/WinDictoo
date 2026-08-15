# WinDictoo

This page: 🇬🇧 **English** | 🇷🇺 [Русский](README.ru.md)

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D6)
![Interface: 8 languages](https://img.shields.io/badge/interface-8%20languages-brightgreen)

**Interface languages:** Русский · English · Deutsch · Français · Español ·
中文 · Türkçe · Հայերեն.
**Speech recognition:** Russian (GigaAM v3), 25 European languages
(Parakeet v3), or 99 languages with Whisper — see
[Recognition models](#recognition-models).

**Local voice dictation for Windows.** Hold a hotkey, speak, release —
the recognized text is inserted into the focused field. Your voice never
leaves the computer.

This is a Windows-native reimagining of [VoxLocal](https://github.com/romarayt/VoxLocal)
(the original is macOS-only): same idea, built on the Windows stack.

![WinDictoo main window](assets/screenshots/main-window-en.png)

Several color themes to choose from (the swatch in the header) — dark,
geek-black, light-green, light-blue, dusty rose, chocolate & gold.

## Install

**[⬇ Download the installer](https://github.com/nowoandi/WinDictoo/releases/latest)** —
on that page, under **Assets**, take the file ending in
**`-Installer.exe`** and double-click it: a minute later WinDictoo is in
your Start menu and on the desktop. No terminal, no admin rights, no
Python — everything is bundled. Updates install the same way on top (or
right from the app: Settings → Privacy → "Check for updates").

### Windows will show a warning — that's expected

The first time you run the downloaded file, a blue **"Windows protected
your PC"** dialog appears. Click the small **More info** link under the
text, then the **Run anyway** button.

It is not a virus and not a bug. Windows greets **every** program whose
author hasn't bought a publisher certificate (roughly €300–500 a year)
this way. WinDictoo doesn't buy one — the source is open, so anyone can
see what's inside. You'll see the warning **once per computer**: later
updates are installed by the app itself (Settings → Privacy → "Check for
updates") and never show this dialog.

The same page also has a no-install variant, if you prefer:

- **`WinDictoo-<version>-win64.zip`** — the same app as a folder: unzip
  and run the `WinDictoo.exe` inside.

The single-file portable build is no longer published. It unpacked its
whole ~108 MB into a temporary folder on every launch, which made starting
up slow and jerky, and it was easy to mistake for the installer.

The only later download is the recognition model on first run — from
216 MB (GigaAM v3) to 3 GB (Whisper large-v3), depending on your pick.

## What it does

- **System-tray app** with a global hotkey — **Ctrl + Space** by default:
  two keys, comfortable to hold with one hand (Alt+Space is taken by the
  Windows system menu and isn't used):
  - *hold*: records while the keys are held; transcribes on release;
  - *toggle*: press once to start, press again to stop.
- **Local recognition**, CPU-only with int8 quantization, on either of two
  engines: [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
  (CTranslate2) for the Whisper sizes, or
  [onnx-asr](https://github.com/istupakov/onnx-asr) for **GigaAM v3**
  (Russian, and much better at it than Whisper `small`) and **Parakeet v3**
  (25 European languages). See "Recognition models" below. The language list
  includes auto-detect,
  Russian, English, German, French, Spanish, Chinese, Turkish, and Armenian;
  the list is easy to extend to any language Whisper understands. On first
  run the language defaults to the Windows system language — change it
  freely afterwards in Settings, or with the quick-switch button right in
  the main window (see "Settings" below).
- **Optional text refinement** (punctuation, casing, filler words) via a
  **local Ollama** instance. If it's unavailable or returns nonsense, the
  raw transcript is used instead — dictation never breaks.
- **Insertion into any application**: clipboard + synthetic Ctrl+V, with the
  previous clipboard contents restored afterwards (unless another app
  changed them in the meantime).
- `Esc` cancels an active dictation.

## Privacy model

- Audio is captured into RAM, recognized locally, and **never saved
  anywhere** — no temporary WAV files touch disk.
- **No cloud APIs, keys, or accounts.** The only network request is a
  one-time download of the Whisper model from Hugging Face on first run.
- Ollama is only ever contacted over loopback (`127.0.0.1` / `localhost` /
  `::1`); external addresses are rejected and HTTP redirects are refused.
  Models Ollama tags `:cloud` are refused too — those run on Ollama's own
  servers, so the address check alone would pass while the transcript still
  left the machine. Picking one disables refinement (the raw transcript is
  used) and says so in Settings → Refinement.
- **No analytics, telemetry, or tracking.**
- The log never contains audio, dictation text, or clipboard contents.

## Requirements

- Windows 10/11; 216 MB to 3 GB for the recognition model, depending on
  which one you pick (downloaded automatically on first run).
- Optional: [Ollama](https://ollama.com) with an instruct model (e.g.
  `ollama pull qwen2.5:3b`).
- Python 3.13+ and [uv](https://docs.astral.sh/uv/) — **only for building
  from source**. The ready builds from
  [Releases](https://github.com/nowoandi/WinDictoo/releases/latest) need
  neither.

## Running it

WinDictoo is an ordinary windowed application. After installing, launch it
by **double-clicking** the **WinDictoo** shortcut on the desktop or in the
Start menu — a window opens with status, a test button, and settings. No
console required.

First run: hold **Ctrl + Space**, speak, release — the text lands in the
focused field. The window can be minimized to the tray (the mic icon); from
the tray you can reopen it, open settings, or quit.

## Building the app (.exe)

The prebuilt `dist\WinDictoo\WinDictoo.exe` is self-contained (Whisper
included, ~260 MB). To rebuild from scratch:

```powershell
uv sync                                                   # dependencies
uv run python packaging/make_icon.py                      # icon
uv run pyinstaller packaging/WinDictoo.spec --noconfirm --distpath dist --workpath build
powershell -ExecutionPolicy Bypass -File packaging/install_shortcuts.ps1  # shortcuts
```

The first transcription downloads the selected recognition model to
`%LOCALAPPDATA%\WinDictoo\models`.

### Packaging a release

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" /DAppVersion=1.8.0 packaging\WinDictoo-Setup.iss
tar -a -c -f dist\WinDictoo-1.8.0-win64.zip -C dist WinDictoo
```

Use `tar` for the zip, **not** `Compress-Archive`. Windows PowerShell 5.1
runs on .NET Framework, where both `Compress-Archive` and
`ZipFile.CreateFromDirectory` write entry names with backslashes. The ZIP
format requires forward slashes, and extractors handed backslashes often
produce a flat pile of oddly-named files instead of a folder — with the
`.exe` nowhere to be seen.

Publish exactly two assets: the installer and that zip. No portable `.exe`
— see the note in `packaging/WinDictoo-Setup.iss` for why a second `.exe`
breaks updating for old versions.

### Running from source (for development)

```powershell
uv run windictoo          # with a console and logs
uv run windictoo -v       # verbose logging
```

## First run

On first launch a **setup wizard** opens: welcome → microphone check (with
a level indicator) → model selection and download → hotkey → test
dictation → done. You can reopen it any time from **Settings → Privacy →
"Show the setup wizard again"**.

## How it works

- **Real insertion** — via the hotkey: place the cursor in a field (Word, a
  browser, a chat app), hold **Ctrl + Space**, speak, release — the text is
  typed right where the cursor was. The WinDictoo window itself can be
  minimized to the tray while this happens.
- The **🎤 Test** button in the window only **shows** the recognized text in
  the window itself (to check the microphone and model) — it never
  inserts anything.

## Settings

The interface uses CustomTkinter: a round mic indicator with an animated
level equalizer, rounded cards, and accent buttons.

The **⋮** button in the window opens the tabs:

- **General** — hotkey (capture by pressing it), hold/toggle mode, key
  suppression, insertion method (type into field / clipboard+Ctrl+V),
  autostart, color theme, **interface language**.
- **Recognition** — recognition model, speech language, CPU thread count, a
  "Load model now" button.
- **Refinement** — enabling Ollama, its address, model, a "Check" button.
- **Privacy** — what and how data is handled, the log, the setup wizard,
  about.

Interface language and speech-recognition language are independent
settings: the former changes the app's own text (buttons, tabs, dialogs —
across 8 languages: ru/en/de/fr/es/zh/tr/hy), the latter only changes what
language Whisper listens for. The recognition language can also be switched
quickly without opening Settings at all — via the language-code button
(**EN**/**RU**/…) next to "Copy" above the recognized text.

The default insertion method is **typing into the focused field**
(`SendInput`, doesn't touch the clipboard). If an application doesn't
accept it, switch to **clipboard+Ctrl+V**.

The hotkey's main key is **suppressed** and never reaches the focused app,
so Space in `Ctrl+Space` doesn't move the caret or type spaces while you're
dictating. If that gets in the way somewhere, uncheck "Don't pass the key
to the app" in Settings → General.

Changes apply immediately. Everything is stored in
`%LOCALAPPDATA%\WinDictoo\config.json` (which can be hand-edited too).

## Recognition models

Two engines are available, and the picker in **Settings → Recognition**
mixes them into one list.

| Model | Size | Languages | Speed |
|---|---|---|---|
| **GigaAM v3** | ~216 MB | Russian only | ~20× real time |
| **Parakeet v3** | ~639 MB | 25 European (incl. ru, en, de, fr, es) | ~15× real time |
| Whisper `tiny` | ~75 MB | 99 | fastest of the Whispers, rough |
| Whisper `base` | ~145 MB | 99 | fast |
| Whisper `small` | ~485 MB | 99 | ~3× real time, balanced |
| Whisper `medium` | ~1.5 GB | 99 | slower, more accurate |
| Whisper `large-v3` | ~3 GB | 99 | most accurate, heavy on CPU |

Speeds measured on a warm cache, CPU only, 4 threads, against the same
3.2-second Russian phrase; all three of GigaAM, Parakeet and Whisper `small`
transcribed it correctly.

**GigaAM v3** and **Parakeet v3** run on onnxruntime (via
[onnx-asr](https://github.com/istupakov/onnx-asr)) rather than Whisper, and
both produce punctuation and capitalisation of their own. Neither takes a
language setting: GigaAM is Russian-only, Parakeet detects the language
itself, so the language picker greys out with a note when one of them is
selected. If you dictate in Russian, GigaAM is the best choice here — it is
less than half the size of Whisper `small` and several times faster.

Whisper remains the only option for the languages the other two don't cover
(Chinese, Turkish, Armenian, and 70-odd more), and the only one where you can
force a specific language.

## The microphone

Opening a capture device costs 100–400 ms, which is exactly long enough to
swallow the first syllable of a dictation. So the stream is opened once and
kept running: while you are not dictating, the last **400 ms** of audio sits
in a small ring buffer, and pressing the hotkey starts the recording from
*there* — a word begun a moment early is already captured. The same happens
at the other end: recording continues for **200 ms** after the key comes up,
for the common habit of releasing it while still finishing the word.

**Settings → General → "When the microphone is open"** decides how long the
stream lingers:

- **Half a minute after** (default) — released 30 s after a dictation, so
  back-to-back phrases start instantly.
- **Always** — fastest possible start, but Windows shows the
  "microphone in use" indicator permanently and Bluetooth headsets switch to
  their headset profile, which makes music through them sound worse.
- **Only while dictating** — the microphone is left completely alone between
  dictations, at the cost of that 100–400 ms and a possibly clipped first
  word.

None of this changes the privacy model: idle audio never leaves the ring
buffer in RAM, is overwritten continuously, and is discarded when the stream
closes.

## Development

```powershell
uv run pytest -m "not integration"   # fast unit tests
uv run pytest -m integration         # real Whisper run against synthesized speech
uv run python tests/smoke_launch.py  # headless check of tray, hotkey, and a session
uv run python tests/smoke_type.py    # typing into a field (needs an interactive desktop)
```

## Known limitations

- Recognition happens after recording stops (no streaming result).
- Insertion via synthetic Ctrl+V — in the rare application that blocks
  synthetic input, the text stays in the clipboard (paste it manually).
- CPU-only: `large-v3` can be slow on weaker machines; use `small` instead.
- Password fields: insertion behaves like a normal Ctrl+V — the app can't
  tell protected fields apart (unlike the macOS original).

## License

MIT — see [LICENSE](LICENSE). Use, modify, and distribute freely, including
commercially.

The recognition models are downloaded at run time and carry their own terms:

- OpenAI **Whisper** — MIT.
- Sber **GigaAM v3** — MIT
  ([ONNX build](https://huggingface.co/istupakov/gigaam-v3-onnx)).
- NVIDIA **Parakeet TDT 0.6B v3** — CC-BY-4.0
  ([model card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)),
  commercial use permitted with attribution.

Some ideas here — the persistent microphone with a pre-roll window, and
offering non-Whisper engines at all — were taken from
[Handy](https://github.com/cjpais/handy) (MIT), a cross-platform
speech-to-text app in Rust.
