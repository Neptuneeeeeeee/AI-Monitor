"""Read the build-pinned profile, never infer an edition from shell state."""
import json
import os
from pathlib import Path

def load_profile():
    here = Path(__file__).resolve().parent
    bundled = here / 'runtime.json'
    path = bundled if bundled.is_file() else here.parent / 'Config/profile.json'
    doc = json.loads(path.read_text())
    channel = doc.get('channel')
    suffix = '' if channel == 'public' else '.local'
    name = 'AI Monitor' + ('' if channel == 'public' else ' Local')
    if (channel not in ('public', 'local') or doc.get('schema') != 1
            or doc.get('bundleID') != 'com.thalnova.aimonitor' + suffix
            or doc.get('dataDirectoryName') != name
            or (channel == 'public' and doc.get('experimentalModules'))):
        raise RuntimeError('Invalid or cross-edition collector profile')
    return doc

PROFILE = load_profile()
KEYCHAIN_PREFIX = PROFILE['bundleID'] + '.'
HOME = Path.home()
SUPPORT = HOME / 'Library/Application Support' / PROFILE['dataDirectoryName']
# Only fixture/test runners may redirect storage. Reject production directories.
if os.environ.get('MONITOR_TEST_MODE') == '1':
    override = os.environ.get('MONITOR_DATA_DIR')
    if override:
        candidate = Path(override).expanduser().resolve()
        production = [HOME/'Library/Application Support'/n for n in
                      ('Monitor','AI Monitor','AI Monitor Local','Thalnova AI Monitor','Thalnova AI Monitor Local')]
        if not candidate.is_absolute() or any(candidate == p or p in candidate.parents for p in production):
            raise RuntimeError('Tests cannot target production storage')
        SUPPORT = candidate
elif os.environ.get('MONITOR_DATA_DIR'):
    raise RuntimeError('MONITOR_DATA_DIR is only supported in explicit test mode')
