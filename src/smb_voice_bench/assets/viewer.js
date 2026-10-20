"use strict";
(() => {
  const data = JSON.parse(document.getElementById("evidence").textContent);
  const app = document.getElementById("app");
  const el = (tag, text, cls) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (cls) node.className = cls; return node; };
  const add = (parent, ...nodes) => { nodes.forEach(n => parent.append(n)); return parent; };
  const badge = text => el("span", text.replaceAll("_", " "), "badge " + (text.includes("fail") || text === "blocked" ? "fail" : text === "pass" ? "pass" : "neutral"));
  const link = (label, path) => { const a = el("a", label); a.href = path; return a; };
  const section = title => { const s = el("section"); s.append(el("h2", title)); app.append(s); return s; };
  const detail = (title, value, open=false) => { const d = el("details"); d.open = open; add(d,el("summary",title),el("pre",JSON.stringify(value,null,2))); return d; };
  const download = (label, name, content, type) => { const a = link(label, URL.createObjectURL(new Blob([content],{type}))); a.download = name; return a; };
  const controls = section("Take the evidence with you"); controls.className = "exports";
  add(controls, link("Plain summary ↗", "summary.txt"), download("Full result JSON ↓", "result.json", JSON.stringify(data.result || data.comparison,null,2), "application/json"));
  if (data.kind === "comparison_report") {
    const comparison = data.comparison;
    const hero = el("section", undefined, "hero");
    add(hero, el("p",data.runs.every(r=>r.execution_mode==="reference")?"SCRIPTED REFERENCE DEMONSTRATIONS / AUDIO UNAVAILABLE":"COMPARE / EXPLICIT RUN HISTORY","eyebrow"), el("h1","Did the change complete the work?"),
      el("p",comparison.declared_change,"lede"), badge(comparison.assessment), el("p","Assessment scope: " + comparison.scope + ". Filters never change this assessment.","muted"));
    app.prepend(hero);
    const notes = section("What this assessment means"); comparison.blockers.forEach(t => notes.append(el("p",t)));
    const rows = section("Baseline → candidate");
    rows.append(el("p","Every selected attempt is retained. Small samples show observations only; they do not establish reliability or causal improvement.","muted"));
    const select = el("select"); select.setAttribute("aria-label","Filter scenario");
    ["All scenarios",...comparison.rows.map(r=>r.scenario_id)].forEach(v => { const o=el("option",v); o.value=v; select.append(o); }); rows.append(select);
    const mode=el("select");mode.setAttribute("aria-label","Filter execution mode");
    ["All execution modes","reference","text","audio"].forEach(v=>{const o=el("option",v);o.value=v;mode.append(o);});rows.append(mode);
    const verdict=el("select");verdict.setAttribute("aria-label","Filter functional verdict");
    ["All functional verdicts","pass","fail","unknown"].forEach(v=>{const o=el("option",v);o.value=v;verdict.append(o);});rows.append(verdict);
    const matches=r=>(mode.value==="All execution modes"||r.execution_mode===mode.value)&&(verdict.value==="All functional verdicts"||r.functional===verdict.value);
    const list=el("div"); rows.append(list);
    const draw = () => {
      list.replaceChildren();
      comparison.rows.filter(r=>(select.value === "All scenarios" || r.scenario_id === select.value)&&((mode.value === "All execution modes" && verdict.value === "All functional verdicts")||[...r.baseline_runs,...r.candidate_runs].some(id=>data.runs.some(run=>run.run_id===id&&matches(run))))).forEach(row => {
        const card=el("article",undefined,"comparison-card");
        add(card,el("h3",row.scenario_id),badge(row.comparability),el("p",row.reason,"muted"));
        const arms=el("div",undefined,"arms");
        ["baseline","candidate"].forEach(arm => {
          const box=el("div",undefined,"arm"); add(box,el("p",arm.toUpperCase(),"eyebrow"),el("strong",String(row[arm+"_critical_failures"])+" critical check failures","big"));
          const stats=row[arm+"_summary"]; add(box,el("p",stats.completed+" / "+stats.attempts+" attempts completed · "+stats.functional_passes+" functional passes"),el("p",stats.known_observed_usd === null ? "Observed cost unavailable" : "$"+stats.known_observed_usd+" observed · "+(stats.cost_complete?"complete":"incomplete")));
          row[arm+"_runs"].forEach(id => { const r=data.runs.find(r=>r.run_id===id); if (r && matches(r)) add(box,link(r.candidate_id+" · "+r.functional+" · inspect every attempt ↗", "runs/"+id+"/index.html"),el("p",r.evidence_origin+" / "+r.execution_mode,"muted")); }); arms.append(box);
        }); card.append(arms); card.append(detail("Timing distributions and observed deltas",row.timing)); list.append(card);
      });
    }; [select,mode,verdict].forEach(s=>s.addEventListener("change",draw)); draw();
    const configuration=section("Configuration and attribution"); configuration.append(detail("Declared configuration snapshots",comparison.extensions["bench:configurations"]));
    configuration.append(el("p",comparison.extensions["bench:attribution"]));configuration.append(detail("Observed configuration field changes",comparison.extensions["bench:configuration_changes"]||[]));
    return;
  }
  const {manifest,result,state,events}=data;
  const hero=el("section",undefined,"hero");
  const label=manifest.execution_mode === "reference" ? "scripted reference demonstration" : manifest.evidence_origin === "external_self_attested" ? "external self-attested evidence" : "private lab export · provenance limitations apply";
  const outcomes={completed:"The booking is complete.",partial:"Booked. Confirmation needs attention.",declined:"The caller declined the booking.",failed:"The requested booking was not completed.",unknown:"The business outcome is unknown."};
  add(hero,el("p",label.toUpperCase(),"eyebrow"),el("h1",outcomes[result.business_outcome]),el("p",manifest.scenario_id,"lede"),badge(result.dimensions.functional),el("p","Functional behavior · "+manifest.candidate_id,"muted")); app.prepend(hero);
  const overview=section("The outcome, in plain language");
  const grid=el("div",undefined,"stats");
  [["Bookings",state?state.bookings.length:"unknown"],["Create decisions",state?new Set(state.attempts.filter(a=>a.tool==="create_booking").map(a=>a.call_id+":"+a.operation_id)).size:"unknown"],["Local confirmations",state?state.confirmations.filter(c=>c.status==="recorded").length:"unknown"]].forEach(([key,value])=>{ const c=el("div",undefined,"stat");add(c,el("strong",String(value),"big"),el("span",key));grid.append(c); }); overview.append(grid);
  if(state) state.confirmations.forEach(c=>overview.append(el("p","Confirmation status: "+c.status+". Local record only; message delivery is unverified.")));
  result.blockers.forEach(t=>overview.append(el("p",t,"callout")));
  const dimensions=section("Separate questions. Separate verdicts."); const dims=el("div",undefined,"dimensions");
  Object.entries(result.dimensions).forEach(([key,value])=>{const row=el("div");add(row,el("span",key.replaceAll("_"," ")),badge(value));dims.append(row);});dimensions.append(dims);
  const checks=section("Independent outcome checks"); const checkFilter=el("select");checkFilter.setAttribute("aria-label","Filter check verdict");["All verdicts","pass","fail","unknown","not_applicable"].forEach(v=>{const o=el("option",v);o.value=v;checkFilter.append(o);});checks.append(checkFilter); const checkList=el("div");checks.append(checkList);const drawChecks=()=>{checkList.replaceChildren();result.checks.filter(c=>checkFilter.value==="All verdicts"||c.verdict===checkFilter.value).forEach(c=>{const row=el("article",undefined,"check"); add(row,badge(c.verdict),el("h3",c.check_id.replaceAll("_"," ")),el("p",c.reason)); checkList.append(row);});};checkFilter.addEventListener("change",drawChecks);drawChecks();
  const timeline=section("Conversation & tool timeline"); timeline.append(link("Complete event file ↓","events.jsonl"));
  let audio=null;
  if(data.audio_path){audio=el("audio");audio.controls=true;audio.preload="metadata";audio.src="conversation.wav";timeline.append(audio);if(!data.timeline_aligned)timeline.append(el("p","Shared-clock alignment is unverified; event seeking is disabled.","callout"));}
  else timeline.append(el("p","Audio unavailable — this evidence contains no playable recording.","callout"));
  (data.channel_audio||[]).forEach(item=>{const label=el("p","Verified derived "+item.channel+" channel");const player=el("audio");player.controls=true;player.preload="none";player.src=item.channel==="caller"?"caller.wav":"assistant.wav";add(timeline,label,player);});
  const filters=el("div",undefined,"filters"); const type=el("select"); type.setAttribute("aria-label","Filter event type");
  ["All events",...new Set(events.map(e=>e.type))].forEach(v=>{const o=el("option",v);o.value=v;type.append(o);});
  const disposition=el("select");disposition.setAttribute("aria-label","Filter attempt disposition");
  ["All dispositions",...new Set((state?.attempts||[]).map(a=>a.disposition))].forEach(v=>{const o=el("option",v);o.value=v;disposition.append(o);});
  const search=el("input");search.type="search";search.placeholder="Search transcript or operation";search.setAttribute("aria-label","Search events");add(filters,type,disposition,search);timeline.append(filters);
  const eventsBox=el("div",undefined,"events");timeline.append(eventsBox);const paging=el("div",undefined,"paging");timeline.append(paging);let page=0;let visible=[];
  const draw=()=>{
    const selectedOps=new Set((state?.attempts||[]).filter(a=>a.disposition===disposition.value).map(a=>a.operation_id));
    visible=events.filter(e=>(type.value==="All events"||e.type===type.value)&&(disposition.value==="All dispositions"||selectedOps.has(e.operation_id))&&JSON.stringify(e).toLowerCase().includes(search.value.toLowerCase()));
    const count=Math.max(1,Math.ceil(visible.length/500));page=Math.min(page,count-1);eventsBox.replaceChildren();paging.replaceChildren();
    visible.slice(page*500,(page+1)*500).forEach(e=>{
      const article=el("article",undefined,"event");article.dataset.offset=String(e.at_ms);const button=el("button",(e.at_ms/1000).toFixed(3)+"s · "+e.type);button.disabled=!audio || !data.timeline_aligned;
      button.addEventListener("click",()=>{audio.currentTime=e.payload.start_ms!==undefined?e.payload.start_ms/1000:e.at_ms/1000;});
      add(article,button,el("p",e.payload.text||e.payload.tool||e.event_id));article.append(detail("Event evidence · "+e.event_id,e));eventsBox.append(article);
    });
    const prev=el("button","← Previous");prev.disabled=page===0;prev.onclick=()=>{page--;draw();};const next=el("button","Next →");next.disabled=page>=count-1;next.onclick=()=>{page++;draw();};add(paging,prev,el("span",visible.length+" events · page "+(page+1)+" / "+count),next);
  };
  [type,disposition].forEach(s=>s.addEventListener("change",()=>{page=0;draw();}));search.addEventListener("input",()=>{page=0;draw();});draw();
  if(audio) audio.addEventListener("timeupdate",()=>{const ms=audio.currentTime*1000;const rows=[...eventsBox.children];let selected=null;rows.forEach(r=>{r.classList.remove("current");if(Number(r.dataset.offset)<=ms)selected=r;});if(selected)selected.classList.add("current");});
  const audit=section("Every attempt, including prevented actions");audit.append(detail("Immutable independent attempt audit",state?.attempts||[],result.dimensions.functional==="fail"));
  audit.append(detail("Independent state snapshot",state));const identity=section("Identity & methods");identity.append(detail("Manifest and configuration identities",manifest));identity.append(detail("Configuration snapshot and source provenance",data.configuration));identity.append(detail("Measurements, unknowns and method versions",result.metrics));
})();
