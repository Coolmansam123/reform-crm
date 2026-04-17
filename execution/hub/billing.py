"""
Billing pages — collections and settlements.
"""
from .shared import _page, T_PI_FINANCE


def _billing_page(section: str, br: str, bt: str, user: dict = None) -> str:
    is_s = section == 'settlements'
    title = 'Settlements' if is_s else 'Collections'
    active_key = f'billing_{section}'
    header = (
        f'<div class="header"><div class="header-left">'
        f'<h1>{title}</h1>'
        f'<div class="sub">{"Settlement records and financial summary" if is_s else "Outstanding balances and follow-up tracking"}</div>'
        f'</div></div>'
    )
    if is_s:
        body = """
<div class="stats-row">
  <div class="stat-chip c-green"> <div class="label">Total Settled</div>    <div class="value" id="s-count">—</div></div>
  <div class="stat-chip c-purple"><div class="label">Avg Settlement</div>   <div class="value" id="s-avg">—</div></div>
  <div class="stat-chip c-red">   <div class="label">Total Atty Fees</div>  <div class="value" id="s-fees">—</div></div>
  <div class="stat-chip c-green"> <div class="label">Net to Reform</div>    <div class="value" id="s-net">—</div></div>
</div>
<div class="panel">
  <div class="panel-hd"><span class="panel-title">Settlement Records</span><span class="panel-ct" id="ct">—</span></div>
  <div class="panel-body" id="tbl"><div class="loading">Loading…</div></div>
</div>"""
        js = f"""
async function load() {{
  const rows = await fetchAll({T_PI_FINANCE});
  const settled = rows.filter(r => r['Settlement Amount'] && parseFloat(r['Settlement Amount']) > 0);
  const fmt$ = n => '$' + Math.round(n).toLocaleString();
  const totSett = settled.reduce((s,r) => s+(parseFloat(r['Settlement Amount'])||0),0);
  const totFees = settled.reduce((s,r) => s+(parseFloat(r['Attorney Fees'])||0),0);
  const totPaid = settled.reduce((s,r) => s+(parseFloat(r['Amount Paid'])||0),0);
  document.getElementById('s-count').textContent = settled.length;
  document.getElementById('s-avg').textContent   = fmt$(settled.length ? totSett/settled.length : 0);
  document.getElementById('s-fees').textContent  = fmt$(totFees);
  document.getElementById('s-net').textContent   = fmt$(totPaid);
  document.getElementById('ct').textContent      = settled.length + ' records';
  const sorted = [...settled].sort((a,b)=>(b['Settlement Date']||b['Date of Settlement']||'').localeCompare(a['Settlement Date']||a['Date of Settlement']||''));
  document.getElementById('tbl').innerHTML = sorted.length ? `
    <table class="data-table"><thead><tr>
      <th>Patient</th><th>Firm</th><th class="r">Settlement</th><th class="r">Atty Fees</th><th class="r">Paid</th>
    </tr></thead><tbody>
    ${{sorted.map(r=>`<tr>
      <td style="font-weight:500">${{esc(r['Patient Name']||r['Name']||'—')}}</td>
      <td style="color:#94a3b8">${{esc(sv(r['Law Firm Name ONLY']||r['Law Firm Name']||r['Law Firm']||'—'))}}</td>
      <td class="r" style="color:#34d399">${{r['Settlement Amount']?'$'+parseFloat(r['Settlement Amount']).toLocaleString():'—'}}</td>
      <td class="r" style="color:#f87171">${{r['Attorney Fees']?'$'+parseFloat(r['Attorney Fees']).toLocaleString():'—'}}</td>
      <td class="r" style="color:#a78bfa">${{r['Amount Paid']?'$'+parseFloat(r['Amount Paid']).toLocaleString():'—'}}</td>
    </tr>`).join('')}}
    </tbody></table>` : '<div class="empty">No settlement records found</div>';
  stampRefresh();
}}
load();
"""
    else:
        body = """
<div class="stats-row">
  <div class="stat-chip c-red">   <div class="label">Total Outstanding</div><div class="value" id="s-out">—</div></div>
  <div class="stat-chip c-green"> <div class="label">Total Paid</div>        <div class="value" id="s-paid">—</div></div>
  <div class="stat-chip c-yellow"><div class="label">Follow-Ups Due</div>   <div class="value" id="s-due">—</div></div>
  <div class="stat-chip">         <div class="label">Total Records</div>     <div class="value" id="s-total">—</div></div>
</div>
<div class="panel">
  <div class="panel-hd"><span class="panel-title">Outstanding Balances</span><span class="panel-ct" id="ct">—</span></div>
  <div class="panel-body" id="tbl"><div class="loading">Loading…</div></div>
</div>"""
        js = f"""
async function load() {{
  const rows = await fetchAll({T_PI_FINANCE});
  const unpaid = rows.filter(r => !r['Paid'] || sv(r['Paid']).toLowerCase()==='no'||sv(r['Paid']).toLowerCase()==='false');
  const paid   = rows.filter(r =>  r['Paid'] && sv(r['Paid']).toLowerCase()!=='no'&&sv(r['Paid']).toLowerCase()!=='false');
  const fmt$ = n => '$' + Math.round(n).toLocaleString();
  const today = new Date().setHours(0,0,0,0);
  const dueSoon = unpaid.filter(r=>{{const d=r['Follow-Up Date'];return d&&(new Date(d).setHours(0,0,0,0)-today)<=86400000*7;}});
  document.getElementById('s-out').textContent   = fmt$(unpaid.reduce((s,r)=>s+(parseFloat(r['Amount Due'])||0),0));
  document.getElementById('s-paid').textContent  = fmt$(paid.reduce((s,r)=>s+(parseFloat(r['Amount Due'])||0),0));
  document.getElementById('s-due').textContent   = dueSoon.length;
  document.getElementById('s-total').textContent = rows.length;
  document.getElementById('ct').textContent      = unpaid.length + ' unpaid';
  const sorted = [...unpaid].sort((a,b)=>new Date(a['Follow-Up Date']||'9999')-new Date(b['Follow-Up Date']||'9999'));
  document.getElementById('tbl').innerHTML = sorted.length ? `
    <table class="data-table"><thead><tr>
      <th>Patient</th><th>Firm</th><th class="r">Amount Due</th><th class="c">Follow-Up</th><th class="c">Type</th>
    </tr></thead><tbody>
    ${{sorted.map(r=>{{
      const du=daysUntil(r['Follow-Up Date']); const ov=du!==null&&du<0;
      return `<tr style="${{ov?'background:rgba(239,68,68,0.04)':''}}">
        <td style="font-weight:500">${{esc(r['Patient Name']||r['Name']||'—')}}</td>
        <td style="color:#94a3b8">${{esc(sv(r['Law Firm Name ONLY']||r['Law Firm Name']||r['Law Firm']||'—'))}}</td>
        <td class="r" style="color:#f87171;font-weight:600">${{r['Amount Due']?'$'+parseFloat(r['Amount Due']).toLocaleString():'—'}}</td>
        <td class="c">${{r['Follow-Up Date']?`<span style="font-size:11px;padding:2px 7px;border-radius:6px;background:${{ov?'rgba(239,68,68,0.15)':'rgba(30,58,95,0.8)'}};color:${{ov?'#f87171':'#94a3b8'}}">${{ov?Math.abs(du)+'d overdue':fmt(r['Follow-Up Date'])}}</span>`:'—'}}</td>
        <td class="c" style="color:#64748b;font-size:11px">${{esc(r['MedPay/PI/Insurance']||'—')}}</td>
      </tr>`;
    }}).join('')}}
    </tbody></table>` : '<div class="empty">No outstanding balances ✓</div>';
  stampRefresh();
}}
load();
"""
    return _page(active_key, title, header, body, js, br, bt, user=user)
