<script>
  const nowLocal = () => {
    const d = new Date()
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
    return d.toISOString().slice(0, 16)
  }

  let username = 'processor'
  let password = 'herb123456'
  let token = localStorage.getItem('herb_token') || ''
  let role = localStorage.getItem('herb_role') || ''
  let view = 'batches'
  let rows = []
  let pressures = []
  let herb = '甘草'
  let tempC = 110
  let minutes = 10
  let pressureId = ''
  let error = ''
  let pressureError = ''
  let batchNo = ''
  let reading = ''
  let readAt = nowLocal()

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || '请求失败')
    return data
  }

  async function enter() {
    const data = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    token = data.access_token
    role = data.role
    localStorage.setItem('herb_token', token)
    localStorage.setItem('herb_role', role)
    await refresh()
  }

  async function loadBatches() {
    rows = await api('/api/batches')
  }

  async function loadPressures() {
    pressures = await api('/api/pressures')
  }

  async function refresh() {
    error = ''
    await Promise.all([loadBatches(), loadPressures()])
    if (!pressureId && unused[0]) pressureId = String(unused[0].id)
  }

  let unused = []
  let linked = []
  $: unused = pressures.filter((p) => p.used_by_batch_id == null)
  $: linked = pressures.filter((p) => p.used_by_batch_id != null)

  async function save() {
    error = ''
    if (!pressureId) {
      error = '请先在蒸汽压力台登记并选择一条未使用的压力记录'
      return
    }
    try {
      await api('/api/batches', {
        method: 'POST',
        body: JSON.stringify({
          herb,
          steps: [{ name: '清炒', temp_c: Number(tempC), minutes: Number(minutes) }],
          pressure_id: Number(pressureId),
        }),
      })
      pressureId = ''
      await refresh()
    } catch (err) {
      error = err.message
    }
  }

  async function registerPressure() {
    pressureError = ''
    try {
      await api('/api/pressures', {
        method: 'POST',
        body: JSON.stringify({
          batch_no: batchNo,
          reading,
          read_at: new Date(readAt).toISOString(),
        }),
      })
      batchNo = ''
      reading = ''
      readAt = nowLocal()
      await loadPressures()
    } catch (err) {
      pressureError = err.message
    }
  }

  function leave() {
    localStorage.clear()
    token = ''
    role = ''
  }

  if (token) refresh()
</script>

<main>
  <h1>饮片炮制记录台</h1>
  {#if !token}
    <p>炮制记录整包保存。清炒温度须在 80 到 150，时长须在 5 到 30 分钟。写清炒必须挂靠一条未使用的蒸汽压力记录。</p>
    <input bind:value={username} />
    <input type="password" bind:value={password} />
    <button on:click={enter}>登录</button>
    <p>processor / herb123456 可写；checker / check123456 只读</p>
  {:else}
    <nav class="topbar">
      <button class="navlink" class:active={view === 'batches'} on:click={() => (view = 'batches')}>炮制文书总表</button>
      <button class="navlink" class:active={view === 'pressures'} on:click={() => (view = 'pressures')}>蒸汽压力链</button>
      <span class="spacer"></span>
      <button on:click={leave}>退出</button>
    </nav>

    {#if view === 'pressures'}
      <section>
        <h2>蒸汽压力台</h2>
        <p>炮制员按锅次登记蒸汽压力读数与读取时刻；每条压力记录只能挂靠一条清炒文书。质检员可查看，不能登记。</p>

        {#if role === 'writer'}
          <h3>压力登记</h3>
          <div class="form-row">
            <input bind:value={batchNo} placeholder="锅次号" />
            <input bind:value={reading} placeholder="压力读数原文（如 0.25 MPa）" />
            <input type="datetime-local" bind:value={readAt} />
            <button on:click={registerPressure}>登记压力</button>
          </div>
          {#if pressureError}<p class="error">{pressureError}</p>{/if}
        {:else}
          <p class="hint">质检员只读：以下压力台账仅供查看。</p>
        {/if}

        <h3>未使用压力记录（{unused.length}）</h3>
        {#if unused.length === 0}
          <p class="hint">暂无未使用记录。</p>
        {:else}
          <table>
            <thead>
              <tr><th>编号</th><th>锅次</th><th>压力原文</th><th>读取时刻</th><th>登记人</th></tr>
            </thead>
            <tbody>
              {#each unused as p}
                <tr>
                  <td>{p.id}</td>
                  <td>{p.batch_no}</td>
                  <td>{p.reading}</td>
                  <td>{p.read_at}</td>
                  <td>{p.registered_by}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}

        <h3>已挂靠文书一览（{linked.length}）</h3>
        {#if linked.length === 0}
          <p class="hint">暂无已挂靠记录。</p>
        {:else}
          <table>
            <thead>
              <tr><th>压力编号</th><th>锅次</th><th>压力原文</th><th>读取时刻</th><th>挂靠文书</th></tr>
            </thead>
            <tbody>
              {#each linked as p}
                <tr>
                  <td>{p.id}</td>
                  <td>{p.batch_no}</td>
                  <td>{p.reading}</td>
                  <td>{p.read_at}</td>
                  <td>#{p.used_by_batch_id} {p.used_by_herb}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </section>
    {:else}
      <section>
        {#if role === 'writer'}
          <h3>写入清炒记录（须挂靠未使用压力）</h3>
          <div class="form-row">
            <input bind:value={herb} placeholder="饮片" />
            <input type="number" bind:value={tempC} title="温度 ℃" />
            <input type="number" bind:value={minutes} title="分钟" />
            <select bind:value={pressureId}>
              <option value="">选择未使用压力记录…</option>
              {#each unused as p}
                <option value={p.id}>#{p.id} 锅次{p.batch_no} · {p.reading} · {p.read_at}</option>
              {/each}
            </select>
            <button on:click={save}>写入清炒记录</button>
          </div>
          {#if unused.length === 0}<p class="hint">没有未使用压力记录，请先到「蒸汽压力链」登记。</p>{/if}
          {#if error}<p class="error">{error}</p>{/if}
        {/if}

        <h3>炮制文书总表</h3>
        <table>
          <thead>
            <tr><th>编号</th><th>饮片</th><th>结论</th><th>原因</th><th>温度</th><th>挂靠压力</th><th>登记人</th></tr>
          </thead>
          <tbody>
            {#each rows as row}
              <tr>
                <td>{row.id}</td>
                <td>{row.herb}</td>
                <td>{row.verdict}</td>
                <td>{row.reason}</td>
                <td>{row.doc.steps[0].temp_c}</td>
                <td>
                  {#if row.doc.pressure}
                    #{row.doc.pressure.pressure_id} {row.doc.pressure.batch_no} · {row.doc.pressure.reading}
                  {:else}
                    <span class="hint">（旧数据未挂靠）</span>
                  {/if}
                </td>
                <td>{row.created_by}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {/if}
  {/if}
</main>

<style>
  main { font-family: sans-serif; max-width: 960px; margin: 24px auto; color: #3f2f1f; }
  h1 { color: #7c2d12; }
  h2 { color: #7c2d12; }
  input, select { margin-right: 8px; padding: 6px; }
  .topbar { display: flex; align-items: center; gap: 16px; border-bottom: 2px solid #7c2d12; padding-bottom: 8px; margin-bottom: 16px; }
  .navlink { background: none; border: none; color: #7c2d12; font-weight: bold; font-size: 15px; cursor: pointer; padding: 0; }
  .navlink.active { text-decoration: underline; }
  .spacer { flex: 1; }
  .form-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 8px; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0 24px; }
  th, td { border: 1px solid #d6c3b0; padding: 6px 8px; text-align: left; font-size: 14px; }
  th { background: #f7ece2; }
  .error { color: #b91c1c; }
  .hint { color: #8a7460; }
</style>
