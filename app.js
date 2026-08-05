(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (value) => String(value ?? "—").replace(/[&<>"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]));
  let pool = []; let active = "all"; let selected = null; let sort = "score";
  const labels = {official:"正式池", candidate:"候选确认中", watch:"观察 / 待核验", removed:"已移除"};
  const classOf = (b) => b.status === "official" ? "high" : b.status === "removed" ? "low" : "mid";
  const statusOf = (b) => `<span class="status ${classOf(b)}">${labels[b.status] || "待核验"}</span>`;
  const fmt = (n, suffix="") => typeof n === "number" ? `${n.toFixed(2)}${suffix}` : "待核验";

  function updateCards(summary) {
    const cards = document.querySelectorAll(".cards article");
    const values = [summary.official, summary.candidate, summary.watch, summary.total];
    const captions = ["已连续3日确认", "满足条件，等待确认", "字段缺失或指标未达标", "扫描到的可转债"];
    cards.forEach((card, i) => { card.querySelector("strong").innerHTML = `${values[i] || 0}<small> 只</small>`; card.querySelector("p").textContent = captions[i]; });
  }
  function showDetail(b) {
    selected = b;
    const checks = [
      ["价格 112–125元", typeof b.price === "number" && b.price >=112 && b.price <=125],
      ["转股溢价率 ≤130%", typeof b.premium === "number" && b.premium <=130],
      ["连续确认", `${b.streak || 0}/3 个交易日`],
      ["60日有效波动", `${b.grid_days || 0}/20 天`],
    ];
    $("#detail").innerHTML = `<div class="detail-head"><div>${statusOf(b)}<h2>${esc(b.name)}</h2><small>${esc(b.code)} · ${esc(b.stock)}</small></div><div class="circle"><b>${b.status === "official" ? "✓" : b.streak || 0}</b><small>${b.status === "official" ? "已确认" : "确认天数"}</small></div></div>
      <span class="event">${esc((b.events || [])[0] || "无近期事件标签")}</span>
      <div class="metrics"><div><span>现价</span><b>${fmt(b.price,"元")}</b></div><div><span>转股溢价率</span><b>${fmt(b.premium,"%")}</b></div><div><span>评级</span><b>${esc(b.rating)}</b></div><div><span>税后到期收益</span><b>${fmt(b.ytm,"%")}</b></div></div>
      <div class="reason"><b>系统判断</b><p>${esc(b.reason)}</p></div>
      <div class="checks">${checks.map(([name, value]) => `<div class="check"><span>${name}</span><b class="${value === true ? "pass" : value === false ? "fail" : ""}">${value === true ? "通过" : value === false ? "未通过" : value}</b></div>`).join("")}</div>
      <div class="remove"><b>数据完整度</b><p>缺少评级、规模、期限、YTM 等关键字段时，系统不会自动进入正式池。</p></div>`;
  }
  function render() {
    const q = $("#search").value.trim().toLowerCase();
    const filtered = pool.filter((b) => (active === "all" || b.status === active) && (!q || `${b.name}${b.code}${b.stock}`.toLowerCase().includes(q)))
      .sort((a,b) => sort === "price" ? (b.price || -1) - (a.price || -1) : sort === "premium" ? (a.premium ?? 9999) - (b.premium ?? 9999) : (b.status === "official") - (a.status === "official"));
    $("#tbody").innerHTML = filtered.map((b) => `<tr data-code="${esc(b.code)}" class="${selected?.code === b.code ? "selected" : ""}"><td><div class="name"><b>${esc(b.name)}</b><span>${esc(b.code)}</span></div><span class="sub">${esc(b.stock)}</span></td><td class="price"><b>${fmt(b.price)}</b><span class="change">${fmt(b.change,"%")}</span></td><td>${fmt(b.premium,"%")}</td><td>${fmt(b.ytm,"%")}</td><td>${fmt(b.balance,"亿")}</td><td><b>${b.grid_days || 0}天</b><span class="sub">近60日</span></td><td><span class="score ${classOf(b)}">${b.streak || 0}</span></td><td>${statusOf(b)}</td></tr>`).join("");
    $("#empty").hidden = filtered.length > 0;
    document.querySelectorAll("#tbody tr").forEach((row) => row.onclick = () => { showDetail(pool.find((b) => b.code === row.dataset.code)); render(); });
    if (!selected && filtered[0]) showDetail(filtered[0]);
  }
  async function load() {
    const button = $(".update"); button.disabled = true; button.textContent = "↻　读取最新快照…";
    try {
      const result = await fetch(`data/latest.json?ts=${Date.now()}`, {cache:"no-store"});
      if (!result.ok) throw new Error("数据文件尚未生成");
      const data = await result.json(); pool = data.bonds || [];
      $(".date").textContent = data.generated_at ? `数据更新：${new Date(data.generated_at).toLocaleString("zh-CN", {hour12:false})}` : "尚未运行首次数据更新";
      $(".top p:last-child").textContent = `${data.source_status || "数据状态未知"} · ${data.source_note || ""}`;
      $(".health").innerHTML = `<i></i>${esc(data.source_status || "等待更新")}`;
      updateCards(data.summary || {}); render();
    } catch (error) {
      $(".top p:last-child").textContent = "数据尚未生成：请在项目根目录运行 python3 start_local.py。";
      $("#tbody").innerHTML = ""; $("#empty").hidden = false; $("#detail").innerHTML = "<p class='note'>正在等待首次公开数据更新。页面不会用演示数据代替真实结果。</p>";
    } finally { button.disabled = false; button.textContent = "↻　刷新数据"; }
  }
  function openManualUpdate() {
    const githubPages = location.hostname.endsWith(".github.io");
    const repo = location.pathname.split("/").filter(Boolean)[0];
    if (!githubPages || !repo) {
      alert("请在 GitHub 仓库的 Actions 页面运行“更新可转债策略池”。线上部署后，此按钮会自动打开对应工作流。");
      return;
    }
    const owner = location.hostname.replace(/\.github\.io$/, "");
    window.open(`https://github.com/${owner}/${repo}/actions/workflows/update-pool.yml`, "_blank", "noopener");
  }
  const tabs = $("#tabs");
  if (tabs.querySelectorAll("button").length < 5) tabs.insertAdjacentHTML("beforeend", "<button></button>");
  tabs.querySelectorAll("button").forEach((button, index) => {
    const states = ["all", "official", "candidate", "watch", "removed"];
    button.textContent = ["全部", "正式池", "候选确认中", "观察", "已移除"][index]; button.dataset.state = states[index];
    button.onclick = () => { active = button.dataset.state; document.querySelectorAll("#tabs button").forEach((x) => x.classList.remove("active")); button.classList.add("active"); render(); };
  });
  $("#search").oninput = render; $("#sort").onchange = (e) => { sort = e.target.value; render(); };
  $(".update").onclick = load;
  $(".run-update").onclick = openManualUpdate;
  load();
})();
