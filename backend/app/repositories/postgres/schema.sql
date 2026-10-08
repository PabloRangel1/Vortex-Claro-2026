-- Esquema do Vortex no PostgreSQL.
--
-- Idempotente: roda a cada inicialização da API e só cria o que falta.
-- Enums do domínio são gravados como texto (o valor do StrEnum).
-- Listas e dicionários sem consulta própria ficam em JSONB.
--
-- `mensagens` e `eventos_friccao` NÃO têm chave estrangeira para
-- `atendimentos` de propósito: o orquestrador grava as mensagens do turno
-- antes de salvar um atendimento novo.

-- `seq` em clientes e planos preserva a ordem de cadastro nas listagens.
CREATE TABLE IF NOT EXISTS clientes (
    seq             BIGSERIAL,
    cliente_id      TEXT PRIMARY KEY,           -- CPF canônico (fictício)
    nome            TEXT NOT NULL,
    cpf_mascarado   TEXT NOT NULL,
    plano           TEXT NOT NULL,
    cliente_desde   TEXT NOT NULL,
    plano_id        TEXT,
    dia_vencimento  INTEGER
);

-- Resolve a identidade entre canais: telefone do WhatsApp e usuario_id do App
-- apontam para o mesmo cliente_id.
CREATE TABLE IF NOT EXISTS identificadores_cliente (
    canal           TEXT NOT NULL,
    identificador   TEXT NOT NULL,
    cliente_id      TEXT NOT NULL REFERENCES clientes (cliente_id) ON DELETE CASCADE,
    PRIMARY KEY (canal, identificador)
);

-- Uma sessão viva por cliente. `expira_em` faz o papel do TTL.
CREATE TABLE IF NOT EXISTS sessoes (
    cliente_id              TEXT PRIMARY KEY REFERENCES clientes (cliente_id) ON DELETE CASCADE,
    protocolo               TEXT NOT NULL,
    canal_ativo             TEXT NOT NULL,
    canal_origem            TEXT NOT NULL,
    canais_utilizados       JSONB NOT NULL DEFAULT '[]',
    iniciada_em             TIMESTAMPTZ NOT NULL,
    ultima_interacao        TIMESTAMPTZ NOT NULL,
    turnos                  INTEGER NOT NULL DEFAULT 0,
    intencao_atual          TEXT,
    turnos_mesma_intencao   INTEGER NOT NULL DEFAULT 0,
    etapa_fluxo             TEXT NOT NULL DEFAULT 'nenhuma',
    acao_pendente           TEXT,
    dados_pendentes         JSONB NOT NULL DEFAULT '{}',
    tentativas_etapa        INTEGER NOT NULL DEFAULT 0,
    expira_em               TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS atendimentos (
    protocolo           TEXT PRIMARY KEY,
    cliente_id          TEXT NOT NULL REFERENCES clientes (cliente_id) ON DELETE CASCADE,
    canal_origem        TEXT NOT NULL,
    canal_atual         TEXT NOT NULL,
    canais_utilizados   JSONB NOT NULL DEFAULT '[]',
    status              TEXT NOT NULL,
    intencao            TEXT NOT NULL,
    confianca           INTEGER NOT NULL DEFAULT 0,
    score_friccao       INTEGER NOT NULL DEFAULT 0,
    score_inicial       INTEGER NOT NULL DEFAULT 0,
    historico_score     JSONB NOT NULL DEFAULT '[]',
    total_mensagens     INTEGER NOT NULL DEFAULT 0,
    ultima_mensagem     TEXT NOT NULL DEFAULT '',
    aberto_em           TIMESTAMPTZ NOT NULL,
    atualizado_em       TIMESTAMPTZ NOT NULL,
    handoff_em          TIMESTAMPTZ,
    handoff_motivo      TEXT,
    atendente           TEXT,
    setor               TEXT,
    transferencias      INTEGER NOT NULL DEFAULT 0,
    nota                INTEGER,
    comentario          TEXT,
    avaliado_em         TIMESTAMPTZ,
    encerrado_em        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_atendimentos_status  ON atendimentos (status);
CREATE INDEX IF NOT EXISTS ix_atendimentos_cliente ON atendimentos (cliente_id, aberto_em DESC);

-- `seq` garante a ordem de chegada mesmo com dois registros no mesmo instante.
CREATE TABLE IF NOT EXISTS mensagens (
    seq         BIGSERIAL PRIMARY KEY,
    id          TEXT NOT NULL UNIQUE,
    protocolo   TEXT NOT NULL,
    remetente   TEXT NOT NULL,
    canal       TEXT,
    conteudo    TEXT NOT NULL,
    intencao    TEXT,
    confianca   INTEGER,
    autor       TEXT,
    criada_em   TIMESTAMPTZ NOT NULL,
    metadados   JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_mensagens_protocolo ON mensagens (protocolo, seq);

-- Trilha de auditoria: só INSERT, nunca UPDATE.
CREATE TABLE IF NOT EXISTS eventos_friccao (
    seq                 BIGSERIAL PRIMARY KEY,
    id                  TEXT NOT NULL UNIQUE,
    protocolo           TEXT NOT NULL,
    codigo_sinal        TEXT NOT NULL,
    peso                INTEGER NOT NULL,
    score_resultante    INTEGER NOT NULL,
    descricao           TEXT NOT NULL,
    criado_em           TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_eventos_protocolo ON eventos_friccao (protocolo, seq);

-- ---------------------------------------------------------------- operação

CREATE TABLE IF NOT EXISTS planos (
    seq                 BIGSERIAL,
    id                  TEXT PRIMARY KEY,
    nome                TEXT NOT NULL,
    categoria           TEXT NOT NULL,
    preco_centavos      INTEGER NOT NULL,
    franquia            TEXT NOT NULL,
    linhas_incluidas    INTEGER NOT NULL
);

-- Uma fatura atual por cliente. Dinheiro sempre em centavos inteiros.
CREATE TABLE IF NOT EXISTS faturas (
    cliente_id      TEXT PRIMARY KEY REFERENCES clientes (cliente_id) ON DELETE CASCADE,
    referencia      TEXT NOT NULL,
    valor_centavos  INTEGER NOT NULL,
    vencimento      DATE NOT NULL,
    codigo_barras   TEXT NOT NULL,
    status          TEXT NOT NULL,
    itens           JSONB NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS equipamentos (
    id                      TEXT PRIMARY KEY,
    cliente_id              TEXT NOT NULL UNIQUE REFERENCES clientes (cliente_id) ON DELETE CASCADE,
    tipo                    TEXT NOT NULL,
    modelo                  TEXT NOT NULL,
    status_conexao          TEXT NOT NULL,
    ultima_reinicializacao  TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS solicitacoes (
    seq                     BIGSERIAL,
    protocolo               TEXT PRIMARY KEY,
    cliente_id              TEXT NOT NULL REFERENCES clientes (cliente_id) ON DELETE CASCADE,
    protocolo_atendimento   TEXT NOT NULL,
    tipo                    TEXT NOT NULL,
    status                  TEXT NOT NULL,
    descricao               TEXT NOT NULL,
    referencia_fatura       TEXT,
    criada_em               TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_solicitacoes_cliente ON solicitacoes (cliente_id, seq);

-- ------------------------------------------------- evolução do esquema
-- ADD COLUMN IF NOT EXISTS: aplica-se tanto a um banco novo quanto a um que
-- já existia antes destas colunas.

ALTER TABLE clientes ADD COLUMN IF NOT EXISTS data_nascimento DATE;
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS cidade TEXT;

ALTER TABLE sessoes ADD COLUMN IF NOT EXISTS identidade_verificada BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE sessoes ADD COLUMN IF NOT EXISTS verificacao_pendente BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE sessoes ADD COLUMN IF NOT EXISTS tentativas_verificacao INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sessoes ADD COLUMN IF NOT EXISTS mensagem_pendente TEXT;

ALTER TABLE atendimentos ADD COLUMN IF NOT EXISTS identidade TEXT NOT NULL DEFAULT 'nao_verificada';
