"""
Áreas de conteúdo reconhecidas pelo Clarity A.I.P.

Lista fechada de propósito: o nome da área vira parte da tag de acesso
("Area" + nível, ex: "Marketing2"), e a tag exige o formato
`^[A-Za-z]+\\d+$` (só letras ASCII seguidas de dígitos, sem espaço ou
acento — ver a CHECK constraint em db/01_init_schema.sql). Uma lista
livre deixaria a IA inventar variações inconsistentes ("Marketing" vs
"marketing" vs "Mkt") que quebrariam o RBAC silenciosamente, já que
"Marketing2" e "marketing2" seriam áreas diferentes para o sistema.
"""

AREAS_VALIDAS: list[str] = [
    "Marketing",
    "Dados",
    "Vendas",
    "Suporte",
    "Financeiro",
    "RH",
    "Juridico",
    "TI",
]
