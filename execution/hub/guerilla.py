"""
Guerilla Marketing pages -- forms, map, log, events, routes, mobile.
"""
import os

from .shared import (
    _page, _mobile_page, _JS_SHARED, _is_admin,
    T_GOR_VENUES, T_GOR_ACTS, T_GOR_BOXES, T_GOR_ROUTES, T_GOR_ROUTE_STOPS,
    T_COM_VENUES, T_COM_ACTS,
)

# ---------------------------------------------------------------------------
# GFR CSS
# ---------------------------------------------------------------------------
_GFR_CSS = """
<style>
.gfr-overlay{position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.72);overflow-y:auto;overflow-x:hidden;display:flex;align-items:flex-start;justify-content:center;padding:32px 16px 60px;opacity:0;visibility:hidden;transition:opacity .2s ease,visibility .2s ease}
.gfr-overlay .gfr-modal{transform:translateY(16px) scale(.97);transition:transform .25s ease,opacity .2s ease;opacity:0}
.gfr-overlay.open{opacity:1;visibility:visible}
.gfr-overlay.open .gfr-modal{transform:translateY(0) scale(1);opacity:1}
.gfr-modal{background:var(--bg2);border:1px solid var(--border);border-radius:14px;width:100%;max-width:660px;overflow:hidden;overflow-x:hidden}
.gfr-form-modal{max-width:720px}
.gfr-hdr{background:#ea580c;padding:14px 18px;display:flex;align-items:center;gap:10px}
.gfr-hdr-title{font-size:15px;font-weight:700;color:#fff}
.gfr-hdr-user{font-size:12px;color:rgba(255,255,255,.78);margin-left:auto;margin-right:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:160px}
.gfr-close{background:rgba(255,255,255,.18);border:none;color:#fff;width:28px;height:28px;border-radius:6px;font-size:20px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;line-height:1}
.gfr-close:hover{background:rgba(255,255,255,.35)}
.gfr-chooser-body{padding:18px}
.gfr-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.gfr-card{background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:14px;cursor:pointer;transition:all .15s;display:flex;flex-direction:column;gap:5px}
.gfr-card:hover{border-color:#ea580c;background:rgba(234,88,12,.08)}
.gfr-card-icon{font-size:20px}
.gfr-card-name{font-size:13px;font-weight:600;color:var(--text)}
.gfr-card-desc{font-size:11px;color:var(--text3);line-height:1.5}
.gfr-card-cta{font-size:12px;color:#ea580c;font-weight:600;margin-top:2px}
.gfr-form-body{padding:0 18px 18px;max-height:72vh;overflow-y:auto;overflow-x:hidden}
.gfr-section{margin-top:18px}
.gfr-section-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#ea580c;padding-bottom:7px;border-bottom:1px solid var(--border);margin-bottom:13px}
.gfr-field{margin-bottom:12px}
.gfr-label{font-size:12px;color:var(--text2);margin-bottom:4px;display:block}
.gfr-label .req{color:#ef4444;margin-left:2px}
.gfr-input,.gfr-select,.gfr-textarea{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:7px;padding:7px 10px;font-size:13px;color:var(--text);font-family:inherit;box-sizing:border-box}
.gfr-input:focus,.gfr-select:focus,.gfr-textarea:focus{outline:none;border-color:#ea580c}
.gfr-textarea{resize:vertical;min-height:56px}
.gfr-radio-group{display:flex;gap:14px;flex-wrap:wrap}
.gfr-radio-group label{display:flex;align-items:center;gap:5px;font-size:13px;color:var(--text2);cursor:pointer}
.gfr-two{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:480px){.gfr-two{grid-template-columns:1fr}}
.gfr-program{background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:13px;margin-bottom:10px}
.gfr-program-title{font-size:12px;font-weight:700;color:var(--text);margin-bottom:3px}
.gfr-program-desc{font-size:11px;color:var(--text3);margin-bottom:11px;line-height:1.5}
.gfr-typeahead-wrap{position:relative}
.gfr-ta-drop{position:absolute;top:calc(100% + 3px);left:0;right:0;z-index:200;background:var(--bg2);border:1px solid var(--border);border-radius:8px;max-height:180px;overflow-y:auto;display:none}
.gfr-ta-drop.open{display:block}
.gfr-ta-item{padding:8px 12px;font-size:13px;color:var(--text2);cursor:pointer}
.gfr-ta-item:hover{background:rgba(234,88,12,.1);color:var(--text)}
.gfr-ta-new{font-style:italic;color:var(--text3)}
.gfr-footer{padding:13px 18px;border-top:1px solid var(--border);display:flex;align-items:center;gap:10px}
.gfr-hipaa{font-size:10px;color:var(--text4);display:flex;align-items:center;gap:4px}
.gfr-spacer{flex:1}
.gfr-btn-cancel{background:var(--bg);border:1px solid var(--border);color:var(--text2);padding:7px 15px;border-radius:7px;font-size:13px;cursor:pointer}
.gfr-btn-cancel:hover{border-color:var(--text3)}
.gfr-btn-submit{background:#ea580c;border:none;color:#fff;padding:7px 20px;border-radius:7px;font-size:13px;font-weight:600;cursor:pointer}
.gfr-btn-submit:hover{background:#c2410c}
.gfr-btn-submit:disabled{opacity:.5;cursor:not-allowed}
.gfr-success{padding:36px 20px;text-align:center}
.gfr-success-icon{font-size:44px;margin-bottom:10px}
.gfr-success-msg{font-size:16px;font-weight:600;color:var(--text);margin-bottom:6px}
.gfr-success-sub{font-size:13px;color:var(--text3);margin-bottom:22px}
.gfr-success-actions{display:flex;gap:10px;justify-content:center}
.gfr-back{background:none;border:none;color:#fff;font-size:13px;cursor:pointer;opacity:.85;padding:0 8px 0 0;display:flex;align-items:center;white-space:nowrap;flex-shrink:0}
.gfr-back:hover{opacity:1;text-decoration:underline}
.gfr-draft-bar{display:none;padding:6px 18px;background:#2563eb18;border-bottom:1px solid #2563eb40;font-size:12px;color:#2563eb;align-items:center;gap:8px}
.gfr-draft-bar.show{display:flex}
.gfr-draft-clear{background:none;border:none;color:#2563eb;text-decoration:underline;cursor:pointer;font-size:12px;padding:0}
</style>
"""

# ---------------------------------------------------------------------------
# GFR HTML (chooser + Form 1)
# ---------------------------------------------------------------------------
_GFR_HTML = (
    # -- Form Chooser Modal ------------------------------------------------
    '<div class="gfr-overlay" id="gfr-chooser" onclick="if(event.target===this)closeGFRChooser()">'
    '<div class="gfr-modal">'
    '<div class="gfr-hdr">'
    '<span class="gfr-hdr-title">Event Forms</span>'
    '<button class="gfr-close" onclick="closeGFRChooser()">&#xd7;</button>'
    '</div>'
    '<div class="gfr-chooser-body">'
    '<div class="gfr-grid">'
    '<div class="gfr-card" onclick="openGFRForm(\'Business Outreach Log\')">'
    '<div class="gfr-card-icon">&#x1f3e2;</div>'
    '<div class="gfr-card-name">Business Outreach Log</div>'
    '<div class="gfr-card-desc">Door-to-door visit, massage box placement, and program interest</div>'
    '<div class="gfr-card-cta">Open &#x2192;</div>'
    '</div>'
    '<div class="gfr-card" onclick="openGFRForm(\'External Event\')">'
    '<div class="gfr-card-icon">&#x1f3aa;</div>'
    '<div class="gfr-card-name">External Event</div>'
    '<div class="gfr-card-desc">Pre-event planning and community event demographic intel</div>'
    '<div class="gfr-card-cta">Open &#x2192;</div>'
    '</div>'
    '<div class="gfr-card" onclick="openGFRForm(\'Mobile Massage Service\')">'
    '<div class="gfr-card-icon">&#x1f486;</div>'
    '<div class="gfr-card-name">Mobile Massage Service</div>'
    '<div class="gfr-card-desc">Book a mobile chair or table massage at a company or event</div>'
    '<div class="gfr-card-cta">Open &#x2192;</div>'
    '</div>'
    '<div class="gfr-card" onclick="openGFRForm(\'Lunch and Learn\')">'
    '<div class="gfr-card-icon">&#x1f37d;&#xfe0f;</div>'
    '<div class="gfr-card-name">Lunch and Learn</div>'
    '<div class="gfr-card-desc">Schedule a chiropractic L&amp;L presentation for company staff</div>'
    '<div class="gfr-card-cta">Open &#x2192;</div>'
    '</div>'
    '<div class="gfr-card" onclick="openGFRForm(\'Health Assessment Screening\')">'
    '<div class="gfr-card-icon">&#x1fa7a;</div>'
    '<div class="gfr-card-name">Health Assessment Screening</div>'
    '<div class="gfr-card-desc">Book a chiropractic health screening event for staff</div>'
    '<div class="gfr-card-cta">Open &#x2192;</div>'
    '</div>'
    '</div></div></div></div>'

    # -- Form 1: Business Outreach Log -------------------------------------
    '<div class="gfr-overlay" id="gfr-form-bol" onclick="if(event.target===this)closeGFRForm(\'bol\')">'
    '<div class="gfr-modal gfr-form-modal">'
    '<div class="gfr-hdr">'
    '<span class="gfr-hdr-title">Business Outreach Log</span>'
    '<span class="gfr-hdr-user" id="gfr-user-bol"></span>'
    '<button class="gfr-close" onclick="closeGFRForm(\'bol\')">&#xd7;</button>'
    '</div>'
    '<div class="gfr-draft-bar" id="gfr-draft-bol">Draft restored <span style="flex:1"></span><button class="gfr-draft-clear" onclick="clearDraft(\'bol\')">Clear</button></div>'
    '<div class="gfr-form-body" id="gfr-body-bol">'

    # Basic Info
    '<div class="gfr-section">'
    '<div class="gfr-section-title">Basic Info</div>'
    '<div class="gfr-field">'
    '<label class="gfr-label">Employee Name</label>'
    '<input class="gfr-input" id="bol-employee" type="text" readonly style="opacity:.6">'
    '</div>'
    '<div class="gfr-field">'
    '<label class="gfr-label">Business Name <span class="req">*</span></label>'
    '<div class="gfr-typeahead-wrap">'
    '<input class="gfr-input" id="bol-biz-name" type="text" placeholder="Search or type business name\u2026" autocomplete="off" oninput="bolVenueSearch(this.value)">'
    '<div class="gfr-ta-drop" id="bol-venue-drop"></div>'
    '</div></div>'
    '<div class="gfr-two">'
    '<div class="gfr-field"><label class="gfr-label">Point of Contact <span class="req">*</span></label>'
    '<input class="gfr-input" id="bol-poc-name" type="text" placeholder="Full name"></div>'
    '<div class="gfr-field"><label class="gfr-label">Contact Phone <span class="req">*</span></label>'
    '<input class="gfr-input" id="bol-poc-phone" type="tel" placeholder="(555) 000-0000"></div>'
    '</div>'
    '<div class="gfr-two">'
    '<div class="gfr-field"><label class="gfr-label">Contact Email <span class="req">*</span></label>'
    '<input class="gfr-input" id="bol-poc-email" type="email" placeholder="email@example.com"></div>'
    '<div class="gfr-field"><label class="gfr-label">Business Address <span class="req">*</span></label>'
    '<input class="gfr-input" id="bol-address" type="text" placeholder="Street, City, State">'
    '<button class="geo-btn" type="button" onclick="fillLocation(\'bol-address\')">📍 Use my location</button></div>'
    '</div></div>'

    # Massage Box
    '<div class="gfr-section">'
    '<div class="gfr-section-title">Massage Box</div>'
    '<div class="gfr-field"><label class="gfr-label">Did You Leave a Massage Box? <span class="req">*</span></label>'
    '<div class="gfr-radio-group">'
    '<label><input type="radio" name="bol-mbox" value="Yes"> Yes</label>'
    '<label><input type="radio" name="bol-mbox" value="No"> No</label>'
    '</div></div></div>'

    # Programs
    '<div class="gfr-section">'
    '<div class="gfr-section-title">Available Programs</div>'

    # L&L
    '<div class="gfr-program">'
    '<div class="gfr-program-title">&#x1f37d;&#xfe0f; Lunch &amp; Learn</div>'
    '<div class="gfr-program-desc">Reform presents a 30\u201360 min educational lunch session on injury prevention and chiropractic care \u2014 fully catered by Reform.</div>'
    '<div class="gfr-two">'
    '<div class="gfr-field"><label class="gfr-label">Interested?</label>'
    '<select class="gfr-select" id="bol-ll-int"><option value="">Select\u2026</option>'
    '<option>Yes</option><option>Maybe</option><option>No</option><option>N/A</option>'
    '</select></div>'
    '<div class="gfr-field"><label class="gfr-label">Follow-Up Date</label>'
    '<input class="gfr-input" id="bol-ll-fu" type="date"></div>'
    '</div>'
    '<div class="gfr-field"><label class="gfr-label">Booking Requested?</label>'
    '<div class="gfr-radio-group">'
    '<label><input type="radio" name="bol-ll-book" value="Yes"> Yes</label>'
    '<label><input type="radio" name="bol-ll-book" value="No"> No</label>'
    '</div></div>'
    '<div class="gfr-field"><label class="gfr-label">Notes</label>'
    '<textarea class="gfr-textarea" id="bol-ll-notes" placeholder="Additional notes\u2026"></textarea>'
    '</div></div>'

    # HAS
    '<div class="gfr-program">'
    '<div class="gfr-program-title">&#x1fa7a; Health Assessment Screening</div>'
    '<div class="gfr-program-desc">Reform staff conduct a free on-site spinal health screening \u2014 checking posture, range of motion, and identifying injury risks for employees.</div>'
    '<div class="gfr-two">'
    '<div class="gfr-field"><label class="gfr-label">Interested?</label>'
    '<select class="gfr-select" id="bol-has-int"><option value="">Select\u2026</option>'
    '<option>Yes</option><option>Maybe</option><option>No</option><option>N/A</option>'
    '</select></div>'
    '<div class="gfr-field"><label class="gfr-label">Follow-Up Date</label>'
    '<input class="gfr-input" id="bol-has-fu" type="date"></div>'
    '</div>'
    '<div class="gfr-field"><label class="gfr-label">Booking Requested?</label>'
    '<div class="gfr-radio-group">'
    '<label><input type="radio" name="bol-has-book" value="Yes"> Yes</label>'
    '<label><input type="radio" name="bol-has-book" value="No"> No</label>'
    '</div></div>'
    '<div class="gfr-field"><label class="gfr-label">Notes</label>'
    '<textarea class="gfr-textarea" id="bol-has-notes" placeholder="Additional notes\u2026"></textarea>'
    '</div></div>'

    # MMS
    '<div class="gfr-program">'
    '<div class="gfr-program-title">&#x1f486; Mobile Massage Service (Employees &amp; Patrons)</div>'
    '<div class="gfr-program-desc">Reform therapists visit on-site to provide chair or table massage for employees or patrons \u2014 bookable as a one-time or recurring wellness event.</div>'
    '<div class="gfr-two">'
    '<div class="gfr-field"><label class="gfr-label">Interested?</label>'
    '<select class="gfr-select" id="bol-mms-int"><option value="">Select\u2026</option>'
    '<option>Yes</option><option>Maybe</option><option>No</option><option>N/A</option>'
    '</select></div>'
    '<div class="gfr-field"><label class="gfr-label">Follow-Up Date</label>'
    '<input class="gfr-input" id="bol-mms-fu" type="date"></div>'
    '</div>'
    '<div class="gfr-field"><label class="gfr-label">Booking Requested?</label>'
    '<div class="gfr-radio-group">'
    '<label><input type="radio" name="bol-mms-book" value="Yes"> Yes</label>'
    '<label><input type="radio" name="bol-mms-book" value="No"> No</label>'
    '</div></div>'
    '<div class="gfr-field"><label class="gfr-label">Notes</label>'
    '<textarea class="gfr-textarea" id="bol-mms-notes" placeholder="Additional notes\u2026"></textarea>'
    '</div></div>'
    '</div>'  # end programs section

    # Gifted
    '<div class="gfr-section">'
    '<div class="gfr-section-title">Gifted Consultation(s) &amp; Massage(s)</div>'
    '<div class="gfr-two">'
    '<div class="gfr-field"><label class="gfr-label">Consultations Gifted</label>'
    '<input class="gfr-input" id="bol-consults" type="number" min="0" placeholder="0"></div>'
    '<div class="gfr-field"><label class="gfr-label">Massages Gifted</label>'
    '<input class="gfr-input" id="bol-massages" type="number" min="0" placeholder="0"></div>'
    '</div></div>'

    '</div>'  # end gfr-form-body
    '<div class="gfr-footer">'
    '<span class="gfr-hipaa">&#x1f6e1;&#xfe0f; HIPAA Compliant</span>'
    '<span class="gfr-spacer"></span>'
    '<button class="gfr-btn-cancel" onclick="closeGFRForm(\'bol\')">Cancel</button>'
    '<button class="gfr-btn-submit" id="bol-submit" onclick="bolSubmit()">Submit</button>'
    '</div>'
    '</div></div>'  # end modal + overlay
)

# ---------------------------------------------------------------------------
# GFR JS (Form 1)
# ---------------------------------------------------------------------------
_GFR_JS = """
// -- GFR chooser ----------------------------------------------------------
function openGFRChooser(){document.getElementById('gfr-chooser').classList.add('open')}
function closeGFRChooser(){document.getElementById('gfr-chooser').classList.remove('open')}
function openGFRForm(ft){
  closeGFRChooser();
  if(ft==='Business Outreach Log'){bolReset();document.getElementById('gfr-form-bol').classList.add('open');}
  // Stages 3 & 4 will add further cases here
}
function closeGFRForm(id){
  saveDraft(id);
  document.getElementById('gfr-form-'+id).classList.remove('open');
}

// -- Draft save/restore system --------------------------------------------
function _formInputs(id){
  var body=document.getElementById('gfr-body-'+id);
  if(!body)return[];
  return Array.from(body.querySelectorAll('input,select,textarea'));
}
function saveDraft(id){
  var inputs=_formInputs(id);
  if(!inputs.length)return;
  var data={};var hasData=false;
  inputs.forEach(function(el){
    if(el.type==='radio'){
      if(el.checked){data[el.name]={v:el.value,t:'radio'};hasData=true;}
    }else if(el.type==='file'){
      // skip file inputs
    }else if(el.id&&el.value){
      data[el.id]={v:el.value,t:el.tagName.toLowerCase()};hasData=true;
    }
  });
  if(hasData)localStorage.setItem('gfr-draft-'+id,JSON.stringify(data));
  else localStorage.removeItem('gfr-draft-'+id);
}
function restoreDraft(id){
  var raw=localStorage.getItem('gfr-draft-'+id);
  if(!raw)return false;
  try{var data=JSON.parse(raw);}catch(e){return false;}
  var restored=false;
  Object.keys(data).forEach(function(k){
    var d=data[k];
    if(d.t==='radio'){
      var r=document.querySelector('input[name="'+k+'"][value="'+d.v+'"]');
      if(r){r.checked=true;restored=true;}
    }else{
      var el=document.getElementById(k);
      if(el&&!el.readOnly){el.value=d.v;restored=true;}
    }
  });
  if(restored){
    var bar=document.getElementById('gfr-draft-'+id);
    if(bar)bar.classList.add('show');
  }
  return restored;
}
function clearDraft(id){
  localStorage.removeItem('gfr-draft-'+id);
  var bar=document.getElementById('gfr-draft-'+id);
  if(bar)bar.classList.remove('show');
  // Re-run the form reset to clear fields
  if(id==='bol')bolReset();
  else if(id==='s2')s2Reset();
  else if(id==='s3')s3Reset();
  else if(id==='s4')s4Reset();
  else if(id==='s5')s5Reset();
}

// -- Venue typeahead (Form 1) ---------------------------------------------
let _vcache=null;
async function _getVenues(){if(!_vcache)_vcache=await fetchAll(TOOL.venuesT);return _vcache;}
let _vtimer=null;
function bolVenueSearch(q){
  clearTimeout(_vtimer);
  var drop=document.getElementById('bol-venue-drop');
  if(q.length<2){drop.classList.remove('open');drop.innerHTML='';return;}
  _vtimer=setTimeout(async function(){
    var venues=await _getVenues();
    var ql=q.toLowerCase();
    var hits=venues.filter(v=>(v['Name']||'').toLowerCase().includes(ql)).slice(0,8);
    drop.innerHTML=hits.map(v=>'<div class="gfr-ta-item" onclick="bolPickVenue('+JSON.stringify(v['Name']||'')+')">'
      +esc(v['Name']||'')+'</div>').join('')
      +(q.trim()?'<div class="gfr-ta-item gfr-ta-new" onclick="bolPickVenue('+JSON.stringify(q.trim())+')">+ Add "'+esc(q.trim())+'"</div>':'');
    drop.classList.add('open');
  },220);
}
function bolPickVenue(name){
  document.getElementById('bol-biz-name').value=name;
  var d=document.getElementById('bol-venue-drop');
  d.classList.remove('open');d.innerHTML='';
}
document.addEventListener('click',function(e){
  if(!e.target.closest('#bol-biz-name')&&!e.target.closest('#bol-venue-drop')){
    var d=document.getElementById('bol-venue-drop');
    if(d){d.classList.remove('open');d.innerHTML='';}
  }
});

// -- Form 1 reset ---------------------------------------------------------
function bolReset(){
  document.getElementById('gfr-user-bol').textContent=GFR_USER;
  document.getElementById('bol-employee').value=GFR_USER;
  ['bol-biz-name','bol-poc-name','bol-poc-phone','bol-poc-email','bol-address',
   'bol-ll-fu','bol-has-fu','bol-mms-fu',
   'bol-ll-notes','bol-has-notes','bol-mms-notes',
   'bol-consults','bol-massages'
  ].forEach(function(id){var el=document.getElementById(id);if(el)el.value='';});
  ['bol-ll-int','bol-has-int','bol-mms-int'].forEach(function(id){
    var el=document.getElementById(id);if(el)el.selectedIndex=0;
  });
  document.querySelectorAll('input[name="bol-mbox"],input[name="bol-ll-book"],input[name="bol-has-book"],input[name="bol-mms-book"]')
    .forEach(function(r){r.checked=false;});
  var body=document.getElementById('gfr-body-bol');if(body)body.style.display='';
  var foot=document.querySelector('#gfr-form-bol .gfr-footer');if(foot)foot.style.display='';
  var old=document.querySelector('#gfr-form-bol .gfr-success');if(old)old.remove();
  var btn=document.getElementById('bol-submit');if(btn){btn.disabled=false;btn.textContent='Submit';}
  _vcache=null;
}

// -- Form 1 submit --------------------------------------------------------
async function bolSubmit(){
  var btn=document.getElementById('bol-submit');
  var bizName=document.getElementById('bol-biz-name').value.trim();
  var pocName=document.getElementById('bol-poc-name').value.trim();
  var phone=document.getElementById('bol-poc-phone').value.trim();
  var email=document.getElementById('bol-poc-email').value.trim();
  var addr=document.getElementById('bol-address').value.trim();
  if(!bizName||!pocName||!phone||!email||!addr){
    alert('Please fill in all required fields in Basic Info.');return;
  }
  var mbox=document.querySelector('input[name="bol-mbox"]:checked');
  if(!mbox){alert('Please indicate whether you left a massage box.');return;}
  btn.disabled=true;btn.textContent='Submitting\u2026';
  var fields={
    business_name:         bizName,
    point_of_contact_name: pocName,
    contact_phone:         phone,
    contact_email:         email,
    business_address:      addr,
    massage_box_left:      mbox.value,
    ll_interested:         document.getElementById('bol-ll-int').value,
    ll_follow_up_date:     document.getElementById('bol-ll-fu').value,
    ll_booking_requested:  (document.querySelector('input[name="bol-ll-book"]:checked')||{}).value||'',
    ll_notes:              document.getElementById('bol-ll-notes').value,
    has_interested:        document.getElementById('bol-has-int').value,
    has_follow_up_date:    document.getElementById('bol-has-fu').value,
    has_booking_requested: (document.querySelector('input[name="bol-has-book"]:checked')||{}).value||'',
    has_notes:             document.getElementById('bol-has-notes').value,
    mms_interested:        document.getElementById('bol-mms-int').value,
    mms_follow_up_date:    document.getElementById('bol-mms-fu').value,
    mms_booking_requested: (document.querySelector('input[name="bol-mms-book"]:checked')||{}).value||'',
    mms_notes:             document.getElementById('bol-mms-notes').value,
    consultations_gifted:  document.getElementById('bol-consults').value||'0',
    massages_gifted:       document.getElementById('bol-massages').value||'0',
  };
  try{
    var r=await fetch('/api/guerilla/log',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({form_type:'Business Outreach Log',fields:fields,user_name:GFR_USER})
    });
    var d=await r.json();
    if(d.ok){
      localStorage.removeItem('gfr-draft-bol');
      var dbar=document.getElementById('gfr-draft-bol');if(dbar)dbar.classList.remove('show');
      var body=document.getElementById('gfr-body-bol');
      var foot=document.querySelector('#gfr-form-bol .gfr-footer');
      body.style.display='none';foot.style.display='none';
      var s=document.createElement('div');s.className='gfr-success';
      s.innerHTML='<div class="gfr-success-icon">\u2705</div>'
        +'<div class="gfr-success-msg">Visit logged successfully!</div>'
        +'<div class="gfr-success-sub">Activity #'+(d.activity_id||'')+'&nbsp;created in Baserow.</div>'
        +'<div class="gfr-success-actions">'
        +'<button class="gfr-btn-submit" onclick="closeGFRForm(\\'bol\\')">Done</button>'
        +'<button class="gfr-btn-cancel" onclick="closeGFRForm(\\'bol\\')">Close</button>'
        +'</div>';
      document.querySelector('#gfr-form-bol .gfr-modal').appendChild(s);
      if (typeof _onFormSubmitSuccess === 'function') _onFormSubmitSuccess();
    }else{
      alert('Error: '+(d.error||'Unknown error'));
      btn.disabled=false;btn.textContent='Submit';
    }
  }catch(e){
    alert('Network error. Please try again.');
    btn.disabled=false;btn.textContent='Submit';
  }
}

// -- Geolocation fill -----------------------------------------------------
async function fillLocation(inputId) {
  var btn = event.currentTarget;
  var orig = btn.textContent;
  btn.textContent = '\U0001f4cd Locating\u2026';
  btn.disabled = true;
  if (!navigator.geolocation) {
    alert('Geolocation is not supported by your browser.');
    btn.textContent = orig; btn.disabled = false; return;
  }
  navigator.geolocation.getCurrentPosition(
    async function(pos) {
      try {
        var r = await fetch('/api/geocode?lat=' + pos.coords.latitude + '&lng=' + pos.coords.longitude);
        var d = await r.json();
        document.getElementById(inputId).value = d.address || (pos.coords.latitude.toFixed(5) + ', ' + pos.coords.longitude.toFixed(5));
      } catch(e) {
        document.getElementById(inputId).value = pos.coords.latitude.toFixed(5) + ', ' + pos.coords.longitude.toFixed(5);
      }
      btn.textContent = orig; btn.disabled = false;
    },
    function(err) {
      alert('Could not get location: ' + err.message);
      btn.textContent = orig; btn.disabled = false;
    },
    { timeout: 10000, enableHighAccuracy: true }
  );
}
"""

# ---------------------------------------------------------------------------
# GFR HTML helpers (called at import time)
# ---------------------------------------------------------------------------
def _gfr_bi(p):
    """Basic Info section for service booking forms (Forms 3-5)."""
    return (
        '<div class="gfr-section">'
        '<div class="gfr-section-title">Basic Info</div>'
        '<div class="gfr-two">'
        f'<div class="gfr-field"><label class="gfr-label">Point of Contact <span class="req">*</span></label>'
        f'<input class="gfr-input" id="{p}-poc" type="text" placeholder="Full name"></div>'
        f'<div class="gfr-field"><label class="gfr-label">Contact Phone <span class="req">*</span></label>'
        f'<input class="gfr-input" id="{p}-phone" type="tel" placeholder="(555)\u00a0000-0000"></div>'
        '</div>'
        '<div class="gfr-two">'
        f'<div class="gfr-field"><label class="gfr-label">Contact Email <span class="req">*</span></label>'
        f'<input class="gfr-input" id="{p}-email" type="email" placeholder="email@example.com"></div>'
        f'<div class="gfr-field"><label class="gfr-label">Company Name <span class="req">*</span></label>'
        f'<input class="gfr-input" id="{p}-company" type="text" placeholder="Company name"></div>'
        '</div></div>'
    )

def _gfr_vb(p):
    """Venue Base section (Address + Indoor/Outdoor + Electricity)."""
    return (
        '<div class="gfr-section">'
        '<div class="gfr-section-title">About Your Venue</div>'
        f'<div class="gfr-field"><label class="gfr-label">Venue Address <span class="req">*</span></label>'
        f'<input class="gfr-input" id="{p}-addr" type="text" placeholder="Street, City, State">'
        f'<button class="geo-btn" type="button" onclick="fillLocation(\'{p}-addr\')">📍 Use my location</button></div>'
        '<div class="gfr-two">'
        f'<div class="gfr-field"><label class="gfr-label">Indoor or Outdoors? <span class="req">*</span></label>'
        f'<select class="gfr-select" id="{p}-inout">'
        '<option value="">\u2026</option><option>Indoor</option><option>Outdoor</option><option>Both</option>'
        f'</select></div>'
        f'<div class="gfr-field"><label class="gfr-label">Access to Electricity? <span class="req">*</span></label>'
        f'<select class="gfr-select" id="{p}-elec">'
        '<option value="">\u2026</option><option>Yes</option><option>No</option><option>Not sure</option>'
        f'</select></div>'
        '</div></div>'
    )

def _gfr_dt_row(p):
    """Date + time picker row (no section wrapper)."""
    h_opts = ''.join(f'<option value="{h}">{h}</option>' for h in range(1, 13))
    m_opts = ''.join(f'<option value="{m:02d}">{m:02d}</option>' for m in range(0, 60, 5))
    return (
        '<div class="gfr-two">'
        f'<div class="gfr-field"><label class="gfr-label">Date <span class="req">*</span></label>'
        f'<input class="gfr-input" id="{p}-date" type="date"></div>'
        f'<div class="gfr-field"><label class="gfr-label">Time <span class="req">*</span></label>'
        '<div style="display:flex;gap:5px;align-items:center">'
        f'<select class="gfr-select" id="{p}-hour" style="flex:1;padding:7px 5px;min-width:0">'
        f'<option value="">HH</option>{h_opts}</select>'
        '<span style="color:var(--text3);font-weight:600">:</span>'
        f'<select class="gfr-select" id="{p}-min" style="flex:1;padding:7px 5px;min-width:0">'
        f'<option value="">MM</option>{m_opts}</select>'
        f'<select class="gfr-select" id="{p}-ampm" style="flex:1;padding:7px 5px;min-width:0">'
        '<option value="">AM/PM</option><option>AM</option><option>PM</option>'
        f'</select></div></div>'
        '</div>'
    )

def _gfr_dt(p):
    """Full Requested Date & Time section."""
    return (
        '<div class="gfr-section">'
        '<div class="gfr-section-title">Requested Date &amp; Time</div>'
        + _gfr_dt_row(p)
        + '</div>'
    )

def _gfr_foot(p, fn):
    """Form footer: HIPAA badge + Cancel + Submit."""
    return (
        '<div class="gfr-footer">'
        '<span class="gfr-hipaa">&#x1f6e1;&#xfe0f; HIPAA Compliant</span>'
        '<span class="gfr-spacer"></span>'
        f'<button class="gfr-btn-cancel" onclick="closeGFRForm(\'{p}\')">Cancel</button>'
        f'<button class="gfr-btn-submit" id="{p}-submit" onclick="{fn}()">Submit</button>'
        '</div>'
    )

# ---------------------------------------------------------------------------
# GFR Forms 3-5 HTML
# ---------------------------------------------------------------------------
_GFR_FORMS345_HTML = (

    # -- Form 3: Mobile Massage Service ------------------------------------
    '<div class="gfr-overlay" id="gfr-form-s3" onclick="if(event.target===this)closeGFRForm(\'s3\')">'
    '<div class="gfr-modal gfr-form-modal">'
    '<div class="gfr-hdr">'
    '<span class="gfr-hdr-title">Mobile Massage Service</span>'
    '<span class="gfr-hdr-user" id="gfr-user-s3"></span>'
    '<button class="gfr-close" onclick="closeGFRForm(\'s3\')">&#xd7;</button>'
    '</div>'
    '<div class="gfr-draft-bar" id="gfr-draft-s3">Draft restored <span style="flex:1"></span><button class="gfr-draft-clear" onclick="clearDraft(\'s3\')">Clear</button></div>'
    '<div class="gfr-form-body" id="gfr-body-s3">'
    + _gfr_bi('s3')
    + _gfr_vb('s3')
    + (
        '<div class="gfr-section">'
        '<div class="gfr-section-title">Participant Details</div>'
        '<div class="gfr-field"><label class="gfr-label">Audience Type <span class="req">*</span></label>'
        '<div class="gfr-radio-group" style="flex-direction:column;gap:8px">'
        '<label><input type="radio" name="s3-audience" value="Customers &amp; patrons"> Customers &amp; patrons</label>'
        '<label><input type="radio" name="s3-audience" value="Company staff"> Company staff</label>'
        '<label><input type="radio" name="s3-audience" value="Customers, patrons, &amp; staff"> Customers, patrons, &amp; staff</label>'
        '</div></div>'
        '<div class="gfr-two">'
        '<div class="gfr-field"><label class="gfr-label">Anticipated Count <span class="req">*</span></label>'
        '<input class="gfr-input" id="s3-count" type="number" min="1" placeholder="0"></div>'
        '<div class="gfr-field"><label class="gfr-label">Company Industry <span class="req">*</span></label>'
        '<input class="gfr-input" id="s3-industry" type="text" placeholder="e.g. Healthcare, Retail\u2026"></div>'
        '</div>'
        '<div class="gfr-field"><label class="gfr-label">Products / Services Offered <span class="req">*</span></label>'
        '<textarea class="gfr-textarea" id="s3-products" placeholder="What does this company offer?\u2026"></textarea></div>'
        '</div>'
    )
    + (
        '<div class="gfr-section">'
        '<div class="gfr-section-title">Requested Service, Date &amp; Time</div>'
        '<div class="gfr-field"><label class="gfr-label">Massage Duration per Participant <span class="req">*</span></label>'
        '<div class="gfr-radio-group">'
        '<label><input type="radio" name="s3-mdur" value="10 min ($20)"> 10 min ($20)</label>'
        '<label><input type="radio" name="s3-mdur" value="15 min ($30)"> 15 min ($30)</label>'
        '<label><input type="radio" name="s3-mdur" value="30 min ($60)"> 30 min ($60)</label>'
        '</div></div>'
        '<div class="gfr-field"><label class="gfr-label">Preferred Massage Type <span class="req">*</span></label>'
        '<div class="gfr-radio-group">'
        '<label><input type="radio" name="s3-mtype" value="Chair massage"> Chair massage</label>'
        '<label><input type="radio" name="s3-mtype" value="Table massage"> Table massage</label>'
        '<label><input type="radio" name="s3-mtype" value="No preference"> No preference</label>'
        '</div></div>'
    )
    + _gfr_dt_row('s3')
    + '</div>'   # close service section
    + '</div>'   # close form-body
    + _gfr_foot('s3', 's3Submit')
    + '</div></div>'  # close modal + overlay

    # -- Form 4: Lunch and Learn -------------------------------------------
    + '<div class="gfr-overlay" id="gfr-form-s4" onclick="if(event.target===this)closeGFRForm(\'s4\')">'
    '<div class="gfr-modal gfr-form-modal">'
    '<div class="gfr-hdr">'
    '<span class="gfr-hdr-title">Lunch and Learn</span>'
    '<span class="gfr-hdr-user" id="gfr-user-s4"></span>'
    '<button class="gfr-close" onclick="closeGFRForm(\'s4\')">&#xd7;</button>'
    '</div>'
    '<div class="gfr-draft-bar" id="gfr-draft-s4">Draft restored <span style="flex:1"></span><button class="gfr-draft-clear" onclick="clearDraft(\'s4\')">Clear</button></div>'
    '<div class="gfr-form-body" id="gfr-body-s4">'
    + _gfr_bi('s4')
    + (
        '<div class="gfr-section">'
        '<div class="gfr-section-title">About Your Venue</div>'
        '<div class="gfr-field"><label class="gfr-label">Venue Address <span class="req">*</span></label>'
        '<input class="gfr-input" id="s4-addr" type="text" placeholder="Street, City, State"></div>'
        '<div class="gfr-two">'
        '<div class="gfr-field"><label class="gfr-label">Indoor or Outdoors? <span class="req">*</span></label>'
        '<select class="gfr-select" id="s4-inout">'
        '<option value="">\u2026</option><option>Indoor</option><option>Outdoor</option><option>Both</option>'
        '</select></div>'
        '<div class="gfr-field"><label class="gfr-label">Access to Electricity? <span class="req">*</span></label>'
        '<select class="gfr-select" id="s4-elec">'
        '<option value="">\u2026</option><option>Yes</option><option>No</option><option>Not sure</option>'
        '</select></div>'
        '</div>'
        '<div class="gfr-two">'
        '<div class="gfr-field"><label class="gfr-label">Conference Room Available? <span class="req">*</span></label>'
        '<select class="gfr-select" id="s4-confroom">'
        '<option value="">\u2026</option><option>Yes</option><option>No</option><option>Not sure</option>'
        '</select></div>'
        '<div class="gfr-field"><label class="gfr-label">Tables / Surfaces for Food? <span class="req">*</span></label>'
        '<select class="gfr-select" id="s4-foodsurface">'
        '<option value="">\u2026</option><option>Yes</option><option>No</option><option>Not sure</option>'
        '</select></div>'
        '</div>'
        '<div class="gfr-field"><label class="gfr-label">Projector or Large TV Screen? <span class="req">*</span></label>'
        '<select class="gfr-select" id="s4-projector">'
        '<option value="">\u2026</option><option>Yes</option><option>No</option><option>Not sure</option>'
        '</select></div>'
        '</div>'
    )
    + (
        '<div class="gfr-section">'
        '<div class="gfr-section-title">Participant Details</div>'
        '<div class="gfr-two">'
        '<div class="gfr-field"><label class="gfr-label">Anticipated Attendees <span class="req">*</span></label>'
        '<input class="gfr-input" id="s4-count" type="number" min="1" placeholder="0"></div>'
        '<div class="gfr-field"><label class="gfr-label">Dietary Restrictions? <span class="req">*</span></label>'
        '<div class="gfr-radio-group" style="margin-top:8px">'
        '<label><input type="radio" name="s4-diets" value="Yes"> Yes</label>'
        '<label><input type="radio" name="s4-diets" value="No"> No</label>'
        '</div></div>'
        '</div>'
        '<div class="gfr-two">'
        '<div class="gfr-field"><label class="gfr-label">Staff Type <span class="req">*</span></label>'
        '<div class="gfr-radio-group" style="margin-top:8px">'
        '<label><input type="radio" name="s4-collar" value="White collar"> White collar</label>'
        '<label><input type="radio" name="s4-collar" value="Blue collar"> Blue collar</label>'
        '<label><input type="radio" name="s4-collar" value="Mixed"> Mixed</label>'
        '</div></div>'
        '<div class="gfr-field"><label class="gfr-label">Healthcare Insurance Offered? <span class="req">*</span></label>'
        '<div class="gfr-radio-group" style="margin-top:8px">'
        '<label><input type="radio" name="s4-hcare" value="Yes"> Yes</label>'
        '<label><input type="radio" name="s4-hcare" value="No"> No</label>'
        '</div></div>'
        '</div>'
        '<div class="gfr-field"><label class="gfr-label">Company Industry <span class="req">*</span></label>'
        '<input class="gfr-input" id="s4-industry" type="text" placeholder="e.g. Healthcare, Retail\u2026"></div>'
        '<div class="gfr-field"><label class="gfr-label">Products / Services Offered <span class="req">*</span></label>'
        '<textarea class="gfr-textarea" id="s4-products" placeholder="What does this company offer?\u2026"></textarea></div>'
        '</div>'
    )
    + _gfr_dt('s4')
    + '</div>'   # close form-body
    + _gfr_foot('s4', 's4Submit')
    + '</div></div>'  # close modal + overlay

    # -- Form 5: Health Assessment Screening --------------------------------
    + '<div class="gfr-overlay" id="gfr-form-s5" onclick="if(event.target===this)closeGFRForm(\'s5\')">'
    '<div class="gfr-modal gfr-form-modal">'
    '<div class="gfr-hdr">'
    '<span class="gfr-hdr-title">Health Assessment Screening</span>'
    '<span class="gfr-hdr-user" id="gfr-user-s5"></span>'
    '<button class="gfr-close" onclick="closeGFRForm(\'s5\')">&#xd7;</button>'
    '</div>'
    '<div class="gfr-draft-bar" id="gfr-draft-s5">Draft restored <span style="flex:1"></span><button class="gfr-draft-clear" onclick="clearDraft(\'s5\')">Clear</button></div>'
    '<div class="gfr-form-body" id="gfr-body-s5">'
    + _gfr_bi('s5')
    + _gfr_vb('s5')
    + (
        '<div class="gfr-section">'
        '<div class="gfr-section-title">Participant Details</div>'
        '<div class="gfr-two">'
        '<div class="gfr-field"><label class="gfr-label">Anticipated Attendees <span class="req">*</span></label>'
        '<input class="gfr-input" id="s5-count" type="number" min="1" placeholder="0"></div>'
        '<div class="gfr-field"><label class="gfr-label">Company Industry <span class="req">*</span></label>'
        '<input class="gfr-input" id="s5-industry" type="text" placeholder="e.g. Healthcare, Retail\u2026"></div>'
        '</div>'
        '<div class="gfr-two">'
        '<div class="gfr-field"><label class="gfr-label">Staff Type <span class="req">*</span></label>'
        '<div class="gfr-radio-group" style="margin-top:8px">'
        '<label><input type="radio" name="s5-collar" value="White collar"> White collar</label>'
        '<label><input type="radio" name="s5-collar" value="Blue collar"> Blue collar</label>'
        '<label><input type="radio" name="s5-collar" value="Mixed"> Mixed</label>'
        '</div></div>'
        '<div class="gfr-field"><label class="gfr-label">Healthcare Insurance Offered? <span class="req">*</span></label>'
        '<div class="gfr-radio-group" style="margin-top:8px">'
        '<label><input type="radio" name="s5-hcare" value="Yes"> Yes</label>'
        '<label><input type="radio" name="s5-hcare" value="No"> No</label>'
        '</div></div>'
        '</div>'
        '<div class="gfr-field"><label class="gfr-label">Products / Services Offered <span class="req">*</span></label>'
        '<textarea class="gfr-textarea" id="s5-products" placeholder="What does this company offer?\u2026"></textarea></div>'
        '</div>'
    )
    + _gfr_dt('s5')
    + '</div>'   # close form-body
    + _gfr_foot('s5', 's5Submit')
    + '</div></div>'  # close modal + overlay
)

# ---------------------------------------------------------------------------
# GFR Form 2 HTML
# ---------------------------------------------------------------------------
_GFR_FORM2_HTML = (
    # -- Form 2: External Event / Interaction Only -------------------------
    '<div class="gfr-overlay" id="gfr-form-s2" onclick="if(event.target===this)closeGFRForm(\'s2\')">'
    '<div class="gfr-modal gfr-form-modal">'
    '<div class="gfr-hdr">'
    '<span class="gfr-hdr-title">Log Interaction</span>'
    '<span class="gfr-hdr-user" id="gfr-user-s2"></span>'
    '<button class="gfr-close" onclick="closeGFRForm(\'s2\')">&#xd7;</button>'
    '</div>'
    '<div class="gfr-draft-bar" id="gfr-draft-s2">Draft restored <span style="flex:1"></span><button class="gfr-draft-clear" onclick="clearDraft(\'s2\')">Clear</button></div>'
    '<div class="gfr-form-body" id="gfr-body-s2">'

    # -- Event toggle ------------------------------------------------------
    '<div class="gfr-section" style="padding-top:4px">'
    '<label style="display:flex;align-items:center;gap:10px;cursor:pointer;font-size:14px;font-weight:600">'
    '<input type="checkbox" id="s2-has-event" onchange="s2ToggleEvent()" style="width:18px;height:18px;cursor:pointer">'
    '<span>Is there an event here?</span>'
    '</label>'
    '<div style="font-size:12px;color:var(--text3);margin-top:4px;margin-left:28px">Check to capture event details (type, date, venue, etc.)</div>'
    '</div>'

    # -- Interaction Details (always visible, the core of every submission) --
    '<div class="gfr-section">'
    '<div class="gfr-section-title">Interaction Details</div>'
    '<div class="gfr-two">'
    '<div class="gfr-field"><label class="gfr-label">Interaction Type <span class="req">*</span></label>'
    '<select class="gfr-select" id="s2-int-type">'
    '<option value="Drop-In">Drop-In</option><option value="Call">Call</option>'
    '<option value="Email">Email</option><option value="Meeting">Meeting</option>'
    '<option value="Mail">Mail</option><option value="Other">Other</option>'
    '</select></div>'
    '<div class="gfr-field"><label class="gfr-label">Outcome <span class="req">*</span></label>'
    '<select class="gfr-select" id="s2-int-outcome">'
    '<option value="Spoke With">Spoke With</option><option value="No Answer">No Answer</option>'
    '<option value="Left Message">Left Message</option><option value="Scheduled Meeting">Scheduled Meeting</option>'
    '<option value="Declined">Declined</option><option value="Follow-Up Needed">Follow-Up Needed</option>'
    '</select></div>'
    '</div>'
    '<div class="gfr-two">'
    '<div class="gfr-field"><label class="gfr-label">Contact Person</label>'
    '<input class="gfr-input" id="s2-int-person" type="text" placeholder="Who did you speak with?"></div>'
    '<div class="gfr-field"><label class="gfr-label">Follow-Up Date</label>'
    '<input class="gfr-input" id="s2-int-fu" type="date"></div>'
    '</div>'
    '<div class="gfr-field"><label class="gfr-label">What happened? <span class="req">*</span></label>'
    '<textarea class="gfr-textarea" id="s2-int-summary" placeholder="Describe the interaction\u2026"></textarea></div>'
    '</div>'

    # -- Event block (hidden by default, shown when checkbox is on) --------
    '<div id="s2-event-block" style="display:none">'

    # Basic Info
    '<div class="gfr-section">'
    '<div class="gfr-section-title">Basic Info</div>'
    '<div class="gfr-two">'
    '<div class="gfr-field"><label class="gfr-label">Name of Event <span class="req">*</span></label>'
    '<input class="gfr-input" id="s2-event-name" type="text" placeholder="Event name"></div>'
    '<div class="gfr-field"><label class="gfr-label">Type of Event <span class="req">*</span></label>'
    '<input class="gfr-input" id="s2-event-type" type="text" placeholder="e.g. Health Fair, 5K, Flea Market\u2026"></div>'
    '</div>'
    '<div class="gfr-two">'
    '<div class="gfr-field"><label class="gfr-label">Event Organizer <span class="req">*</span></label>'
    '<input class="gfr-input" id="s2-organizer" type="text" placeholder="Organizer name or organization"></div>'
    '<div class="gfr-field"><label class="gfr-label">Organizer Phone</label>'
    '<input class="gfr-input" id="s2-org-phone" type="tel" placeholder="(555)\u00a0000-0000"></div>'
    '</div>'
    '<div class="gfr-two">'
    '<div class="gfr-field"><label class="gfr-label">Cost of Event <span class="req">*</span></label>'
    '<input class="gfr-input" id="s2-cost" type="text" placeholder="e.g. Free, $500, $1,200"></div>'
    '<div class="gfr-field"><label class="gfr-label">Event Duration</label>'
    '<input class="gfr-input" id="s2-duration" type="text" placeholder="e.g. 2 hours, 90 mins"></div>'
    '</div>'
    '<div class="gfr-two">'
    '<div class="gfr-field"><label class="gfr-label">Event Status</label>'
    '<select class="gfr-select" id="s2-status">'
    '<option value="Prospective">Prospective</option>'
    '<option value="Approved">Approved</option>'
    '<option value="Scheduled">Scheduled</option>'
    '<option value="Completed">Completed</option>'
    '</select></div>'
    '<div class="gfr-field"><label class="gfr-label">Event Flyer <span style="font-weight:400;color:var(--text3)">(optional)</span></label>'
    '<input class="gfr-input" id="s2-flyer" type="file" accept="image/*,.pdf" style="padding:5px"></div>'
    '</div>'
    '</div>'

    # About Event Venue + Participant Details + Event Date & Time
    + _gfr_vb('s2')
    + (
        '<div class="gfr-section">'
        '<div class="gfr-section-title">Participant Details</div>'
        '<div class="gfr-two">'
        '<div class="gfr-field"><label class="gfr-label">Staff Type</label>'
        '<div class="gfr-radio-group" style="margin-top:8px;flex-direction:column;gap:6px">'
        '<label><input type="radio" name="s2-collar" value="White collar"> White collar</label>'
        '<label><input type="radio" name="s2-collar" value="Blue collar"> Blue collar</label>'
        '<label><input type="radio" name="s2-collar" value="Mixed"> Mixed</label>'
        '</div></div>'
        '<div class="gfr-field"><label class="gfr-label">Healthcare Insurance Offered?</label>'
        '<div class="gfr-radio-group" style="margin-top:8px">'
        '<label><input type="radio" name="s2-hcare" value="Yes"> Yes</label>'
        '<label><input type="radio" name="s2-hcare" value="No"> No</label>'
        '</div></div>'
        '</div>'
        '<div class="gfr-field"><label class="gfr-label">Company Industry</label>'
        '<input class="gfr-input" id="s2-industry" type="text" placeholder="e.g. Healthcare, Retail\u2026"></div>'
        '</div>'
    )
    + _gfr_dt('s2')
    + '</div>'   # close s2-event-block
    + '</div>'   # close form-body
    + _gfr_foot('s2', 's2Submit')
    + '</div></div>'  # close modal + overlay
)

# ---------------------------------------------------------------------------
# GFR Forms 2-5 JS
# ---------------------------------------------------------------------------
_GFR_FORMS345_JS = """
// -- GFR shared helpers ---------------------------------------------------
function _gfrGetDatetime(p){
  var d=document.getElementById(p+'-date').value;
  var h=document.getElementById(p+'-hour').value;
  var m=document.getElementById(p+'-min').value;
  var ap=document.getElementById(p+'-ampm').value;
  return (d&&h&&m&&ap) ? d+' '+h+':'+m+' '+ap : '';
}
function _gfrSuccess(fid,actId){
  localStorage.removeItem('gfr-draft-'+fid);
  var bar=document.getElementById('gfr-draft-'+fid);if(bar)bar.classList.remove('show');
  var body=document.getElementById('gfr-body-'+fid);
  var foot=document.querySelector('#gfr-form-'+fid+' .gfr-footer');
  body.style.display='none';foot.style.display='none';
  var s=document.createElement('div');s.className='gfr-success';
  s.innerHTML='<div class="gfr-success-icon">\u2705</div>'
    +'<div class="gfr-success-msg">Submitted successfully!</div>'
    +'<div class="gfr-success-sub">Activity #'+(actId||'')+' created in Baserow.</div>'
    +'<div class="gfr-success-actions">'
    +'<button class="gfr-btn-submit" id="gfr-la-'+fid+'">Log Another</button>'
    +'<button class="gfr-btn-cancel" id="gfr-cl-'+fid+'">Close</button>'
    +'</div>';
  document.querySelector('#gfr-form-'+fid+' .gfr-modal').appendChild(s);
  document.getElementById('gfr-la-'+fid).onclick=function(){closeGFRForm(fid);};
  document.getElementById('gfr-cl-'+fid).onclick=function(){closeGFRForm(fid);};
  // Forms s2-s5 reused as the route Check-In form: notify the route page so
  // it can flip the stop status to Visited (matches the bol form behavior at
  // the bottom of _GFR_JS).
  if (typeof _onFormSubmitSuccess === 'function') _onFormSubmitSuccess();
}
async function _gfrDoSubmit(fid,ftype,fields,btn){
  try{
    var r=await fetch('/api/guerilla/log',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({form_type:ftype,fields:fields,user_name:GFR_USER})
    });
    var d=await r.json();
    if(d.ok){_gfrSuccess(fid,d.activity_id);}
    else{alert('Error: '+(d.error||'Unknown error'));btn.disabled=false;btn.textContent='Submit';}
  }catch(e){alert('Network error. Please try again.');btn.disabled=false;btn.textContent='Submit';}
}
function _gfrBaseReset(p,radioNames,extraIds,extraSels){
  ['poc','phone','email','company','addr','date'].concat(extraIds||[]).forEach(function(s){
    var el=document.getElementById(p+'-'+s);if(el)el.value='';
  });
  ['inout','elec','hour','min','ampm'].concat(extraSels||[]).forEach(function(s){
    var el=document.getElementById(p+'-'+s);if(el)el.selectedIndex=0;
  });
  (radioNames||[]).forEach(function(n){
    document.querySelectorAll('input[name="'+n+'"]').forEach(function(r){r.checked=false;});
  });
  var old=document.querySelector('#gfr-form-'+p+' .gfr-success');if(old)old.remove();
  var body=document.getElementById('gfr-body-'+p);if(body)body.style.display='';
  var foot=document.querySelector('#gfr-form-'+p+' .gfr-footer');if(foot)foot.style.display='';
  var btn=document.getElementById(p+'-submit');if(btn){btn.disabled=false;btn.textContent='Submit';}
}

// -- openGFRForm (replaces Stage 2 stub, handles all 4 completed forms) ---
function openGFRForm(ft){
  closeGFRChooser();
  if(ft==='Business Outreach Log'){bolReset();restoreDraft('bol');document.getElementById('gfr-form-bol').classList.add('open');}
  else if(ft==='Mobile Massage Service'){s3Reset();restoreDraft('s3');document.getElementById('gfr-form-s3').classList.add('open');}
  else if(ft==='Lunch and Learn'){s4Reset();restoreDraft('s4');document.getElementById('gfr-form-s4').classList.add('open');}
  else if(ft==='Health Assessment Screening'){s5Reset();restoreDraft('s5');document.getElementById('gfr-form-s5').classList.add('open');}
  else if(ft==='External Event'){s2Reset();restoreDraft('s2');document.getElementById('gfr-form-s2').classList.add('open');}
}

// -- Form 3: Mobile Massage Service ----------------------------------------
function s3Reset(){
  _gfrBaseReset('s3',['s3-audience','s3-mdur','s3-mtype'],['count','industry','products'],[]);
  document.getElementById('gfr-user-s3').textContent=GFR_USER;
}
async function s3Submit(){
  var btn=document.getElementById('s3-submit');
  var poc=document.getElementById('s3-poc').value.trim();
  var phone=document.getElementById('s3-phone').value.trim();
  var email=document.getElementById('s3-email').value.trim();
  var company=document.getElementById('s3-company').value.trim();
  var addr=document.getElementById('s3-addr').value.trim();
  var inout=document.getElementById('s3-inout').value;
  var elec=document.getElementById('s3-elec').value;
  var audience=(document.querySelector('input[name="s3-audience"]:checked')||{}).value||'';
  var count=document.getElementById('s3-count').value.trim();
  var industry=document.getElementById('s3-industry').value.trim();
  var products=document.getElementById('s3-products').value.trim();
  var mdur=(document.querySelector('input[name="s3-mdur"]:checked')||{}).value||'';
  var mtype=(document.querySelector('input[name="s3-mtype"]:checked')||{}).value||'';
  var dt=_gfrGetDatetime('s3');
  if(!poc||!phone||!email||!company||!addr||!inout||!elec){alert('Please complete all Basic Info and Venue fields.');return;}
  if(!audience||!count||!industry||!products){alert('Please complete all Participant Details fields.');return;}
  if(!mdur||!mtype||!dt){alert('Please complete the Requested Service, Date & Time section.');return;}
  btn.disabled=true;btn.textContent='Submitting\u2026';
  var fields={
    point_of_contact_name:poc,contact_phone:phone,contact_email:email,company_name:company,
    venue_address:addr,indoor_outdoor:inout,has_electricity:elec,
    audience_type:audience,anticipated_count:count,company_industry:industry,products_services:products,
    massage_duration:mdur,massage_type:mtype,requested_datetime:dt
  };
  await _gfrDoSubmit('s3','Mobile Massage Service',fields,btn);
}

// -- Form 4: Lunch and Learn -----------------------------------------------
function s4Reset(){
  _gfrBaseReset('s4',['s4-diets','s4-collar','s4-hcare'],['count','industry','products'],['confroom','foodsurface','projector']);
  document.getElementById('gfr-user-s4').textContent=GFR_USER;
}
async function s4Submit(){
  var btn=document.getElementById('s4-submit');
  var poc=document.getElementById('s4-poc').value.trim();
  var phone=document.getElementById('s4-phone').value.trim();
  var email=document.getElementById('s4-email').value.trim();
  var company=document.getElementById('s4-company').value.trim();
  var addr=document.getElementById('s4-addr').value.trim();
  var inout=document.getElementById('s4-inout').value;
  var elec=document.getElementById('s4-elec').value;
  var confroom=document.getElementById('s4-confroom').value;
  var foodsurface=document.getElementById('s4-foodsurface').value;
  var projector=document.getElementById('s4-projector').value;
  var count=document.getElementById('s4-count').value.trim();
  var diets=(document.querySelector('input[name="s4-diets"]:checked')||{}).value||'';
  var collar=(document.querySelector('input[name="s4-collar"]:checked')||{}).value||'';
  var hcare=(document.querySelector('input[name="s4-hcare"]:checked')||{}).value||'';
  var industry=document.getElementById('s4-industry').value.trim();
  var products=document.getElementById('s4-products').value.trim();
  var dt=_gfrGetDatetime('s4');
  if(!poc||!phone||!email||!company||!addr||!inout||!elec||!confroom||!foodsurface||!projector){alert('Please complete all Basic Info and Venue fields.');return;}
  if(!count||!diets||!collar||!hcare||!industry||!products){alert('Please complete all Participant Details fields.');return;}
  if(!dt){alert('Please select a requested date and time.');return;}
  btn.disabled=true;btn.textContent='Submitting\u2026';
  var fields={
    point_of_contact_name:poc,contact_phone:phone,contact_email:email,company_name:company,
    venue_address:addr,indoor_outdoor:inout,has_electricity:elec,
    has_conference_room:confroom,has_food_surfaces:foodsurface,has_projector:projector,
    anticipated_count:count,dietary_restrictions:diets,staff_collar:collar,healthcare_insurance:hcare,
    company_industry:industry,products_services:products,requested_datetime:dt
  };
  await _gfrDoSubmit('s4','Lunch and Learn',fields,btn);
}

// -- Form 5: Health Assessment Screening -----------------------------------
function s5Reset(){
  _gfrBaseReset('s5',['s5-collar','s5-hcare'],['count','industry','products'],[]);
  document.getElementById('gfr-user-s5').textContent=GFR_USER;
}
async function s5Submit(){
  var btn=document.getElementById('s5-submit');
  var poc=document.getElementById('s5-poc').value.trim();
  var phone=document.getElementById('s5-phone').value.trim();
  var email=document.getElementById('s5-email').value.trim();
  var company=document.getElementById('s5-company').value.trim();
  var addr=document.getElementById('s5-addr').value.trim();
  var inout=document.getElementById('s5-inout').value;
  var elec=document.getElementById('s5-elec').value;
  var count=document.getElementById('s5-count').value.trim();
  var industry=document.getElementById('s5-industry').value.trim();
  var collar=(document.querySelector('input[name="s5-collar"]:checked')||{}).value||'';
  var hcare=(document.querySelector('input[name="s5-hcare"]:checked')||{}).value||'';
  var products=document.getElementById('s5-products').value.trim();
  var dt=_gfrGetDatetime('s5');
  if(!poc||!phone||!email||!company||!addr||!inout||!elec){alert('Please complete all Basic Info and Venue fields.');return;}
  if(!count||!industry||!collar||!hcare||!products){alert('Please complete all Participant Details fields.');return;}
  if(!dt){alert('Please select a requested date and time.');return;}
  btn.disabled=true;btn.textContent='Submitting\u2026';
  var fields={
    point_of_contact_name:poc,contact_phone:phone,contact_email:email,company_name:company,
    venue_address:addr,indoor_outdoor:inout,has_electricity:elec,
    anticipated_count:count,staff_collar:collar,healthcare_insurance:hcare,
    company_industry:industry,products_services:products,requested_datetime:dt
  };
  await _gfrDoSubmit('s5','Health Assessment Screening',fields,btn);
}

// -- Form 2: External Event / Interaction Only ----------------------------
function s2ToggleEvent(){
  var cb=document.getElementById('s2-has-event');
  var block=document.getElementById('s2-event-block');
  if(block)block.style.display=cb.checked?'':'none';
}
function s2Reset(){
  ['s2-event-name','s2-event-type','s2-organizer','s2-org-phone','s2-cost',
   's2-duration','s2-addr','s2-date','s2-industry','s2-int-person','s2-int-fu','s2-int-summary'].forEach(function(id){
    var el=document.getElementById(id);if(el)el.value='';
  });
  ['s2-inout','s2-elec','s2-hour','s2-min','s2-ampm','s2-status','s2-int-type','s2-int-outcome'].forEach(function(id){
    var el=document.getElementById(id);if(el)el.selectedIndex=0;
  });
  document.querySelectorAll('input[name="s2-collar"],input[name="s2-hcare"]').forEach(function(r){r.checked=false;});
  var flyer=document.getElementById('s2-flyer');if(flyer)flyer.value='';
  var cb=document.getElementById('s2-has-event');if(cb)cb.checked=false;
  var block=document.getElementById('s2-event-block');if(block)block.style.display='none';
  var old=document.querySelector('#gfr-form-s2 .gfr-success');if(old)old.remove();
  var body=document.getElementById('gfr-body-s2');if(body)body.style.display='';
  var foot=document.querySelector('#gfr-form-s2 .gfr-footer');if(foot)foot.style.display='';
  var btn=document.getElementById('s2-submit');if(btn){btn.disabled=false;btn.textContent='Submit';}
  document.getElementById('gfr-user-s2').textContent=GFR_USER;
}
async function s2Submit(){
  var btn=document.getElementById('s2-submit');
  // Interaction details — always required
  var intType=document.getElementById('s2-int-type').value;
  var intOutcome=document.getElementById('s2-int-outcome').value;
  var intPerson=document.getElementById('s2-int-person').value.trim();
  var intFu=document.getElementById('s2-int-fu').value;
  var intSummary=document.getElementById('s2-int-summary').value.trim();
  if(!intSummary){alert('Please describe the interaction in the "What happened?" field.');return;}

  var hasEvent=document.getElementById('s2-has-event').checked;

  // Build fields based on whether this is event-or-interaction-only
  var fields={
    interaction_type:intType,interaction_outcome:intOutcome,
    interaction_person:intPerson,interaction_follow_up:intFu,
    interaction_summary:intSummary,
    has_event:hasEvent
  };
  var formType='Interaction Only';
  var flyer=null;

  if(hasEvent){
    var evtName=document.getElementById('s2-event-name').value.trim();
    var evtType=document.getElementById('s2-event-type').value.trim();
    var organizer=document.getElementById('s2-organizer').value.trim();
    var orgPhone=document.getElementById('s2-org-phone').value.trim();
    var cost=document.getElementById('s2-cost').value.trim();
    var duration=document.getElementById('s2-duration').value.trim();
    var addr=document.getElementById('s2-addr').value.trim();
    var inout=document.getElementById('s2-inout').value;
    var elec=document.getElementById('s2-elec').value;
    var collar=(document.querySelector('input[name="s2-collar"]:checked')||{}).value||'';
    var hcare=(document.querySelector('input[name="s2-hcare"]:checked')||{}).value||'';
    var industry=document.getElementById('s2-industry').value.trim();
    var status=document.getElementById('s2-status').value;
    var dt=_gfrGetDatetime('s2');
    flyer=(document.getElementById('s2-flyer').files||[])[0]||null;
    if(!evtName||!evtType||!organizer||!cost){alert('Please fill in all required Basic Info fields (Name, Type, Organizer, Cost).');return;}
    if(!addr||!inout||!elec){alert('Please complete the Venue section.');return;}
    if(!dt){alert('Please select an event date and time.');return;}
    formType='External Event';
    fields.event_name=evtName;fields.event_type=evtType;fields.event_organizer=organizer;
    fields.organizer_phone=orgPhone;fields.event_cost=cost;fields.event_duration=duration;
    fields.venue_address=addr;fields.indoor_outdoor=inout;fields.has_electricity=elec;
    fields.staff_collar=collar;fields.healthcare_insurance=hcare;fields.company_industry=industry;
    fields.event_datetime=dt;fields.event_status=status;
  }

  btn.disabled=true;btn.textContent='Submitting\u2026';
  try{
    var r;
    if(flyer){
      var fd=new FormData();
      fd.append('form_type',formType);
      fd.append('fields',JSON.stringify(fields));
      fd.append('user_name',GFR_USER);
      fd.append('flyer',flyer);
      r=await fetch('/api/guerilla/log',{method:'POST',body:fd});
    }else{
      r=await fetch('/api/guerilla/log',{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({form_type:formType,fields:fields,user_name:GFR_USER})});
    }
    var d=await r.json();
    if(d.ok){_gfrSuccess('s2',d.activity_id);}
    else{alert('Error: '+(d.error||'Unknown error'));btn.disabled=false;btn.textContent='Submit';}
  }catch(e){alert('Network error. Please try again.');btn.disabled=false;btn.textContent='Submit';}
}
"""

# ---------------------------------------------------------------------------
# GFR convenience bundles
# ---------------------------------------------------------------------------
GFR_EXTRA_HTML = _GFR_CSS + _GFR_HTML + _GFR_FORMS345_HTML + _GFR_FORM2_HTML
GFR_EXTRA_JS = _GFR_JS + '\n' + _GFR_FORMS345_JS
