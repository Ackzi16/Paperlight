"""Avoid an incompatible ICU DLL picked up from a build machine's Poppler PATH."""
from pathlib import Path
import os
import shutil
import pefile

root=Path(__file__).resolve().parent.parent
runtime=(root/'dist'/'Paperlight'/'_internal').resolve()
icu=runtime/'icuuc.dll'
if icu.exists():
    with pefile.PE(str(icu)) as binary:
        exports={row.name for row in binary.DIRECTORY_ENTRY_EXPORT.symbols}
    if b'ucnv_open' not in exports:
        # Qt uses the unversioned ICU API supplied by Windows 10/11. Some build
        # environments put Poppler's versioned ICU on PATH; it cannot satisfy Qt.
        system=Path(os.environ['SystemRoot'])/'System32'/'icuuc.dll'
        with pefile.PE(str(system)) as binary:
            assert any(row.name==b'ucnv_open' for row in binary.DIRECTORY_ENTRY_EXPORT.symbols)
        quarantine=root/'tmp'/'verification'/'quarantined-runtime'
        quarantine.mkdir(parents=True,exist_ok=True)
        for name in ['icuuc.dll','icudt78.dll']:
            candidate=(runtime/name).resolve()
            assert candidate.parent==runtime
            if candidate.exists():
                shutil.move(str(candidate),str(quarantine/name))
        print('Excluded incompatible Poppler ICU; Qt will use the Windows ICU API.')
