from __future__ import annotations
import argparse, sqlite3
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models import AuditLog, McpOAuthClient, User, UserSession
from app.services.auth import create_session
from app.services.mcp_oauth import register_client

class SmokeFailure(RuntimeError): pass
def fail(message: str) -> None: raise SmokeFailure(message)

def sqlite_path():
    url=get_settings().database_url; prefix="sqlite:///"
    if not url.startswith(prefix): fail(f"SQLite required, got {url!r}")
    return url[len(prefix):]

def logical_snapshot():
    db=sqlite3.connect(sqlite_path()); db.row_factory=sqlite3.Row
    try:
        tables=[r[0] for r in db.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]
        result={}
        for table in tables:
            info=list(db.execute(f'pragma table_info("{table}")'))
            cols=[r[1] for r in info]; primary=[r[1] for r in info if r[5]]; order=primary or cols
            rows=db.execute(f'select * from "{table}" order by '+",".join(f'"{c}"' for c in order)).fetchall()
            result[table]=[dict(r) for r in rows]
        return result
    finally: db.close()

def require_no_store(r):
    if r.headers.get("cache-control")!="no-store" or r.headers.get("pragma")!="no-cache": fail("no-store headers missing")

EXPECTED_FIELDS={
"database_id","client_id","client_name","status","client_type","token_endpoint_auth_method",
"redirect_origins","scopes","created_at","connected_at","last_used_at","active_token_count",
"token_family_count","total_token_count","authorization_code_count","active_consent_count",
"registered_by_current_user"}

def validate_payload(payload):
    if set(payload)!={"clients","total"}: fail(f"top-level fields wrong: {sorted(payload)}")
    if payload["total"]!=len(payload["clients"]): fail("total mismatch")
    for item in payload["clients"]:
        if set(item)!=EXPECTED_FIELDS: fail(f"manageable fields wrong: {sorted(set(item)^EXPECTED_FIELDS)}")
        for value in item.values():
            if isinstance(value,str) and value.startswith("pp_mcp_secret_"): fail("payload exposed plaintext client secret")
        if item["status"] not in {"registered","connected","revoked"}: fail(f"unexpected status {item['status']}")

def check_only():
    with TestClient(app) as client:
        r=client.get("/api/settings/mcp/oauth-clients/manageable")
        if r.status_code!=401: fail(f"unauth GET returned {r.status_code}")
        o=client.get("/openapi.json")
        if o.status_code!=200: fail("OpenAPI unavailable")
        methods=set(o.json().get("paths",{}).get("/api/settings/mcp/oauth-clients/manageable",{}))
        if methods!={"get"}: fail(f"OpenAPI methods wrong: {methods}")
    print("[PASS] manageable OAuth GET is protected and registered in OpenAPI")

def full():
    before=logical_snapshot(); fixture_id=None; session_id=None; audit_floor=0
    db=SessionLocal()
    try:
        user=db.execute(select(User).order_by(User.id.asc())).scalars().first()
        if user is None: fail("existing user required")
        uid=user.id
        audit_floor=int(db.execute(select(func.coalesce(func.max(AuditLog.id),0))).scalar_one())
        issued=register_client(
            db,client_name="Patch 559 "+uuid4().hex[:8],
            redirect_uris=["https://example.test/callback"],
            grant_types=("authorization_code","refresh_token"),response_types=("code",),
            token_endpoint_auth_method="none",
            metadata={"registration_source":"settings","client_type":"public"},
            actor_user_id=uid,registered_by_user_id=uid,commit=True)
        fixture_id=issued.client.id
        session_token=create_session(db,user=user,user_agent="Patch 559 manageable smoke",ip_address="127.0.0.1",commit=True)
        session_id=session_token.session.id; bearer=session_token.token
    finally: db.close()
    try:
        h={"Authorization":f"Bearer {bearer}"}
        with TestClient(app) as client:
            first=client.get("/api/settings/mcp/oauth-clients/manageable",headers=h)
            if first.status_code!=200: fail(f"first GET {first.status_code}: {first.text[:300]}")
            require_no_store(first); payload=first.json(); validate_payload(payload)
            by={x["database_id"]:x for x in payload["clients"]}
            if by.get(9,{}).get("status")!="connected" or by.get(13,{}).get("status")!="connected": fail("legacy connected clients missing")
            if by[9]["registered_by_current_user"] or by[13]["registered_by_current_user"]: fail("legacy clients ownership-backfilled")
            fixture=by.get(fixture_id)
            if not fixture or fixture["status"]!="registered" or not fixture["registered_by_current_user"] or fixture["connected_at"] is not None: fail("registered fixture wrong")
            if any(fixture[k]!=0 for k in ("active_token_count","token_family_count","total_token_count","authorization_code_count","active_consent_count")): fail("registered fixture counters nonzero")
            revoked=client.delete(f"/api/settings/mcp/oauth-clients/{fixture_id}",headers=h)
            if revoked.status_code!=200: fail(f"registered fixture DELETE returned {revoked.status_code}: {revoked.text[:300]}")
            require_no_store(revoked)
            second=client.get("/api/settings/mcp/oauth-clients/manageable",headers=h)
            if second.status_code!=200: fail(f"second GET {second.status_code}: {second.text[:300]}")
            require_no_store(second); payload2=second.json(); validate_payload(payload2)
            fixture2={x["database_id"]:x for x in payload2["clients"]}.get(fixture_id)
            if not fixture2 or fixture2["status"]!="revoked" or not fixture2["registered_by_current_user"]: fail("revoked fixture wrong")
    finally:
        if fixture_id is not None and session_id is not None:
            db=SessionLocal()
            try:
                db.execute(delete(UserSession).where(UserSession.id==session_id))
                db.execute(delete(AuditLog).where(AuditLog.id>audit_floor,AuditLog.entity_type=="mcp_oauth_client",AuditLog.entity_id==fixture_id))
                db.execute(delete(McpOAuthClient).where(McpOAuthClient.id==fixture_id))
                db.commit()
            except Exception:
                db.rollback(); raise
            finally: db.close()
    after=logical_snapshot()
    if after!=before:
        changed=sorted(k for k in before if before.get(k)!=after.get(k))
        fail(f"fixture cleanup did not restore logical database exactly: {changed}")
    print("[PASS] manageable OAuth covers registered, connected and revoked, uses one app lifespan, exposes no secret material, omits Abandoned status and restores copied DB exactly")

def main():
    p=argparse.ArgumentParser(); p.add_argument("--check-only",action="store_true"); a=p.parse_args()
    check_only() if a.check_only else full()
if __name__=="__main__": main()
