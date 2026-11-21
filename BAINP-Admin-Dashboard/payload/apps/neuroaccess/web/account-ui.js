/* Account screens. Text content is never inserted as HTML. */
export function accountScreen(page,{api,h,afterLogin}){
 document.body.className='account-shell';document.querySelectorAll('body > nav').forEach(x=>x.hidden=true);
 const root=h('main',{id:'main',class:'account-page'}),nav=h('nav',{'aria-label':'Account navigation'},h('a',{href:'#/home'},'BAINP home'),h('a',{href:'#/journey'},'My Brain Health'),h('a',{href:'#/workspace/participants'},'My profile'));
 const feedback=h('p',{role:'status','aria-live':'polite',class:'account-message'});root.append(nav,feedback);document.getElementById('app').replaceChildren(root);
 const alive=()=>root.isConnected;
 const task=async(fn,button)=>{if(button)button.disabled=true;feedback.textContent='Working…';try{const message=await fn();if(alive())feedback.textContent=message||'';}catch(e){if(alive())feedback.textContent=e.message;}finally{if(button)button.disabled=false;}};
 const input=(form,label,type='text',required=true)=>{const id='acct-'+crypto.randomUUID(),control=h('input',{id,type,required,autocomplete:type==='password'?'current-password':type==='email'?'email':'off'});form.append(h('label',{for:id},label),control);return control;};
 const submit=(form,text,fn)=>{const b=h('button',{type:'submit'},text);form.append(b);form.addEventListener('submit',e=>{e.preventDefault();void task(fn,b);});return b;};
 const btn=(label,fn)=>{const b=h('button',{type:'button',onClick:()=>void task(fn,b)},label);return b;};
 const fresh=async()=>{const me=await api('/session');if(me.role==='admin')nav.append(h('a',{href:'#/admin'},'Administration'),h('a',{href:'#/test-lab'},'Test lab'));nav.append(h('a',{href:'#/security'},'Account security'));return me;};
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
  });root.append(form,h('p',{},h('a',{href:page==='signin'?'#/register':'#/signin'},page==='signin'?'Request an account':'Already have an account? Sign in')),h('p',{},h('a',{href:'#/recover'},'Recover access')));return;
 }
 if(page==='recover'){
  root.append(h('h1',{},'Recover access'),h('p',{},'Ask your administrator to verify your identity and issue a one-time recovery code. Codes expire after 30 minutes. Email and SMS delivery are not configured.'));
  const form=h('form',{class:'account-form'}),code=input(form,'Recovery code','password'),password=input(form,'New password','password'),confirm=input(form,'Confirm new password','password');password.minLength=15;password.autocomplete=confirm.autocomplete='new-password';
  submit(form,'Set new password',async()=>{if(password.value!==confirm.value)throw Error('Passwords do not match.');const r=await api('/auth/recover','POST',{code:code.value,new_password:password.value});form.reset();return r.message;});root.append(form,h('a',{href:'#/signin'},'Back to sign in'));return;
 }
 void task(async()=>{
  const me=await fresh();if(!alive())return;
  root.append(h('h1',{},page==='security'?'Account & security':page==='admin'?'Administration':'Test lab'),h('p',{},me.name+' · '+me.email+' · '+me.role),h('p',{class:'warning'},'Email not verified · Local testing. No email or SMS delivery configured.'));
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
