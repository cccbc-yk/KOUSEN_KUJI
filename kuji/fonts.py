# fonts/ のフォントを、PC にインストールせずにこのアプリの中だけで使えるようにする
import ctypes
import sys


def load_fonts(directory):
    paths = sorted(p for p in directory.glob("*") if p.suffix.lower() in (".ttf", ".otf"))
    for path in paths:
        try:
            if sys.platform == "darwin":
                _load_mac(path)
            elif sys.platform == "win32":
                ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, 0)  # 0x10 = このプロセスだけ
        except OSError as e:
            print(f"フォントが読めません: {path.name} ({e})", file=sys.stderr)


def _load_mac(path):
    cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    ct = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreText.framework/CoreText")
    cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
    cf.CFURLCreateFromFileSystemRepresentation.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long,
                                                          ctypes.c_bool]
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
    ct.CTFontManagerRegisterFontsForURL.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
    raw = str(path).encode("utf-8")
    url = cf.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
    try:
        ct.CTFontManagerRegisterFontsForURL(url, 1, None)  # 1 = このプロセスだけ
    finally:
        cf.CFRelease(url)
