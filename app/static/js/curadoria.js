(async () => {
  await exigirLogin();
  await carregarPendentes();
})();

const listaEl = document.getElementById("lista-pendentes");

async function carregarPendentes() {
  listaEl.innerHTML = "<p>Carregando...</p>";
  const resp = await fetch("/api/v1/tags-sugeridas");
  if (resp.status === 401) {
    window.location.href = "/login";
    return;
  }
  const itens = await resp.json();

  if (itens.length === 0) {
    listaEl.innerHTML = '<div class="vazio-lista">Nenhuma sugestão pendente para você revisar no momento.</div>';
    return;
  }

  listaEl.innerHTML = "";
  for (const item of itens) {
    listaEl.appendChild(renderizarItem(item));
  }
}

function renderizarItem(item) {
  const [areaSugerida, nivelSugerido] = separarTag(item.tag_sugerida);

  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `
    <h2>${escaparHtml(item.documento.titulo)}</h2>
    <span class="tag-badge">${escaparHtml(item.tag_sugerida)}</span>
    <span>confiança: ${(item.confianca * 100).toFixed(0)}%</span>
    ${item.precisa_atencao ? '<span class="badge-atencao">⚠ baixa confiança — revisar com atenção</span>' : ""}
    <p class="justificativa">${escaparHtml(item.justificativa)}</p>

    <div class="linha-corrigir">
      <div>
        <label>Área (corrigir se necessário)</label>
        <select class="campo-area">
          ${AREAS_VALIDAS.map((a) => `<option value="${a}" ${a === areaSugerida ? "selected" : ""}>${a}</option>`).join("")}
        </select>
      </div>
      <div>
        <label>Nível (1-4)</label>
        <input type="number" class="campo-nivel" min="1" max="4" value="${nivelSugerido}">
      </div>
    </div>
    <label>Comentário do revisor</label>
    <textarea class="campo-comentario" placeholder="Motivo da decisão (opcional para aprovar, obrigatório para rejeitar)"></textarea>
    <div class="erro campo-erro" style="display: none;"></div>
    <div class="acoes">
      <button class="botao-aprovar">Aprovar</button>
      <button class="botao-rejeitar secundario">Rejeitar</button>
    </div>
  `;

  card.querySelector(".botao-aprovar").addEventListener("click", () =>
    revisar(item.id, "aprovar", card)
  );
  card.querySelector(".botao-rejeitar").addEventListener("click", () =>
    revisar(item.id, "rejeitar", card)
  );

  return card;
}

async function revisar(tagId, acao, card) {
  const area = card.querySelector(".campo-area").value;
  const nivel = parseInt(card.querySelector(".campo-nivel").value, 10);
  const comentario = card.querySelector(".campo-comentario").value.trim();
  const caixaErro = card.querySelector(".campo-erro");
  caixaErro.style.display = "none";

  if (acao === "rejeitar" && !comentario) {
    caixaErro.textContent = "Informe o motivo da rejeição.";
    caixaErro.style.display = "block";
    return;
  }

  const payload =
    acao === "aprovar" ? { area, nivel, comentario: comentario || null } : { comentario };

  const resp = await fetch(`/api/v1/tags-sugeridas/${tagId}/${acao}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    const dados = await resp.json().catch(() => ({}));
    caixaErro.textContent = dados.detail || "Não foi possível concluir a ação.";
    caixaErro.style.display = "block";
    return;
  }

  card.remove();
  if (!listaEl.querySelector(".card")) {
    listaEl.innerHTML = '<div class="vazio-lista">Nenhuma sugestão pendente para você revisar no momento.</div>';
  }
}

function separarTag(tag) {
  const match = tag.match(/^([A-Za-z]+)(\d+)$/);
  return match ? [match[1], parseInt(match[2], 10)] : ["", 1];
}
