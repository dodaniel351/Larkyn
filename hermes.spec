# PyInstaller spec for Larkyn (onedir, windowed).
# Build:  .venv\Scripts\pyinstaller.exe hermes.spec --noconfirm
#
# CUDA DLLs from the nvidia-* pip wheels are bundled into <app>/cuda; the
# Whisper engine adds that folder to the DLL search path at runtime.

import os
import sys
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None
project = os.path.abspath(".")


def python_openssl_binaries():
    """Pin the interpreter's own OpenSSL DLLs.

    PyInstaller resolves _ssl.pyd's libssl/libcrypto dependencies by searching
    PATH, which can pick up an incompatible OpenSSL build from another tool and
    break `import ssl` at runtime ("specified procedure could not be found").
    """
    out = []
    dlls = os.path.join(sys.base_prefix, "DLLs")
    for name in ("libcrypto-3-x64.dll", "libssl-3-x64.dll",
                 "libcrypto-3.dll", "libssl-3.dll"):
        path = os.path.join(dlls, name)
        if os.path.exists(path):
            out.append((path, "."))
    return out


def nvidia_cuda_binaries():
    """(src, dest) pairs for every DLL under site-packages/nvidia/*/bin."""
    out = []
    try:
        import nvidia
    except Exception:
        return out
    for root in nvidia.__path__:
        for dirpath, _dirs, files in os.walk(root):
            if os.path.basename(dirpath).lower() == "bin":
                for f in files:
                    if f.lower().endswith(".dll"):
                        out.append((os.path.join(dirpath, f), "cuda"))
    return out


datas = [
    (os.path.join(project, "assets"), "assets"),
]
datas += collect_data_files("faster_whisper")   # silero VAD model
datas += collect_data_files("qfluentwidgets")   # qss / fluent resources

a = Analysis(
    ["run.py"],
    pathex=[project],
    binaries=python_openssl_binaries() + nvidia_cuda_binaries(),
    datas=datas,
    hiddenimports=[
        "hermes.llm.ollama_provider",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "jedi"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Larkyn",
    icon=os.path.join(project, "assets", "hermes.ico"),
    debug=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="Larkyn",
)
