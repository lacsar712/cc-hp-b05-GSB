<script>
  export let token
  export let role

  let pressures = []
  let potNo = ''
  let pressureText = ''
  let readAt = ''
  let error = ''

  async function api(path, options = {}) {
    const res = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || '请求失败')
    return data
  }

  async function load() {
    pressures = await api('/api/pressures')
  }

  async function register() {
    error = ''
    try {
      await api('/api/pressures', {
        method: 'POST',
        body: JSON.stringify({
          pot_no: potNo,
          pressure_text: pressureText,
          read_at: readAt ? new Date(readAt).toISOString() : null,
        }),
      })
      potNo = ''
      pressureText = ''
      readAt = ''
      await load()
    } catch (err) {
      error = err.message
    }
  }

  function fmt(iso) {
    return new Date(iso).toLocaleString()
  }

  load()
</script>

<section>
  <h2>蒸汽压力台</h2>

  <h3>压力登记</h3>
  {#if role === 'writer'}
    <div class="row">
      <input bind:value={potNo} placeholder="锅次号，如 G-2026-001" />
      <input bind:value={pressureText} placeholder="压力读数原文，如 0.32 MPa" />
      <input type="datetime-local" bind:value={readAt} title="读取时刻，留空取当前时间" />
      <button on:click={register}>登记压力</button>
    </div>
    {#if error}<p class="err">{error}</p>{/if}
  {:else}
    <p class="muted">质检员可查看压力台，登记仅炮制员可操作。</p>
  {/if}

  <h3>未使用列表</h3>
  <ul>
    {#each pressures.filter((p) => !p.used_by_batch_id) as p}
      <li>锅次 {p.pot_no} · {p.pressure_text} · 读取于 {fmt(p.read_at)} · 登记人 {p.created_by}</li>
    {:else}
      <li class="muted">暂无未使用的压力记录</li>
    {/each}
  </ul>

  <h3>已挂靠文书一览</h3>
  <ul>
    {#each pressures.filter((p) => p.used_by_batch_id) as p}
      <li>
        锅次 {p.pot_no} · {p.pressure_text} · 读取于 {fmt(p.read_at)}
        → 文书 #{p.used_by_batch_id} · {p.linked_herb} · {p.linked_verdict}
      </li>
    {:else}
      <li class="muted">暂无已挂靠的压力记录</li>
    {/each}
  </ul>
</section>

<style>
  h2 { color: #7c2d12; }
  h3 { margin: 18px 0 8px; color: #9a3412; }
  .row { display: flex; flex-wrap: wrap; gap: 8px; }
  input { padding: 6px; }
  .err { color: #b91c1c; }
  .muted { color: #78716c; }
</style>
