from pathlib import Path
import zipfile

root=Path(__file__).resolve().parent.parent
with zipfile.ZipFile(root/'dist'/'paperlight-source.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for name in ['main.py','requirements.txt','requirements-dev.txt','LICENSE','THIRD_PARTY_NOTICES.md','README.md','CONTEXT.md']:
        archive.write(root/name,name)
    for folder in ['paperlight','tools','tests','packaging','docs','assets','.scratch/preview/issues']:
        for path in (root/folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                archive.write(path,path.relative_to(root))
