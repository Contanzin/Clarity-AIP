// Helpers compartilhados entre as páginas. Nada de framework — fetch()
// simples contra a API JSON já existente (a sessão é um cookie, então o
// fetch same-origin já manda ela automaticamente).

// Memoizado: tanto inicializarNav() quanto a checagem de cada página chamam
// isso na carga da página — sem cache, isso dispara duas requisições
// (ambas 401 se deslogado) para a mesma pergunta "quem está logado?".
let _usuarioAtualPromise = null;

function obterUsuarioAtual() {
  if (!_usuarioAtualPromise) {
    _usuarioAtualPromise = fetch("/api/v1/auth/me").then((resp) => (resp.ok ? resp.json() : null));
  }
  return _usuarioAtualPromise;
}

async function exigirLogin() {
  const usuario = await obterUsuarioAtual();
  if (!usuario) {
    window.location.href = "/login";
    return null;
  }
  return usuario;
}

async function fazerLogout() {
  await fetch("/api/v1/auth/logout", { method: "POST" });
  window.location.href = "/login";
}

async function inicializarNav() {
  const alvo = document.getElementById("usuario-logado");
  if (!alvo) return;
  const usuario = await obterUsuarioAtual();
  if (!usuario) {
    alvo.innerHTML = '<a href="/login">Entrar</a>';
    return;
  }
  alvo.textContent = `${usuario.nome} `;
  const sair = document.createElement("a");
  sair.href = "#";
  sair.textContent = "Sair";
  sair.style.marginLeft = "0.5rem";
  sair.addEventListener("click", (ev) => {
    ev.preventDefault();
    fazerLogout();
  });
  alvo.appendChild(sair);
}

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto ?? "";
  return div.innerHTML;
}

document.addEventListener("DOMContentLoaded", inicializarNav);
