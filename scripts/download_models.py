"""Fetch exact release assets and record SHA-256 provenance. No model substitution."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'weights'
SOURCES = {
    'Good-Tennis': ['tennis-ball.pt', 'yolo11s-pose.pt',
                    'yolox_nano_8xb8-300e_humanart-40f6f0d0.onnx',
                    'rtmpose-s_simcc-body7_pt-body7_420e-256x192-acd4a1ef_20230504.onnx',
                    'rtmo-s_8xb32-600e_body7-640x640-dac2bf74_20231211.onnx'],
    'Good-Badminton': ['yolo11s-ball.pt', 'yolo11n-pose.pt'],
}

def main():
    TARGET.mkdir(exist_ok=True)
    manifest = []
    for repo, names in SOURCES.items():
        request = urllib.request.Request(f'https://api.github.com/repos/yo-WASSUP/{repo}/releases/tags/v0.1.0', headers={'User-Agent': 'Racket-Intelligence'})
        with urllib.request.urlopen(request, timeout=30) as response:
            release = json.load(response)
        assets = {a['name']: a for a in release['assets']}
        for name in names:
            asset = assets[name]
            destination = TARGET / name
            if not destination.exists() or destination.stat().st_size != asset['size']:
                print(f'Downloading {name}', flush=True)
                temporary = destination.with_suffix(destination.suffix + '.part')
                urllib.request.urlretrieve(asset['browser_download_url'], temporary)
                if temporary.stat().st_size != asset['size']:
                    raise RuntimeError(f'Incomplete download: {name}')
                temporary.replace(destination)
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            expected = asset.get('digest')
            if expected and expected != 'sha256:' + digest:
                raise RuntimeError(f'Checksum mismatch: {name}')
            manifest.append({'file': name, 'sha256': digest, 'source': asset['browser_download_url'], 'release': release['tag_name'], 'bytes': asset['size']})
    (TARGET / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('All seven reference assets are ready.', flush=True)

if __name__ == '__main__':
    main()
