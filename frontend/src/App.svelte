<script>
  import PressureView from './PressureView.svelte'

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
  let pressureId = null
  let error = ''

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
    await load()
  }

  async function load() {
    rows = await api('/api/batches')
    pressures = await api('/api/pressures')
  }

  async function save() {
    error = ''
    if (!pressureId) {
      error = '请先选择一条未使用的蒸汽压力记录'
      return
    }
    try {
      await api('/api/batches', {
        method: 'POST',
        body: JSON.stringify({
          herb,
          pressure_id: pressureId,
          steps: [{ name: '清炒', temp_c: Number(tempC), minutes: Number(minutes) }],
        }),
      })
      pressureId = null
      await load()
    } catch (err) {
      error = err.message
    }
  }

  function show(next) {
    view = next
    if (next === 'batches') load()
  }

  function leave() {
    localStorage.clear()
    token = ''
    role = ''
  }

  if (token) load()
</script>

<main>
  <h1>饮片炮制记录台</h1>
  {#if !token}
    <p>炮制记录整包保存。清炒温度须在 80 到 150，时长须在 5 到 30 分钟。写入清炒必须挂靠一条未使用的蒸汽压力记录。</p>
    <input bind:value={username} />
    <input type="password" bind:value={password} />
    <button on:click={enter}>登录</button>
    <p>processor / herb123456 可写；checker / check123456 只读</p>
  {:else}
    <nav>
      <a href="/" class:active={view === 'batches'} on:click|preventDefault={() => show('batches')}>记录总表</a>
      <a href="/" class:active={view === 'pressure'} on:click|preventDefault={() => show('pressure')}>蒸汽压力</a>
      <button on:click={leave}>退出</button>
    </nav>
    {#if view === 'pressure'}
      <PressureView {token} {role} />
    {:else}
      {#if role === 'writer'}
        <div class="row">
          <input bind:value={herb} placeholder="饮片" />
          <input type="number" bind:value={tempC} />
          <input type="number" bind:value={minutes} />
          <select bind:value={pressureId}>
            <option value={null}>选择未使用的压力记录</option>
            {#each pressures.filter((p) => !p.used_by_batch_id) as p}
              <option value={p.id}>锅次 {p.pot_no} · {p.pressure_text}</option>
            {/each}
          </select>
          <button on:click={save}>写入清炒记录</button>
        </div>
        {#if pressures.every((p) => p.used_by_batch_id)}
          <p class="muted">暂无未使用的压力记录，请先到「蒸汽压力」页登记。</p>
        {/if}
        {#if error}<p class="err">{error}</p>{/if}
      {/if}
      <ul>
        {#each rows as row}
          <li>
            {row.herb} · {row.verdict} · {row.reason} · 温度 {row.doc.steps[0].temp_c}
            {#if row.doc.pressure}
              · 压力 {row.doc.pressure.text}（锅次 {row.doc.pressure.pot_no}）
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</main>

<style>
  main { font-family: sans-serif; max-width: 720px; margin: 24px auto; color: #3f2f1f; }
  h1 { color: #7c2d12; }
  input, select { margin-right: 8px; padding: 6px; }
  nav { display: flex; gap: 16px; align-items: center; border-bottom: 1px solid #d6c9b8; padding-bottom: 10px; margin-bottom: 16px; }
  nav a { color: #7c2d12; text-decoration: none; }
  nav a.active { font-weight: bold; border-bottom: 2px solid #7c2d12; }
  nav button { margin-left: auto; }
  .row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  .err { color: #b91c1c; }
  .muted { color: #78716c; }
</style>
