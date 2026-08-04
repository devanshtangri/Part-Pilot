from __future__ import annotations
import json, os, sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import AuditLog, McpDirectAuth, User, UserSession
from app.services.auth import create_session
from app.services.mcp_direct_auth import validate_bearer_key

# PARTPILOT:MCP_DIRECT_AUTH_API_SMOKE:V485
SECRET_FILE=Path('/data/.partpilot-instance-secret')
class SmokeFailure(RuntimeError): pass
def fail(message): raise SmokeFailure(message)
def sqlite_path():
    url=get_settings().database_url; prefix='sqlite:///'
    if not url.startswith(prefix): fail(f'SQLite required, got {url!r}')
    return Path(url[len(prefix):]).resolve()
def snapshot():
    con=sqlite3.connect(sqlite_path()); con.row_factory=sqlite3.Row
    try:
        tables=[r[0] for r in con.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name")]
        rows={t:[dict(r) for r in con.execute(f'select * from "{t}" order by rowid')] for t in tables}
        has_seq=con.execute("select 1 from sqlite_master where type='table' and name='sqlite_sequence'").fetchone() is not None
        seq=([tuple(r) for r in con.execute('select name,seq from sqlite_sequence order by name')] if has_seq else [])
        return {'rows':rows,'has_seq':has_seq,'seq':seq}
    finally: con.close()
def restore_seq(before):
    con=sqlite3.connect(sqlite_path())
    try:
        has_seq=con.execute("select 1 from sqlite_master where type='table' and name='sqlite_sequence'").fetchone() is not None
        if before['has_seq']:
            if not has_seq: fail('sqlite_sequence disappeared during smoke cleanup')
            con.execute('delete from sqlite_sequence')
            con.executemany('insert into sqlite_sequence(name,seq) values (?,?)',before['seq'])
            con.commit()
        elif has_seq:
            current=[tuple(r) for r in con.execute('select name,seq from sqlite_sequence order by name')]
            if current: fail(f'smoke unexpectedly created sqlite_sequence rows: {current}')
    finally: con.close()
def no_store(r):
    if r.headers.get('cache-control')!='no-store' or r.headers.get('pragma')!='no-cache': fail('Secret response is cacheable')
def main():
    before=snapshot(); secret_before=SECRET_FILE.read_bytes() if SECRET_FILE.exists() else None
    db=SessionLocal(); session_id=None; baseline=0; keys=[]
    try:
        user=db.execute(select(User).where(User.is_active.is_(True)).order_by(User.id)).scalars().first()
        if user is None: fail('One active user is required')
        baseline=int(db.execute(select(func.max(AuditLog.id))).scalar() or 0)
        issued=create_session(db,user=user,user_agent='Patch 486 direct-auth API smoke',ip_address='127.0.0.1',commit=False)
        session_id=issued.session.id; db.commit(); headers={'Authorization':f'Bearer {issued.token}'}
        from app.main import app
        with TestClient(app) as client:
            for method,path in [('get','/api/settings/mcp/direct-auth'),('post','/api/settings/mcp/direct-auth/bearer-key'),('post','/api/settings/mcp/direct-auth/reveal'),('delete','/api/settings/mcp/direct-auth')]:
                r=getattr(client,method)(path)
                if r.status_code!=401: fail(f'Unauthenticated {method} {path}: {r.status_code}')
            initial=client.get('/api/settings/mcp/direct-auth',headers=headers); no_store(initial)
            if initial.status_code!=200 or initial.json()!={'mode':'disabled','configured':False,'masked_key':None,'rotated_at':None,'last_used_at':None}: fail(f'Bad initial status: {initial.text}')
            first=client.post('/api/settings/mcp/direct-auth/bearer-key',headers=headers)
            if first.status_code!=200: fail(f'First rotation failed: {first.status_code} {first.text}')
            no_store(first)
            key1=first.json().get('key')
            if not isinstance(key1,str) or not key1.startswith('pp_mcp_key_'): fail('First rotation returned an invalid key')
            keys.append(key1)
            status=client.get('/api/settings/mcp/direct-auth',headers=headers)
            if status.status_code!=200: fail(f'Status failed: {status.status_code} {status.text}')
            no_store(status)
            if status.json().get('configured') is not True or key1 in status.text: fail('Status leaked or omitted configuration')
            reveal=client.post('/api/settings/mcp/direct-auth/reveal',headers=headers)
            if reveal.status_code!=200: fail(f'Reveal failed: {reveal.status_code} {reveal.text}')
            no_store(reveal)
            if reveal.json().get('key')!=key1: fail('Reveal returned the wrong key')
            second=client.post('/api/settings/mcp/direct-auth/bearer-key',headers=headers)
            if second.status_code!=200: fail(f'Second rotation failed: {second.status_code} {second.text}')
            no_store(second)
            key2=second.json().get('key')
            if not isinstance(key2,str) or key2==key1: fail('Second rotation did not issue a fresh key')
            keys.append(key2)
            verify=SessionLocal()
            try:
                if validate_bearer_key(verify,key1,touch=False,commit=False): fail('Old key survived rotation')
                if not validate_bearer_key(verify,key2,touch=False,commit=False): fail('New key rejected')
            finally: verify.rollback(); verify.close()
            disabled=client.delete('/api/settings/mcp/direct-auth',headers=headers)
            if disabled.status_code!=200: fail(f'Disable failed: {disabled.status_code} {disabled.text}')
            no_store(disabled)
            if disabled.json().get('mode')!='disabled': fail('Disable returned the wrong mode')
            repeated=client.delete('/api/settings/mcp/direct-auth',headers=headers)
            if repeated.status_code!=200: fail('Repeated disable failed')
        audits=db.execute(select(AuditLog).where(AuditLog.id>baseline).order_by(AuditLog.id)).scalars().all()
        events=[x.event_type for x in audits]
        expected=['settings.mcp_direct_key_rotated','settings.mcp_direct_key_revealed','settings.mcp_direct_key_rotated','settings.mcp_direct_auth_disabled']
        if events!=expected: fail(f'Unexpected events: {events}')
        payload=json.dumps([{'e':x.event_type,'s':x.summary,'b':x.before_json,'a':x.after_json,'m':x.metadata_json} for x in audits],sort_keys=True,default=str)
        if any(k in payload for k in keys): fail('Audit leaked key')
        if any(x.actor_type!='user' or x.actor_user_id!=user.id for x in audits): fail('Audit actor mismatch')
        cleanup=SessionLocal()
        try:
            cleanup.query(AuditLog).filter(AuditLog.id>baseline).delete(synchronize_session=False)
            cleanup.query(McpDirectAuth).delete(synchronize_session=False)
            if session_id is not None:
                row=cleanup.get(UserSession,session_id)
                if row is not None: cleanup.delete(row)
            cleanup.commit()
        finally: cleanup.close()
        restore_seq(before)
        if snapshot()!=before: fail('Database cleanup mismatch')
    finally:
        db.rollback(); db.close()
        if secret_before is None: SECRET_FILE.unlink(missing_ok=True)
        else: SECRET_FILE.write_bytes(secret_before); os.chmod(SECRET_FILE,0o600)
    print('MCP direct auth API smoke PASS')
if __name__=='__main__': main()
