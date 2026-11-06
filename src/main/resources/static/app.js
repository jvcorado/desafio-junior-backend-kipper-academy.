const $ = (q, root = document) => root.querySelector(q);
const state = { tickets: [], policies: [], conflicts: [], page: 'board', team: '', search: '' };
const labels = { RECEIVED:'Recebido', PROCESSING:'Analisando', REVIEW:'Revisão humana', READY:'Pronto para enviar', SENDING:'Envio em confirmação', FORWARDED:'Encaminhado', DELIVERY_FAILED:'Envio rejeitado', DELIVERY_UNKNOWN:'Resultado desconhecido', CLOSED:'Concluído', BILLING:'Cobrança', TECHNICAL:'Técnico', OTHER:'Outros', FINANCE:'Financeiro', NORMAL:'Normal', HIGH:'Alta', OPEN:'Aguardando revisão', RELEASED:'Liberado', DISMISSED:'Revisado e descartado' };
const esc = value => String(value ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const label = v => labels[v] || v || 'Não definida';
const date = v => new Date(v).toLocaleString('pt-BR', {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
let noticeTimer;
function notice(message, error = false) {
  const el = $('#notice'); el.textContent = message; el.classList.toggle('error', error); el.hidden = false;
  clearTimeout(noticeTimer); noticeTimer = setTimeout(() => {el.hidden = true;}, 14000);
}
async function api(path, method='GET', body) {
  const response = await fetch('/api'+path, {method, headers:{'Content-Type':'application/json'}, ...(method==='GET'?{}:{body:JSON.stringify(body ?? {})})});
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) throw new Error(data?.error ? data.error+(data.fields?' · '+data.fields.join('; '):'') : data?.outcome==='CONFLICT'?'Conflito preservado para revisão na fila.':'Não foi possível concluir a ação.');
  return data;
}
async function refresh() {
  try {
    const [tickets,policies,conflicts] = await Promise.all([api('/tickets'),api('/policies'),api('/conflicts')]);
    Object.assign(state,{tickets,policies,conflicts});
    render();
  } catch(e) { notice(e.message,true); }
}
function render() {
  $('#conflict-count').textContent = state.conflicts.filter(c=>c.status==='OPEN').length;
  $('#total').textContent = state.tickets.length;
  $('#pending').textContent = state.tickets.filter(t=>!['FORWARDED','CLOSED'].includes(t.status)).length;
  $('#forwarded').textContent = state.tickets.filter(t=>['FORWARDED','CLOSED'].includes(t.status)).length;
  $('#high').textContent = state.tickets.filter(t=>t.priority==='HIGH').length;
  const groups = [ ['Novos',['RECEIVED','PROCESSING','READY']], ['Revisão e pendências',['REVIEW','SENDING','DELIVERY_FAILED','DELIVERY_UNKNOWN']], ['Encaminhados',['FORWARDED']], ['Concluídos',['CLOSED']] ];
  const filtered = state.tickets.filter(t=>(!state.team||t.team===state.team)&&[t.customerName,t.ticketId,t.id,t.message].join(' ').toLowerCase().includes(state.search));
  $('#board').innerHTML = groups.map(([title,statuses])=> {
    const tickets=filtered.filter(t=>statuses.includes(t.status));
    return `<section class="column"><h2 class="column-heading"><i></i>${title}<b>${tickets.length}</b></h2>${tickets.length?tickets.map(card).join(''):'<div class="empty">Tudo em ordem por aqui.<br>Nenhum chamado nesta etapa.</div>'}</section>`;
  }).join('');
  $('#policies').innerHTML = state.policies.map(p=>`<article class="policy-card"><span class="badge">${p.active?'ATIVA':'REMOVIDA'} · V${p.version}</span><h3>${esc(p.subject)}</h3><span class="muted">${esc(label(p.category))} → ${esc(label(p.team))}</span><p>${esc(p.rule)}</p><footer><button class="text-button" data-edit-policy="${esc(p.id)}">${p.active?'Editar política':'Editar e reativar'}</button>${p.active?`<button class="text-button danger" data-remove-policy="${esc(p.id)}">Remover</button>`:''}</footer></article>`).join('');
  $('#conflicts').innerHTML = state.conflicts.length?state.conflicts.map(c=> {
    let event; try { event=JSON.parse(c.payload); } catch { event={}; }
    return `<article class="conflict-card"><span class="badge review">${esc(label(c.status))}</span><span class="muted">${esc(date(c.created_at))}</span><h3>${esc(event.customerName)} · ${esc(c.event_id)}</h3><p>${esc(event.message)}</p><p class="muted">Chamado original: ${esc(c.original_ticket_id)}${c.released_ticket_id?' · Novo chamado: '+esc(c.released_ticket_id):''}</p>${c.resolution?`<p>Revisão: ${esc(c.resolution)}</p>`:''}${c.status==='OPEN'?`<button class="text-button" data-resolve="${esc(c.id)}">Revisar conflito →</button>`:''}</article>`;
  }).join(''):'<div class="empty">Nenhum conflito recebido.</div>';
}
function card(t) {
  const action = {RECEIVED:['process','Iniciar triagem →'],DELIVERY_FAILED:['retry','Tentar envio novamente'],DELIVERY_UNKNOWN:['reconcile','Consultar confirmação'],SENDING:['reconcile','Consultar confirmação']}[t.status];
  return `<article class="card"><div class="card-head"><span>#${esc(t.id.slice(0,8))}</span>${t.priority?`<span class="badge ${t.priority==='HIGH'?'high':''}">PRIORIDADE ${esc(label(t.priority).toUpperCase())}</span>`:'<span class="badge review">A DEFINIR</span>'}</div><h3>${esc(t.customerName)}</h3><p class="message">${esc(t.message)}</p><div class="card-status">${esc(label(t.status))}${t.deliveryAdapter==='demo'?' · Simulação':''}</div><div class="card-footer"><span class="badge ${t.team==='FINANCE'?'finance':t.team==='TECHNICAL'?'tech':'review'}">${esc(label(t.team)||'Aguardando triagem')}</span><button data-detail="${esc(t.id)}">Ver detalhes ↗</button></div>${action?`<button class="action" data-action="${action[0]}" data-id="${esc(t.id)}">${action[1]}</button>`:''}</article>`;
}
async function detail(id) {
  try {
    const d=await api('/tickets/'+id),t=d.ticket;
    const url=t.externalUrl;
    const safeUrl=url && (url.startsWith('https://github.com/') || url.startsWith('/demo.html?') || /^\/\?ticket=[a-f0-9-]{36}$/.test(url));
    $('#detail').innerHTML = `<span class="badge">${esc(label(t.status))}${t.deliveryAdapter==='demo'?' · SIMULAÇÃO':''}</span><dl class="details-grid">${[['Cliente',t.customerName],['WhatsApp',t.whatsapp],['ID do chamado',t.ticketId],['ID interno',t.id],['Categoria',label(t.category)],['Prioridade',label(t.priority)],['Equipe',label(t.team)],['Recebido em',date(t.createdAt)]].map(([k,v])=>`<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join('')}</dl><h3>Mensagem original</h3><p class="detail-message">${esc(t.message)}</p><h3>Justificativa</h3><p>${esc(t.explanation||'Aguardando análise.')}</p>${safeUrl?`<p><a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${t.deliveryAdapter==='demo'?'Ver registro simulado':t.deliveryAdapter==='panel'?'Abrir cartão no Kanban':'Abrir issue confirmada'} ↗</a></p>`:''}<details><summary>Histórico de análises e ferramentas (${d.analyses.length})</summary><pre>${esc(JSON.stringify(d.analyses,null,2))}</pre></details><details><summary>Tentativas de encaminhamento (${d.attempts.length})</summary><pre>${esc(JSON.stringify(d.attempts,null,2))}</pre></details>${d.actions?.length?`<details><summary>Ações humanas (${d.actions.length})</summary><pre>${esc(JSON.stringify(d.actions,null,2))}</pre></details>`:''}${t.status==='REVIEW'?`<button class="primary" data-note-action="reanalyze" data-id="${esc(id)}">Reanalisar após revisão</button>`:''}${t.status==='FORWARDED'?`<button class="primary" data-note-action="close" data-id="${esc(id)}">Encerrar atendimento</button>`:''}${t.status==='PROCESSING'?`<button class="text-button" data-note-action="recover" data-id="${esc(id)}">Recuperar análise interrompida</button>`:''}`;
    if(!$('#detail-dialog').open) $('#detail-dialog').showModal();
  } catch(e) { notice(e.message,true); }
}
document.addEventListener('click',async e=> {
  const b=e.target.closest('button'); if(!b) return;
  if(b.classList.contains('close')) { b.closest('dialog').close(); return; }
  if(b.dataset.page) {
    state.page=b.dataset.page;
    for(const page of ['board','policies','conflicts']) $('#'+page+'-page').hidden=page!==state.page;
    document.querySelectorAll('.nav').forEach(n=>n.classList.toggle('active',n===b));
    $('#page-title').textContent=state.page==='board'?'Cada chamado, no lugar certo.':state.page==='policies'?'Regras claras para cada decisão.':'Nenhuma mensagem fica para trás.';
    $('#page-subtitle').textContent=state.page==='board'?'Acompanhe a triagem, a revisão e os encaminhamentos da sua equipe.':state.page==='policies'?'Gerencie o catálogo que orienta o agente de triagem.':'Revise eventos com identidades repetidas e conteúdos diferentes.';
    $('#new-event').hidden=state.page!=='board'; return;
  }
  if(b.hasAttribute('data-team')) { state.team=b.dataset.team; document.querySelectorAll('[data-team]').forEach(n=>n.classList.toggle('selected',n===b)); render(); return; }
  if(b.dataset.detail) { await detail(b.dataset.detail); return; }
  if(b.dataset.action || b.dataset.noteAction) {
    let body={}; const action=b.dataset.action||b.dataset.noteAction;
    if(b.dataset.noteAction) {
      const f=$('#note-form'); f.reset(); f.elements.id.value=b.dataset.id; f.elements.action.value=action;
      $('#note-title').textContent=action==='close'?'Encerrar atendimento':'Registrar revisão humana';
      $('.form-error',f).textContent=''; $('#note-dialog').showModal(); return;
    }
    b.disabled=true;
    try { await api(`/tickets/${b.dataset.id}/${action}`,'POST',body); notice('Ação registrada. Confira o estado e o histórico do chamado.'); if(b.closest('dialog')) await detail(b.dataset.id); }
    catch(err) { notice(err.message,true); }
    finally { b.disabled=false; await refresh(); } return;
  }
  if(b.dataset.editPolicy) { const p=state.policies.find(p=>p.id===b.dataset.editPolicy); const f=$('#policy-form'); f.elements.id.value=p.id; f.elements.version.value=p.version; for(const k of ['category','subject','rule']) f.elements[k].value=p[k]; $('.form-error',f).textContent=''; $('#policy-dialog').showModal(); return; }
  if(b.dataset.removePolicy) {
    const p=state.policies.find(p=>p.id===b.dataset.removePolicy),f=$('#remove-form');
    f.elements.id.value=p.id; f.elements.version.value=p.version;
    $('#remove-description').textContent=`Remover a política “${p.subject}”?`;
    $('.form-error',f).textContent=''; $('#remove-dialog').showModal(); return;
  }
  if(b.dataset.resolve) { const f=$('#resolution-form'); f.reset(); f.elements.id.value=b.dataset.resolve; $('.form-error',f).textContent=''; $('#resolution-dialog').showModal(); }
});
$('#search').addEventListener('input',e=>{state.search=e.target.value.toLowerCase();render();});
$('#new-event').onclick=()=>{$('#event-form').reset();$('.form-error',$('#event-form')).textContent='';$('#event-dialog').showModal();};
$('#new-policy').onclick=()=>{$('#policy-form').reset();$('.form-error',$('#policy-form')).textContent='';$('#policy-dialog').showModal();};
function submit(form, handler) { form.addEventListener('submit',async e=>{e.preventDefault();const b=$('[type=submit]',form);b.disabled=true;try{await handler(new FormData(form));form.closest('dialog').close();notice('Dados salvos.');await refresh();}catch(err){$('.form-error',form).textContent=err.message;}finally{b.disabled=false;}}); }
submit($('#event-form'), async f=> {
  const id=crypto.randomUUID();
  await api('/manual-events','POST',{source:'panel-test',eventId:'evt-'+id,ticketId:'test-'+id,customerId:'fictional-'+id,customerName:f.get('customerName'),whatsapp:f.get('whatsapp'),message:f.get('message'),occurredAt:new Date().toISOString()});
});
submit($('#policy-form'),async f=>{
  const category=f.get('category'),team={BILLING:'FINANCE',TECHNICAL:'TECHNICAL',OTHER:'REVIEW'}[category],id=f.get('id');
  await api('/policies'+(id?'/'+id:''),id?'PUT':'POST',{category,team,subject:f.get('subject'),rule:f.get('rule'),expectedVersion:id?Number(f.get('version')):null});
});
submit($('#resolution-form'),async f=>{
  const action=f.get('action');
  await api(`/conflicts/${f.get('id')}/${action}`,'POST',action==='dismiss'?{note:f.get('note')}:{note:f.get('note'),newEventId:f.get('newEventId'),newTicketId:f.get('newTicketId')});
});
submit($('#note-form'),async f=>{
  const id=f.get('id'); await api(`/tickets/${id}/${f.get('action')}`,'POST',{note:f.get('note')});
  await detail(id);
});
submit($('#remove-form'),async f=>{await api(`/policies/${f.get('id')}?version=${f.get('version')}`,'DELETE');});
(async()=>{try{const c=await api('/config');$('#mode').textContent=`IA: ${c.aiMode==='demo'?'simulada':'provedor real'} · Encaminhamento: ${({demo:'simulado',panel:'Kanban interno',github:'GitHub'})[c.deliveryMode]||c.deliveryMode}`;}catch(e){notice(e.message,true);}await refresh();const ticket=new URLSearchParams(location.search).get('ticket');if(ticket&&/^[a-f0-9-]{36}$/.test(ticket))await detail(ticket);})();
setInterval(refresh,10000);
