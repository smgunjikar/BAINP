"""BBC-BE v1 data dictionary. Units remain as reported; no silent conversion or cutoffs."""
VERSION='bbc-be-research-v1.2.0'
SCOPES={'context','clinical_biomarkers','family_history','genomic_summary','molecular_research'}
SYSTEMS={'cardiovascular':'Cardiovascular','metabolic':'Metabolic','sleep':'Sleep & activity','wellbeing':'Mental wellbeing','lifestyle':'Lifestyle','history':'Health & medication history','molecular':'Molecular biomarker research','genomic':'Family & genomic context'}
def metric(label,system,units,origins,scope='context',assay=False):
    return dict(label=label,system=system,units=units,origins=origins,scope=scope,assay_required=assay)
CLINICAL=['clinician_entry','lab_report','professional_report'];LAB=['lab_report','research_lab','professional_report']
METRICS={
 'bp_systolic':metric('Systolic blood pressure','cardiovascular',['mmHg'],['self_report','clinician_entry','professional_report','device']),
 'bp_diastolic':metric('Diastolic blood pressure','cardiovascular',['mmHg'],['self_report','clinician_entry','professional_report','device']),
 'heart_rate':metric('Heart rate','cardiovascular',['bpm'],['self_report','clinician_entry','device']),
 'hba1c':metric('HbA1c','metabolic',['%','mmol/mol'],LAB,'clinical_biomarkers',True),
 'glucose':metric('Glucose','metabolic',['mg/dL','mmol/L'],LAB+['device'],'clinical_biomarkers',True),
 'ldl_cholesterol':metric('LDL cholesterol','metabolic',['mg/dL','mmol/L'],LAB,'clinical_biomarkers',True),
 'hdl_cholesterol':metric('HDL cholesterol','metabolic',['mg/dL','mmol/L'],LAB,'clinical_biomarkers',True),
 'total_cholesterol':metric('Total cholesterol','metabolic',['mg/dL','mmol/L'],LAB,'clinical_biomarkers',True),
 'triglycerides':metric('Triglycerides','metabolic',['mg/dL','mmol/L'],LAB,'clinical_biomarkers',True),
 'sleep_duration':metric('Sleep duration','sleep',['h','min'],['self_report','clinician_entry','device']),
 'sleep_efficiency':metric('Device-estimated sleep efficiency','sleep',['%'],['device']),
 'steps':metric('Daily steps','sleep',['count'],['device','self_report']),
 'movement_rms':metric('Movement RMS','sleep',['g'],['device']),
 'activity_minutes':metric('Reported activity duration','lifestyle',['min/week','min/day'],['self_report','clinician_entry','device']),
 'questionnaire_total':metric('Externally administered questionnaire total','wellbeing',['score'],['self_report','clinician_entry','professional_report']),
 'amyloid_beta_42':metric('Amyloid beta 42','molecular',['pg/mL','ng/L'],LAB,'clinical_biomarkers',True),
 'amyloid_beta_40':metric('Amyloid beta 40','molecular',['pg/mL','ng/L'],LAB,'clinical_biomarkers',True),
 'ptau181':metric('Phosphorylated tau 181','molecular',['pg/mL','ng/L'],LAB,'clinical_biomarkers',True),
 'ptau217':metric('Phosphorylated tau 217','molecular',['pg/mL','ng/L'],LAB,'clinical_biomarkers',True),
 'nfl':metric('Neurofilament light','molecular',['pg/mL','ng/L'],LAB,'clinical_biomarkers',True),
 'gfap':metric('GFAP','molecular',['pg/mL','ng/L'],LAB,'clinical_biomarkers',True),
 'crp':metric('C-reactive protein','molecular',['mg/L'],LAB,'clinical_biomarkers',True),
 'f2_isoprostanes':metric('F2-isoprostanes (experimental)','molecular',['pg/mL','ng/mL','ng/mg creatinine'],['research_lab'],'molecular_research',True),
 'oxidized_nucleic_acid_marker':metric('Assay-specific oxidized nucleic-acid marker','molecular',['ng/mL','ng/mg creatinine'],['research_lab'],'molecular_research',True),
}
REPORTS={
 'condition':dict(scope='context',system='history',label='Reported medical condition'),
 'medication':dict(scope='context',system='history',label='Reported medication/context change'),
 'sleep_report':dict(scope='context',system='sleep',label='Reported sleep context'),
 'lifestyle_report':dict(scope='context',system='lifestyle',label='Reported lifestyle context'),
 'family_history':dict(scope='family_history',system='genomic',label='Consented family-history context'),
 'professional_genomic_finding':dict(scope='genomic_summary',system='genomic',label='Professional genomic summary'),
 'wellbeing_report':dict(scope='context',system='wellbeing',label='Reported wellbeing context')}
EVIDENCE=[
 dict(id='WHO-PREVENTION',title='WHO dementia risk reduction guidelines, second edition',url='https://www.who.int/publications/i/item/9789240123557',text='Population guidance for adults without dementia, including adults with mild cognitive impairment. It covers health behaviours and management of relevant health conditions.',source_checked_on='2026-11-07'),
 dict(id='NIA-COGNITIVE-HEALTH',title='NIA cognitive health and older adults',url='https://www.nia.nih.gov/health/cognitive-health-and-older-adults',text='Background on physical health, sleep and medicines in discussions about cognitive health.',source_checked_on='2026-11-07'),
 dict(id='WHO-DEMENTIA',title='WHO: dementia and potentially modifiable health context',url='https://www.who.int/news-room/fact-sheets/detail/dementia',text='General information includes physical activity, tobacco, blood pressure, cholesterol and blood glucose. This is not an individually calculated prevention benefit or medication recommendation.'),
 dict(id='NIA-BIOMARKERS',title='NIA: biomarkers in dementia assessment and research',url='https://www.nia.nih.gov/health/biomarkers-dementia-detection-and-research',text='Biomarkers are part of a broader assessment. The meaning of a result depends on the test and clinical context; this module does not generate a dementia diagnosis.'),
 dict(id='FHIR-OBSERVATION',title='HL7 FHIR: observation timing and reference-range concepts',url='https://hl7.org/fhir/observation-definitions.html',text='Physiologically relevant time, result-availability time and reference context are distinct concepts. This implementation is not a certified FHIR server.')]

for item in EVIDENCE:item.setdefault('source_checked_on','2026-11-06')
