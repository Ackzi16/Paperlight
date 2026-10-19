import sys


def record_startup_error(error):
    import os
    from pathlib import Path
    from datetime import datetime,timezone
    log=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Paperlight'/'startup-error.log'
    log.parent.mkdir(parents=True,exist_ok=True)
    log.write_text(f'{datetime.now(timezone.utc).isoformat()} {type(error).__name__}: startup failed; document details omitted.\n',encoding='utf-8')


def attach_worker_pipes():
    # PyInstaller's windowed runtime sets Python stdio to None. QProcess still
    # supplies inherited Windows pipe handles; reopen those for the worker.
    if not getattr(sys,'frozen',False) or sys.platform!='win32':
        return
    import ctypes
    import msvcrt
    import os
    get_handle=ctypes.windll.kernel32.GetStdHandle
    get_handle.argtypes=[ctypes.c_uint32]
    get_handle.restype=ctypes.c_void_p
    for name,number,flags,mode in [('stdin',-10,os.O_RDONLY,'r'),
                                  ('stdout',-11,os.O_WRONLY,'w'),
                                  ('stderr',-12,os.O_WRONLY,'w')]:
        handle=get_handle(number)
        if handle and handle!=ctypes.c_void_p(-1).value:
            descriptor=msvcrt.open_osfhandle(handle,flags)
            setattr(sys,name,os.fdopen(descriptor,mode,encoding='utf-8',buffering=1))


def entry():
    if '--index' in sys.argv:
        attach_worker_pipes()
        from paperlight.worker import main
        return main()
    from paperlight.app import run
    args=sys.argv[1:]
    smoke=None
    if '--smoke' in args:
        i=args.index('--smoke')
        smoke=args[i+1]
        del args[i:i+2]
    return run(args[0] if args else None,smoke)


if __name__ == '__main__':
    try:
        code=entry()
    except Exception as exc:
        import traceback
        record_startup_error(exc)
        if sys.stderr:
            traceback.print_exc()
        code=1
    raise SystemExit(code)
