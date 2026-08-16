(async () => {
  await exigirLogin();
})();

const resultadoEnvioEl = document.getElementById("resultado-envio");
const caixaErro = document.getElementById("erro-envio");

document.getElementById("form-envio").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  caixaErro.style.display = "none";
  resultadoEnvioEl.innerHTML = "";

  const titulo = document.getElementById("titulo").value.trim();
  const conteudo = document.getElementById("conteudo").value.trim();
  const arquivoInput = document.getElementById("arquivo");
  const arquivo = arquivoInput.files[0];

  if (!conteudo && !arquivo) {
    caixaErro.textContent = "Cole o conteúdo ou selecione um arquivo .txt.";
    caixaErro.style.display = "block";
    return;
  }

  const formData = new FormData();
  formData.append("titulo", titulo);
  if (arquivo) {
    formData.append("arquivo", arquivo);
  } else {
    formData.append("conteudo", conteudo);
  }

  const botao = document.getElementById("botao-enviar");
  botao.disabled = true;
  botao.textContent = "Analisando com IA...";

  try {
    const resp = await fetch("/api/v1/documentos", { method: "POST", body: formData });

    if (resp.status === 401) {
      window.location.href = "/login";
      return;
    }

    const dados = await resp.json().catch(() => ({}));

    if (!resp.ok) {
      caixaErro.textContent = dados.detail || "Não foi possível enviar o documento.";
      caixaErro.style.display = "block";
      return;
    }

    resultadoEnvioEl.innerHTML = `
      <div class="card resultado-encontrado">
        <h2>Documento enviado</h2>
        <p><strong>${escaparHtml(dados.titulo)}</strong> — status: pendente de aprovação</p>
        <p>Tag sugerida pela IA: <span class="tag-badge">${escaparHtml(dados.tag_sugerida.tag_sugerida)}</span>
           (confiança ${(dados.tag_sugerida.confianca * 100).toFixed(0)}%)
           ${dados.tag_sugerida.precisa_atencao ? '<span class="badge-atencao">⚠ baixa confiança</span>' : ""}
        </p>
        <p class="justificativa">${escaparHtml(dados.tag_sugerida.justificativa)}</p>
        <a href="/curadoria">Ver na fila de curadoria →</a>
      </div>`;

    document.getElementById("form-envio").reset();
  } finally {
    botao.disabled = false;
    botao.textContent = "Enviar";
  }
});
