from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.config import get_settings
from app.db.session import SessionLocal, dispose_database_engine
from app.models import AuditLog, McpOAuthClient, User
from app.services.auth import create_session

# PARTPILOT:MCP_OAUTH_MANUAL_REGISTRATION_SMOKE:V555
class SmokeFailure(RuntimeError): pass
def fail(message: str) -> None: raise SmokeFailure(message)
def db_path() -> Path:
    url=get_settings().database_url; prefix="sqlite:///"
    if not url.startswith(prefix): fail(f"SQLite required, got {url!r}")
    return Path(url[len(prefix):]).resolve()
def snapshot():
    c=sqlite3.connect(db_path()); c.row_factory=sqlite3.Row
    try:
        tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        rows={t:[dict(r) for r in c.execute(f'SELECT * FROM "{t}" ORDER BY rowid')] for t in tables}
        seq=[]
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'").fetchone():
            seq=[tuple(r) for r in c.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name")]
        return rows,seq
    finally: c.close()
def backup():
    fd,p=tempfile.mkstemp(prefix="pp555_",suffix=".db"); os.close(fd); p=Path(p)
    a=sqlite3.connect(db_path()); b=sqlite3.connect(p)
    try: a.backup(b)
    finally: b.close(); a.close()
    return p
def restore(p):
    dispose_database_engine()
    for s in ("-wal","-shm","-journal"): Path(str(db_path())+s).unlink(missing_ok=True)
    a=sqlite3.connect(p); b=sqlite3.connect(db_path())
    try: a.backup(b)
    finally: b.close(); a.close()
    dispose_database_engine()
def no_store(r):
    if r.headers.get("cache-control")!="no-store" or r.headers.get("pragma")!="no-cache": fail("no-store headers missing")
def text_hits(needle):
    c=sqlite3.connect(db_path()); hits=[]
    try:
        tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for t in tables:
            for col,typ in [(r[1],str(r[2]).upper()) for r in c.execute(f'PRAGMA table_info("{t}")')]:
                if any(x in typ for x in ("CHAR","CLOB","TEXT","JSON")):
                    if c.execute(f'SELECT 1 FROM "{t}" WHERE instr(CAST("{col}" AS TEXT),?)>0 LIMIT 1',(needle,)).fetchone(): hits.append(f"{t}.{col}")
        return hits
    finally: c.close()
def check_only():
    from app.main import app
    with TestClient(app) as c:
        r=c.post("/api/settings/mcp/oauth-clients",json={"client_name":"x","redirect_uris":["https://example.invalid/cb"],"client_type":"public","token_endpoint_auth_method":"none"})
        if r.status_code!=401: fail(f"unauthenticated POST returned {r.status_code}")
        o=c.get("/openapi.json").json()["paths"]["/api/settings/mcp/oauth-clients"]
        if set(o)!={"get","post"}: fail(f"OpenAPI methods changed: {set(o)}")
        s=json.dumps(o).casefold()
        if "client_secret_hash" in s or "pp_mcp_secret_" in s: fail("OpenAPI secret exposure")
    print("[PASS] protected POST and secret-safe OpenAPI")
def full():
    before=snapshot(); bak=backup()
    try:
        db=SessionLocal()
        try:
            user=db.execute(select(User).order_by(User.id)).scalars().first()
            if user is None: fail("existing user required")
            uid=user.id
            audit_floor=db.execute(select(AuditLog.id).order_by(AuditLog.id.desc()).limit(1)).scalar_one_or_none() or 0
            existing={x.id:(x.client_id,x.client_secret_hash,x.registered_by_user_id,x.revoked_at) for x in db.execute(select(McpOAuthClient)).scalars()}
            if existing.get(9,(None,None,1,None))[2] is not None or existing.get(13,(None,None,1,None))[2] is not None: fail("existing ownership was backfilled")
            token=create_session(db,user=user,user_agent="Patch 555 smoke",ip_address="127.0.0.1",commit=True).token
        finally: db.close()
        headers={"Authorization":f"Bearer {token}"}
        pub={"client_name":"Patch 555 Public Fixture","redirect_uris":["http://127.0.0.1:45491/callback","https://public-fixture.example/callback"],"client_type":"public","token_endpoint_auth_method":"none"}
        conf={"client_name":"Patch 555 Confidential Fixture","redirect_uris":["https://confidential-fixture.example/callback"],"client_type":"confidential","token_endpoint_auth_method":"client_secret_basic"}
        from app.main import app
        with TestClient(app) as c:
            for bad in ({**pub,"client_name":"bad public","token_endpoint_auth_method":"client_secret_post"},{**conf,"client_name":"bad confidential","token_endpoint_auth_method":"none"},{**pub,"client_name":"bad redirect","redirect_uris":["http://not-loopback.example/cb"]}):
                r=c.post("/api/settings/mcp/oauth-clients",headers=headers,json=bad)
                if r.status_code!=422: fail(f"bad request returned {r.status_code}: {r.text[:200]}")
                no_store(r)
            d=SessionLocal()
            try:
                if len(list(d.execute(select(McpOAuthClient)).scalars()))!=len(existing): fail("rejected request created partial row")
            finally: d.close()
            rp=c.post("/api/settings/mcp/oauth-clients",headers=headers,json=pub); no_store(rp)
            if rp.status_code!=201 or rp.json().get("client_secret") is not None: fail(f"public registration failed: {rp.status_code} {rp.text[:300]}")
            rc=c.post("/api/settings/mcp/oauth-clients",headers=headers,json=conf); no_store(rc)
            if rc.status_code!=201: fail(f"confidential registration failed: {rc.status_code} {rc.text[:300]}")
            secret=rc.json().get("client_secret")
            if not isinstance(secret,str) or not secret.startswith("pp_mcp_secret_"): fail("one-time secret malformed")
            rg=c.get("/api/settings/mcp/oauth-clients",headers=headers); no_store(rg)
            if secret in rg.text or "client_secret_hash" in rg.text: fail("GET exposed secret material")
        d=SessionLocal()
        try:
            made={x.client_name:x for x in d.execute(select(McpOAuthClient).where(McpOAuthClient.client_name.in_([pub["client_name"],conf["client_name"]]))).scalars()}
            if set(made)!={pub["client_name"],conf["client_name"]}: fail("created rows missing")
            p,q=made[pub["client_name"]],made[conf["client_name"]]
            if p.registered_by_user_id!=uid or q.registered_by_user_id!=uid: fail("ownership incorrect")
            digest=hashlib.sha256(secret.encode()).hexdigest()
            if p.client_secret_hash is not None or q.client_secret_hash!=digest: fail("digest-only storage incorrect")
            audits=list(d.execute(select(AuditLog).where(AuditLog.id>audit_floor,AuditLog.event_type=="mcp.oauth_client_registered",AuditLog.entity_id.in_([p.id,q.id]))).scalars())
            if len(audits)!=2 or any(a.actor_type!="user" or a.actor_user_id!=uid for a in audits): fail("user-attributed audit missing")
            if any(secret in json.dumps({"summary":a.summary,"metadata":a.metadata_json},sort_keys=True) or digest in json.dumps({"summary":a.summary,"metadata":a.metadata_json},sort_keys=True) for a in audits): fail("audit exposed secret")
            for i,v in existing.items():
                x=d.get(McpOAuthClient,i)
                if x is None or (x.client_id,x.client_secret_hash,x.registered_by_user_id,x.revoked_at)!=v: fail(f"existing client {i} changed")
        finally: d.close()
        hits=text_hits(secret)
        if hits: fail(f"plaintext at rest in {hits}")
    finally: restore(bak); bak.unlink(missing_ok=True)
    if snapshot()!=before: fail("exact logical restore failed")
    print("[PASS] ownership, audit, one-time secret, digest-only storage, rejection rollback, preservation and exact restore")
def main():
    p=argparse.ArgumentParser(); p.add_argument("--check-only",action="store_true"); a=p.parse_args(); check_only() if a.check_only else full()
if __name__=="__main__": main()
