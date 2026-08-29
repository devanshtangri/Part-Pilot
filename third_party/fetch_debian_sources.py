#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, pathlib, urllib.request

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--output')
    ap.add_argument('--check-only', action='store_true')
    args=ap.parse_args()
    if not args.check_only and not args.output: raise SystemExit('--output is required unless --check-only is used')
    out=pathlib.Path(args.output) if args.output else None
    if out is not None: out.mkdir(parents=True, exist_ok=True)
    with open(args.manifest, newline='', encoding='utf-8') as f:
        rows=list(csv.DictReader(f, delimiter='\t'))
    if not rows: raise SystemExit('empty source manifest')
    seen=set()
    for row in rows:
        required={'url','filename','size','sha256'}
        if set(row) != required: raise SystemExit('unexpected source manifest columns')
        if row['filename'] in seen: raise SystemExit(f"duplicate source filename: {row['filename']}")
        seen.add(row['filename'])
        if len(row['sha256']) != 64 or any(c not in '0123456789abcdef' for c in row['sha256']): raise SystemExit(f"invalid sha256: {row['filename']}")
        if int(row['size']) <= 0: raise SystemExit(f"invalid size: {row['filename']}")
        if args.check_only: continue
        name=row['filename']; expected_size=int(row['size']); expected_sha=row['sha256']
        assert out is not None
        target=out/name; tmp=target.with_suffix(target.suffix+'.tmp')
        h=hashlib.sha256(); size=0
        with urllib.request.urlopen(row['url'], timeout=120) as r, open(tmp,'wb') as w:
            while True:
                chunk=r.read(1024*1024)
                if not chunk: break
                w.write(chunk); h.update(chunk); size += len(chunk)
        if size != expected_size or h.hexdigest() != expected_sha:
            tmp.unlink(missing_ok=True); raise SystemExit(f'source verification failed: {name}')
        tmp.replace(target)
    return 0
if __name__ == '__main__': raise SystemExit(main())
