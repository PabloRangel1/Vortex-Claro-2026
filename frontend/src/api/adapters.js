/**
 * Tradução payload da API → view models.
 *
 * Existe para isolar os componentes de renomeações no backend: se um campo
 * mudar de nome, o conserto é aqui e em nenhum outro lugar.
 */

const ROTULO_CANAL = { app: 'App Claro', whatsapp: 'WhatsApp' }

export const rotuloCanal = (canal) => ROTULO_CANAL[canal] ?? canal

export function adaptarItemFila(item) {
  return {
    protocolo: item.protocolo,
    clienteId: item.cliente_ref,
    nome: item.nome,
    canalAtual: item.canal_atual,
    canalOrigem: item.canal_origem,
    houveTroca: item.houve_troca_de_canal,
    status: item.status,
    setor: item.setor,
    setorRotulo: item.setor_rotulo,
    segmento: item.segmento ?? 'pos',
    segmentoRotulo: item.segmento_rotulo ?? 'Pós-pago',
    plano: item.plano ?? '',
    intencao: item.intencao,
    intencaoRotulo: item.intencao_rotulo,
    confianca: item.confianca,
    score: item.score_friccao,
    nivel: item.nivel,
    ultimaMensagem: item.ultima_mensagem,
    aguardandoDesde: item.aguardando_desde,
    esperaSegundos: item.espera_segundos,
  }
}

export function adaptarMensagem(m) {
  return {
    id: m.id,
    remetente: m.remetente,
    canal: m.canal,
    canalRotulo: m.canal_rotulo,
    conteudo: m.conteudo,
    intencao: m.intencao,
    confianca: m.confianca,
    autor: m.autor,
    criadaEm: m.criada_em,
    tipo: m.metadados?.tipo ?? null,
    de: m.metadados?.de ?? null,
    para: m.metadados?.para ?? null,
    // Só em mensagens de ação do autoatendimento (tipo "acao")
    acao: m.metadados?.acao ?? null,
    status: m.metadados?.status ?? null,
    codigo: m.metadados?.codigo ?? null,
    dados: m.metadados?.dados ?? {},
    solicitacao: m.metadados?.solicitacao ?? null,
    requerHandoff: m.metadados?.requer_handoff ?? false,
    motivo: m.metadados?.motivo ?? null,
    // Resposta do bot em que a IA interpretou a mensagem ou escreveu o texto
    ia: m.metadados?.ia === true,
  }
}

/** Conversa guiada em andamento: o que o bot espera e os botões de resposta. */
export function adaptarFluxo(f) {
  if (!f) return null
  return {
    etapa: f.etapa,
    acaoPendente: f.acao_pendente,
    opcoes: (f.opcoes ?? []).map((o) => ({ rotulo: o.rotulo, texto: o.texto })),
  }
}

export function adaptarAtendimento(dados) {
  return {
    protocolo: dados.protocolo,
    cliente: {
      id: dados.cliente.cliente_ref,
      nome: dados.cliente.nome,
      cpf: dados.cliente.cpf_mascarado,
      plano: dados.cliente.plano,
      clienteDesde: dados.cliente.cliente_desde,
      email: dados.cliente.email ?? null,
      cidade: dados.cliente.cidade ?? null,
    },
    identidade: dados.identidade ?? 'nao_verificada',
    canalOrigem: dados.canal_origem,
    canalOrigemRotulo: dados.canal_origem_rotulo,
    canalAtual: dados.canal_atual,
    canalAtualRotulo: dados.canal_atual_rotulo,
    canaisUtilizados: dados.canais_utilizados,
    houveTroca: dados.houve_troca_de_canal,
    status: dados.status,
    atendente: dados.atendente,
    setor: dados.setor,
    setorRotulo: dados.setor_rotulo,
    transferencias: dados.transferencias ?? 0,
    encerradoEm: dados.encerrado_em,
    avaliacao: {
      nota: dados.avaliacao?.nota ?? null,
      comentario: dados.avaliacao?.comentario ?? null,
      em: dados.avaliacao?.em ?? null,
    },
    intencao: dados.intencao,
    intencaoRotulo: dados.intencao_rotulo,
    confianca: dados.confianca,
    score: dados.score_friccao,
    scoreInicial: dados.score_inicial,
    deltaScore: dados.delta_score,
    nivel: dados.nivel,
    historicoScore: dados.historico_score,
    handoff: {
      acionado: dados.handoff.acionado,
      em: dados.handoff.em,
      motivo: dados.handoff.motivo,
    },
    fluxo: adaptarFluxo(dados.fluxo),
    contatos30Dias: dados.contatos_30_dias ?? 1,
    contatosAnteriores: (dados.contatos_anteriores ?? []).map((c) => ({
      protocolo: c.protocolo,
      abertoEm: c.aberto_em,
      status: c.status,
      intencao: c.intencao,
      intencaoRotulo: c.intencao_rotulo,
      houveHandoff: c.houve_handoff,
      nota: c.nota,
    })),
    mensagens: dados.mensagens.map(adaptarMensagem),
    eventos: dados.eventos_friccao.map((e) => ({
      codigo: e.codigo_sinal,
      peso: e.peso,
      scoreResultante: e.score_resultante,
      descricao: e.descricao,
      criadoEm: e.criado_em,
    })),
    totalMensagens: dados.total_mensagens,
    abertoEm: dados.aberto_em,
    atualizadoEm: dados.atualizado_em,
    duracaoSegundos: dados.duracao_segundos,
  }
}

export function adaptarRespostaCanal(dados) {
  return {
    protocolo: dados.protocolo,
    clienteId: dados.cliente_ref,
    nomeCliente: dados.nome_cliente,
    canal: dados.canal,
    intencao: dados.intencao,
    intencaoRotulo: dados.intencao_rotulo,
    confianca: dados.confianca,
    score: dados.score_friccao,
    scoreAnterior: dados.score_anterior,
    deltaScore: dados.delta_score,
    nivel: dados.nivel,
    sinais: dados.sinais.map((s) => ({
      codigo: s.codigo,
      peso: s.peso,
      descricao: s.descricao,
    })),
    status: dados.status,
    handoffAcionado: dados.handoff_acionado,
    trocaDeCanal: dados.troca_de_canal,
    sessaoNova: dados.sessao_nova,
    resposta: dados.resposta,
    origemResposta: dados.origem_resposta,
    geradoPorIa: dados.gerado_por_ia ?? false,
    acoes: (dados.acoes ?? []).map((a) => ({
      acao: a.acao,
      status: a.status,
      codigo: a.codigo,
      mensagem: a.mensagem,
      dados: a.dados ?? {},
      solicitacao: a.protocolo_solicitacao,
      requerHandoff: a.requer_handoff,
    })),
    fluxo: adaptarFluxo(dados.fluxo),
    totalMensagens: dados.total_mensagens,
    latenciaMs: dados.latencia_ms,
  }
}

export function adaptarEstatisticas(d) {
  return {
    resumo: {
      total: d.resumo.total_atendimentos,
      emAberto: d.resumo.em_aberto,
      encerrados: d.resumo.encerrados,
      scoreMedio: d.resumo.score_medio,
      scoreMaximo: d.resumo.score_maximo,
      handoffs: d.resumo.handoffs,
      taxaHandoff: d.resumo.taxa_handoff,
      transferencias: d.resumo.transferencias,
      trocaDeCanal: d.resumo.troca_de_canal,
    },
    porIntencao: d.por_intencao.map((i) => ({
      intencao: i.intencao,
      rotulo: i.rotulo,
      total: i.total,
      scoreMedio: i.score_medio,
      handoffs: i.handoffs,
    })),
    porNivel: d.por_nivel.map((n) => ({
      nivel: n.nivel,
      total: n.total,
      percentual: n.percentual,
    })),
    porCanal: d.por_canal_origem.map((c) => ({
      canal: c.canal,
      rotulo: c.rotulo,
      total: c.total,
    })),
    sinais: d.sinais.map((s) => ({
      codigo: s.codigo,
      rotulo: s.rotulo,
      ocorrencias: s.ocorrencias,
      pesoAcumulado: s.peso_acumulado,
    })),
    csat: {
      media: d.csat.media,
      total: d.csat.total_avaliacoes,
      percentualSatisfeitos: d.csat.percentual_satisfeitos,
      distribuicao: d.csat.distribuicao,
      comentarios: d.csat.comentarios,
    },
    porDia: (d.por_dia ?? []).map((x) => ({
      data: x.data,
      total: x.total,
      resolvidoBot: x.resolvido_bot,
      transferido: x.transferido,
      emAndamento: x.em_andamento,
      scoreMedio: x.score_medio,
    })),
    impacto: d.impacto
      ? {
          contatos: d.impacto.contatos,
          trocasDeCanal: d.impacto.trocas_de_canal,
          protocolosSemVortex: d.impacto.protocolos_sem_vortex,
          protocolosComVortex: d.impacto.protocolos_com_vortex,
          relatosRepetidosSemVortex: d.impacto.relatos_repetidos_sem_vortex,
          relatosRepetidosComVortex: d.impacto.relatos_repetidos_com_vortex,
          emRisco: d.impacto.em_risco,
          emRiscoAtendidosComContexto: d.impacto.em_risco_atendidos_com_contexto,
          emRiscoRetidos: d.impacto.em_risco_retidos,
          emRiscoInsatisfeitos: d.impacto.em_risco_insatisfeitos,
          receitaMensalProtegidaCentavos: d.impacto.receita_mensal_protegida_centavos,
          upgrades: d.impacto.upgrades,
          receitaMensalUpgradesCentavos: d.impacto.receita_mensal_upgrades_centavos,
          jornadaExemplo: {
            protocolo: d.impacto.jornada_exemplo.protocolo,
            canais: d.impacto.jornada_exemplo.canais,
            historicoScore: d.impacto.jornada_exemplo.historico_score,
            intencaoRotulo: d.impacto.jornada_exemplo.intencao_rotulo,
            houveHandoff: d.impacto.jornada_exemplo.houve_handoff,
          },
        }
      : null,
    autoatendimento: {
      resolvidosSemHumano: d.autoatendimento?.resolvidos_sem_humano ?? 0,
      taxaResolucao: d.autoatendimento?.taxa_resolucao ?? 0,
      acoesExecutadas: d.autoatendimento?.acoes_executadas ?? 0,
      falhas: d.autoatendimento?.falhas ?? 0,
      respostasComIa: d.autoatendimento?.respostas_com_ia ?? 0,
      porAcao: (d.autoatendimento?.por_acao ?? []).map((a) => ({
        acao: a.acao,
        total: a.total,
        sucesso: a.sucesso,
      })),
    },
  }
}

export function adaptarCliente(c) {
  return {
    clienteId: c.cliente_ref,
    dicaVerificacao: c.dica_verificacao ?? null,
    nome: c.nome,
    plano: c.plano,
    usuarioApp: c.identificadores?.app ?? null,
    telefoneWhatsApp: c.identificadores?.whatsapp ?? null,
  }
}

// ------------------------------------------------------------- histórico

export function adaptarClienteLista(c) {
  return {
    clienteId: c.cliente_ref,
    nome: c.nome,
    cpf: c.cpf_mascarado,
    plano: c.plano,
    segmento: c.segmento,
    segmentoRotulo: c.segmento_rotulo,
    cidade: c.cidade,
    totalAtendimentos: c.total_atendimentos,
    emAberto: c.em_aberto,
    ultimoContato: c.ultimo_contato,
    csatMedio: c.csat_medio,
  }
}

export function adaptarHistorico(h) {
  return {
    cliente: {
      id: h.cliente.cliente_ref,
      nome: h.cliente.nome,
      cpf: h.cliente.cpf_mascarado,
      plano: h.cliente.plano,
      clienteDesde: h.cliente.cliente_desde,
      email: h.cliente.email,
      cidade: h.cliente.cidade,
    },
    segmentoRotulo: h.segmento_rotulo,
    dataNascimento: h.data_nascimento,
    whatsapp: h.telefone_whatsapp,
    usuarioApp: h.usuario_app,
    atendimentos: h.atendimentos.map((a) => ({
      protocolo: a.protocolo,
      abertoEm: a.aberto_em,
      encerradoEm: a.encerrado_em,
      canalOrigem: a.canal_origem,
      canais: a.canais_utilizados,
      status: a.status,
      intencao: a.intencao,
      intencaoRotulo: a.intencao_rotulo,
      score: a.score_friccao,
      houveHandoff: a.houve_handoff,
      motivoHandoff: a.handoff_motivo,
      identidade: a.identidade,
      nota: a.nota,
      comentario: a.comentario,
    })),
    solicitacoes: h.solicitacoes.map((s) => ({
      protocolo: s.protocolo,
      protocoloAtendimento: s.protocolo_atendimento,
      tipo: s.tipo,
      status: s.status,
      descricao: s.descricao,
      criadaEm: s.criada_em,
    })),
  }
}
