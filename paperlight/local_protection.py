"""Windows current-user DPAPI storage; no plaintext fallback."""
import ctypes
from ctypes import wintypes
import os

MAGIC = b'Paperlight-DPAPI-v1\x00'
MAX_BLOB = 32*1024*1024


class Blob(ctypes.Structure):
    _fields_ = [('length',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]


def _blob(data):
    buffer = ctypes.create_string_buffer(data)
    return Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte))),buffer


def _transform(data, purpose, decrypt=False):
    if os.name != 'nt':
        raise OSError('Windows data protection is required for local storage.')
    if not isinstance(data,bytes) or len(data)>MAX_BLOB:
        raise ValueError('Local protected data exceeds the supported size.')
    crypt32 = ctypes.WinDLL('crypt32.dll',use_last_error=True,winmode=0x00000800)
    kernel32 = ctypes.WinDLL('kernel32.dll',use_last_error=True,winmode=0x00000800)
    source,source_buffer = _blob(data)
    entropy,entropy_buffer = _blob(b'Paperlight/'+purpose.encode('ascii'))
    output = Blob()
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),
                         ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source),None,ctypes.byref(entropy),None,None,1,ctypes.byref(output)):
        raise OSError('Windows data protection could not process local data.')
    try:
        return ctypes.string_at(output.data,output.length)
    finally:
        if output.data:
            ctypes.memset(output.data,0,output.length)
            kernel32.LocalFree(output.data)


def protect(data, purpose):
    return MAGIC+_transform(data,purpose)


def unprotect(data, purpose):
    if not data.startswith(MAGIC):
        raise ValueError('Local data is not protected by Paperlight.')
    return _transform(data[len(MAGIC):],purpose,decrypt=True)
