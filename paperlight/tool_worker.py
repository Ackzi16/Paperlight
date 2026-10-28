"""One-job PDF toolbox process. Paths and passwords arrive over stdin."""
import contextlib,json,os,sys
import pymupdf as f
from .tool_engine import execute

def main():
    protocol=sys.stdout
    def emit(row):print(json.dumps(row,ensure_ascii=True),file=protocol,flush=True)
    try:
        line=sys.stdin.readline(2*1024*1024)
        if not line.endswith('\n'):raise ValueError()
        with open(os.devnull,'w',encoding='utf-8') as diagnostics:
            f.set_messages(stream=diagnostics);f.set_log(stream=diagnostics)
            f.TOOLS.mupdf_display_errors(False);f.TOOLS.mupdf_display_warnings(False)
            with contextlib.redirect_stdout(diagnostics),contextlib.redirect_stderr(diagnostics):execute(json.loads(line),emit)
        return 0
    except Exception:
        emit(dict(kind='fatal',message='The toolbox job could not be started. Check the inputs and options.'))
        return 1
