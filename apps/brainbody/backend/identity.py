"""Exact namespace checks only. Do not infer aliases or equate IDs across cohorts."""
def ownership_index(c,mode):
    result={}
    def add(cohort,subject,pid):
        if cohort and subject:result.setdefault((cohort,subject),set()).add(pid)
    if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nt_imaging_links'").fetchone():
        for r in c.execute('SELECT participant_id,cohort,subject FROM nt_imaging_links WHERE mode=?',(mode,)):add(r['cohort'],r['subject'],r['participant_id'])
    if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nt_source_records'").fetchone():
        for r in c.execute("SELECT participant_id,json_extract(payload,'$.source_cohort') AS cohort,json_extract(payload,'$.source_subject') AS subject FROM nt_source_records WHERE mode=?",(mode,)):add(r['cohort'],r['subject'],r['participant_id'])
    return result

def conflicting_owner(c,pid,mode,cohort,subject,index=None):
    if not cohort or not subject:return False
    owners=(ownership_index(c,mode) if index is None else index).get((cohort,subject),set())
    return any(owner!=str(pid) for owner in owners)
