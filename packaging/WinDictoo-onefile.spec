# Single-file build: one portable WinDictoo.exe (no install, no folder).
# Build: uv run pyinstaller packaging/WinDictoo-onefile.spec --noconfirm --distpath ../dist_onefile --workpath ../build_onefile
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for pkg in ("faster_whisper", "ctranslate2", "onnxruntime", "tokenizers", "av",
            "customtkinter", "darkdetect"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += ["pystray._win32", "PIL._tkinter_finder"]

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

# Everything (scripts + binaries + datas) goes into one EXE → single file.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WinDictoo",
    console=False,          # windowed
    icon="../assets/windictoo.ico",
    upx=False,
    runtime_tmpdir=None,
)
