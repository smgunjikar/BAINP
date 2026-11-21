"""Independent BBC-BE interpretation limits. No clinical threshold or diagnosis engine."""
def findings(record):
    out=[]
    def add(code,text):out.append(dict(code=code,text=text))
    if record['quality']!='usable':add('SOURCE_QUALITY_'+record['quality'].upper(),'Source quality excludes this record from numeric trend summaries.')
    if record.get('needs_review'):add('REPORTED_REVIEW_REQUEST','A concern or review request was recorded; it is not an engine-generated diagnosis.')
    if record['kind']=='professional_genomic_finding':add('PROFESSIONAL_GENOMIC_CONTEXT','Professional summary only. No individual disease-onset prediction or automatic genetic interpretation.')
    if record.get('metric') in ('f2_isoprostanes','oxidized_nucleic_acid_marker'):add('EXPERIMENTAL_MOLECULAR_CONTEXT','Research assay only. A peripheral result is not a direct measure of brain/neuronal oxidative injury.')
    if record.get('metric')=='sleep_efficiency':add('DEVICE_SLEEP_ESTIMATE','Device estimate; not equivalent to polysomnography.')
    if record.get('metric')=='questionnaire_total':add('EXTERNAL_INSTRUMENT_CONTEXT','Externally administered total. Instrument validity, permissions and clinical meaning are not inferred by this engine.')
    if record['kind']=='measurement':
        if record['qualifier']!='exact':add('NONPOINT_OR_ABSENT_RESULT','Censored/absent result is preserved and excluded from point-value trends and interval-position labels.')
        assay=record.get('assay')
        value=record.get('value')
        if assay and value is not None and record['qualifier']=='exact':
            lo,hi=assay.get('lower_quantitation_limit'),assay.get('upper_quantitation_limit')
            if (lo is not None and value<lo) or (hi is not None and value>hi):add('QUANTITATION_LIMIT_REVIEW','Reported exact value is outside supplied quantitation limits; check the original assay report.')
    return out

def interval_position(record):
    ref=record.get('reference')
    if not ref:return 'NO_SUPPLIED_REFERENCE'
    if record.get('qualifier')!='exact' or record.get('value') is None:return 'NO_POINT_INTERPRETATION'
    if record['quality']!='usable':return 'SOURCE_QUALITY_REVIEW'
    if ref['applies_to_participant']!='yes':return 'REFERENCE_APPLICABILITY_UNCONFIRMED'
    if ref['kind']=='decision_limit':return 'CLINICAL_DECISION_LIMIT_REQUIRES_REVIEW'
    if ref.get('lower') is not None and record['value']<ref['lower']:return 'BELOW_SUPPLIED_INTERVAL'
    if ref.get('upper') is not None and record['value']>ref['upper']:return 'ABOVE_SUPPLIED_INTERVAL'
    return 'WITHIN_SUPPLIED_INTERVAL_NOT_A_HEALTH_CLASSIFICATION'

BOUNDARIES=['No dementia diagnosis, treatment selection or individualized prevention benefit is calculated.',
 'Assay, specimen, units, method, source and context remain distinct. No silent cross-assay or unit pooling.',
 'A supplied reference interval is not a disease diagnosis or a universal cutoff.',
 'Wearables do not supply a direct measurement of brain oxidative stress in this implementation.',
 'Temporal co-occurrence does not establish causation. Later-entered records are not treated as previously known evidence.',
 'Genomic summaries require separate consent and explicit disclosure; raw variant interpretation is not supported.']
