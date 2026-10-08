"""Configuração da aplicação.

Todo número que o motor de fricção usa mora aqui — nunca hardcoded nos services.
Isso permite calibrar a demo (ou rodar cenários diferentes na banca) sem tocar
em lógica de negócio.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Aplicação ---
    app_name: str = "Vortex"
    ambiente: str = "desenvolvimento"
    versao: str = "0.1.0"

    # --- Persistência ---
    # Com DATABASE_URL definida (no .env), a API usa PostgreSQL. Sem ela, cai
    # nos repositórios em memória — é assim que os testes rodam.
    database_url: str | None = None

    # --- IA (Fase 5) ---
    # Sem GEMINI_API_KEY a conversa roda só com as regras determinísticas.
    gemini_api_key: str | None = None
    gemini_modelo: str = "gemini-3.5-flash-lite"
    # Passado o limite, desiste e segue pelas regras. Turnos com IA podem
    # passar do orçamento de 2s por mensagem; os sem IA continuam abaixo dele.
    ia_timeout_segundos: float = 4.0
    ia_pausa_apos_erro_segundos: int = 60

    # --- Verificação de identidade ---
    # Canais em que o cliente confirma os 3 primeiros dígitos do CPF antes do
    # autoatendimento. O App já é autenticado por login.
    verificacao_canais: list[str] = ["whatsapp"]
    verificacao_tentativas: int = 3

    # --- Demonstração ---
    # Na subida (com a base vazia) e a cada "Reiniciar demo", carrega conversas
    # simuladas para o dashboard e as estatísticas não abrirem vazios.
    semear_demonstracao: bool = True

    # --- Privacidade ---
    # Chave da referência pública do cliente (o CPF não sai pela API).
    chave_referencia: str = "vortex-demo-troque-em-producao"
    # O simulador mostra os 3 dígitos do CPF para quem apresenta. Útil na banca;
    # desligue se os simuladores ficarem expostos a terceiros.
    simulador_dica_verificacao: bool = True

    # --- Administração ---
    # Com ADMIN_TOKEN definido, POST /reset exige o cabeçalho X-Admin-Token.
    # Fora do ambiente de desenvolvimento, sem token o reset fica desligado.
    admin_token: str | None = None

    # --- Sessão ---
    sessao_ttl_segundos: int = 1800

    # --- Motor de fricção ---
    score_minimo: int = 0
    score_maximo: int = 100
    limiar_handoff: int = 70
    limiar_atencao: int = 40
    # Repetição literal (SequenceMatcher sobre o texto inteiro)
    limiar_similaridade: float = 0.75
    # Repetição reformulada (sobreposição de palavras de conteúdo)
    limiar_contencao: float = 0.70
    min_tokens_contencao: int = 4

    peso_repeticao: int = 18
    peso_intencao_repetida: int = 12
    peso_pedido_humano: int = 25
    peso_troca_canal: int = 16
    peso_sentimento_base: int = 6
    peso_sentimento_max: int = 20
    peso_caixa_alta: int = 5
    peso_loop: int = 8
    peso_loop_max: int = 24
    peso_impaciencia: int = 8
    peso_decaimento: int = 12

    turnos_para_loop: int = 4
    turnos_mesma_intencao: int = 3
    janela_impaciencia_segundos: int = 60
    mensagens_impaciencia: int = 3
    janela_repeticao: int = 5

    # --- NLP ---
    confianca_minima_nlp: int = 35

    # --- Autoatendimento ---
    dias_vencimento_permitidos: list[int] = [5, 10, 15, 20]

    # --- CORS (Vite dev server do frontend) ---
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
