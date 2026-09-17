#!/usr/bin/env python3
"""Open the verified candidate in disconnected demo mode; do not install it."""
from pathlib import Path
import json
import os
import subprocess
import time
import uuid
from build import PUBLIC, output_for, source_hashes

def main():
    output=output_for(PUBLIC,'public')
    receipt=json.loads((output/'BUILD.json').read_text())
    if receipt['publicSourceHashes']!=source_hashes(PUBLIC):
        raise RuntimeError('The candidate does not match current sources. Run scripts/build.sh first.')
    app=(output/receipt['app']).resolve()
    profile=json.loads((app/'Contents/Resources/RuntimeProfile.json').read_text())
    if profile['channel']!='public' or profile['bundleID']!='com.thalnova.aimonitor':
        raise RuntimeError('Not the public preview candidate')
    subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True,timeout=30)
    destination=PUBLIC.parent/'logs' if (PUBLIC.parent/'WORKSPACE.json').exists() else PUBLIC/'logs'
    destination.mkdir(parents=True,exist_ok=True)
    state=destination/('demo-ready-'+uuid.uuid4().hex+'.json')
    subprocess.run(['/usr/bin/open','-n',str(app),'--args','--demo','--demo-receipt',str(state)],check=True,timeout=30)
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        try:
            doc=json.loads(state.read_text())
            if doc.get('status')=='ready' and doc.get('windowVisible') is True:
                if doc.get('servicesEnabled') is not False or doc.get('apiServicesEnabled') is not False:
                    raise RuntimeError('Unexpected live-service preview')
                os.kill(doc['pid'],0)
                result={**doc,'app':str(app),'stateFile':str(state),'installationPerformed':False}
                (destination/'last-preview.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
                print(json.dumps(result,ensure_ascii=False,indent=2));return 0
        except (FileNotFoundError,json.JSONDecodeError):pass
        time.sleep(0.25)
    raise RuntimeError('No ready, visible demo window confirmed; inspect the application before retrying')
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:print('PREVIEW_FAILED:',error);raise SystemExit(1)
