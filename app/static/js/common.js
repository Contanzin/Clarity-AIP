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

async function exigirAdmin() {
  const usuario = await exigirLogin();
  if (usuario && !usuario.is_admin) {
    window.location.href = "/busca";
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
    marcarLinkAtivo();
    return;
  }
  const perfil = document.createElement("a");
  perfil.href = "/perfil";
  perfil.textContent = usuario.nome;
  perfil.title = "Ver perfil";
  alvo.replaceChildren(perfil);
  const navAdmin = document.getElementById("nav-admin");
  if (navAdmin && usuario.is_admin) {
    navAdmin.innerHTML = '<a href="/admin">Admin</a>';
  }
  const sair = document.createElement("a");
  sair.href = "#";
  sair.textContent = "Sair";
  sair.style.marginLeft = "0.5rem";
  sair.addEventListener("click", (ev) => {
    ev.preventDefault();
    fazerLogout();
  });
  alvo.appendChild(sair);
  marcarLinkAtivo();
}

// FastAPI manda `detail` como string nos erros da aplicação (ex: "Credenciais
// inválidas"), mas como uma LISTA de objetos {msg, loc, ...} nos erros de
// validação do Pydantic (422) — por isso nunca usar `dados.detail` direto
// como texto, ou vira "[object Object]" na tela.
function extrairErro(dados, fallback) {
  const d = dados && dados.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length > 0) {
    return d.map((e) => (e && e.msg) || "Valor inválido").join("; ");
  }
  return fallback;
}

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto ?? "";
  return div.innerHTML;
}

// O tema inicial já foi aplicado por um script inline em base.html (antes do
// primeiro paint, pra não piscar) — aqui só cuidamos do botão de alternância.
function inicializarBotaoTema() {
  const botao = document.getElementById("botao-tema");
  if (!botao) return;

  const atualizarIcone = () => {
    const escuro = document.documentElement.getAttribute("data-theme") === "dark";
    botao.textContent = escuro ? "☀️" : "🌙";
  };
  atualizarIcone();

  botao.addEventListener("click", () => {
    const novoTema = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", novoTema);
    localStorage.setItem("tema", novoTema);
    atualizarIcone();
  });
}

function marcarLinkAtivo() {
  document.querySelectorAll("header.topo nav a").forEach((a) => {
    if (a.getAttribute("href") === window.location.pathname) a.classList.add("ativo");
  });
}

document.addEventListener("DOMContentLoaded", () => {
  inicializarNav();
  inicializarBotaoTema();
});
