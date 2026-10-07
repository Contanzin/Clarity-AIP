"""
Rotas de páginas HTML do Clarity A.I.P (Passo 9).

As páginas em si são só o "shell" (Jinja2, sem dados por requisição) — toda
a interatividade (login, busca, curadoria) roda em JS puro no navegador,
chamando a API JSON já existente e testada. Sem framework de frontend,
como decidido no README.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.areas import AREAS_VALIDAS

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
async def raiz(request: Request):
    return request.app.state.templates.TemplateResponse(request, "busca.html", {})


@router.get("/login", response_class=HTMLResponse)
async def pagina_login(request: Request):
    return request.app.state.templates.TemplateResponse(request, "login.html", {})


@router.get("/busca", response_class=HTMLResponse)
async def pagina_busca(request: Request):
    return request.app.state.templates.TemplateResponse(request, "busca.html", {})


@router.get("/enviar", response_class=HTMLResponse)
async def pagina_enviar(request: Request):
    return request.app.state.templates.TemplateResponse(request, "enviar.html", {})


@router.get("/curadoria", response_class=HTMLResponse)
async def pagina_curadoria(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "curadoria.html", {"areas_validas": AREAS_VALIDAS}
    )


@router.get("/perfil", response_class=HTMLResponse)
async def pagina_perfil(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "perfil.html", {"areas_validas": AREAS_VALIDAS}
    )


@router.get("/admin", response_class=HTMLResponse)
async def pagina_admin(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "admin.html", {"areas_validas": AREAS_VALIDAS}
    )
