"use strict";
const el = id => document.getElementById(id);
const put = (id, value) => { el(id).textContent = value; };
const num = n => Number(n).toFixed(3);
const percent = n => Number(n).toFixed(1) + "%";
const pretty = s => s.replaceAll("_", " ");
let report;
function svg(tag, attrs, text) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([k,v]) => node.setAttribute(k,v));
  if (text !== undefined) node.textContent = text;
  return node;
}
function draw() {
  const data = el("range").value === "all" ? report.holdout : report.holdout.slice(-Number(el("range").value));
  const chart=el("chart"); chart.replaceChildren();
  const narrow=chart.clientWidth<520;
  const width=narrow?Math.max(300,Math.round(chart.clientWidth)):820;
  const height=narrow?280:335;
  const left=narrow?43:55, right=width-(narrow?12:25), bottom=height-50;
  chart.setAttribute("viewBox", "0 0 "+width+" "+height);
  const lo=Math.min(...data.map(d=>Math.min(d.lower,d.actual,d.persistence,d.prediction)));
  const hi=Math.max(...data.map(d=>Math.max(d.upper,d.actual,d.persistence,d.prediction)));
  const spread=Math.max(hi-lo, .001);
  const x=i=>left+i*(right-left)/Math.max(data.length-1,1);
  const y=v=>bottom-(v-lo)*(bottom-40)/spread;
  for(let i=0;i<=5;i++){
    const v=lo+spread*i/5, yy=y(v);
    chart.append(svg("line",{x1:left,y1:yy,x2:right,y2:yy,class:"grid"}),svg("text",{x:left-7,y:yy+4,"text-anchor":"end",class:"axis"},v.toFixed(1)));
  }
  const pts=k=>data.map((d,i)=>[x(i),y(d[k])].join(","));
  chart.append(svg("polygon",{points:pts("upper").concat(pts("lower").reverse()).join(" "),class:"confidence"}));
  [["persistence","baseLine"],["prediction","predLine"],["actual","actualLine"]].forEach(([k,c])=>chart.append(svg("polyline",{points:pts(k).join(" "),class:c})));
  [0,Math.floor((data.length-1)/2),data.length-1].forEach(i=>chart.append(svg("text",{x:x(i),y:bottom+25,"text-anchor":i===0?"start":i===data.length-1?"end":"middle",class:"axis"},data[i].date)));
}
async function init(){
  const [rr,fr]=await Promise.all([fetch("/api/report"),fetch("/api/forecast")]);
  if(!rr.ok) throw Error("Report could not be loaded.");
  report=await rr.json();
  put("model",pretty(report.selected_model)); put("rmse",num(report.test.candidate.rmse));
  put("baseline","Persistence: "+num(report.test.persistence.rmse));
  put("coverage",percent(report.test.interval_coverage_pct));
  put("gate",report.gate.passed?"PASS":"BLOCKED"); el("gate").className=report.gate.passed?"ok":"fail";
  put("ticker",report.dataset.ticker+" (fictional)"); put("asof",report.dataset.last_date);
  put("samples",report.counts.holdout); put("hash",report.dataset.sha256.slice(0,16)+"…");
  if(fr.ok){const f=await fr.json();put("point",f.point.toFixed(2));put("interval","Empirical 90% band: "+f.lower.toFixed(2)+" – "+f.upper.toFixed(2));put("last",f.last_close.toFixed(2));}
  else {put("point","Withheld");put("interval","Holdout release gate blocked this candidate.");put("last",report.holdout.at(-1).actual.toFixed(2));}
  for(const [name,m] of Object.entries(report.validation)){
    const row=document.createElement("tr"); if(name===report.selected_model)row.className="selected";
    for(const val of [pretty(name),num(m.mae),num(m.rmse),percent(m.mape_pct),percent(m.directional_accuracy_pct),name===report.selected_model?"Champion":"Candidate"]){
      const td=document.createElement("td"); td.textContent=val;row.append(td);
    }el("models").append(row);
  }
  for(const [id,key] of [["train","first_train_target"],["val","first_validation_target"],["test","first_holdout_target"],["end","last_holdout_target"]])put(id,report.split[key]);
  put("release","Release checks: "+Object.entries(report.gate.checks).map(([k,v])=>k+" "+(v?"PASS":"FAIL")).join(" · ")+" · Tolerance "+percent(report.gate.tolerance*100));
  el("range").addEventListener("change",draw);window.addEventListener("resize",()=>requestAnimationFrame(draw));draw();
}
init().catch(err=>{el("error").hidden=false;put("error",err.message);});
