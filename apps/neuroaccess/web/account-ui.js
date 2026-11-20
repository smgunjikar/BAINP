/* Account screens. Text content is never inserted as HTML. */
export function accountScreen(page,{api,h,afterLogin,mount=null,onDirty=()=>{},personId=null,mode="active",onDone=null}){
 if(!mount){document.body.className='account-shell';document.querySelectorAll('body > nav').forEach(x=>x.hidden=true);}
 const root=h(mount?'section':'main',{id:mount?'profile-health-panel':'main',class:'account-page'}),nav=h('nav',{'aria-label':'Account navigation'},h('a',{href:'#/home'},'BAINP home'),h('a',{href:'#/journey'},'My Brain Health'),h('a',{href:'#/workspace/participants'},'My profile'));
 const feedback=h('p',{role:'status','aria-live':'polite',class:'account-message'});if(!mount)root.append(nav);root.append(feedback);(mount||document.getElementById('app')).replaceChildren(root);
 const alive=()=>root.isConnected;
 const task=async(fn,button)=>{if(button)button.disabled=true;feedback.textContent='Working…';try{const message=await fn();if(alive())feedback.textContent=message||'';}catch(e){if(alive())feedback.textContent=e.message;}finally{if(button)button.disabled=false;}};
 const input=(form,label,type='text',required=true)=>{const id='acct-'+crypto.randomUUID(),control=h('input',{id,type,required,autocomplete:type==='password'?'current-password':type==='email'?'email':'off'});form.append(h('label',{for:id},label),control);return control;};
 const submit=(form,text,fn)=>{const b=h('button',{type:'submit'},text);form.append(b);form.addEventListener('submit',e=>{e.preventDefault();void task(fn,b);});return b;};
 const btn=(label,fn)=>{const b=h('button',{type:'button',onClick:()=>void task(fn,b)},label);return b;};
 const fresh=async()=>{const me=await api('/session');if(me.role==='admin')nav.append(h('a',{href:'#/admin'},'Administration'),h('a',{href:'#/test-lab'},'Test lab'));nav.append(h('a',{href:'#/health'},'My health'),h('a',{href:'#/security'},'Account security'));return me;};
 if(page==='signin'||page==='register'){
  root.append(h('h1',{},page==='signin'?'Welcome back.':'Create your BAINP account'),h('p',{},page==='signin'?'Sign in to your personal workspace.':'New accounts require administrator approval. Email addresses are not yet verified by this local system.'));
  const form=h('form',{class:'account-form'}),name=page==='register'?input(form,'Your name'):null,email=input(form,'Email address','email'),password=input(form,'Password','password');password.maxLength=128;
  if(page==='register'){password.minLength=15;password.autocomplete='new-password';form.append(h('p',{},'Use a unique passphrase with at least 15 characters.'));}
  const confirm=page==='register'?input(form,'Confirm password','password'):null;
  if(confirm)confirm.autocomplete='new-password';
  submit(form,page==='signin'?'Sign in':'Request account',async()=>{
   if(confirm&&confirm.value!==password.value)throw Error('Passwords do not match.');
   if(page==='signin'){await api('/login','POST',{email:email.value,password:password.value});password.value='';await afterLogin();return;}
   const r=await api('/auth/register','POST',{email:email.value,password:password.value,name:name.value});password.value='';confirm.value='';return r.message;
  });root.append(form);
  root.append(h('p',{},h('a',{href:page==='signin'?'#/register':'#/signin'},page==='signin'?'Request an account':'Already have an account? Sign in')),h('p',{},h('a',{href:'#/recover'},'Recover access')));return;
 }
 if(page==='recover'){
  root.append(h('h1',{},'Recover access'),h('p',{},'Ask your administrator to verify your identity and issue a one-time recovery code. Codes expire after 30 minutes. Email and SMS delivery are not configured.'));
  const form=h('form',{class:'account-form'}),code=input(form,'Recovery code','password'),password=input(form,'New password','password'),confirm=input(form,'Confirm new password','password');password.minLength=15;password.autocomplete=confirm.autocomplete='new-password';
  submit(form,'Set new password',async()=>{if(password.value!==confirm.value)throw Error('Passwords do not match.');const r=await api('/auth/recover','POST',{code:code.value,new_password:password.value});form.reset();return r.message;});root.append(form,h('a',{href:'#/signin'},'Back to sign in'));return;
 }
 void task(async()=>{
  const me=await fresh();if(!alive())return;
  root.append(h('h1',{},page==='security'?'Account & security':page==='admin'?'Administration':'Test lab'),h('p',{},me.name+' · '+me.email+' · '+me.role),h('p',{class:'warning'},'Email not verified · Local testing. No email or SMS delivery configured.'));
  if(page==='health'){
   root.querySelector('h1').replaceChildren(h('span',{},'Health & Medical ID'));
   if(!personId){const owner=await api('/owner-profile?mode='+mode);personId=owner.participant_id;}
   if(!personId){root.append(h('p',{},'Create or select your profile first.'),h('a',{href:'#/workspace/participants'},'My profile'));return;}
   const healthPath='/auth/profile-health/'+encodeURIComponent(personId)+'?mode='+mode;
   let saved=await api(healthPath);if(!alive())return;if(saved.revision===0)root.append(h('p',{class:'setup-progress'},'Health setup · Final onboarding step. Optional details may be left blank.'));
   root.append(h('p',{},'For: '+saved.profile.display_name),h('p',{},'Date of birth: '+(saved.profile.birth_date||'Not recorded')+' · Age: '+saved.current_age),h('p',{},'Edit date of birth in Personal details. Optional health fields can be left blank. These are self-reported records, not diagnoses.'));
   const form=h('form',{class:'account-form medical-form'}),fields={};
   const choices={sex:[['','Not provided'],['female','Female'],['male','Male'],['intersex','Intersex'],['prefer_not_to_say','Prefer not to say']],blood_type:[['','Not provided'],['unknown','Unknown'],...['A+','A-','B+','B-','AB+','AB-','O+','O-'].map(v=>[v,v])],wheelchair:[['','Not provided'],['yes','Yes'],['no','No'],['unknown','Unknown'],['not_applicable','Not applicable']],skin_type:[['','Not provided'],['unknown','Unknown'],...['I','II','III','IV','V','VI'].map(v=>[v,'Type '+v]),['prefer_not_to_say','Prefer not to say']]};
   for(const key of ['medication_status','allergy_status','memory_changes','daily_function','sleep_concerns','mood_concerns','family_history','sensory_changes','falls_balance'])choices[key]=[['','Not provided'],['yes','Yes'],['no','No'],['unknown','Unknown']];
   const groups=[['Personal health details',[
    ['sex','Sex (optional)'],['height_cm','Height (cm)','number'],['weight_kg','Weight (kg)','number'],['blood_type','Blood type (self-reported)'],['skin_type','Fitzpatrick skin phototype (optional)'],['wheelchair','Wheelchair use'],['pregnancy','Pregnancy notes (optional)','textarea']]],
    ['Medications & allergies',[
    ['medication_status','Do you currently take medication?'],['medications','Current medications: name, dose, schedule and notes','textarea'],['heart_rate_medications','Medications affecting heart rate (self-reported)','textarea'],['allergy_status','Do you have any known allergies?'],['allergies','Allergens, reactions and severity (self-reported)','textarea']]],
    ['Medical ID & emergency contact',[
    ['conditions','Current conditions','textarea'],['emergency_contact','Emergency contact name, relationship and phone','textarea'],['additional_notes','Additional information and notes','textarea']]],
    ['Brain-health concerns — optional context',[
    ['memory_changes','Have you noticed changes in memory, attention or thinking?'],['changes_onset','When did changes begin? Sudden or gradual?','textarea'],['daily_function','Are changes affecting everyday activities?'],['sleep_concerns','Any ongoing sleep concerns?'],['mood_concerns','Any mood or anxiety concerns?'],['family_history','Any family history of cognitive disorders?'],['sensory_changes','Any changes in hearing or vision?'],['falls_balance','Any falls, balance or movement concerns?'],['substance_context','Alcohol, tobacco or other substance context (optional)','textarea'],['screening_notes','Further concerns to discuss with a clinician','textarea']]],
    ['Goals and reminder preferences',[
    ['move_goal','Personal move goal (kcal/day)','number'],['units','Preferred display units (note; measurements above remain cm/kg)'],['sleep_reminder','Preferred sleep reminder time','time'],['medication_reminder','Preferred medication reminder time','time'],['bp_reminder','Preferred blood pressure logging time','time'],['mood_reminder','Preferred mood logging time','time']]]];
   for(const [title,items]of groups){const panel=h('fieldset',{},h('legend',{},title));
    for(const [key,label,type]of items){const id='medical-'+key;let control;
     if(choices[key])control=h('select',{id},...choices[key].map(([value,text])=>h('option',{value},text)));
     else if(type==='textarea')control=h('textarea',{id,rows:3,maxlength:2000});
     else control=h('input',{id,type:type||'text',maxlength:2000,...(type==='number'?{step:'any'}:{})});
     control.value=saved.details[key]||'';fields[key]=control;panel.append(h('label',{for:id},label),control);
    }
    if(title==='Personal health details')panel.append(h('p',{class:'muted'},'Fitzpatrick I–VI describes skin response to sunlight. It is not a cognitive risk score. Choose Unknown if unsure.'),h('a',{href:'https://dermnetnz.org/topics/skin-phototype',target:'_blank',rel:'noopener noreferrer'},'Skin phototype reference'));
    if(title==='Brain-health concerns — optional context')panel.append(h('p',{},'These questions record concerns; they are not a validated screening instrument and do not diagnose or calculate dementia risk. Discuss persistent changes with a qualified clinician. Sudden confusion, new weakness or speech difficulty requires urgent medical attention.'));
    if(title==='Goals and reminder preferences')panel.append(h('p',{},'Reminder preferences are stored only. Notifications and wearable measurements are not connected.'));
    form.append(panel);
   }
   const lookup=h('section',{class:'medication-lookup'},h('h3',{},'Medication name library'));
   const term=input(lookup,'Search a medicine name','search',false),lookupConsent=h('input',{id:'medicine-search-consent',type:'checkbox'}),results=h('div',{role:'status'});
   lookup.append(h('label',{for:'medicine-search-consent'},lookupConsent,' Send only this search term to the US National Library of Medicine (RxNorm).'),h('p',{},'Optional online name lookup. No profile is sent. Coverage is not a complete Indian brand catalogue. Suggestions are not prescriptions or interaction checks.'),btn('Search medication library',async()=>{
    if(!lookupConsent.checked)throw Error('Agree to external search first, or enter the medicine manually.');
    const response=await api('/auth/medications/search','POST',{term:term.value,consent:lookupConsent.checked});results.replaceChildren();
    if(!response.items.length)results.append(h('p',{},'No match found. Enter the medicine manually.'));
    for(const item of response.items)results.append(btn('Add: '+item.name,async()=>{fields.medications.value=[fields.medications.value,item.name+' [RxNorm '+item.rxcui+']'].filter(Boolean).join('\n');fields.medication_status.value='yes';onDirty(true);return 'Added to the draft. Confirm the product and save your health details.';}));
    return response.truncated?'Showing the first 50 matches. Refine the medicine name.':'Search complete.';
   }),results);form.insertBefore(lookup,form.children[2]);
   form.addEventListener('input',()=>onDirty(true));
   const agree=h('input',{id:'health-consent',type:'checkbox',required:true});
   form.append(h('label',{for:'health-consent'},agree,' I agree to store these optional health details for this participant. I can clear them later.'),h('p',{},'Policy: optional-profile-health-v1. Saving records your agreement and time. Previous assessment results remain unchanged.'));
   submit(form,'Save health details',async()=>{const response=await api(healthPath,'PUT',{revision:saved.revision,consent:agree.checked,details:{...Object.fromEntries(Object.entries(fields).map(([key,control])=>[key,control.value])),health_reviewed:'yes'}});saved=await api(healthPath);onDirty(false);return response.message;});root.append(form);
   root.append(btn('Finish setup / return to overview',async()=>{if(onDone)onDone();else location.hash='/workspace/home';}));
   const share=h('section',{class:'medical-share'},h('h2',{},'Create a shareable Medical ID'),h('p',{},'Exports use saved information. Choose exactly what to include. Anyone receiving the file can read it; exported copies cannot be remotely revoked. No public link or emergency-service connection is created.'));
   const shareFields={};for(const [key,label]of [['display_name','Name'],['birth_date','Date of birth'],['sex','Sex'],['blood_type','Blood type'],['medications','Medications'],['allergies','Allergies'],['conditions','Current conditions'],['emergency_contact','Emergency contact'],['additional_notes','Additional notes']]){const control=h('input',{type:'checkbox',id:'share-'+key});shareFields[key]=[control,label];share.append(h('label',{for:'share-'+key},control,label));}
   const shareConsent=h('input',{id:'share-consent',type:'checkbox'});share.append(h('label',{for:'share-consent'},shareConsent,' I understand the privacy implications and want to create this Medical ID file.'));
   function download(name,content,type){const url=URL.createObjectURL(new Blob([content],{type}));const link=h('a',{href:url,download:name});document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
   share.append(btn('Download Medical ID card',async()=>{
    if(!shareConsent.checked)throw Error('Confirm Medical ID export consent.');const selected=Object.entries(shareFields).filter(([,entry])=>entry[0].checked);if(!selected.length)throw Error('Select at least one field.');
    const record=await api(healthPath),doc=document.implementation.createHTMLDocument('BAINP Medical ID');doc.documentElement.lang=document.documentElement.lang||'en';
    const meta=doc.createElement('meta');meta.httpEquiv='Content-Security-Policy';meta.content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'";doc.head.append(meta);
    const style=doc.createElement('style');style.textContent='body{font:18px system-ui;max-width:680px;margin:32px auto;padding:24px;border:2px solid #222;border-radius:18px}dt{font-weight:bold;margin-top:18px}dd{margin:4px 0;white-space:pre-wrap;overflow-wrap:anywhere}small{display:block;margin-top:24px}';doc.head.append(style);
    const title=doc.createElement('h1');title.textContent='BAINP Medical ID';doc.body.append(title);const list=doc.createElement('dl');
    for(const [key,[control,label]]of selected){const dt=doc.createElement('dt'),dd=doc.createElement('dd');dt.textContent=label;let value=key==='display_name'||key==='birth_date'?record.profile[key]:record.details[key];if(!value&&key==='allergies'&&record.details.allergy_status==='no')value='No known allergies reported';if(!value&&key==='medications'&&record.details.medication_status==='no')value='No current medications reported';dd.textContent=String(value||'Not recorded');list.append(dt,dd);}doc.body.append(list);
    const note=doc.createElement('small');note.textContent='Self-reported, not clinically verified. ID '+personId.slice(0,8)+' · Generated '+new Date().toLocaleString()+'. Not an emergency-service connection. Use your browser print command to print this card.';doc.body.append(note);
    download('BAINP-Medical-ID.html','<!doctype html>'+doc.documentElement.outerHTML,'text/html');return 'Medical ID file created from your selected saved fields.';
   }));root.append(share);
   const exportConsent=h('input',{id:'export-confirm',type:'checkbox'});root.append(h('h2',{},'Export health workspace'),h('p',{},'Exports all accessible records in this workspace database, including profiles, saved assessments, check-ins, consent and optional health data. External raw files, other databases, cloud/device data and credentials are excluded. Administrators: this includes every participant in the currently opened workspace.'),h('label',{for:'export-confirm'},exportConsent,' I want to download the private data in this workspace.'),btn('Export health workspace JSON',async()=>{if(!exportConsent.checked)throw Error('Confirm private data export.');const data=await api('/auth/export-health-workspace','POST',{confirm:true});download('BAINP-health-workspace.json',JSON.stringify(data,null,2),'application/json');return 'Exported records and a scope manifest. Keep this private file secure.';}),btn('Withdraw consent and clear optional health details',async()=>{if(prompt('Type CLEAR to withdraw optional health storage consent and clear these details')!=='CLEAR')return 'Cancelled.';const result=await api(healthPath+'&revision='+saved.revision,'DELETE',{});onDirty(false);accountScreen('health',{api,h,afterLogin,mount,onDirty,personId,mode,onDone});return result.message;}));
   const legacy=h('details',{},h('summary',{},'Previous account-level health record'),h('p',{},'Earlier versions stored one health record for the whole account. Review it before assigning any information to this participant.'));
   legacy.append(btn('Review previous health record',async()=>{const old=await api('/auth/health');legacy.querySelector('.legacy-record')?.remove();const panel=h('div',{class:'legacy-record'});for(const [key,value]of Object.entries(old.details))panel.append(h('p',{},key+': '+value));
    if(!Object.keys(old.details).length){panel.append(h('p',{},'No previous account-level health details.'));legacy.append(panel);return;}
    panel.append(btn('Copy compatible fields into this participant draft',async()=>{if(!confirm('Copy this account-level information into the draft for '+saved.profile.display_name+'? Confirm it belongs to this person.'))return 'Cancelled.';for(const [key,control]of Object.entries(fields)){if(key in old.details){const value=old.details[key];if(choices[key]&&!choices[key].some(([v])=>v===value))continue;control.value=value;}}onDirty(true);return 'Copied into the draft only. Review all fields, consent and save. Date of birth must be entered in Personal details.';}),btn('Clear previous account-level record',async()=>{if(prompt('Type CLEAR OLD to remove the previous account-level health record')!=='CLEAR OLD')return 'Cancelled.';const result=await api('/auth/health?revision='+old.revision,'DELETE',{});panel.replaceChildren(h('p',{},result.message));return result.message;}));legacy.append(panel);
   }));root.append(legacy);
   return;
  }
  if(page==='security'){
   const form=h('form',{class:'account-form'}),current=input(form,'Current password','password'),next=input(form,'New password','password'),confirm=input(form,'Confirm new password','password');next.minLength=15;next.autocomplete=confirm.autocomplete='new-password';
   submit(form,'Change password',async()=>{if(next.value!==confirm.value)throw Error('Passwords do not match.');const r=await api('/auth/password','POST',{current_password:current.value,new_password:next.value});form.reset();location.hash='/signin';return r.message;});root.append(form);
   const sessions=await api('/auth/sessions');root.append(h('h2',{},'Active sessions'),h('p',{},sessions.items.length+' session(s). Sessions expire after 30 minutes idle or 8 hours total.'),btn('Sign out everywhere',async()=>{await api('/auth/logout-all','POST',{});location.href='/#/signin';location.reload();}),btn('Sign out here',async()=>{await api('/logout','POST',{});location.href='/#/signin';location.reload();}));return;
  }
  if(me.role!=='admin')throw Error('Administrator access is required.');
  if(page==='admin'){
   const stats=await api('/admin/overview');
   root.append(h('h2',{},'BAINP administration centre'),h('p',{},'Private user workspaces • Account approval • Sign-in activity • Separate test records'));
   const cards=h('div',{class:'account-list'});
   for(const [label,value] of [['Approved accounts',stats.accounts.active||0],['Awaiting approval',stats.accounts.pending||0],['Disabled accounts',stats.accounts.disabled||0],['Valid login sessions',stats.valid_sessions],['Legacy active records',stats.legacy_records.active||0],['Demo test records',stats.legacy_records.demo||0]])cards.append(h('section',{},h('h3',{},label),h('strong',{},String(value))));
   root.append(cards,h('p',{},'Valid sessions means unexpired and used within 30 minutes; it does not prove someone is online. Demo records are test profiles, not login accounts.'),btn('Refresh dashboard',async()=>{accountScreen('admin',{api,h,afterLogin});}));
   const date=v=>v?new Date(v*1000).toLocaleString():'Never';
   const rows=h('tbody');const search=h('input',{type:'search','aria-label':'Search account activity',placeholder:'Search name or email'});
   const draw=()=>{rows.replaceChildren(...stats.activity.filter(u=>(u.name+' '+u.email).toLowerCase().includes(search.value.toLowerCase())).map(u=>h('tr',{},...[u.name,u.email,u.status,date(u.created),date(u.last_login),String(u.sessions)].map(v=>h('td',{},v)))));};search.addEventListener('input',draw);draw();
   root.append(h('h2',{},'Account activity'),search,h('p',{},'Showing up to '+stats.account_limit+' newest accounts.'),h('div',{class:'scroll-table'},h('table',{},h('thead',{},h('tr',{},...['Name','Email','Status','Registered','Last successful login','Valid sessions'].map(v=>h('th',{scope:'col'},v)))),rows)));
   root.append(h('h2',{},'Latest sign-in and registration events'),h('div',{class:'scroll-table'},h('table',{},h('thead',{},h('tr',{},...['Time','Event','Account'].map(v=>h('th',{scope:'col'},v)))),h('tbody',{},...stats.events.map(e=>h('tr',{},h('td',{},date(e.stamp)),h('td',{},e.action),h('td',{},e.email||'Unidentified / registration request')))))));
   root.append(h('a',{href:'#/test-lab'},'Open separate active/demo test lab'));
  }
  const access=h('form',{class:'account-form'});access.append(h('h2',{},'Choose workspace'),h('p',{},'Every administrator access to another workspace is recorded.'));
  const target=h('select',{'aria-label':'Workspace'},h('option',{value:'self'},'My personal workspace'),h('option',{value:'legacy'},'Existing active/demo test records'));
  const users=(await api('/admin/users')).items;for(const u of users.filter(x=>x.status==='active'))target.append(h('option',{value:u.id},u.email));access.append(target);
  const reason=input(access,'Reason for access'),password=input(access,'Confirm your administrator password','password');reason.minLength=8;
  submit(access,'Open selected workspace',async()=>{await api('/admin/workspace','POST',{target:target.value,reason:reason.value,password:password.value});password.value='';location.href=target.value==='legacy'?'/?mode=active#/test-lab':'/?mode=active#/workspace/participants';location.reload();});root.append(access);
  if(page==='admin'){
   root.append(h('h2',{},'Accounts'),h('p',{},'Approve requests, disable access, or issue recovery codes. Archive closes an account and retains its records; it does not erase data.'));
   const list=h('div',{class:'account-list'});for(const u of users){
    const row=h('section',{},h('h3',{},u.name),h('p',{},u.email+' · '+u.status+' · '+u.role));
    const form=h('form'),action=h('select',{'aria-label':'Action for '+u.email},...['approve','disable','enable','recovery','delete'].map(x=>h('option',{value:x},x==='delete'?'Archive account':x==='recovery'?'Issue recovery code':x[0].toUpperCase()+x.slice(1))));
    form.append(action);const why=input(form,'Reason'),pass=input(form,'Administrator password','password');why.minLength=8;
    submit(form,'Apply action',async()=>{if(action.value==='delete'&&prompt('Type the exact email to archive this account:')!==u.email)throw Error('Archive cancelled.');const r=await api('/admin/users/'+u.id,'POST',{action:action.value,password:pass.value,reason:why.value});pass.value='';return r.recovery_code?'Share this one-time code privately after verifying identity. Expires in 30 minutes:\n'+r.recovery_code:r.message;});row.append(form);list.append(row);
   }root.append(list,h('h2',{},'Recent audit events'));
   const result=await api('/admin/audit');const table=h('table',{},h('thead',{},h('tr',{},...['Time','Actor','Action','Target','Detail'].map(x=>h('th',{scope:'col'},x)))),h('tbody',{},...result.items.map(x=>h('tr',{},...[new Date(x.stamp*1000).toLocaleString(),x.actor||'Anonymous',x.action,x.target,x.detail].map(v=>h('td',{},v))))));root.append(h('div',{class:'scroll-table'},table));return;
  }
  root.append(h('p',{class:'warning'},'Test workspace: '+me.workspace+'. Active and demo records remain separate. Deleting a record removes its related database records; exported files and backups may remain.'));
  if(me.workspace!=='legacy'){root.append(h('p',{},'Use Choose workspace above to enter Existing active/demo test records.'));return;}
  const mode=new URLSearchParams(location.search).get('mode')==='demo'?'demo':'active';root.append(h('nav',{},h('a',{href:'/?mode=active#/test-lab'},'Active records'),h('a',{href:'/?mode=demo#/test-lab'},'Demo records')),h('h2',{},mode==='demo'?'Demo records':'Active records'));
  let offset=0;const list=h('div',{class:'account-list'});root.append(list);
  const load=async()=>{const result=await api('/participants?mode='+mode+'&offset='+offset);for(const record of result.items){const row=h('section',{},h('h3',{},record.profile.display_name),h('p',{},record.id),btn('Open record',async()=>{await api('/owner-profile/'+record.id+'?mode='+mode,'PUT',{});location.href='/?mode='+mode+'#/workspace/participants';location.reload();}),btn('Delete record',async()=>{if(prompt('Type DELETE '+record.id+' to permanently remove this database record:')!=='DELETE '+record.id)throw Error('Deletion cancelled.');const latest=await api('/participants/'+record.id+'?mode='+mode);await api('/participants/'+record.id+'?mode='+mode,'DELETE',{confirm_id:record.id,revision:latest.revision});row.remove();return 'Record deleted.';}));list.append(row);}offset+=50;more.hidden=!result.has_more;};
  const more=btn('Load more',load);root.append(more);await load();
  const form=h('form',{class:'account-form'});form.append(h('h2',{},'Create test record'));const name=input(form,'Test display name'),consent=h('input',{type:'checkbox',required:true,id:'test-consent'});form.append(h('label',{for:'test-consent'},consent,' I authorize storing this test profile.'));
  submit(form,'Create test record',async()=>{const profile={display_name:name.value,age:30,education_years:12,digital_familiarity:'medium',language:'en',vision_limitation:false,vision_aid:'none',hearing_limitation:false,hearing_aid:false,motor_limitation:false,input_method:'keyboard',device_type:'desktop',text_size:'standard',high_contrast:false,reduced_motion:false,assistance:'none',assistance_authorized:false,can_see_and_respond:'unsure'};const r=await api('/participants','POST',{id:crypto.randomUUID(),mode,profile,consent_to_store:consent.checked});await api('/owner-profile/'+r.id+'?mode='+mode,'PUT',{});location.href='/?mode='+mode+'#/workspace/participants';location.reload();});root.append(form);
 });
}
