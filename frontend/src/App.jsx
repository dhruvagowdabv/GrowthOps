import { useEffect, useMemo, useState } from "react";
import {
  Activity, ArrowDownRight, ArrowUpRight, BarChart3, Bell, Check, ChevronDown,
  CircleHelp, Clock3, Database, Download, FileSpreadsheet, Filter, GitBranch,
  LayoutDashboard, Lightbulb, LoaderCircle, Menu, Network, Plus, Search,
  Settings2, ShieldCheck, Sparkles, Table2, UploadCloud, X, AlertTriangle
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getOverview, getRelationships } from "./api/analytics.js";
import { getProfile, getUploadAnalytics, getValidation, ingestUpload, uploadCsv } from "./api/uploads.js";

const nav = [
  { label: "Overview", icon: LayoutDashboard },
  { label: "Analytics", icon: BarChart3 },
  { label: "Insights", icon: Lightbulb },
  { label: "Recommendations", icon: Sparkles },
  { label: "Data Quality", icon: ShieldCheck },
  { label: "Schema", icon: Table2 },
  { label: "Relationships", icon: Network },
];
const colors = ["#6658e8", "#39b8a4", "#f2ad55", "#ed7c92", "#4f9ee8"];
const number = (value) => value == null ? "—" : Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
const percent = (value) => value == null ? "—" : `${Number(value).toFixed(1)}%`;
const friendly = (error) => error?.message || "Something went wrong. Please try again.";

function IconButton({ children, label, onClick, className = "" }) {
  return <button type="button" className={`icon-button ${className}`} aria-label={label} onClick={onClick}>{children}</button>;
}
function StatCard({ title, value, caption, icon: Icon, tone = "violet" }) {
  return <div className="stat-card"><div className="stat-top"><span>{title}</span><span className={`stat-icon ${tone}`}><Icon size={18}/></span></div><div className="stat-value">{value}</div><div className="stat-caption">{caption}</div></div>;
}
function Panel({ title, subtitle, action, children, className = "" }) {
  return <section className={`panel ${className}`}><div className="panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>{children}</section>;
}
function EmptyState({ icon: Icon = Database, title, text, action }) {
  return <div className="empty-state"><span className="empty-icon"><Icon size={24}/></span><h3>{title}</h3><p>{text}</p>{action}</div>;
}
function Loading({ text = "Loading your workspace…" }) {
  return <div className="loading-state"><LoaderCircle className="spin" size={22}/><span>{text}</span></div>;
}
function DataTable({ columns, rows, empty = "Nothing to show yet." }) {
  if (!rows?.length) return <div className="table-empty">{empty}</div>;
  return <div className="table-responsive"><table className="table align-middle mb-0"><thead><tr>{columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr></thead><tbody>{rows.map((row, i) => <tr key={row.id || row.name || i}>{columns.map((c) => <td key={c.key}>{c.render ? c.render(row[c.key], row) : String(row[c.key] ?? "—")}</td>)}</tr>)}</tbody></table></div>;
}

export default function App() {
  const [page, setPage] = useState("Overview");
  const [overview, setOverview] = useState(null);
  const [selectedId, setSelectedId] = useState("");
  const [analytics, setAnalytics] = useState(null);
  const [relationships, setRelationships] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [mobileNav, setMobileNav] = useState(false);
  const [search, setSearch] = useState("");
  const [recentProfile, setRecentProfile] = useState(null);
  const [validation, setValidation] = useState(null);
  const [ingestion, setIngestion] = useState(null);

  async function loadOverview(preferredId = "") {
    setLoading(true); setError("");
    try {
      const data = await getOverview();
      setOverview(data);
      const datasets = data.datasets || [];
      const nextId = preferredId || selectedId || datasets[0]?.upload_id || "";
      setSelectedId(nextId);
      if (nextId) await loadDataset(nextId, false);
      else { setAnalytics(null); setLoading(false); }
    } catch (e) { setError(friendly(e)); setLoading(false); }
  }
  async function loadDataset(id, showLoader = true) {
    if (!id) { setAnalytics(null); return; }
    if (showLoader) setDetailLoading(true);
    try {
      const [detail, rel] = await Promise.all([
        getOverview(id),
        getRelationships([id]).catch(() => null),
      ]);
      setAnalytics(detail.analytics || null);
      setRelationships(rel);
      setSelectedId(id);
    } catch (e) { setError(friendly(e)); }
    finally { setDetailLoading(false); setLoading(false); }
  }
  useEffect(() => { loadOverview(); }, []);

  const datasets = overview?.datasets || [];
  const activeDataset = datasets.find((d) => d.upload_id === selectedId);
  const summary = analytics?.summary || activeDataset?.summary || {};
  const quality = analytics?.quality || {};
  const schemaColumns = analytics?.schema?.columns || [];
  const numeric = analytics?.numeric || {};
  const distributions = analytics?.distributions || {};
  const trends = analytics?.trends || {};
  const correlations = analytics?.correlations || [];
  const insights = analytics?.insights || [];
  const recommendations = analytics?.recommendations || [];
  const candidateKeys = analytics?.candidate_keys || [];
  const filteredDatasets = datasets.filter((d) => (d.filename || "").toLowerCase().includes(search.toLowerCase()));

  async function handleUpload(file) {
    if (!file) return;
    setUploadError("");
    if (!file.name.toLowerCase().endsWith(".csv")) { setUploadError("Please choose a CSV file."); return; }
    setUploading(true); setProgress(0); setPage("Upload");
    try {
      const uploaded = await uploadCsv(file, setProgress);
      setProgress(100);
      const id = uploaded.upload_id;
      const [profile, valid] = await Promise.all([getProfile(id), getValidation(id)]);
      setRecentProfile(profile); setValidation(valid.validation || null);
      if (valid.validation?.status !== "error") {
        try { setIngestion(await ingestUpload(id)); } catch { /* Analytics remains available even if ingestion is not needed. */ }
      }
      const detail = await getOverview(id);
      setOverview((old) => ({ ...(old || {}), datasets: [detail, ...((old?.datasets || []).filter((d) => d.upload_id !== id))] }));
      setSelectedId(id);
      await loadDataset(id);
      setPage("Overview");
    } catch (e) { setUploadError(friendly(e)); }
    finally { setUploading(false); }
  }

  const numericChart = useMemo(() => Object.entries(numeric).slice(0, 8).map(([name, stats]) => ({
    name, mean: stats.mean ?? 0, min: stats.min ?? 0, max: stats.max ?? 0,
  })), [analytics]);
  const categoryChart = useMemo(() => {
    const first = Object.entries(distributions).find(([, values]) => values?.length);
    return first ? { name: first[0], values: first[1].slice(0, 6) } : null;
  }, [analytics]);
  const trendChart = useMemo(() => {
    const first = Object.entries(trends).find(([, values]) => values?.length);
    return first ? { name: first[0], values: first[1].slice(-24) } : null;
  }, [analytics]);

  const navTo = (label) => { setPage(label); setMobileNav(false); };
  const datasetSelector = <div className="dataset-select-wrap"><Database size={16}/><select aria-label="Select dataset" value={selectedId} onChange={(e) => loadDataset(e.target.value)} disabled={!datasets.length}><option value="">Select dataset</option>{datasets.map((d) => <option key={d.upload_id} value={d.upload_id}>{d.filename}</option>)}</select><ChevronDown size={15}/></div>;

  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
      <div className="brand"><span className="brand-mark"><Activity size={21}/></span><span>growth<span className="brand-accent">ops</span><small>DATA WORKSPACE</small></span><IconButton label="Close menu" className="mobile-close" onClick={() => setMobileNav(false)}><X size={18}/></IconButton></div>
      <div className="workspace-label">WORKSPACE</div>
      <nav className="main-nav">{nav.map(({ label, icon: Icon }) => <button key={label} className={`nav-link ${page === label ? "active" : ""}`} onClick={() => navTo(label)}><Icon size={18}/><span>{label}</span>{label === "Data Quality" && quality.score != null && <span className="nav-count">{Math.round(quality.score * 100)}</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="help-card"><span className="help-icon"><CircleHelp size={18}/></span><strong>Need a hand?</strong><p>Explore your data with confidence.</p><button onClick={() => navTo("Recommendations")}>Explore tips <span>↗</span></button></div><button className="nav-link settings-link" onClick={() => setError("Workspace settings are not available in the current API.")}><Settings2 size={18}/><span>Settings</span></button><div className="profile-row"><div className="avatar">G</div><div><strong>GrowthOps user</strong><small>Personal workspace</small></div><ChevronDown size={16}/></div></div>
    </aside>
    {mobileNav && <button className="mobile-backdrop" aria-label="Close navigation" onClick={() => setMobileNav(false)}/>}
    <main className="main-area">
      <header className="topbar"><div className="topbar-left"><IconButton label="Open navigation" className="menu-toggle" onClick={() => setMobileNav(true)}><Menu size={20}/></IconButton><div className="breadcrumb">Workspace <span>/</span> <strong>{page}</strong></div></div><div className="topbar-actions">{datasetSelector}<span className="topbar-divider"/><IconButton label="Notifications" onClick={() => setError("You’re all caught up — notifications are not connected yet.")}><Bell size={18}/></IconButton><div className="avatar top-avatar">G</div></div></header>
      <div className="page-content">
        {error && <div className="alert alert-warning d-flex align-items-center justify-content-between gap-3"><span><AlertTriangle size={17} className="me-2"/>{error}</span><button className="btn-close" onClick={() => setError("")} aria-label="Dismiss"/></div>}
        <div className="page-title-row"><div><div className="eyebrow"><span className="eyebrow-dot"/>{page === "Overview" ? "YOUR DATA AT A GLANCE" : "GROWTHOPS WORKSPACE"}</div><h1>{page === "Overview" ? "Good to see you again." : page}</h1><p className="page-subtitle">{page === "Overview" ? "Here’s what’s happening across your datasets today." : page === "Upload" ? "Bring in a CSV and let’s get to know your data." : `Explore ${page.toLowerCase()} from your selected dataset.`}</p></div><div className="title-actions"><button className="btn btn-soft" onClick={() => loadOverview(selectedId)}><Activity size={16}/> Refresh</button><button className="btn btn-primary-custom" onClick={() => navTo("Upload")}><Plus size={17}/> Add dataset</button></div></div>

        {page === "Upload" && <div className="upload-layout">
          <Panel title="Upload a dataset" subtitle="CSV files work best. Your original columns are preserved.">
            <label className={`drop-zone ${uploading ? "drop-zone-busy" : ""}`} htmlFor="csv-file">
              <span className="upload-icon"><UploadCloud size={26}/></span><strong>{uploading ? "Uploading your dataset…" : "Drop your CSV here"}</strong><span>or <u>browse files</u> from your computer</span><small>CSV format · File size limits are enforced by the API</small>
              <input id="csv-file" type="file" accept=".csv,text/csv" disabled={uploading} onChange={(e) => { handleUpload(e.target.files?.[0]); e.target.value = ""; }}/>
            </label>
            {uploading && <div className="upload-progress"><div className="d-flex justify-content-between"><span>Uploading and profiling</span><strong>{progress}%</strong></div><div className="progress"><div className="progress-bar" style={{ width: `${progress}%` }}/></div><small>Preparing a profile and checking data quality…</small></div>}
            {uploadError && <div className="alert alert-danger mt-3 mb-0">{uploadError}</div>}
            {recentProfile && !uploading && <div className="upload-success"><Check size={18}/><div><strong>Dataset uploaded</strong><p>{recentProfile.filename || "Your CSV"} is ready to explore.</p></div></div>}
          </Panel>
          <Panel title="What happens next?" subtitle="A simple flow from raw data to useful signals."><div className="step-list">{[{n:"01",title:"Profile your columns",text:"Infer data types and understand completeness."},{n:"02",title:"Check data quality",text:"Review nulls, duplicates and validation results."},{n:"03",title:"Explore analytics",text:"See numeric summaries, distributions and trends when available."}].map(s=><div className="step-row" key={s.n}><span>{s.n}</span><div><strong>{s.title}</strong><p>{s.text}</p></div></div>)}</div></Panel>
          {validation && <Panel title="Validation result" subtitle="Based on the backend response."><div className="validation-result"><span className={`status-pill ${validation.status === "error" ? "status-danger" : "status-good"}`}>{validation.status || "checked"}</span><span>{validation.errors?.length ?? 0} errors · {validation.warnings?.length ?? 0} warnings</span></div><DataTable columns={[{key:"message",label:"Finding"},{key:"severity",label:"Severity"}]} rows={[...(validation.errors || []).map((x,i)=>({...x,id:"e"+i,severity:"Error"})),...(validation.warnings || []).map((x,i)=>({...x,id:"w"+i,severity:"Warning"}))]}/>{ingestion && <p className="muted-note mt-3 mb-0">Ingestion status: <strong>{ingestion.ingestion?.status || "complete"}</strong></p>}</Panel>}
        </div>}

        {page !== "Upload" && loading && <Loading/>}
        {page !== "Upload" && !loading && !datasets.length && <Panel title="Your workspace is ready" subtitle="Upload a CSV to start exploring your data."><EmptyState icon={FileSpreadsheet} title="No datasets yet" text="Start with any CSV. GrowthOps will infer its structure and show only the analytics it can calculate." action={<button className="btn btn-primary-custom" onClick={() => navTo("Upload")}><UploadCloud size={17}/> Upload your first dataset</button>}/></Panel>}
        {page !== "Upload" && !loading && datasets.length > 0 && detailLoading && <Loading text="Updating dataset insights…"/>}

        {page === "Overview" && !loading && !detailLoading && datasets.length > 0 && <>
          <div className="dataset-banner"><div className="dataset-file-icon"><FileSpreadsheet size={21}/></div><div className="dataset-banner-copy"><strong>{activeDataset?.filename || "Selected dataset"}</strong><span>Last added {activeDataset?.created_at ? new Date(activeDataset.created_at).toLocaleDateString() : "—"} · {activeDataset?.status || "Uploaded"}</span></div><span className="status-pill status-good"><span/> Ready to explore</span><button className="text-action" onClick={() => navTo("Schema")}>View schema <ArrowUpRight size={15}/></button></div>
          <div className="stats-grid"><StatCard title="Total rows" value={number(summary.row_count)} caption="Records in this dataset" icon={Table2}/><StatCard title="Columns" value={number(summary.column_count)} caption="Fields detected" icon={Database} tone="teal"/><StatCard title="Data completeness" value={percent(quality.completeness_percent)} caption={`${number(quality.null_cells)} empty cells found`} icon={ShieldCheck} tone="amber"/><StatCard title="Quality score" value={quality.score == null ? "—" : `${Math.round(quality.score * 100)}%`} caption="Completeness & duplicate-aware" icon={Sparkles} tone="pink"/></div>
          <div className="content-grid"><Panel title="Numeric overview" subtitle="Average values across inferred numeric measures" action={<span className="panel-chip">Mean by column</span>}>{numericChart.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height={245}><BarChart data={numericChart} margin={{top:10,right:8,left:-16,bottom:20}}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#edf0f6"/><XAxis dataKey="name" tick={{fontSize:11,fill:"#8992a7"}} axisLine={false} tickLine={false} angle={-15} textAnchor="end" interval={0}/><YAxis tick={{fontSize:11,fill:"#8992a7"}} axisLine={false} tickLine={false}/><Tooltip cursor={{fill:"#f6f5ff"}}/><Bar dataKey="mean" fill="#6c5ce7" radius={[5,5,0,0]} maxBarSize={34}/></BarChart></ResponsiveContainer></div> : <EmptyState icon={BarChart3} title="No numeric measures detected" text="If numeric columns are available, their summaries will appear here."/>}</Panel>
          <Panel title="Dataset composition" subtitle={categoryChart ? `Most common values in ${categoryChart.name}` : "Categorical distribution when available"} action={<span className="panel-chip">Top values</span>}>{categoryChart ? <div className="donut-layout"><div className="donut-chart"><ResponsiveContainer width="100%" height={210}><PieChart><Pie data={categoryChart.values} dataKey="count" nameKey="value" innerRadius={55} outerRadius={82} paddingAngle={3}>{categoryChart.values.map((v,i)=><Cell key={v.value} fill={colors[i%colors.length]}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer></div><div className="legend-list">{categoryChart.values.slice(0,5).map((v,i)=><div key={v.value}><span style={{background:colors[i%colors.length]}}/><span className="legend-name">{v.value}</span><strong>{number(v.count)}</strong></div>)}</div></div>:<EmptyState icon={BarChart3} title="No distributions yet" text="A distribution appears when the API identifies categorical columns with observed values."/>}</Panel></div>
          <div className="content-grid lower-grid"><Panel title="Record trend" subtitle={trendChart ? `Frequency over time · ${trendChart.name}` : "Date-based record frequency"}>{trendChart ? <div className="chart-wrap"><ResponsiveContainer width="100%" height={205}><LineChart data={trendChart.values} margin={{top:10,right:10,left:-18,bottom:0}}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#edf0f6"/><XAxis dataKey="date" tick={{fontSize:10,fill:"#8992a7"}} axisLine={false} tickLine={false}/><YAxis tick={{fontSize:11,fill:"#8992a7"}} axisLine={false} tickLine={false}/><Tooltip/><Line type="monotone" dataKey="count" stroke="#35b6a2" strokeWidth={2.5} dot={false}/></LineChart></ResponsiveContainer></div>:<EmptyState icon={Activity} title="No time series available" text="A trend will appear when a date-like column and observations are detected."/>}</Panel>
          <Panel title="Latest insights" subtitle="Observations generated from calculated metrics" action={<button className="panel-link" onClick={()=>navTo("Insights")}>View all <ArrowUpRight size={14}/></button>}>{insights.length ? <div className="insight-list">{insights.slice(0,3).map((it,i)=><div className="insight-row" key={i}><span className={`insight-symbol ${it.severity === "warning" ? "warning" : ""}`}>{it.severity === "warning" ? <AlertTriangle size={16}/> : <Lightbulb size={16}/>}</span><div><strong>{it.message}</strong><small>{it.type || "Observation"} · {it.severity || "info"}</small></div></div>)}</div>:<EmptyState icon={Lightbulb} title="No insights generated" text="Insights will show up when the API finds meaningful patterns."/>}</Panel></div>
          <Panel title="Your datasets" subtitle="Recently added files in this workspace" action={<button className="panel-link" onClick={()=>navTo("Upload")}><Plus size={15}/> Add dataset</button>}><div className="dataset-search"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search datasets…"/></div><DataTable columns={[{key:"filename",label:"Dataset",render:(v,row)=><button className="dataset-name-button" onClick={()=>loadDataset(row.upload_id)}><span className="mini-file"><FileSpreadsheet size={16}/></span><span>{v}</span></button>},{key:"summary",label:"Rows",render:(v)=>number(v?.row_count)},{key:"dataset_type",label:"Detected type",render:(v)=>v || "Generic dataset"},{key:"status",label:"Status",render:(v)=><span className="status-pill status-good">{v || "uploaded"}</span>},{key:"upload_id",label:"",render:(v)=><button className="panel-link" onClick={()=>loadDataset(v)}>Open <ArrowUpRight size={14}/></button>}] } rows={filteredDatasets}/></Panel>
        </>}

        {page === "Analytics" && !loading && !detailLoading && datasets.length > 0 && <><div className="stats-grid"><StatCard title="Numeric measures" value={number(summary.numeric_columns)} caption="Columns inferred as measures" icon={BarChart3}/><StatCard title="Categorical fields" value={number(summary.categorical_columns)} caption="Categories and flags" icon={Filter} tone="teal"/><StatCard title="Date fields" value={number(summary.datetime_columns)} caption="Datetime columns detected" icon={Clock3} tone="amber"/><StatCard title="Potential keys" value={number(summary.candidate_key_count)} caption="Candidates, not guaranteed unique IDs" icon={GitBranch} tone="pink"/></div><div className="content-grid"><Panel title="Numeric summaries" subtitle="Calculated statistics for inferred numeric measures"><DataTable columns={[{key:"name",label:"Column"},{key:"count",label:"Count",render:number},{key:"mean",label:"Mean",render:number},{key:"median",label:"Median",render:number},{key:"min",label:"Min",render:number},{key:"max",label:"Max",render:number},{key:"stddev",label:"Std. dev.",render:number}]} rows={Object.entries(numeric).map(([name,s])=>({name,...s}))}/></Panel><Panel title="Correlations" subtitle="Measured linear relationships between numeric columns"><DataTable columns={[{key:"left",label:"Column A"},{key:"right",label:"Column B"},{key:"coefficient",label:"Pearson r",render:(v)=><strong>{number(v)}</strong>},{key:"coefficient",label:"Strength",render:(v)=><span className="panel-chip">{Math.abs(v)>=.8?"Strong":Math.abs(v)>=.5?"Moderate":"Weak"}</span>}]} rows={correlations}/></Panel></div><Panel title="Distributions" subtitle="Observed value frequencies"><DataTable columns={[{key:"name",label:"Column"},{key:"value",label:"Value"},{key:"count",label:"Count",render:number}]} rows={Object.entries(distributions).flatMap(([name,values])=>values.map(v=>({name,...v,id:name+v.value})))}/></Panel></>}

        {page === "Insights" && !loading && !detailLoading && datasets.length > 0 && <Panel title="Insights from your data" subtitle="Only observations returned by the analytics engine are shown.">{insights.length ? <div className="insights-grid">{insights.map((it,i)=><article className="insight-card" key={i}><div className="insight-card-top"><span className={`insight-symbol ${it.severity==="warning"?"warning":""}`}>{it.severity==="warning"?<AlertTriangle size={17}/>:<Lightbulb size={17}/>}</span><span className="panel-chip">{it.type || "Insight"}</span></div><h3>{it.message}</h3><p>Severity: {it.severity || "info"}</p>{it.evidence && <details><summary>View supporting evidence</summary><pre>{JSON.stringify(it.evidence,null,2)}</pre></details>}</article>)}</div>:<EmptyState icon={Lightbulb} title="No insights available" text="The analytics engine hasn't returned any observations for this dataset yet."/>}</Panel>}

        {page === "Recommendations" && !loading && !detailLoading && datasets.length > 0 && <Panel title="Suggested analyses" subtitle="Ideas based on detected column semantics and computed analytics. These are suggestions, not claims.">{recommendations.length ? <div className="recommendations-grid">{recommendations.map((r,i)=><article className="recommendation-card" key={i}><div className="recommendation-top"><span className="recommendation-icon"><Sparkles size={17}/></span><span className="panel-chip">{r.type || "Analysis"}</span><span className="priority">Priority {r.priority ?? "—"}</span></div><h3>{r.title}</h3><p>{r.reason}</p><div className="recommendation-tags">{(r.columns || []).map(c=><span key={c}>{c}</span>)}</div></article>)}</div>:<EmptyState icon={Sparkles} title="No recommendations yet" text="Suggestions appear when there are suitable measures, dimensions, or date fields."/>}</Panel>}

        {page === "Data Quality" && !loading && !detailLoading && datasets.length > 0 && <><div className="stats-grid"><StatCard title="Completeness" value={percent(quality.completeness_percent)} caption="Share of non-empty cells" icon={ShieldCheck}/><StatCard title="Null cells" value={number(quality.null_cells)} caption="Empty values across dataset" icon={AlertTriangle} tone="amber"/><StatCard title="Columns with nulls" value={number(quality.columns_with_nulls)} caption="Columns needing a closer look" icon={Database} tone="teal"/><StatCard title="Duplicate rows" value={number(quality.duplicate_rows)} caption={percent(quality.duplicate_row_percent)} icon={Table2} tone="pink"/></div><Panel title="Column-level quality" subtitle="Null counts and uniqueness are based on the selected dataset"><DataTable columns={[{key:"name",label:"Column"},{key:"inferred_type",label:"Inferred type"},{key:"null_count",label:"Null count",render:number},{key:"unique_ratio",label:"Unique ratio",render:(v)=>v==null?"—":percent(v*100)},{key:"semantic",label:"Role",render:(v)=>v?.role || "—"},{key:"semantic",label:"Confidence",render:(v)=>v?.confidence==null?"—":percent(v.confidence*100)}]} rows={schemaColumns.map(c=>({...c,unique_ratio:c.semantic?.unique_ratio}))}/></Panel></>}

        {page === "Schema" && !loading && !detailLoading && datasets.length > 0 && <><div className="stats-grid"><StatCard title="Total columns" value={number(summary.column_count)} caption="Inferred from the CSV header" icon={Table2}/><StatCard title="Numeric" value={number(summary.numeric_columns)} caption="Integer and number measures" icon={BarChart3} tone="teal"/><StatCard title="Categorical" value={number(summary.categorical_columns)} caption="Categories and flags" icon={Filter} tone="amber"/><StatCard title="Potential keys" value={number(candidateKeys.length)} caption="Candidates only; verify before use" icon={GitBranch} tone="pink"/></div><Panel title="Detected schema" subtitle="Column names, inferred types and semantic roles"><DataTable columns={[{key:"name",label:"Column name",render:(v)=><strong>{v}</strong>},{key:"inferred_type",label:"Inferred type",render:(v)=><span className="type-pill">{v || "unknown"}</span>},{key:"semantic",label:"Role",render:(v)=>v?.role || "—"},{key:"null_count",label:"Null count",render:number},{key:"semantic",label:"Unique ratio",render:(v)=>v?.unique_ratio==null?"—":percent(v.unique_ratio*100)},{key:"semantic",label:"Confidence",render:(v)=>v?.confidence==null?"—":percent(v.confidence*100)}]} rows={schemaColumns}/></Panel><Panel title="Potential key columns" subtitle="These columns are candidates, not guaranteed primary keys"><DataTable columns={[{key:"name",label:"Column"},{key:"role",label:"Inferred role"},{key:"unique_ratio",label:"Unique ratio",render:(v)=>percent((v||0)*100)},{key:"confidence",label:"Confidence",render:(v)=>percent((v||0)*100)},{key:"reason",label:"Reason",render:(v)=>String(v||"").replaceAll("_"," ")}]} rows={candidateKeys}/></Panel></>}

        {page === "Relationships" && !loading && !detailLoading && datasets.length > 0 && <Panel title="Dataset relationships" subtitle="Potential links detected across selected datasets">{relationships?.relationships?.length ? <DataTable columns={[{key:"left",label:"Dataset / field"},{key:"right",label:"Related dataset / field"},{key:"type",label:"Relationship"},{key:"confidence",label:"Confidence",render:(v)=>v==null?"—":percent(v*100)}]} rows={relationships.relationships.map((r,i)=>({...r,id:i,left:r.left || r.source || r.from || "—",right:r.right || r.target || r.to || "—"}))}/>:<EmptyState icon={Network} title="No relationships returned" text="The API did not return any likely links for this selection. Add more datasets to explore cross-dataset relationships." action={<button className="btn btn-soft" onClick={()=>navTo("Upload")}><Plus size={16}/> Add another dataset</button>}/>}</Panel>}

        <footer className="page-footer"><span>GrowthOps <span className="footer-dot">·</span> Understand your data, faster.</span><span><span className="api-indicator"/>{import.meta.env.VITE_API_BASE_URL || "API: localhost:8000"}</span></footer>
      </div>
    </main>
  </div>;
}
