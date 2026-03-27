<script lang="ts">
  import { onMount } from 'svelte';

  const apiBase = (import.meta as any).env?.PUBLIC_API_BASE_URL ?? '/api';
  let username = 'demo';
  let password = 'demo1234';
  let accessToken = '';
  let refreshToken = '';
  let me: { id: number; username: string } | null = null;
  let screen: 'splash' | 'login' | 'home' = 'splash';

  let health: any = null;
  let error: string | null = null;
  let projectId: number | null = null;
  let files: Array<{ id: number; relative_path: string; kind: string; index_status: string }> = [];
  let selectedFile: { id: number; relative_path: string; content: string } | null = null;

  let uploadPath = '설정/인물/엘리온.txt';
  let uploadKind: 'settings' | 'manuscript' = 'settings';
  let uploadContent = '엘리온의 검 이름은 아르카디아다.';

  let ragQuery = '엘리온 검 이름';
  let ragResults: any = null;

  async function refreshAccess(): Promise<boolean> {
    if (!refreshToken) return false;
    const res = await fetch(`${apiBase}/auth/token/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: refreshToken })
    });
    if (!res.ok) return false;
    const data = await res.json();
    accessToken = data.access ?? '';
    return !!accessToken;
  }

  async function apiFetch(path: string, init: RequestInit = {}, retry = true) {
    const headers: Record<string, string> = {
      ...(init.headers as Record<string, string> | undefined)
    };
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
    const res = await fetch(`${apiBase}${path}`, { ...init, headers });
    if (res.status === 401 && retry) {
      const ok = await refreshAccess();
      if (ok) return apiFetch(path, init, false);
    }
    return res;
  }

  async function login() {
    error = null;
    const res = await fetch(`${apiBase}/auth/dev-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (!res.ok) {
      error = data?.error?.message ?? `${res.status} 로그인 실패`;
      return;
    }
    accessToken = data.access;
    refreshToken = data.refresh;
    me = data.user;
    screen = 'home';
  }

  function loginWithGoogle() {
    window.location.href = `${apiBase}/auth/google/start`;
  }

  async function whoami() {
    error = null;
    const res = await apiFetch(`/auth/me`);
    const data = await res.json();
    if (!res.ok) {
      error = data?.error?.message ?? `${res.status} 인증 확인 실패`;
      screen = 'login';
      return;
    }
    me = data.user;
    screen = 'home';
  }

  function logout() {
    accessToken = '';
    refreshToken = '';
    me = null;
    projectId = null;
    files = [];
    selectedFile = null;
    ragResults = null;
    screen = 'login';
  }

  async function ping() {
    error = null;
    try {
      const res = await fetch(`${apiBase}/health/`);
      health = await res.json();
    } catch (e: any) {
      error = e?.message ?? String(e);
    }
  }

  async function createProject() {
    error = null;
    selectedFile = null;
    ragResults = null;
    const res = await apiFetch(`/projects/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'demo' })
    });
    const data = await res.json();
    if (!res.ok) {
      error = data?.error?.message ?? `${res.status} 프로젝트 생성 실패`;
      return;
    }
    projectId = data.project_id;
    await refreshTree();
  }

  async function refreshTree() {
    if (!projectId) return;
    const res = await apiFetch(`/projects/${projectId}/files/tree`);
    const data = await res.json();
    if (!res.ok) {
      error = data?.error?.message ?? `${res.status} 트리 조회 실패`;
      return;
    }
    files = data.files ?? [];
  }

  async function uploadText() {
    if (!projectId) await createProject();
    if (!projectId) return;
    error = null;
    const res = await apiFetch(`/projects/${projectId}/files/upload_text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        relative_path: uploadPath,
        kind: uploadKind,
        content: uploadContent
      })
    });
    if (!res.ok) {
      error = `${res.status} 업로드 실패`;
      return;
    }
    await refreshTree();
  }

  async function openFile(fileId: number) {
    selectedFile = null;
    const res = await apiFetch(`/files/${fileId}`);
    const data = await res.json();
    if (!res.ok) {
      error = data?.error?.message ?? `${res.status} 파일 열기 실패`;
      return;
    }
    selectedFile = data;
  }

  async function runRag() {
    if (!projectId) return;
    ragResults = null;
    const res = await apiFetch(`/rag/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, query: ragQuery, top_k: 5, scope: 'settings_only' })
    });
    const data = await res.json();
    if (!res.ok) {
      error = data?.error?.message ?? `${res.status} RAG 실패`;
      return;
    }
    ragResults = data;
  }

  onMount(async () => {
    const hash = window.location.hash?.replace(/^#/, '') ?? '';
    if (hash) {
      const hp = new URLSearchParams(hash);
      const a = hp.get('access') ?? '';
      const r = hp.get('refresh') ?? '';
      const uid = hp.get('uid');
      const uname = hp.get('username');
      if (a && r && uid && uname) {
        accessToken = a;
        refreshToken = r;
        me = { id: Number(uid), username: uname };
        screen = 'home';
        history.replaceState(null, '', window.location.pathname + window.location.search);
        return;
      }
    }

    // 간단한 스플래시 후 로그인 화면으로 진입
    await new Promise((resolve) => setTimeout(resolve, 1200));
    screen = 'login';
  });
</script>

{#if screen === 'splash'}
  <div class="splash">
    <div class="logo">Nodex Studio</div>
    <div class="muted">작가를 위한 로컬 AI 집필 스튜디오</div>
  </div>
{:else if screen === 'login'}
  <div class="loginWrap">
    <div class="loginCard">
      <div class="brand large">Nodex Studio</div>
      <div class="muted">로그인 후 홈으로 이동할 수 있습니다.</div>
      <div class="loginForm">
        <label class="label" for="login-username">username</label>
        <input id="login-username" class="input" bind:value={username} placeholder="username" />
        <label class="label" for="login-password">password</label>
        <input
          id="login-password"
          class="input"
          bind:value={password}
          type="password"
          placeholder="password"
        />
        <button on:click={login}>로그인</button>
        <button on:click={loginWithGoogle}>Google로 로그인</button>
      </div>
      {#if error}
        <div class="error">에러: {error}</div>
      {/if}
    </div>
  </div>
{:else}
  <div class="app">
    <header class="appbar">
      <div class="brand">Nodex Studio</div>
      <div class="spacer"></div>
      <div class="muted small">{me ? `${me.username} (#${me.id})` : 'unauth'}</div>
      <div class="muted small">project: {projectId ?? '—'}</div>
      <button on:click={whoami} disabled={!accessToken}>me</button>
      <button on:click={ping}>health</button>
      <button on:click={createProject} disabled={!accessToken}>프로젝트 생성</button>
      <button on:click={refreshTree} disabled={!projectId || !accessToken}>트리 새로고침</button>
      <button on:click={logout}>로그아웃</button>
    </header>

    <main class="main">
    <aside class="tree">
      <div class="panelTitle">Project Files</div>
      {#if !accessToken}
        <div class="muted">먼저 로그인하세요.</div>
      {:else if !projectId}
        <div class="muted">먼저 “프로젝트 생성”을 눌러주세요.</div>
      {:else}
        {#if files.length === 0}
          <div class="muted">아직 파일이 없습니다. 아래에서 업로드하세요.</div>
        {:else}
          <ul class="fileList">
            {#each files as f}
              <li class="fileRow">
                <button class="fileBtn" on:click={() => openFile(f.id)}>
                  <span class="path">{f.relative_path}</span>
                  <span class="badge {f.index_status}">{f.index_status}</span>
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      {/if}
    </aside>

    <section class="editor">
      <div class="panelTitle">Editor</div>
      <div class="grid">
        <label class="label" for="upload-path">업로드 경로</label>
        <input id="upload-path" class="input" bind:value={uploadPath} />
        <label class="label" for="upload-kind">kind</label>
        <select id="upload-kind" class="input" bind:value={uploadKind}>
          <option value="settings">settings</option>
          <option value="manuscript">manuscript</option>
        </select>
        <label class="label" for="upload-content">내용</label>
        <textarea id="upload-content" class="textarea" bind:value={uploadContent} />
        <div class="row">
          <button on:click={uploadText} disabled={!accessToken || !uploadPath || !uploadContent}>
            텍스트 업로드
          </button>
        </div>
      </div>
      {#if selectedFile}
        <div class="panelTitle">열린 파일: {selectedFile.relative_path}</div>
        <pre class="pre">{selectedFile.content}</pre>
      {/if}
    </section>

    <aside class="loredex">
      <div class="panelTitle">LoreDex</div>
      <div class="muted">RAG만 MVP로 연결되어 있습니다.</div>
      <div class="row">
        <input class="input" bind:value={ragQuery} placeholder="질문" />
        <button on:click={runRag} disabled={!projectId || !accessToken}>RAG 질의</button>
      </div>
      {#if error}
        <div class="error">에러: {error}</div>
      {:else if health}
        <pre class="pre">{JSON.stringify(health, null, 2)}</pre>
      {/if}
      {#if ragResults}
        <pre class="pre">{JSON.stringify(ragResults, null, 2)}</pre>
      {/if}
    </aside>
    </main>
  </div>
{/if}

<style>
  :global(html, body) {
    height: 100%;
    margin: 0;
    background: #0b0d12;
    color: #e7e9ee;
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Apple SD Gothic Neo",
      "Noto Sans KR", sans-serif;
  }
  .app {
    height: 100%;
    display: flex;
    flex-direction: column;
  }
  .splash {
    height: 100%;
    display: grid;
    place-items: center;
    text-align: center;
    gap: 8px;
    background: radial-gradient(circle at 30% 20%, #1b2440 0%, #0b0d12 48%, #090b10 100%);
  }
  .logo {
    font-size: 42px;
    font-weight: 800;
    letter-spacing: 0.5px;
  }
  .loginWrap {
    height: 100%;
    display: grid;
    place-items: center;
    padding: 16px;
  }
  .loginCard {
    width: 100%;
    max-width: 420px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 20px;
    display: grid;
    gap: 12px;
  }
  .brand.large {
    font-size: 24px;
  }
  .loginForm {
    display: grid;
    gap: 8px;
  }
  .appbar {
    min-height: 52px;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.02);
  }
  .brand {
    font-weight: 700;
    letter-spacing: 0.2px;
  }
  .spacer {
    flex: 1;
  }
  button {
    background: #2b3347;
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #e7e9ee;
    padding: 8px 10px;
    border-radius: 10px;
    cursor: pointer;
  }
  button:hover {
    background: #343d56;
  }
  .main {
    flex: 1;
    display: grid;
    grid-template-columns: 260px 1fr 420px;
    gap: 0;
    min-height: 0;
  }
  .tree,
  .editor,
  .loredex {
    min-height: 0;
    padding: 12px;
  }
  .tree {
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.01);
  }
  .editor {
    border-right: 1px solid rgba(255, 255, 255, 0.08);
  }
  .loredex {
    background: rgba(255, 255, 255, 0.01);
  }
  .panelTitle {
    font-size: 12px;
    opacity: 0.7;
    margin-bottom: 10px;
  }
  .muted {
    opacity: 0.7;
    font-size: 13px;
  }
  .small {
    font-size: 12px;
  }
  .row {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-top: 8px;
  }
  .grid {
    display: grid;
    grid-template-columns: 92px 1fr;
    gap: 8px;
    align-items: center;
    margin-bottom: 12px;
  }
  .label {
    opacity: 0.7;
    font-size: 12px;
  }
  .input {
    width: 100%;
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    padding: 8px 10px;
    color: #e7e9ee;
    outline: none;
  }
  .input.slim {
    width: 140px;
    padding: 6px 8px;
    font-size: 12px;
  }
  .textarea {
    width: 100%;
    height: 140px;
    resize: none;
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    padding: 12px;
    color: #e7e9ee;
    outline: none;
  }
  .textarea:focus {
    border-color: rgba(167, 194, 255, 0.6);
  }
  .pre {
    margin-top: 10px;
    background: rgba(0, 0, 0, 0.35);
    padding: 10px;
    border-radius: 12px;
    overflow: auto;
    max-height: 220px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }
  .error {
    margin-top: 10px;
    color: #ffb4b4;
  }
  .fileList {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .fileBtn {
    width: 100%;
    display: flex;
    gap: 8px;
    justify-content: space-between;
    align-items: center;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 8px 10px;
    border-radius: 10px;
    cursor: pointer;
  }
  .fileBtn:hover {
    background: rgba(255, 255, 255, 0.06);
  }
  .path {
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .badge {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    opacity: 0.9;
  }
  .badge.ready {
    border-color: rgba(120, 255, 180, 0.4);
  }
  .badge.pending {
    border-color: rgba(255, 220, 120, 0.35);
  }
  .badge.failed {
    border-color: rgba(255, 120, 120, 0.4);
  }
</style>

