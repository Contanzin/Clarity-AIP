"""
Modelos ORM do Clarity A.I.P.

Mapeia as tabelas PostgreSQL para classes Python usando SQLAlchemy.
Todos os relacionamentos e constraints estão aqui.

Tipos customizados:
- documento_status: ENUM('pendente', 'aprovado')
- tag_sugestao_status: ENUM('pendente_revisao', 'aprovada', 'rejeitada')
- acesso_resultado: ENUM('permitido', 'acesso_negado', 'documento_pendente')
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime, ForeignKey,
    Enum as SQLEnum, UniqueConstraint, CheckConstraint, Index
)
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.core.database import Base
import enum


# ============================================================================
# ENUMS (tipos de dados customizados)
# ============================================================================

class DocumentoStatus(str, enum.Enum):
    """Status de um documento."""
    PENDENTE = "pendente"
    APROVADO = "aprovado"


class TagSugestaoStatus(str, enum.Enum):
    """Status de uma sugestão de tag."""
    PENDENTE_REVISAO = "pendente_revisao"
    APROVADA = "aprovada"
    REJEITADA = "rejeitada"


class AcessoResultado(str, enum.Enum):
    """Resultado de uma tentativa de acesso."""
    PERMITIDO = "permitido"
    ACESSO_NEGADO = "acesso_negado"
    DOCUMENTO_PENDENTE = "documento_pendente"


# ============================================================================
# TABELAS / MODELOS ORM
# ============================================================================

class Usuario(Base):
    """
    Usuário/colaborador da Claro.
    
    Atributos:
        id: Chave primária
        nome: Nome completo
        email: Email único
        ativo: Se o usuário está ativo (pode acessar a app)
        data_criacao: Timestamp de criação
        data_atualizacao: Timestamp da última atualização
    
    Relacionamentos:
        tags: Permissões de acesso (1:N com UsuarioTag)
        logs_acesso: Histórico de acessos (1:N com LogAccesso)
        documentos_criados: Documentos que este usuário criou (1:N com Documento)
        tags_sugeridas_revisadas: Tags que este usuário revisou (1:N com TagSugerida)
    """

    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    ativo = Column(Boolean, default=True, nullable=False)
    data_criacao = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    data_atualizacao = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relacionamentos
    tags = relationship(
        "UsuarioTag",
        back_populates="usuario",
        cascade="all, delete-orphan",
        lazy="selectin",  # Eager load das tags
        # UsuarioTag tem duas FKs para usuarios (usuario_id e
        # atribuida_por_usuario_id) — sem isso o SQLAlchemy não sabe qual
        # usar para este relacionamento.
        foreign_keys="UsuarioTag.usuario_id",
    )
    logs_acesso = relationship(
        "LogAccesso",
        back_populates="usuario",
        cascade="all, delete-orphan",
        foreign_keys="LogAccesso.usuario_id"
    )
    documentos_criados = relationship(
        "Documento",
        back_populates="usuario_criador",
        foreign_keys="Documento.usuario_criador_id"
    )
    tags_sugeridas_revisadas = relationship(
        "TagSugerida",
        back_populates="revisor",
        foreign_keys="TagSugerida.revisor_id"
    )

    def __repr__(self):
        return f"<Usuario(id={self.id}, nome={self.nome}, email={self.email}, ativo={self.ativo})>"


class UsuarioTag(Base):
    """
    Tag de acesso de um usuário (permissão).
    
    Relação N:M entre Usuario e suas tags.
    Uma tag é do formato "Area+Nivel" (ex: "Marketing2").
    
    Atributos:
        id: Chave primária
        usuario_id: Referência para Usuario
        tag: String no formato "Area+Nivel" (ex: "Marketing2", "Dados1")
        atribuida_por_usuario_id: Quem atribuiu esta tag (para auditoria)
        data_atribuicao: Quando foi atribuída
        observacoes: Notas sobre por que foi atribuída
    
    Relacionamentos:
        usuario: Back-reference para Usuario
        atribuida_por: Qual usuário atribuiu (self-referential)
    """

    __tablename__ = "usuario_tags"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    tag = Column(String(50), nullable=False, index=True)
    atribuida_por_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    data_atribuicao = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    observacoes = Column(Text, nullable=True)

    # Validação: tag deve ser "Area+Nivel" (ex: "Marketing2")
    __table_args__ = (
        UniqueConstraint("usuario_id", "tag", name="uq_usuario_tag"),
        CheckConstraint("tag ~ '^[A-Za-z]+\\d+$'", name="ck_tag_format"),
    )

    # Relacionamentos
    usuario = relationship("Usuario", back_populates="tags", foreign_keys=[usuario_id])
    atribuida_por = relationship("Usuario", foreign_keys=[atribuida_por_usuario_id])

    def __repr__(self):
        return f"<UsuarioTag(usuario_id={self.usuario_id}, tag={self.tag})>"


class Documento(Base):
    """
    Documento do acervo da Claro.
    
    Armazena metadados, embedding vetorial e controle de acesso.
    Todos os documentos começam com status='pendente' e só ficam acessíveis
    quando são aprovados (status='aprovado').
    
    Atributos:
        id: Chave primária
        titulo: Título do documento
        area: Área (ex: "Marketing", "Dados", "Vendas")
        nivel_acesso_exigido: Nível mínimo de acesso (1, 2, 3...)
        status: 'pendente' ou 'aprovado'
        caminho_arquivo: Caminho/URL do arquivo original
        resumo_executivo: Resumo fiel do documento (pode ser editado)
        embedding: Vetor de embedding para busca semântica (pgvector)
        data_criacao: Timestamp
        data_atualizacao: Timestamp
        usuario_criador_id: Quem criou o documento
    
    Relacionamentos:
        usuario_criador: Usuário que criou o documento
        tag_sugerida: TagSugerida associada (1:1)
        logs_acesso: LogAccesso (1:N)
    """

    __tablename__ = "documentos"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(500), nullable=False)
    area = Column(String(50), nullable=False, index=True)
    nivel_acesso_exigido = Column(Integer, nullable=False)
    status = Column(
        SQLEnum(DocumentoStatus, name="documento_status", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
        default=DocumentoStatus.PENDENTE,
        index=True
    )
    caminho_arquivo = Column(String(1000), nullable=False)
    resumo_executivo = Column(Text, nullable=True)
    # Vector(768): embedding de 768 dimensões (padrão Gemini)
    embedding = Column(Vector(768), nullable=True)
    data_criacao = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    data_atualizacao = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    usuario_criador_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    # Índice vetorial para busca semântica
    __table_args__ = (
        CheckConstraint("nivel_acesso_exigido >= 1", name="ck_nivel_positivo"),
        Index("idx_documentos_embedding", "embedding", postgresql_using="ivfflat"),
    )

    # Relacionamentos
    usuario_criador = relationship("Usuario", back_populates="documentos_criados", foreign_keys=[usuario_criador_id])
    tag_sugerida = relationship(
        "TagSugerida",
        back_populates="documento",
        uselist=False,
        cascade="all, delete-orphan"
    )
    logs_acesso = relationship(
        "LogAccesso",
        back_populates="documento",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Documento(id={self.id}, titulo={self.titulo}, area={self.area}, status={self.status})>"


class TagSugerida(Base):
    """
    Sugestão de tag feita pela IA para um documento.
    
    Workflow:
    1. Documento chega com status='pendente'
    2. IA sugere uma tag com confiança e justificativa
    3. Revisor humano analisa (status='pendente_revisao')
    4. Revisor aprova (status='aprovada') ou rejeita (status='rejeitada')
    5. Se aprovada, documento muda para status='aprovado'
    
    Atributos:
        id: Chave primária
        documento_id: Referência para Documento (UNIQUE)
        tag_sugerida: Tag proposta (ex: "Marketing2")
        justificativa: Trechos e raciocínio da sugestão
        confianca: 0.0-1.0 (< 0.7 deve ser destacada na UI)
        status: 'pendente_revisao', 'aprovada', 'rejeitada'
        criada_em: Quando a IA criou a sugestão
        revisada_em: Quando o humano revisou
        revisor_id: Qual usuário revisou
        comentario_revisor: Feedback do revisor
    
    Relacionamentos:
        documento: Back-reference para Documento
        revisor: Usuário que revisou
    """

    __tablename__ = "tags_sugeridas"

    id = Column(Integer, primary_key=True, index=True)
    documento_id = Column(Integer, ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    tag_sugerida = Column(String(50), nullable=False)
    justificativa = Column(Text, nullable=False)
    confianca = Column(Float, nullable=False)
    status = Column(
        SQLEnum(TagSugestaoStatus, name="tag_sugestao_status", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
        default=TagSugestaoStatus.PENDENTE_REVISAO,
        index=True
    )
    criada_em = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    revisada_em = Column(DateTime(timezone=True), nullable=True)
    revisor_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    comentario_revisor = Column(Text, nullable=True)

    # Validação: confiança entre 0 e 1
    __table_args__ = (
        CheckConstraint("confianca >= 0.0 AND confianca <= 1.0", name="ck_confianca"),
    )

    # Relacionamentos
    documento = relationship("Documento", back_populates="tag_sugerida", foreign_keys=[documento_id])
    revisor = relationship("Usuario", back_populates="tags_sugeridas_revisadas", foreign_keys=[revisor_id])

    def __repr__(self):
        return f"<TagSugerida(documento_id={self.documento_id}, tag={self.tag_sugerida}, confianca={self.confianca})>"


class LogAccesso(Base):
    """
    Log de auditoria: toda tentativa de acesso (sucesso ou falha).
    
    Atributos:
        id: Chave primária (BIGSERIAL para volume alto)
        usuario_id: Quem tentou acessar
        documento_id: Qual documento (NULL se acesso geral)
        resultado: 'permitido', 'acesso_negado', 'documento_pendente'
        motivo_negacao: Por que foi negado (ex: 'tag_insuficiente')
        ip_request: IP de origem (para rastreabilidade)
        query_texto: Texto da pergunta/busca
        timestamp: Quando ocorreu
    """

    __tablename__ = "logs_acesso"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True)
    documento_id = Column(Integer, ForeignKey("documentos.id", ondelete="SET NULL"), nullable=True, index=True)
    resultado = Column(
        SQLEnum(AcessoResultado, name="acesso_resultado", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
        index=True
    )
    motivo_negacao = Column(String(100), nullable=True)
    ip_request = Column(String(45), nullable=True)  # IPv4 ou IPv6
    query_texto = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)

    # Relacionamentos
    usuario = relationship("Usuario", back_populates="logs_acesso", foreign_keys=[usuario_id])
    documento = relationship("Documento", back_populates="logs_acesso", foreign_keys=[documento_id])

    def __repr__(self):
        return f"<LogAccesso(usuario_id={self.usuario_id}, documento_id={self.documento_id}, resultado={self.resultado})>"
