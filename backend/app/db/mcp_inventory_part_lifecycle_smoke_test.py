from __future__ import annotations
import json
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.db.settings import set_app_setting
from app.models import AuditLog, McpWriteIntent, Part, PartType, User, StockMovement
from app.services.app_settings import MCP_DIRECT_CLIENTS_ENABLED_KEY, MCP_DIRECT_NO_AUTH_ENABLED_KEY
from app.services.mcp_direct_auth import DIRECT_AUTH_BEARER_KEY, create_named_direct_client
from app.services.mcp_permissions import DEFAULT_MCP_TOOL_PERMISSIONS, MCP_TOOL_PERMISSIONS_KEY

# PARTPILOT:MCP_INVENTORY_PART_LIFECYCLE_SMOKE:V762
READ_TOOLS={"search_parts","get_part_details","list_projects","get_project_details","list_reservations","get_reservation_details"}
LIFECYCLE_TOOLS={"soft_delete_part","restore_part"}
EXPECTED_HEAD="0022_mcp_inventory_part_lifecycle"
class SmokeFailure(RuntimeError): pass
def fail(message:str)->None: raise SmokeFailure(message)
def database_path()->Path:
    url=get_settings().database_url; prefix="sqlite:///"
    if not url.startswith(prefix): fail(f"Lifecycle smoke requires SQLite, got {url!r}")
    return Path(url[len(prefix):]).resolve()
def headers(key:str)->dict[str,str]:
    return {"Accept":"application/json, text/event-stream","Content-Type":"application/json","Origin":"https://partpilot.example","Authorization":f"Bearer {key}"}
def tools(client,key,rid):
    r=client.post('/mcp',headers=headers(key),json={"jsonrpc":"2.0","id":rid,"method":"tools/list","params":{}})
    if r.status_code!=200: fail(f"tools/list failed: {r.status_code} {r.text[:500]}")
    return {x.get('name') for x in r.json().get('result',{}).get('tools',[]) if isinstance(x,dict)}
def call(client,key,rid,name,args):
    r=client.post('/mcp',headers=headers(key),json={"jsonrpc":"2.0","id":rid,"method":"tools/call","params":{"name":name,"arguments":args}})
    if r.status_code!=200: fail(f"{name} HTTP {r.status_code}: {r.text[:500]}")
    return r.json().get('result',{})
def ok(result,label):
    if result.get('isError') is True: fail(f"{label} failed: {result}")
    value=result.get('structuredContent')
    if not isinstance(value,dict): fail(f"{label} missing structured content")
    return value
def expect_error(result,label):
    if result.get('isError') is not True: fail(f"{label} should fail closed: {result}")

def main()->None:
    path=database_path(); before=path.read_bytes(); direct_id=None
    try:
        db=SessionLocal()
        try:
            rev=db.connection().exec_driver_sql('SELECT version_num FROM alembic_version').scalar_one()
            if rev!=EXPECTED_HEAD: fail(f"Expected {EXPECTED_HEAD}, got {rev}")
            if len(DEFAULT_MCP_TOOL_PERMISSIONS)!=14: fail('Expected 14-tool canonical policy')
            owner=db.execute(select(User).where(User.is_active.is_(True),User.role=='owner').order_by(User.id)).scalars().first()
            ptype=db.execute(select(PartType).where(PartType.is_active.is_(True)).order_by(PartType.id)).scalars().first()
            if owner is None or ptype is None: fail('Lifecycle smoke requires active owner and part type')
            issued=create_named_direct_client(db,actor_user_id=owner.id,name='Patch 762 lifecycle smoke',mode=DIRECT_AUTH_BEARER_KEY,commit=False)
            direct_id=issued.record.id; key=issued.plaintext_key; owner_id=owner.id
            part=Part(part_type_id=ptype.id,part_number='P762-LIFECYCLE',name='Patch 762 lifecycle fixture',total_quantity=7,reserved_quantity=2,low_stock_enabled=False,is_deleted=False)
            db.add(part); db.flush(); part_id=part.id
            set_app_setting(db,'mcp.enabled',True,commit=False); set_app_setting(db,'mcp.read_tools_enabled',True,commit=False); set_app_setting(db,'mcp.write_tools_enabled',True,commit=False)
            set_app_setting(db,MCP_DIRECT_CLIENTS_ENABLED_KEY,True,commit=False); set_app_setting(db,MCP_DIRECT_NO_AUTH_ENABLED_KEY,False,commit=False)
            policy={name:(name in READ_TOOLS or name in LIFECYCLE_TOOLS) for name in DEFAULT_MCP_TOOL_PERMISSIONS}
            set_app_setting(db,MCP_TOOL_PERMISSIONS_KEY,policy,commit=False); db.commit()
        finally: db.close()
        from app.main import app
        with TestClient(app,base_url='https://partpilot.example') as client:
            if tools(client,key,1)!=READ_TOOLS|LIFECYCLE_TOOLS: fail('Lifecycle tool visibility is wrong')
            delete_args={'part_id':part_id,'idempotency_key':'p762-delete-001'}
            preview=ok(call(client,key,2,'soft_delete_part',delete_args),'delete preview'); token=preview.get('confirmation_token')
            exact=preview.get('preview',{})
            if preview.get('phase')!='preview' or not isinstance(token,str) or exact.get('reversible') is not True or exact.get('permanent_purge') is not False: fail('Delete preview safeguard shape is wrong')
            before_state=exact.get('before_state',{}); proposed=exact.get('proposed_state',{})
            if before_state.get('total_quantity')!=7 or before_state.get('reserved_quantity')!=2 or before_state.get('is_deleted') is not False or proposed.get('is_deleted') is not True: fail('Delete preview state is wrong')
            verify=SessionLocal()
            try:
                row=verify.get(Part,part_id)
                if row is None or row.is_deleted: fail('Delete preview mutated inventory')
            finally: verify.close()
            done=ok(call(client,key,3,'soft_delete_part',{**delete_args,'confirmation_token':token}),'delete confirm')
            if done.get('phase')!='completed' or done.get('deleted_part',{}).get('total_quantity')!=7 or done.get('deleted_part',{}).get('reserved_quantity')!=2: fail('Delete confirmation did not preserve quantities')
            replay=ok(call(client,key,4,'soft_delete_part',{**delete_args,'confirmation_token':token}),'delete replay')
            if replay.get('replayed') is not True: fail('Delete replay was not idempotent')
            restore_args={'part_id':part_id,'idempotency_key':'p762-restore-drift'}
            rp=ok(call(client,key,5,'restore_part',restore_args),'restore drift preview'); rt=rp.get('confirmation_token')
            drift=SessionLocal()
            try:
                row=drift.get(Part,part_id); row.name='Patch 762 drifted name'; drift.commit()
            finally: drift.close()
            expect_error(call(client,key,6,'restore_part',{**restore_args,'confirmation_token':rt}),'restore state drift')
            fix=SessionLocal()
            try:
                row=fix.get(Part,part_id); row.name='Patch 762 lifecycle fixture'; fix.commit()
            finally: fix.close()
            restore_args={'part_id':part_id,'idempotency_key':'p762-restore-001'}
            rp=ok(call(client,key,7,'restore_part',restore_args),'restore preview'); rt=rp.get('confirmation_token')
            if rp.get('preview',{}).get('before_state',{}).get('is_deleted') is not True or rp.get('preview',{}).get('proposed_state',{}).get('is_deleted') is not False: fail('Restore preview state is wrong')
            restored=ok(call(client,key,8,'restore_part',{**restore_args,'confirmation_token':rt}),'restore confirm')
            part_result=restored.get('part',{})
            if part_result.get('total_quantity')!=7 or part_result.get('reserved_quantity')!=2: fail('Restore confirmation changed quantities')
            rr=ok(call(client,key,9,'restore_part',{**restore_args,'confirmation_token':rt}),'restore replay')
            if rr.get('replayed') is not True: fail('Restore replay was not idempotent')
            verify=SessionLocal()
            try:
                row=verify.get(Part,part_id)
                if row is None or row.is_deleted or row.total_quantity!=7 or row.reserved_quantity!=2: fail('Final lifecycle state is wrong')
                if verify.execute(select(func.count(StockMovement.id)).where(StockMovement.part_id==part_id)).scalar_one()!=0: fail('Lifecycle operations created stock movements')
                audits=list(verify.execute(select(AuditLog).where(AuditLog.entity_type=='part',AuditLog.entity_id==part_id,AuditLog.event_type.in_(['part.deleted','part.restored'])).order_by(AuditLog.id)).scalars())
                if [a.event_type for a in audits]!=['part.deleted','part.restored']: fail(f'Unexpected lifecycle audits: {[a.event_type for a in audits]}')
                for a in audits:
                    meta=a.metadata_json if isinstance(a.metadata_json,dict) else {}
                    if a.actor_type!='mcp' or a.actor_user_id!=owner_id or meta.get('mcp_client_name')!='Patch 762 lifecycle smoke': fail('Lifecycle MCP audit attribution is wrong')
                intents=list(verify.execute(select(McpWriteIntent).where(McpWriteIntent.principal_key==f'direct:{direct_id}',McpWriteIntent.tool_name.in_(LIFECYCLE_TOOLS))).scalars())
                serialized=json.dumps([{'preview':i.preview_json,'result':i.result_json,'digest':i.confirmation_digest} for i in intents],sort_keys=True,default=str)
                for candidate in (token,rt):
                    if candidate in serialized: fail('Plaintext lifecycle confirmation token was persisted')
            finally: verify.close()
        print('[PASS] guarded MCP reversible part lifecycle preserves quantities/history, rejects drift, replays idempotently, records MCP client attribution and never exposes permanent purge')
    finally:
        engine.dispose(); path.write_bytes(before)
if __name__=='__main__': main()
