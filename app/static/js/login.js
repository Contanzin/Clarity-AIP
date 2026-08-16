(async () => {
  // Já logado? Não faz sentido mostrar o formulário de novo.
  const usuario = await obterUsuarioAtual();
  if (usuario) {
    window.location.href = "/busca";
  }
})();

document.getElementById("form-login").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const email = document.getElementById("email").value.trim();
  const caixaErro = document.getElementById("erro-login");
  caixaErro.style.display = "none";

  const resp = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });

  if (!resp.ok) {
    const dados = await resp.json().catch(() => ({}));
    caixaErro.textContent = dados.detail || "Não foi possível entrar. Verifique o email.";
    caixaErro.style.display = "block";
    return;
  }

  window.location.href = "/busca";
});
