(async () => {
  const usuario = await exigirAdmin();
  if (!usuario) return;
  inicializarAbas();
  await carregarSolicitacoes();
  await carregarUsuarios();
  await carregarDocumentos();
})();

function inicializarAbas() {
  const abas = document.querySelectorAll(".aba");
  abas.forEach((aba) => {
    aba.addEventListener("click", () => {
      abas.forEach((a) => {
        a.classList.remove("ativa");
        a.setAttribute("aria-selected", "false");
        document.getElementById(a.dataset.painel).hidden = true;
      });
      aba.classList.add("ativa");
      aba.setAttribute("aria-selected", "true");
      document.getElementById(aba.dataset.painel).hidden = false;
    });
  });
}

const STATUS_BADGE = { pendente_revisao: "badge-atencao", aprovada: "badge-sucesso", rejeitada: "badge-negado" };
const STATUS_LABEL = { pendente_revisao: "pendente", aprovada: "aprovada", rejeitada: "rejeitada" };
const DOC_STATUS_BADGE = { pendente: "badge-atencao", aprovado: "badge-sucesso" };

// ============================================================================
// PEDIDOS DE UPGRADE
// ============================================================================

async function carregarSolicitacoes() {
  const el = document.getElementById("lista-solicitacoes-admin");
  el.innerHTML = "<p>Carregando...</p>";
  const resp = await fetch("/api/v1/admin/solicitacoes-upgrade");
  const itens = await resp.json();

  if (itens.length === 0) {
    el.innerHTML = '<div class="vazio-lista">Nenhum pedido de upgrade ainda.</div>';
    return;
  }

  el.innerHTML = "";
  for (const s of itens) {
    el.appendChild(renderizarSolicitacao(s));
  }
}

function renderizarSolicitacao(s) {
  const card = document.createElement("div");
  card.className = "card";
  const pendente = s.status === "pendente_revisao";
  card.innerHTML = `
    <strong>${escaparHtml(s.usuario_nome)}</strong> (${escaparHtml(s.usuario_email)})
    <span class="tag-badge">${escaparHtml(s.tag_solicitada)}</span>
    <span class="${STATUS_BADGE[s.status]}">${STATUS_LABEL[s.status]}</span>
    <p class="justificativa">${escaparHtml(s.justificativa)}</p>
    ${pendente ? `
      <label>Comentário (opcional para aprovar, obrigatório para rejeitar)</label>
      <textarea class="campo-comentario"></textarea>
      <div class="erro campo-erro" style="display: none;"></div>
      <div class="acoes">
        <button class="botao-aprovar">Aprovar</button>
        <button class="botao-rejeitar secundario">Rejeitar</button>
      </div>
    ` : (s.comentario_revisor ? `<p class="justificativa"><strong>Resposta:</strong> ${escaparHtml(s.comentario_revisor)}</p>` : "")}
  `;

  if (pendente) {
    card.querySelector(".botao-aprovar").addEventListener("click", () => revisarSolicitacao(s.id, "aprovar", card));
    card.querySelector(".botao-rejeitar").addEventListener("click", () => revisarSolicitacao(s.id, "rejeitar", card));
  }
  return card;
}

async function revisarSolicitacao(id, acao, card) {
  const comentario = card.querySelector(".campo-comentario").value.trim();
  const caixaErro = card.querySelector(".campo-erro");
  caixaErro.style.display = "none";

  if (acao === "rejeitar" && !comentario) {
    caixaErro.textContent = "Informe o motivo da rejeição.";
    caixaErro.style.display = "block";
    return;
  }

  const resp = await fetch(`/api/v1/admin/solicitacoes-upgrade/${id}/${acao}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ comentario: comentario || null }),
  });

  if (!resp.ok) {
    const dados = await resp.json().catch(() => ({}));
    caixaErro.textContent = extrairErro(dados, "Não foi possível concluir a ação.");
    caixaErro.style.display = "block";
    return;
  }

  await carregarSolicitacoes();
  await carregarUsuarios();
}

// ============================================================================
// USUÁRIOS
// ============================================================================

async function carregarUsuarios() {
  const el = document.getElementById("lista-usuarios-admin");
  el.innerHTML = "<p>Carregando...</p>";
  const resp = await fetch("/api/v1/admin/usuarios");
  const itens = await resp.json();
  el.innerHTML = "";
  for (const u of itens) {
    el.appendChild(renderizarUsuario(u));
  }
}

function renderizarUsuario(u) {
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `
    <strong>${escaparHtml(u.nome)}</strong> (${escaparHtml(u.email)})
    ${u.is_admin ? '<span class="tag-badge">admin</span>' : ""}
    ${!u.ativo ? '<span class="badge-negado">inativo</span>' : ""}
    <p>${escaparHtml(u.cargo || "—")} · ${escaparHtml(u.departamento || "—")}</p>
    <div class="tags-usuario">
      ${u.tags.map((t) => `<span class="tag-badge">${escaparHtml(t.tag)} <a href="#" class="remover-tag" data-tag="${escaparHtml(t.tag)}">×</a></span>`).join(" ")}
    </div>
    <div class="linha-corrigir">
      <div>
        <label>Conceder tag — Área</label>
        <select class="campo-area-nova">
          ${AREAS_VALIDAS.map((a) => `<option value="${a}">${a}</option>`).join("")}
        </select>
      </div>
      <div>
        <label>Nível (1-4)</label>
        <input type="number" class="campo-nivel-novo" min="1" max="4" value="1">
      </div>
    </div>
    <div class="erro campo-erro" style="display: none;"></div>
    <div class="acoes">
      <button class="botao-conceder secundario">Conceder tag</button>
      <button class="botao-toggle-ativo secundario">${u.ativo ? "Desativar" : "Ativar"}</button>
      <button class="botao-toggle-admin secundario">${u.is_admin ? "Remover admin" : "Tornar admin"}</button>
    </div>
  `;

  card.querySelectorAll(".remover-tag").forEach((el) =>
    el.addEventListener("click", (ev) => {
      ev.preventDefault();
      removerTag(u.id, el.dataset.tag);
    })
  );
  card.querySelector(".botao-conceder").addEventListener("click", () => {
    const area = card.querySelector(".campo-area-nova").value;
    const nivel = card.querySelector(".campo-nivel-novo").value;
    concederTag(u.id, `${area}${nivel}`, card);
  });
  card.querySelector(".botao-toggle-ativo").addEventListener("click", () =>
    atualizarUsuario(u.id, { ativo: !u.ativo })
  );
  card.querySelector(".botao-toggle-admin").addEventListener("click", () =>
    atualizarUsuario(u.id, { is_admin: !u.is_admin })
  );

  return card;
}

async function concederTag(usuarioId, tag, card) {
  const caixaErro = card.querySelector(".campo-erro");
  caixaErro.style.display = "none";
  const resp = await fetch(`/api/v1/admin/usuarios/${usuarioId}/tags`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag }),
  });
  if (!resp.ok) {
    const dados = await resp.json().catch(() => ({}));
    caixaErro.textContent = extrairErro(dados, "Não foi possível conceder a tag.");
    caixaErro.style.display = "block";
    return;
  }
  await carregarUsuarios();
}

async function removerTag(usuarioId, tag) {
  await fetch(`/api/v1/admin/usuarios/${usuarioId}/tags/${tag}`, { method: "DELETE" });
  await carregarUsuarios();
}

async function atualizarUsuario(usuarioId, payload) {
  await fetch(`/api/v1/admin/usuarios/${usuarioId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  await carregarUsuarios();
}

// ============================================================================
// DOCUMENTOS
// ============================================================================

async function carregarDocumentos() {
  const el = document.getElementById("lista-documentos-admin");
  el.innerHTML = "<p>Carregando...</p>";
  const resp = await fetch("/api/v1/admin/documentos");
  const itens = await resp.json();

  if (itens.length === 0) {
    el.innerHTML = '<div class="vazio-lista">Nenhum documento enviado ainda.</div>';
    return;
  }

  el.innerHTML = "";
  for (const d of itens) {
    el.appendChild(renderizarDocumento(d));
  }
}

function renderizarDocumento(d) {
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `
    <strong>${escaparHtml(d.titulo)}</strong>
    <span class="tag-badge">${escaparHtml(d.area)}${d.nivel_acesso_exigido}</span>
    <span class="${DOC_STATUS_BADGE[d.status] || "tag-badge"}">${escaparHtml(d.status)}</span>
    <p class="justificativa">Criado por ${escaparHtml(d.usuario_criador_nome || "desconhecido")}</p>
    <div class="erro campo-erro" style="display: none;"></div>
    <div class="acoes">
      <button class="botao-excluir-documento secundario">Excluir</button>
    </div>
  `;
  card.querySelector(".botao-excluir-documento").addEventListener("click", () => excluirDocumento(d, card));
  return card;
}

async function excluirDocumento(d, card) {
  if (!window.confirm(`Excluir "${d.titulo}" permanentemente? Essa ação não pode ser desfeita.`)) return;

  const resp = await fetch(`/api/v1/admin/documentos/${d.id}`, { method: "DELETE" });
  if (!resp.ok) {
    const dados = await resp.json().catch(() => ({}));
    const caixaErro = card.querySelector(".campo-erro");
    caixaErro.textContent = extrairErro(dados, "Não foi possível excluir o documento.");
    caixaErro.style.display = "block";
    return;
  }

  card.remove();
}
