"use strict";
const $ = id => document.getElementById(id);
const nf = new Intl.NumberFormat("en-US");
const money = v => v == null ? "—" : new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(v/100);
const number = v => nf.format(v);
const pct = v => v == null ? "—" : number(v)+"%";
const node = (tag, value, cls) => {
  const n = document.createElement(tag);
  if(value != null) n.textContent = value;
  if(cls) n.className = cls;
  return n;
};
const replace = (id, children) => $(id).replaceChildren(...children);
async function get(path) {
  const res = await fetch(path, {headers:{Accept:"application/json"},cache:"no-store"});
  if(!res.ok) throw new Error("Request failed ("+res.status+")");
  return res.json();
}
function table(id, rows) {
  replace(id, rows.length ? rows.map(r => {
    const tr=node("tr");
    r.forEach(v => tr.append(node("td",v)));
    return tr;
  }) : [(() => {
    const tr=node("tr"),td=node("td","No matching data","empty");
    td.colSpan=$(id).closest("table").querySelectorAll("th").length;
    tr.append(td);return tr;
  })()]);
}
function choices(id, values, all) {
  const previous=$(id).value;
  replace(id,[new Option(all,""),...values.map(v=>new Option(v,v))]);
  $(id).value=values.includes(previous)?previous:"";
}
function cards(s) {
  const data=[
    ["Net revenue",money(s.net_cents),"Gross less discounts"],
    ["Gross revenue",money(s.gross_cents),"Before discounts"],
    ["Units sold",number(s.units),"Quantity, not transactions"],
    ["Sale lines",number(s.sales),"One fact per source sale"],
    ["Customers",number(s.customers),"Distinct customer IDs"],
    ["Repeat customers",number(s.repeat_customers),"Two or more sale lines"],
    ["Discount rate",pct(s.discount_pct),"Discount / gross"],
    ["Average sale",money(s.avg_sale_cents),"Net revenue / sale lines"]
  ];
  replace("kpis",data.map(([label,value,detail])=>{
    const el=node("article",null,"kpi");
    el.append(node("label",label),node("strong",value),node("small",detail));
    return el;
  }));
}
function bars(id, rows, label) {
  const max=Math.max(1,...rows.map(r=>r.net_cents));
  replace(id,rows.length?rows.map(r=>{
    const div=node("div"), caption=node("div",null,"bar-label"), track=node("div",null,"bar-track"), fill=node("div",null,"bar-fill");
    caption.append(node("span",label(r)),node("strong",money(r.net_cents)));
    fill.style.width=(100*r.net_cents/max)+"%";track.append(fill);div.append(caption,track);return div;
  }):[node("p","No matching data","empty")]);
}
function trend(months) {
  const max=Math.max(1,...months.map(m=>m.net_cents));
  replace("trend",months.length?months.map(m=>{
    const col=node("div",null,"trend-col"), plot=node("div",null,"trend-plot"), bar=node("div",null,"trend-bar");
    bar.style.height=(100*m.net_cents/max)+"%";
    bar.title=m.month+": "+money(m.net_cents);
    plot.append(bar);
    col.append(plot,node("div",m.month,"trend-label"));return col;
  }):[node("p","No matching data","empty")]);
}
async function render() {
  const request=++render.seq, q=new URLSearchParams();
  for(const id of ["start","end","category","country"]) if($(id).value) q.set(id,$(id).value);
  $("apply").disabled=true;$("status").textContent="Loading…";$("status").className="";
  try {
    const d=await get("/api/report?"+q);
    if(request!==render.seq) return;
    cards(d.summary);trend(d.monthly);
    choices("category",d.options.categories,"All categories");
    choices("country",d.options.countries,"All countries");
    table("months",d.monthly.map(m=>[m.month,number(m.sales),number(m.units),money(m.net_cents),pct(m.yoy_pct)]));
    table("ranked",d.products.map(r=>[r.units_rank,r.product_type,number(r.units),money(r.net_cents)]));
    bars("categories",d.categories,r=>r.category);
    bars("regions",d.regions,r=>r.region+" · "+r.country);
    $("status").textContent=number(d.summary.sales)+" sale lines in current selection · USD · amounts rounded for display";
  }catch(err){
    if(request!==render.seq) return;
    $("status").textContent="Unable to refresh. "+err.message+". Displayed results may be from the previous selection.";
    $("status").className="error";
  }finally{if(request===render.seq)$("apply").disabled=false;}
}
render.seq=0;
async function operations() {
  try{
    await get("/health");$("health").textContent="Warehouse ready";$("health").className="pill good";
    const [q,r]=await Promise.all([get("/api/quality"),get("/api/runs")]);
    $("quality-status").textContent=q.passed?"All checks passed":"Check failures";
    $("quality-status").className="pill "+(q.passed?"good":"bad");
    if(!q.passed){$("health").textContent="Quality check failed";$("health").className="pill bad";}
    replace("checks",q.checks.map(c=>{
      const el=node("div",null,c.passed?"check":"check fail");
      el.append(node("span",c.name.replaceAll("_"," ")),node("span",c.passed?"PASS":c.failures+" failures"));return el;
    }));
    table("runs",r.map(a=>[a.started_at,a.status,number(a.rows_seen),number(a.rows_inserted),number(a.rows_skipped),a.error_code||"—"]));
  }catch(err){$("health").textContent="Ops unavailable";$("health").className="pill bad";$("quality-status").textContent="Unavailable";}
}
$("apply").addEventListener("click",render);
$("reset").addEventListener("click",()=>{for(const id of ["start","end","category","country"])$(id).value="";render();});
render();operations();
