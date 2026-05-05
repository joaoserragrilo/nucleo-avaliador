"""
Tabelas fiscais e defaults.

NOTA: Tabelas IMT são as oficiais de 2025 (artigo 17.º do CIMT). Em 2026 podem
ter actualização ligeira via OE 2026. Conferir Portal das Finanças antes de
usar em decisão real. Os defaults estão centralizados aqui para serem fáceis
de actualizar.

Fonte: AT — Autoridade Tributária e Aduaneira.
"""

# ---------------------------------------------------------------------------
# IMT — Imposto Municipal sobre as Transmissões Onerosas de Imóveis
# ---------------------------------------------------------------------------
# Cada bracket: (limite_superior, taxa, parcela_a_abater)
# Para o último bracket de "taxa única" (sem parcela a abater), usar parcela = 0
# e marcar TAXA_UNICA = True via tuplo (limite, taxa, 0, "unica").

# Habitação Própria e Permanente (HPP) — taxa marginal com parcela a abater
IMT_HPP_2025 = [
    # (limite_superior_eur, taxa, parcela_a_abater_eur, modo)
    (104_261, 0.00, 0, "marginal"),
    (142_618, 0.02, 2_085.22, "marginal"),
    (194_458, 0.05, 6_363.90, "marginal"),
    (324_058, 0.07, 10_252.98, "marginal"),
    (621_501, 0.08, 13_493.56, "marginal"),
    (1_128_287, 0.06, 0, "unica"),
    (float("inf"), 0.075, 0, "unica"),
]

# Habitação Secundária / Não Permanente
IMT_HABITACAO_SECUNDARIA_2025 = [
    (104_261, 0.01, 0, "unica"),
    (142_618, 0.02, 1_042.61, "marginal"),
    (194_458, 0.05, 5_321.29, "marginal"),
    (324_058, 0.07, 9_210.37, "marginal"),
    (621_501, 0.08, 12_450.95, "marginal"),
    (1_128_287, 0.06, 0, "unica"),
    (float("inf"), 0.075, 0, "unica"),
]

# Outros prédios urbanos / terrenos para construção / prédios rústicos
IMT_OUTROS_PREDIOS_URBANOS = 0.065  # 6,5% taxa única
IMT_PREDIOS_RUSTICOS = 0.05         # 5% taxa única

# ---------------------------------------------------------------------------
# Imposto do Selo (verba 1.1 da TGIS — transmissões onerosas)
# ---------------------------------------------------------------------------
IS_TRANSMISSAO = 0.008  # 0,8% sobre o maior entre VPT e preço

# ---------------------------------------------------------------------------
# IMI — Imposto Municipal sobre Imóveis (anual, sobre VPT)
# Taxas variam por município (0,3% a 0,45% prédio urbano avaliado).
# Default conservador para zona Lisboa/margem sul.
# ---------------------------------------------------------------------------
IMI_TAXA_DEFAULT = 0.0035  # 0,35% — calibrar por município se necessário

# AIMI — Adicional ao IMI (só se VPT total > 600k por sujeito passivo)
AIMI_LIMIAR_PF = 600_000
AIMI_TAXA_PF = 0.007  # 0,7% sobre excesso (escalão básico)

# Para PJ (Lda) AIMI é 0,4% sobre o valor total (sem dedução)
AIMI_TAXA_PJ = 0.004

# ---------------------------------------------------------------------------
# IVA — Imposto sobre o Valor Acrescentado em obra
# ---------------------------------------------------------------------------
IVA_NORMAL = 0.23
IVA_VERBA_2_23 = 0.06   # Reabilitação de imóvel em ARU ou afecto a habitação
                         # — condições estritas; ler verba 2.23 da Lista I do CIVA.

# ---------------------------------------------------------------------------
# Tributação na saída (revenda)
# ---------------------------------------------------------------------------
# IRC para Lda — 21% standard + derrama municipal
IRC_TAXA = 0.21
DERRAMA_MUNICIPAL_LISBOA = 0.015  # Lisboa, Almada, Setúbal, Seixal: ~1,5%
DERRAMA_MUNICIPAL_DEFAULT = 0.015

# Taxa efectiva combinada Lda (sem derrama estadual — só relevante > 1,5M lucro)
IRC_EFETIVO_DEFAULT = IRC_TAXA + DERRAMA_MUNICIPAL_DEFAULT  # 22,5%

# IRS — Mais-valias imobiliárias (PF, não HPP)
# Default: 50% da mais-valia × taxa marginal IRS, OU taxa autónoma 28%.
# Modelo simplificado v1: taxa autónoma 28% sobre mais-valia.
IRS_MV_TAXA_AUTONOMA = 0.28

# ---------------------------------------------------------------------------
# Custos transação (compra)
# ---------------------------------------------------------------------------
CUSTOS_NOTARIO_REGISTO_DEFAULT = 1_500  # Escritura + registo predial. Varia 800-2500€.

# ---------------------------------------------------------------------------
# Custos transação (venda)
# ---------------------------------------------------------------------------
COMISSAO_IMOBILIARIA_DEFAULT = 0.05  # 5% + IVA típico em PT

# ---------------------------------------------------------------------------
# Targets de referência (Núcleo Assets)
# ---------------------------------------------------------------------------
TARGET_ROI_FIXANDFLIP = 0.20      # 20% ROI total mínimo
TARGET_MARGEM_ABS_MIN = 30_000    # Margem absoluta mínima em €
TARGET_CICLO_MAX_MESES = 18       # Ciclo total máximo aceitável

# ---------------------------------------------------------------------------
# Stress test thresholds
# ---------------------------------------------------------------------------
STRESS_PRECO_VENDA = [-0.05, -0.10, -0.15]
STRESS_CICLO_MESES = [3, 6]
STRESS_OBRA_PCT = [0.20, 0.40]

# ---------------------------------------------------------------------------
# Obra — €/m² por estado de conservação (replicado do Excel actual)
# ---------------------------------------------------------------------------
# Sem IVA. O IVA aplica-se depois (6% Verba 2.23 ou 23% normal).
OBRA_EUR_M2_POR_ESTADO = {
    "Bom": 0,
    "Desatualizado": 300,
    "Remodelacao moderada": 450,
    "Remodelacao profunda": 650,
    "Ruina": 900,
}

# ---------------------------------------------------------------------------
# Factor de ajuste de comparáveis (replicado do Excel)
# ---------------------------------------------------------------------------
COMPARAVEIS_FACTOR = {
    "Iguais a revenda": 1.00,
    "Um pouco acima da revenda": 0.95,
    "Bastante acima da revenda": 0.90,
    "Muito acima da revenda": 0.85,
}

# ---------------------------------------------------------------------------
# ROIs alvo para simulacao de preco maximo de aquisicao
# ---------------------------------------------------------------------------
SIMULACAO_ROI_ALVOS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]

# ---------------------------------------------------------------------------
# Tipos de imovel suportados
# ---------------------------------------------------------------------------
TIPOS_IMOVEL = ["Apartamento", "Moradia", "Predio", "Terreno", "Comercial"]
TIPOLOGIAS = ["T0", "T1", "T2", "T3", "T4", "T5+", "N/A"]
ESTADOS_CONSERVACAO = list(OBRA_EUR_M2_POR_ESTADO.keys())
VENDEDORES = ["Particular", "Agente", "Banca", "Heranca", "Outro"]

# ---------------------------------------------------------------------------
# Mapeamento Estado Conservação (interno → Núcleo OS Activos)
# ---------------------------------------------------------------------------
# Internamente mantemos 5 níveis para granularidade do cálculo €/m² obra.
# Ao gravar no Airtable Activos, mapeamos para os 4 valores existentes.
ESTADO_INTERNO_PARA_AIRTABLE = {
    "Bom": "Bom estado",
    "Desatualizado": "Para remodelar",
    "Remodelacao moderada": "Para remodelar",
    "Remodelacao profunda": "Para remodelar",
    "Ruina": "Ruína",
}

# ---------------------------------------------------------------------------
# Mapeamento Veredicto cor → Recomendação Triagem I
# ---------------------------------------------------------------------------
VEREDICTO_PARA_RECOMENDACAO = {
    "verde": "Visitar",
    "amarelo": "Monitorizar",
    "vermelho": "Excluir",
}

# ---------------------------------------------------------------------------
# Tipos de imóvel: alinhar com Núcleo OS (Activos.Tipo de imovel)
# Single select existente no Airtable: Moradia, Prédio, Espaço Comercial,
# Terreno, Outro, Apartamento
# ---------------------------------------------------------------------------
TIPO_INTERNO_PARA_AIRTABLE = {
    "Apartamento": "Apartamento",
    "Moradia": "Moradia",
    "Predio": "Prédio",
    "Terreno": "Terreno",
    "Comercial": "Espaço Comercial",
}

# Tipologia: Núcleo OS usa T0-T4+, Outro
TIPOLOGIA_INTERNA_PARA_AIRTABLE = {
    "T0": "T0", "T1": "T1", "T2": "T2", "T3": "T3",
    "T4": "T4+", "T5+": "T4+", "N/A": "Outro",
}

# Canal de origem (Activos.Canal origem)
CANAIS_ORIGEM = ["Idealista", "Imovirtual", "Agente", "Contacto existente",
                 "Meta Ads", "Flyer", "Outro"]
PARSER_PARA_CANAL = {
    "idealista": "Idealista",
    "imovirtual": "Imovirtual",
    "remax": "Agente",
    "casasapo": "Outro",
    "generico": "Outro",
    "texto": "Outro",
}
