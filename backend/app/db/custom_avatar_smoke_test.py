from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.db.session import SessionLocal, dispose_database_engine
from app.models import AuditLog, User, UserSession
from app.services.auth import create_session
from app.services.backups import (
    create_backup_artifact,
    remove_backup_operation_directory,
)

# PARTPILOT:CUSTOM_AVATAR_SMOKE:V598


class CustomAvatarSmokeFailure(RuntimeError):
    pass


def fail(message: str) -> None:
    raise CustomAvatarSmokeFailure(message)


def db_path() -> Path:
    from app.core.config import get_settings
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        fail(f"SQLite required, got {url!r}")
    return Path(url[len(prefix):]).resolve()


def copy_database(source: Path, destination: Path) -> None:
    src = sqlite3.connect(source)
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

def snapshot():
    c=sqlite3.connect(db_path()); c.row_factory=sqlite3.Row
    try:
        tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {t:[dict(r) for r in c.execute(f'SELECT * FROM "{t}" ORDER BY rowid')] for t in tables}
    finally:
        c.close()

def make_image(fmt: str, color: tuple[int,int,int], size=(640,360)) -> bytes:
    out=io.BytesIO()
    Image.new("RGB",size,color).save(out,format=fmt)
    return out.getvalue()

def check_only() -> None:
    from app.main import app
    with TestClient(app) as client:
        for method in ("get","delete"):
            response=getattr(client,method)("/api/auth/profile/avatar-image")
            if response.status_code != 401:
                fail(f"unauthenticated {method} returned {response.status_code}")
        response=client.put(
            "/api/auth/profile/avatar-image",
            files={"image":("x.png",b"x","image/png")},
        )
        if response.status_code != 401:
            fail(f"unauthenticated upload returned {response.status_code}")
        paths=client.get("/openapi.json").json().get("paths",{})
        methods=set(paths.get("/api/auth/profile/avatar-image",{}))
        if methods != {"get","put","delete"}:
            fail(f"avatar-image OpenAPI methods unexpected: {methods}")
    print("[PASS] protected custom-avatar routes and OpenAPI")

def full() -> None:
    baseline=snapshot()
    fd,raw=tempfile.mkstemp(prefix="pp598-original-",suffix=".db"); os.close(fd)
    original=Path(raw); copy_database(db_path(),original)
    artifact_operation=None
    artifact_root=Path(tempfile.mkdtemp(prefix="pp598-artifact-"))
    try:
        db=SessionLocal()
        try:
            user=db.execute(select(User).order_by(User.id)).scalars().first()
            if user is None: fail("existing user required")
            user_id=int(user.id); builtin=user.avatar_id; password_hash=user.password_hash
            sessions={r.id:(r.token_hash,r.revoked_at,r.expires_at) for r in db.execute(select(UserSession)).scalars()}
            audit_floor=db.execute(select(AuditLog.id).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none() or 0
            token=create_session(db,user=user,user_agent="Patch 598 custom-avatar smoke",ip_address="127.0.0.1",commit=True).token
        finally:
            db.close()
        headers={"Authorization":f"Bearer {token}"}
        from app.main import app
        png=make_image("PNG",(20,150,120))
        jpeg=make_image("JPEG",(180,70,60),(360,640))
        with TestClient(app) as client:
            initial=client.get("/api/auth/profile",headers=headers)
            if initial.status_code!=200 or initial.json().get("has_custom_avatar") is not False:
                fail(f"initial profile custom-avatar state wrong: {initial.status_code} {initial.text[:200]}")
            missing=client.get("/api/auth/profile/avatar-image",headers=headers)
            if missing.status_code!=404: fail(f"missing avatar image returned {missing.status_code}")
            wrong=client.put("/api/auth/profile/avatar-image",headers=headers,files={"image":("x.txt",b"abc","text/plain")})
            if wrong.status_code!=415: fail(f"wrong MIME returned {wrong.status_code}")
            invalid=client.put("/api/auth/profile/avatar-image",headers=headers,files={"image":("x.png",b"not-an-image","image/png")})
            if invalid.status_code!=422: fail(f"invalid image returned {invalid.status_code}: {invalid.text[:200]}")
            too_large=client.put("/api/auth/profile/avatar-image",headers=headers,files={"image":("x.png",b"x"*(5*1024*1024+1),"image/png")})
            if too_large.status_code!=413: fail(f"oversize returned {too_large.status_code}")
            uploaded=client.put("/api/auth/profile/avatar-image",headers=headers,files={"image":("avatar.png",png,"image/png")})
            if uploaded.status_code!=200: fail(f"PNG upload failed: {uploaded.status_code} {uploaded.text[:300]}")
            body=uploaded.json(); digest=body.get("avatar_image_sha256")
            if body.get("has_custom_avatar") is not True or not isinstance(digest,str) or len(digest)!=64:
                fail(f"upload profile metadata wrong: {body}")
            fetched=client.get("/api/auth/profile/avatar-image",headers=headers)
            if fetched.status_code!=200 or fetched.headers.get("content-type")!="image/webp":
                fail(f"avatar fetch failed: {fetched.status_code} {fetched.headers.get('content-type')}")
            if hashlib.sha256(fetched.content).hexdigest()!=digest:
                fail("avatar fetch hash mismatch")
            if fetched.headers.get("cache-control")!="private, no-store, max-age=0" or fetched.headers.get("x-content-type-options")!="nosniff":
                fail("avatar response cache/security headers wrong")
            with Image.open(io.BytesIO(fetched.content)) as decoded:
                if decoded.format!="WEBP" or decoded.size!=(256,256):
                    fail(f"normalized image wrong: {decoded.format} {decoded.size}")
            same=client.put("/api/auth/profile/avatar-image",headers=headers,files={"image":("avatar.png",png,"image/png")})
            if same.status_code!=200 or same.json().get("avatar_image_sha256")!=digest:
                fail("same-image idempotency response wrong")
            changed=client.put("/api/auth/profile/avatar-image",headers=headers,files={"image":("avatar.jpg",jpeg,"image/jpeg")})
            if changed.status_code!=200 or changed.json().get("avatar_image_sha256")==digest:
                fail("replacement avatar did not change hash")
            replacement_digest=changed.json()["avatar_image_sha256"]

            artifact=create_backup_artifact(db_path(),artifact_root)
            artifact_operation=artifact.operation_directory
            extracted=artifact_root/"avatar-backup.db"
            import zipfile
            with zipfile.ZipFile(artifact.archive_path,"r") as z:
                extracted.write_bytes(z.read("partpilot.db"))
            c=sqlite3.connect(extracted)
            try:
                row=c.execute("SELECT avatar_image_mime,avatar_image_sha256,avatar_image_size_bytes,length(avatar_image_data) FROM users WHERE id=?",(user_id,)).fetchone()
            finally:
                c.close()
            if row is None or row[0]!="image/webp" or row[1]!=replacement_digest or row[2]!=row[3] or row[2]<1:
                fail(f"backup did not preserve avatar blob metadata: {row}")

            removed=client.delete("/api/auth/profile/avatar-image",headers=headers)
            if removed.status_code!=200 or removed.json().get("has_custom_avatar") is not False or removed.json().get("avatar_image_sha256") is not None:
                fail(f"avatar delete response wrong: {removed.status_code} {removed.text[:200]}")
            if removed.json().get("avatar_id")!=builtin:
                fail("custom-avatar delete changed built-in fallback")
            if client.get("/api/auth/profile/avatar-image",headers=headers).status_code!=404:
                fail("deleted avatar image remained readable")
            second=client.delete("/api/auth/profile/avatar-image",headers=headers)
            if second.status_code!=200: fail("idempotent second delete failed")

        db=SessionLocal()
        try:
            user=db.get(User,user_id)
            if user is None: fail("user disappeared")
            if user.password_hash!=password_hash or user.avatar_id!=builtin:
                fail("custom-avatar flow changed password or built-in avatar")
            preexisting={r.id:(r.token_hash,r.revoked_at,r.expires_at) for r in db.execute(select(UserSession).where(UserSession.id.in_(sessions))).scalars()}
            if preexisting!=sessions: fail("custom-avatar flow changed pre-existing sessions")
            audits=list(db.execute(select(AuditLog).where(AuditLog.id>audit_floor,AuditLog.entity_type=="user",AuditLog.entity_id==user_id,AuditLog.event_type.in_(["auth.avatar_image_updated","auth.avatar_image_removed"]))).scalars())
            events=[a.event_type for a in audits]
            if events.count("auth.avatar_image_updated")!=2 or events.count("auth.avatar_image_removed")!=1:
                fail(f"custom-avatar audit counts wrong: {events}")
            serialized=json.dumps([{"before":a.before_json,"after":a.after_json,"metadata":a.metadata_json,"summary":a.summary} for a in audits],sort_keys=True).casefold()
            if "data:image" in serialized or "webp;" in serialized or len(serialized)>10000:
                fail("custom-avatar audit exposed image bytes")
        finally:
            db.close()
    finally:
        dispose_database_engine()
        src=sqlite3.connect(original); dst=sqlite3.connect(db_path())
        try: src.backup(dst)
        finally: dst.close(); src.close()
        dispose_database_engine(); original.unlink(missing_ok=True)
        if artifact_operation is not None:
            try: remove_backup_operation_directory(artifact_operation,expected_parent=artifact_root)
            except Exception: pass
        import shutil; shutil.rmtree(artifact_root,ignore_errors=True)
    if snapshot()!=baseline: fail("custom-avatar smoke exact restore failed")
    print("[PASS] custom-avatar upload/read/replace/delete, normalization, safe audits, backup preservation, password/session safety and exact restore")

def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--check-only",action="store_true"); args=parser.parse_args()
    check_only() if args.check_only else full()

if __name__=="__main__":
    main()
