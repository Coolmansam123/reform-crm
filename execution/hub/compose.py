"""
Compose-email FAB (floating action button) HTML and JS.
Injected on every desktop page by `_page()`.
"""

# ─── Compose FAB ───────────────────────────────────────────────────────────────
_COMPOSE_HTML = (
    '<div class="compose-overlay" id="compose-overlay" onclick="if(event.target===this)closeCompose()">'
    '<div class="compose-box">'
    '<div class="compose-header">'
    '<h3 id="compose-title">New Email</h3>'
    '<button class="compose-close" onclick="closeCompose()">\u2715</button>'
    '</div>'
    '<div class="compose-fields">'
    '<div class="compose-field-row">'
    '<span class="compose-field-label">To</span>'
    '<div style="position:relative;flex:1">'
    '<input type="text" id="compose-to" placeholder="Name or email" autocomplete="off" data-1p-ignore data-lpignore="true" data-bwignore="true">'
    '<div id="compose-ac-list" class="compose-ac-list"></div>'
    '</div>'
    '<span class="compose-ccbcc-toggle" id="ccbcc-toggle" onclick="toggleCcBcc()">Cc/Bcc</span>'
    '</div>'
    '<div class="compose-ccbcc" id="ccbcc-fields">'
    '<div class="compose-field-row"><span class="compose-field-label">Cc</span><input type="text" id="compose-cc" placeholder="Email addresses"></div>'
    '<div class="compose-field-row"><span class="compose-field-label">Bcc</span><input type="text" id="compose-bcc" placeholder="Email addresses"></div>'
    '</div>'
    '<div class="compose-field-row" style="border-bottom:none">'
    '<span class="compose-field-label">Subj</span>'
    '<input type="text" id="compose-subject" placeholder="Subject">'
    '</div>'
    '</div>'
    '<div class="compose-body-wrap">'
    '<textarea id="compose-body" placeholder="Write your message\u2026"></textarea>'
    '</div>'
    '<div class="compose-sig" id="compose-sig">'
    'Best regards,<br>'
    '<strong>Reform Chiropractic</strong><br>'
    '(832) 699-3148 \u00b7 reformchiropractic.com'
    '</div>'
    '<div class="compose-toolbar">'
    '<select class="compose-template-sel" id="compose-template" onchange="_applyTemplate()">'
    '<option value="">Templates\u2026</option>'
    '<option value="intro_attorney">Attorney Intro</option>'
    '<option value="followup">General Follow-Up</option>'
    '<option value="referral_thanks">Referral Thank You</option>'
    '<option value="event_invite">Event Invitation</option>'
    '</select>'
    '<div class="spacer"></div>'
    '<div class="compose-actions">'
    '<div class="compose-status" id="compose-status"></div>'
    '<button class="btn-cancel" onclick="closeCompose()">Cancel</button>'
    '<button class="btn-send" id="btn-send" onclick="sendEmail()">Send \u2192</button>'
    '</div></div></div></div>'
)
_COMPOSE_JS = """
/* ── Autocomplete ──────────────────────────────────────────────── */
var _acCache=null, _acIdx=-1;
async function _acLoad(){
  if(_acCache) return _acCache;
  try{var r=await fetch('/api/contacts/autocomplete');if(r.ok)_acCache=await r.json();else _acCache=[];}
  catch(e){_acCache=[];}
  return _acCache;
}
function _acFilter(q){
  if(!_acCache||!q) return [];
  var lq=q.toLowerCase();
  return _acCache.filter(function(c){return c.n.toLowerCase().includes(lq)||(c.e&&c.e.toLowerCase().includes(lq));}).slice(0,8);
}
function _acRender(items){
  var el=document.getElementById('compose-ac-list'); _acIdx=-1;
  if(!items.length){el.classList.remove('open');return;}
  el.innerHTML=items.map(function(c,i){
    return '<div class="compose-ac-item" data-idx="'+i+'" onmousedown="_acPick('+i+')">'+
      '<span class="compose-ac-name">'+esc(c.n)+'</span>'+(c.e?'<span class="compose-ac-email">'+esc(c.e)+'</span>':'')+'</div>';
  }).join('');
  el.classList.add('open');
}
function _acPick(i){
  var items=_acFilter(document.getElementById('compose-to').value.trim());
  if(items[i]){document.getElementById('compose-to').value=items[i].e||items[i].n;document.getElementById('compose-ac-list').classList.remove('open');document.getElementById('compose-subject').focus();}
}
function _acKeydown(e){
  var el=document.getElementById('compose-ac-list');if(!el.classList.contains('open'))return;
  var items=el.querySelectorAll('.compose-ac-item');
  if(e.key==='ArrowDown'){e.preventDefault();_acIdx=Math.min(_acIdx+1,items.length-1);items.forEach(function(x,j){x.classList.toggle('sel',j===_acIdx);});}
  else if(e.key==='ArrowUp'){e.preventDefault();_acIdx=Math.max(_acIdx-1,0);items.forEach(function(x,j){x.classList.toggle('sel',j===_acIdx);});}
  else if(e.key==='Enter'&&_acIdx>=0){e.preventDefault();_acPick(_acIdx);}
  else if(e.key==='Escape'){el.classList.remove('open');}
}
(function(){
  var inp=document.getElementById('compose-to'); if(!inp) return;
  inp.addEventListener('input',function(){var q=inp.value.trim();if(q.length<1){document.getElementById('compose-ac-list').classList.remove('open');return;}_acLoad().then(function(){_acRender(_acFilter(q));});});
  inp.addEventListener('keydown',_acKeydown);
  inp.addEventListener('blur',function(){setTimeout(function(){document.getElementById('compose-ac-list').classList.remove('open');},150);});
})();

/* ── CC/BCC toggle ─────────────────────────────────────────────── */
function toggleCcBcc(){
  var el=document.getElementById('ccbcc-fields');
  el.classList.toggle('open');
  document.getElementById('ccbcc-toggle').textContent=el.classList.contains('open')?'Hide':'Cc/Bcc';
  if(el.classList.contains('open'))document.getElementById('compose-cc').focus();
}

/* ── Templates ─────────────────────────────────────────────────── */
var _TEMPLATES = {
  intro_attorney: {
    subject: 'Introduction: Reform Chiropractic \u2014 PI Case Collaboration',
    body: 'Good afternoon,\\n\\nMy name is Daniel Cisneros and I\\'m reaching out from Reform Chiropractic. We specialize in treating personal injury patients and would love to discuss how we can support your firm\\'s clients with their treatment needs.\\n\\nWe provide thorough documentation, timely reporting, and ensure your clients receive the highest quality care throughout their recovery.\\n\\nWould you be available for a brief call this week to discuss a potential partnership?'
  },
  followup: {
    subject: 'Following Up \u2014 Reform Chiropractic',
    body: 'Hi,\\n\\nI wanted to follow up on our recent conversation. Please let me know if you have any questions or if there\\'s anything we can help with.\\n\\nLooking forward to hearing from you.'
  },
  referral_thanks: {
    subject: 'Thank You for the Referral!',
    body: 'Hi,\\n\\nI wanted to personally thank you for the recent referral. We truly appreciate your trust in Reform Chiropractic.\\n\\nWe\\'ll make sure your client receives excellent care. Please don\\'t hesitate to reach out if you need any updates on their progress.'
  },
  event_invite: {
    subject: 'You\\'re Invited \u2014 Reform Chiropractic Event',
    body: 'Hi,\\n\\nWe\\'d love to invite you to an upcoming event hosted by Reform Chiropractic.\\n\\nPlease let us know if you\\'re interested and we\\'ll share all the details.\\n\\nHope to see you there!'
  }
};
function _applyTemplate(){
  var sel=document.getElementById('compose-template');
  var t=_TEMPLATES[sel.value];
  if(!t){return;}
  document.getElementById('compose-subject').value=t.subject;
  document.getElementById('compose-body').value=t.body;
  sel.value='';
  document.getElementById('compose-body').focus();
}

/* ── Signature ─────────────────────────────────────────────────── */
var _SIG = '\\n\\n--\\nBest regards,\\nReform Chiropractic\\n(832) 699-3148 \\u00b7 reformchiropractic.com';

/* ── Open / Close ──────────────────────────────────────────────── */
var _composeThreadId='';
function openCompose(to,subject,threadId){
  _composeThreadId=threadId||'';
  document.getElementById('compose-to').value=to||'';
  document.getElementById('compose-subject').value=subject||'';
  document.getElementById('compose-body').value='';
  document.getElementById('compose-cc').value='';
  document.getElementById('compose-bcc').value='';
  document.getElementById('compose-template').value='';
  document.getElementById('compose-status').innerHTML='';
  document.getElementById('compose-ac-list').classList.remove('open');
  document.getElementById('ccbcc-fields').classList.remove('open');
  document.getElementById('ccbcc-toggle').textContent='Cc/Bcc';
  document.getElementById('compose-title').textContent=threadId?'Reply':'New Email';
  document.getElementById('btn-send').textContent=threadId?'Reply \\u2192':'Send \\u2192';
  document.getElementById('compose-overlay').classList.add('open');
  if(!to)_acLoad();
  setTimeout(function(){document.getElementById(to?'compose-body':'compose-to').focus();},50);
}
function closeCompose(){
  _cancelUndo();
  document.getElementById('compose-overlay').classList.remove('open');
  document.getElementById('compose-ac-list').classList.remove('open');
}

/* ── Send with Undo ────────────────────────────────────────────── */
var _undoTimer=null, _undoAbort=false;
function _cancelUndo(){if(_undoTimer){clearTimeout(_undoTimer);_undoTimer=null;_undoAbort=true;}}
async function sendEmail(){
  var to=document.getElementById('compose-to').value.trim();
  var subj=document.getElementById('compose-subject').value.trim();
  var bodyText=document.getElementById('compose-body').value.trim();
  var cc=document.getElementById('compose-cc').value.trim();
  var bcc=document.getElementById('compose-bcc').value.trim();
  var st=document.getElementById('compose-status');
  if(!to||!subj||!bodyText){st.innerHTML='<span style="color:#ef4444">Please fill in all fields.</span>';return;}
  var fullBody=bodyText+_SIG;
  /* Undo countdown */
  _undoAbort=false;
  var btn=document.getElementById('btn-send');
  btn.disabled=true; btn.style.opacity='0.5';
  var secs=5;
  st.innerHTML='<span style="color:#3b82f6">Sending in '+secs+'s</span> <button class="compose-undo" onclick="_doUndo()">Undo</button>';
  _undoTimer=setInterval(function(){
    secs--;
    if(secs<=0){clearInterval(_undoTimer);_undoTimer=null;_doActualSend(to,cc,bcc,subj,fullBody);}
    else{var sp=st.querySelector('span');if(sp)sp.textContent='Sending in '+secs+'s';}
  },1000);
}
function _doUndo(){
  _cancelUndo();
  var st=document.getElementById('compose-status');
  st.innerHTML='<span style="color:#64748b">Send cancelled.</span>';
  var btn=document.getElementById('btn-send');
  btn.disabled=false; btn.style.opacity='1';
}
async function _doActualSend(to,cc,bcc,subj,body){
  var st=document.getElementById('compose-status');
  var btn=document.getElementById('btn-send');
  if(_undoAbort){btn.disabled=false;btn.style.opacity='1';return;}
  st.innerHTML='<span style="color:#94a3b8">Sending\\u2026</span>';
  try{
    var payload={to:to,subject:subj,body:body};
    if(cc)payload.cc=cc;
    if(bcc)payload.bcc=bcc;
    if(_composeThreadId)payload.threadId=_composeThreadId;
    var r=await fetch('/api/gmail/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    var d=await r.json();
    if(r.ok){st.innerHTML='<span style="color:#059669">\\u2713 Sent!</span>';setTimeout(closeCompose,1200);}
    else{st.innerHTML='<span style="color:#ef4444">Error: '+(d.error||r.status)+'</span>';}
  }catch(e){st.innerHTML='<span style="color:#ef4444">Network error.</span>';}
  btn.disabled=false; btn.style.opacity='1';
}
"""
