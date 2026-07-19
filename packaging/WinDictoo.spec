# PyInstaller spec for WinDictoo. Build: uv run pyinstaller packaging/WinDictoo.spec
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
# faster-whisper pulls native ctranslate2 + onnxruntime + tokenizers assets
# that PyInstaller does not discover automatically.
for pkg in ("faster_whisper", "ctranslate2", "onnxruntime", "tokenizers", "av",
            "customtkinter", "darkdetect"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += ["pystray._win32", "PIL._tkinter_finder", "hf_xet"]

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=["torch", "tensorflow", "matplotlib"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WinDictoo",
    console=False,          # windowed: no console
    icon="../assets/windictoo.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="WinDictoo",
)
