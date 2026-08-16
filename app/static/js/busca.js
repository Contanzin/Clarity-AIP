(async () => {
  await exigirLogin();
})();

const caixaResultado = document.getElementById("resultado");

document.getElementById("form-busca").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const pergunta = document.getElementById("pergunta").value.trim();
  if (!pergunta) return;

  const botao = document.getElementById("botao-buscar");
  botao.disabled = true;
  botao.textContent = "Buscando...";
  caixaResultado.innerHTML = "";

  try {
    const resp = await fetch("/api/v1/busca", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pergunta }),
    });

    if (resp.status === 401) {
      window.location.href = "/login";
      return;
    }

    if (!resp.ok) {
      const dados = await resp.json().catch(() => ({}));
      caixaResultado.innerHTML = `<div class="erro">${escaparHtml(dados.detail || "Erro ao buscar.")}</div>`;
      return;
    }

    const dados = await resp.json();
    caixaResultado.innerHTML = renderizarResultado(dados);
  } finally {
    botao.disabled = false;
    botao.textContent = "Buscar";
  }
});

function renderizarResultado(dados) {
  if (dados.resultado === "encontrado") {
    return `
      <div class="card resultado-encontrado">
        <h2>${escaparHtml(dados.titulo)}</h2>
        <p>${escaparHtml(dados.resumo_executivo)}</p>
        <a href="${dados.link}" target="_blank">Abrir documento oficial →</a>
      </div>`;
  }
  if (dados.resultado === "restrito") {
    return `
      <div class="card resultado-restrito">
        <h2>Acesso restrito</h2>
        <p>${escaparHtml(dados.mensagem)}</p>
        <p>Tag necessária: <span class="tag-badge">${escaparHtml(dados.tag_necessaria)}</span></p>
        <p style="color: var(--cor-texto-suave); font-size: 0.85rem;">
          Solicite essa tag através do processo de governança interno.
        </p>
      </div>`;
  }
  return `
    <div class="card resultado-vazio">
      <p>${escaparHtml(dados.mensagem)}</p>
    </div>`;
}
