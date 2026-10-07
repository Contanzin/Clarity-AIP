(async () => {
  const usuario = await exigirLogin();
  if (!usuario) return;
  renderizarPerfil(usuario);
  await carregarArquivos();
  await carregarSolicitacoes();
})();

function renderizarPerfil(usuario) {
  document.getElementById("dados-perfil").innerHTML = `
    <p><strong>${escaparHtml(usuario.nome)}</strong> — ${escaparHtml(usuario.email)}</p>
    <p>${escaparHtml(usuario.cargo || "Cargo não informado")} · ${escaparHtml(usuario.departamento || "Departamento não informado")}</p>
    <p>Tags de acesso:
      ${usuario.tags.length
        ? usuario.tags.map((t) => `<span class="tag-badge">${escaparHtml(t.tag)}</span>`).join(" ")
        : '<span style="color: var(--cor-texto-suave);">nenhuma</span>'}
    </p>
  `;
}

async function carregarArquivos() {
  const listaEl = document.getElementById("lista-arquivos");
  listaEl.innerHTML = "<p>Carregando...</p>";
  const resp = await fetch("/api/v1/documentos");
  const itens = await resp.json();

  if (itens.length === 0) {
    listaEl.innerHTML = '<div class="vazio-lista">Você ainda não tem acesso a nenhum documento aprovado.</div>';
    return;
  }

  listaEl.innerHTML = itens
    .map(
      (d) => `
    <div class="card">
      <strong>${escaparHtml(d.titulo)}</strong>
      <span class="tag-badge">${escaparHtml(d.area)}${d.nivel_acesso_exigido}</span>
      <div><a href="${d.link}" target="_blank">Abrir documento →</a></div>
    </div>`
    )
    .join("");
}

const STATUS_LABEL = {
  pendente_revisao: "pendente de revisão",
  aprovada: "aprovada",
  rejeitada: "rejeitada",
};
const STATUS_BADGE = {
  pendente_revisao: "badge-atencao",
  aprovada: "badge-sucesso",
  rejeitada: "badge-negado",
};

async function carregarSolicitacoes() {
  const listaEl = document.getElementById("lista-solicitacoes");
  listaEl.innerHTML = "<p>Carregando...</p>";
  const resp = await fetch("/api/v1/solicitacoes-upgrade");
  const itens = await resp.json();

  if (itens.length === 0) {
    listaEl.innerHTML = '<div class="vazio-lista">Você ainda não pediu nenhum upgrade de tag.</div>';
    return;
  }

  listaEl.innerHTML = itens
    .map(
      (s) => `
    <div class="card">
      <span class="tag-badge">${escaparHtml(s.tag_solicitada)}</span>
      <span class="${STATUS_BADGE[s.status] || "tag-badge"}">${STATUS_LABEL[s.status] || s.status}</span>
      <p class="justificativa">${escaparHtml(s.justificativa)}</p>
      ${s.comentario_revisor ? `<p class="justificativa"><strong>Resposta:</strong> ${escaparHtml(s.comentario_revisor)}</p>` : ""}
    </div>`
    )
    .join("");
}

document.getElementById("form-senha").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const erroEl = document.getElementById("erro-senha");
  const sucessoEl = document.getElementById("sucesso-senha");
  erroEl.style.display = "none";
  sucessoEl.style.display = "none";

  const senhaAtual = document.getElementById("senha-atual").value;
  const senhaNova = document.getElementById("senha-nova").value;
  const senhaNovaConfirmar = document.getElementById("senha-nova-confirmar").value;

  if (senhaNova !== senhaNovaConfirmar) {
    erroEl.textContent = "A confirmação não bate com a nova senha.";
    erroEl.style.display = "block";
    return;
  }

  const resp = await fetch("/api/v1/auth/senha", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ senha_atual: senhaAtual, senha_nova: senhaNova }),
  });

  if (!resp.ok) {
    const dados = await resp.json().catch(() => ({}));
    erroEl.textContent = extrairErro(dados, "Não foi possível trocar a senha.");
    erroEl.style.display = "block";
    return;
  }

  document.getElementById("form-senha").reset();
  sucessoEl.textContent = "Senha alterada com sucesso.";
  sucessoEl.style.display = "block";
});

document.getElementById("form-upgrade").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const caixaErro = document.getElementById("erro-upgrade");
  caixaErro.style.display = "none";

  const area = document.getElementById("campo-area-upgrade").value;
  const nivel = document.getElementById("campo-nivel-upgrade").value;
  const justificativa = document.getElementById("campo-justificativa-upgrade").value.trim();

  const resp = await fetch("/api/v1/solicitacoes-upgrade", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag_solicitada: `${area}${nivel}`, justificativa }),
  });

  if (!resp.ok) {
    const dados = await resp.json().catch(() => ({}));
    caixaErro.textContent = extrairErro(dados, "Não foi possível enviar o pedido.");
    caixaErro.style.display = "block";
    return;
  }

  document.getElementById("form-upgrade").reset();
  await carregarSolicitacoes();
});
