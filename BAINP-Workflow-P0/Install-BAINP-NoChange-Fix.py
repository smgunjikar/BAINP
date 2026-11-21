"""Preserve workflow state when saving identical profiles/permissions. No database migration."""
import argparse
import ast
import shutil
from datetime import datetime
from pathlib import Path

PROFILE_OLD = """            c.execute('UPDATE participants SET profile=?,revision=revision+1,updated_at=? WHERE id=?',(dump(profile),now(),identity))"""
PROFILE_NEW = """            # bainp_no_change_profile_v1: an unchanged save is not a profile revision.
            if json.loads(row['profile']) == profile:
                return view_person(row)
""" + PROFILE_OLD
CONSENT_OLD = """            revision = current['revision'] + 1
            connection.execute('INSERT INTO ncw_consents"""
CONSENT_NEW = """            # bainp_no_change_consent_v1: preserve evidence/session for unchanged scopes.
            scopes = ('enabled', 'history_allowed', 'assessment_allowed', 'case_tracking')
            if current['revision'] > 0 and all(bool(current[key]) == payload[key] for key in scopes):
                return remember(connection, payload['operation_id'], pid, mode, request,
                                dict(revision=current['revision'], replayed=False))
            revision = current['revision'] + 1
            connection.execute('INSERT INTO ncw_consents"""

SPECS = [
 ('apps/neuroaccess/backend/api.py','bainp_no_change_profile_v1',PROFILE_OLD,PROFILE_NEW),
 ('apps/neurocontinuum/backend/engine.py','bainp_no_change_consent_v1',CONSENT_OLD,CONSENT_NEW),
]

def prepare(root):
    result = {}
    for rel, marker, old, new in SPECS:
        path = root / rel
        source = path.read_text(encoding='utf-8-sig')
        if marker in source:
            if new not in source: raise ValueError('Modified patch marker: ' + rel)
            continue
        if source.count(old) != 1:
            raise ValueError('Unsupported source structure; nothing changed: ' + rel)
        changed = source.replace(old,new,1)
        ast.parse(changed)
        result[rel] = changed
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-root',required=True,type=Path)
    p.add_argument('--check',action='store_true')
    args=p.parse_args();root=args.project_root.resolve()
    updates=prepare(root)
    print('Compatibility passed. Files to update:',len(updates))
    if args.check or not updates:return
    backup=root/'patch_backups'/('unchanged-save-'+datetime.now().strftime('%Y%m%d-%H%M%S%f'))
    originals={rel:(root/rel).read_bytes() for rel in updates}
    # Complete backups before touching source.
    for rel in updates:
        target=backup/rel;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(root/rel,target)
    try:
        for rel,source in updates.items():
            (root/rel).write_text(source,encoding='utf-8')
    except BaseException:
        for rel,data in originals.items():(root/rel).write_bytes(data)
        raise
    print('Installed. Restart the backend. Backup:',backup)

if __name__=='__main__':main()
