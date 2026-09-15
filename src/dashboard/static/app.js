'use strict';
const $=id=>document.getElementById(id);
const number=new Intl.NumberFormat('pt-BR',{maximumFractionDigits:1});
const integer=new Intl.NumberFormat('pt-BR',{maximumFractionDigits:0});
const money=new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'});
const short=new Intl.NumberFormat('pt-BR',{notation:'compact',maximumFractionDigits:1});
const escapeHTML=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nice=s=>s==='nao_informado'?'Não informado':String(s).replaceAll('_',' ');
let active='comercial', data=null, defaults=null, sequence=0;
const format=(v,type)=>v===null||v===undefined?'—':type==='money'?money.format(v):type==='percent'?number.format(v)+'%':type==='days'?number.format(v)+' dias':type==='km'?number.format(v)+' km':type==='score'?number.format(v)+' / 5':integer.format(v);
const panels={
 comercial:{eyebrow:'01 / VISÃO COMERCIAL',title:'O ritmo das vendas.',objective:'Entenda a evolução do valor entregue e a composição das vendas.',scope:'Somente pedidos entregues · Valores incluem frete',
 cards:r=>[['Valor entregue',r.valor_entregue,'money',integer.format(r.entregues)+' pedidos entregues'],['Pedidos entregues',r.entregues,'integer','Status: delivered'],['Ticket médio',r.ticket,'money',integer.format(r.base_ticket)+' pedidos com valor conhecido'],['Participação do frete',r.percentual_frete,'percent','Frete ÷ valor total entregue']],
 charts:[['mensal','Valor entregue ao longo do tempo','Compras por mês · valores incluem frete','line','money'],['categorias','Categorias que mais vendem','Top 10 por valor entregue · base: itens','bar','money'],['porte','Ticket médio por porte municipal','População de 2017: pequeno < 50 mil; médio até 500 mil; grande > 500 mil','columns','money']],
 method:'Valor entregue é a soma dos valores dos pedidos entregues, incluindo frete. Ticket médio considera apenas valores conhecidos. A classificação municipal usa população de 2017 como contexto fixo; não mede a população atual. Municípios não resolvidos aparecem como “Não informado”.'},
 logistica:{eyebrow:'02 / EFICIÊNCIA LOGÍSTICA',title:'Da compra à entrega.',objective:'Identifique atrasos e diferenças de prazo entre períodos e estados.',scope:'Somente pedidos entregues · Datas válidas para cada indicador',
 cards:r=>[['Prazo médio',r.prazo,'days',integer.format(r.base_prazo)+' entregas com prazo calculável'],['Entregas atrasadas',r.atraso,'percent',integer.format(r.atrasados)+' de '+integer.format(r.base_atraso)+' entregas avaliáveis'],['Pedidos atrasados',r.atrasados,'integer','Entrega após a data estimada'],['Distância média',r.distancia,'km',integer.format(r.base_distancia)+' itens com coordenadas']],
 charts:[['prazo_mensal','Evolução do prazo de entrega','Média por pedido · agrupamento pelo mês da compra','line','days'],['atraso_uf','Atrasos por UF do cliente','Percentual entre entregas com atraso calculável','bar','percent']],
 method:'Prazo e atraso são calculados por pedido. Datas ausentes ficam fora apenas da base do indicador correspondente; não representam prazo zero nem entrega pontual. A distância é a média por item entre coordenadas aproximadas de CEPs e não representa percurso rodoviário. Estados com poucas entregas devem ser interpretados com cautela; consulte as bases na tabela de cada gráfico.'},
 satisfacao:{eyebrow:'03 / EXPERIÊNCIA DO CLIENTE',title:'O que os clientes sentem.',objective:'Acompanhe a satisfação e sua associação com o cumprimento do prazo.',scope:'Avaliações de todos os status · Comparação de atraso apenas para entregues',
 cards:r=>[['Nota média',r.nota,'score',integer.format(r.avaliados)+' pedidos avaliados'],['Avaliações positivas',r.positivas,'percent','Notas 4 ou 5 · base: '+integer.format(r.avaliados)],['Cobertura de avaliações',r.cobertura,'percent',integer.format(r.avaliados)+' de '+integer.format(r.pedidos_filtrados)+' pedidos'],['Avaliações negativas',r.negativas,'percent','Notas 1 ou 2 · nota 3 é neutra']],
 charts:[['notas','Distribuição das avaliações','Uma avaliação consolidada por pedido','columns','integer'],['nota_atraso','Prazo cumprido, experiência melhor?','Nota média · entregues com avaliação e atraso calculável','columns','score']],
 method:'Cada pedido contribui uma vez para a nota média, independentemente do número de itens. Pedidos sem nota não entram nas médias e percentuais de satisfação. A comparação entre atraso e avaliação mostra associação e não demonstra causalidade.'}
};
function table(rows,type){return '<details><summary>Ver valores e bases de cálculo</summary><table><thead><tr><th>Grupo</th><th>Valor</th><th>Base</th></tr></thead><tbody>'+rows.map(r=>`<tr><td>${escapeHTML(nice(r.nome))}</td><td>${format(r.valor,type)}</td><td>${integer.format(r.base)}</td></tr>`).join('')+'</tbody></table></details>';}
function graph(rows,kind,type){
 if(!rows.length||rows.every(r=>r.valor===null))return '<div class="empty">Sem dados para os filtros selecionados.</div>';
 const maximum=Math.max(...rows.map(r=>r.valor||0),1);
 if(kind==='bar')return rows.map(r=>`<div class="bar-row" title="${escapeHTML(nice(r.nome))}: ${format(r.valor,type)} · base ${integer.format(r.base)}"><div><div class="bar-name">${escapeHTML(nice(r.nome))}</div><div class="bar-track"><div class="bar-fill" style="width:${100*(r.valor||0)/maximum}%"></div></div></div><div class="bar-number">${r.valor===null?'—':type==='percent'?format(r.valor,type):'R$ '+short.format(r.valor)}</div></div>`).join('')+table(rows,type);
 const W=560,H=285,L=62,R=15,T=20,B=47,w=W-L-R,h=H-T-B;
 const top=type==='score'?5:maximum*1.15;
 const y=v=>T+h-(v/top)*h;
 const axis=Array.from({length:5},(_,i)=>{const v=top*i/4;return `<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#e7ebe5" stroke-dasharray="3 4"/><text x="${L-10}" y="${y(v)+4}" text-anchor="end">${type==='money'?'R$ ':''}${short.format(v)}</text>`}).join('');
 let marks='';
 if(kind==='line'){
  const x=i=>L+(rows.length===1?w/2:w*i/(rows.length-1));
  // A missing month remains a gap, rather than becoming a zero observation.
  let segments=[],segment=[];
  rows.forEach((r,i)=>{if(r.valor===null){if(segment.length)segments.push(segment);segment=[];}else segment.push([x(i),y(r.valor)]);});if(segment.length)segments.push(segment);
  marks=segments.map(seg=>`<polygon points="${seg[0][0]},${T+h} ${seg.map(p=>p.join(',')).join(' ')} ${seg.at(-1)[0]},${T+h}" fill="#287b76" opacity=".07"/><polyline points="${seg.map(p=>p.join(',')).join(' ')}" fill="none" stroke="#287b76" stroke-width="2.5"/>`).join('');
  marks+=rows.map((r,i)=>`${r.valor===null?'':`<circle tabindex="0" aria-label="${r.nome}: ${format(r.valor,type)}, base ${r.base}" cx="${x(i)}" cy="${y(r.valor)}" r="3" fill="#287b76"><title>${r.nome}: ${format(r.valor,type)} · base ${integer.format(r.base)}</title></circle>`}${i%Math.max(1,Math.ceil(rows.length/6))===0||i===rows.length-1?`<text x="${x(i)}" y="${H-16}" text-anchor="middle">${r.nome.slice(5)}/${r.nome.slice(2,4)}</text>`:''}`).join('');
 }else{
  const cell=w/rows.length,bw=Math.min(62,cell*.55);
  marks=rows.map((r,i)=>{const x=L+cell*i+cell/2;return `<rect tabindex="0" aria-label="${escapeHTML(nice(r.nome))}: ${format(r.valor,type)}, base ${r.base}" x="${x-bw/2}" y="${y(r.valor||0)}" width="${bw}" height="${T+h-y(r.valor||0)}" rx="3" fill="${i%2?'#83b4a2':'#287b76'}"><title>${escapeHTML(nice(r.nome))}: ${format(r.valor,type)} · base ${integer.format(r.base)}</title></rect><text class="value-label" x="${x}" y="${y(r.valor||0)-10}" text-anchor="middle">${r.valor===null?'—':type==='money'?'R$ '+short.format(r.valor):type==='score'?number.format(r.valor):integer.format(r.valor)}</text><text x="${x}" y="${H-16}" text-anchor="middle">${escapeHTML(nice(r.nome))}</text>`;}).join('');
 }
 return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gráfico; valores detalhados na tabela abaixo">${axis}${marks}</svg>`+table(rows,type);
}
function render(){
 const p=panels[active];
 $('title').textContent=p.title;$('eyebrow').textContent=p.eyebrow;$('objective').textContent=p.objective;
 document.querySelectorAll('[data-panel]').forEach(b=>{b.classList.toggle('active',b.dataset.panel===active);if(b.dataset.panel===active)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
 if(!data)return;
 $('scope').textContent=p.scope;
 $('selection').textContent=integer.format(data.resumo.pedidos_filtrados)+' pedidos no recorte · '+(data.filtros.uf==='Todas'?'Brasil':nice(data.filtros.uf));
 $('method').textContent=p.method;
 $('kpis').innerHTML=p.cards(data.resumo).map(([label,value,type,base])=>`<article class="kpi"><div class="kpi-label">${label}<span>↗</span></div><div class="kpi-value" title="${format(value,type)}">${type==='money'&&value>=1000000?'R$ '+short.format(value):format(value,type)}</div><div class="kpi-base">${base}</div></article>`).join('');
 $('charts').innerHTML=p.charts.map(([key,title,subtitle,kind,type],i)=>`<article class="chart-card ${i===2?'wide':''}"><div class="chart-heading"><h2>${title}</h2><span class="chart-tag">${kind==='line'?'SÉRIE TEMPORAL':'COMPARATIVO'}</span></div><p class="chart-subtitle">${subtitle}</p>${graph(data[key],kind,type)}</article>`).join('');
 $('content').hidden=false;
}
async function load(){
 const seq=++sequence;
 $('apply').disabled=true;$('download').disabled=true;$('status').className='';$('status').textContent='Atualizando indicadores…';$('content').hidden=true;
 try{
  const response=await fetch('/api/painel?'+new URLSearchParams({inicio:$('inicio').value,fim:$('fim').value,uf:$('uf').value}));
  const result=await response.json();if(seq!==sequence)return;if(!response.ok)throw Error(result.erro||'Não foi possível carregar os dados.');
  data=result;$('status').textContent='';$('period').textContent=result.filtros.inicio.split('-').reverse().join('/')+' — '+result.filtros.fim.split('-').reverse().join('/');
  render();$('download').disabled=false;
 }catch(error){if(seq===sequence){data=null;$('status').textContent=error.message;$('status').className='error';}}
 finally{if(seq===sequence)$('apply').disabled=false;}
}
$('filters').addEventListener('submit',e=>{e.preventDefault();load();});
$('reset').addEventListener('click',()=>{if(!defaults)return;$('inicio').value=defaults.inicio;$('fim').value=defaults.fim;$('uf').value='Todas';load();});
document.querySelectorAll('[data-panel]').forEach(b=>b.addEventListener('click',()=>{active=b.dataset.panel;render();}));
$('download').addEventListener('click',()=>{
 if(!data)return;
 const rows=[['Painel',active],['Início',data.filtros.inicio],['Fim',data.filtros.fim],['UF',data.filtros.uf],[],['KPI','Valor','Base']];
 panels[active].cards(data.resumo).forEach(([label,value,type,base])=>rows.push([label,value===null?'':value,base]));
 panels[active].charts.forEach(([key,title])=>{rows.push([],[title],['Grupo','Valor','Base']);data[key].forEach(r=>rows.push([nice(r.nome),r.valor??'',r.base]));});
 const csv='\uFEFF'+rows.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(';')).join('\r\n');
 const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='painel-'+active+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
(async()=>{try{const response=await fetch('/api/opcoes');const result=await response.json();if(!response.ok)throw Error(result.erro);defaults=result;$('inicio').value=result.inicio;$('fim').value=result.fim;result.ufs.forEach(uf=>{const o=document.createElement('option');o.value=uf;o.textContent=nice(uf);$('uf').appendChild(o);});await load();}catch(error){$('status').className='error';$('status').textContent=error.message;}})();
