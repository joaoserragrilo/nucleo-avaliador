# Avaliador de Propriedades — F&F (v1)

Pequeno tool para análise de viabilidade de Fix-and-Flip residencial em Portugal. Pensado para a tese da Núcleo Assets (Lisboa, margem sul, Setúbal). Streamlit (Python), corre 100% local. Sem cloud, sem subscrição.

## Setup (Windows) — ler com atenção

A tua máquina é Windows ARM64 (Snapdragon X / Surface Pro X). Há um detalhe importante: o `pyarrow` (dependência obrigatória do Streamlit) **não tem wheels para ARM64**, por isso precisas de instalar **Python x64** (não ARM64). O Windows ARM64 corre Python x64 em emulação automática, com performance que para um app deste tamanho é negligível.

### Passo 1 — Desinstalar o Python ARM64 actual

Painel de Controlo → Aplicações Instaladas → procurar "Python 3.12" (ou versão que tens) → Desinstalar.

Apagar também a pasta `.venv` na pasta do projecto, se existir.

### Passo 2 — Instalar Python x64

Vai a https://www.python.org/downloads/windows/ e escolhe **"Windows installer (64-bit)"**. Não escolher ARM64.

Durante a instalação, marca a checkbox **"Add Python to PATH"**.

Verificação: abre uma nova janela de PowerShell ou CMD e corre:

```
python --version
python -c "import platform; print(platform.machine())"
```

Deve dizer `Python 3.x.y` e `AMD64` (não `ARM64`).

### Passo 3 — Setup

Na pasta do projecto, duplo-clique em:

```
setup.bat
```

Cria virtualenv em `.venv/`, instala Streamlit + pyarrow. O `setup.bat` valida automaticamente que o Python é x64 antes de tentar instalar — se ainda for ARM64, avisa e pára.

### Passo 4 — Correr

```
run.bat
```

Abre automaticamente no browser em http://localhost:8501.

## v2 — Novidades

- **Importação de anúncios — qualquer site**:
  - **Por URL**: parser dedicado para Idealista, Remax, Imovirtual, Casa Sapo + parser genérico baseado em JSON-LD/meta/microdata que cobre Era, Century 21, Decisões e Soluções, Realtv, Maxfinance e qualquer site com SEO decente. Tenta `cloudscraper` em fallback para contornar Cloudflare quando possível.
  - **Por Texto**: abres o anúncio no browser, Ctrl+A → Ctrl+C → colas no tool. Funciona em **qualquer site**, imune a Cloudflare/anti-bot. É o caminho mais robusto.
- **Caracterização do imóvel**: tipo (apartamento/moradia/prédio/terreno), tipologia (T0-T5+), área m², estado de conservação, vendedor.
- **Estimativa de obra automática**: área × €/m² do estado (Bom 0, Desatualizado 300, Moderada 450, Profunda 650, Ruína 900). Override manual disponível.
- **Tabela de comparáveis editável**: adiciona URLs + preço + m² + tipologia. O tool calcula preço/m² médio e aplica factor de ajuste (1.0 / 0.95 / 0.90 / 0.85) consoante os comparáveis estejam ao nível do imóvel ou acima.
- **Integração INE**: 121 freguesias/concelhos da AML com séries Q4 2022 → Q3 2025 e estimativas lineares Q1-Q4 2026. Dropdown na UI puxa o preço/m² automaticamente.
- **Modo de cálculo de venda**: manual / comparáveis / INE / máx(comparáveis, INE).
- **Simulação preço máximo de aquisição**: dado um ROI alvo (10%, 15%, 20%... 40%), calcula quanto pagar no máximo. Útil para negociar.
- **Modo "Equipa" rápido**: 3 inputs essenciais + defaults sensatos. Para triagem rápida sem precisar de saber as 30 variáveis.
- **Tab Consulta INE**: explorar a tabela de preços medianos como base de dados (pesquisar freguesia, ver crescimento histórico).

## Setup adicional v2

A v2 adiciona dependências `requests`, `beautifulsoup4`, `lxml`. Para correr:

```
.\setup.bat
```

Vai apagar o `.venv` antigo, criar novo, e instalar tudo (incluindo as dependências novas). 1-2 minutos.

## O que faz na v1

Recebe inputs manuais de um deal (preço, VPT, obra, financiamento, ciclo, venda, estrutura fiscal Lda/PF) e devolve:

- Custos detalhados (IMT, IS, notário, IVA obra, juros, IMI, holding, comissão venda, IRC ou mais-valia)
- Equity necessário, lucro bruto e líquido
- ROI total, Cash-on-Cash anualizado, IRR aproximado, margem absoluta
- Stress tests (preço de venda −5/−10/−15%, ciclo +3/+6m, obra +20/+40%)
- Cenário pessimista combinado (V−10% + ciclo+6m + obra+40%) — métrica chave de robustez
- Veredicto verde/amarelo/vermelho com flags justificativos
- Histórico local de deals em `data/deals.json`

## O que NÃO faz na v1 (e está no roadmap)

- Não importa de Idealista (placeholder na tab 3, planeado v1.1)
- Não escreve em Airtable (planeado v1.2)
- Não modela BnH nem capital partner (deliberadamente — a v1 é só F&F)
- Não modela split de propriedade horizontal (planeado v2)

## Estrutura

```
Avaliador de Propriedades/
├── app.py                  # Streamlit UI
├── lib/
│   ├── constants.py        # Tabelas IMT, taxas, defaults
│   ├── taxes.py            # IMT, IS, IMI, IVA obra, IRC, IRS-MV
│   ├── engine.py           # Modelo financeiro F&F
│   ├── robustness.py       # Stress tests + veredicto
│   └── persistence.py      # Save/load deals em data/deals.json
├── data/
│   └── deals.json          # Criado no primeiro guardar
├── requirements.txt
├── setup.bat
├── run.bat
├── avaliador.html          # Versão HTML standalone (fallback, podes ignorar)
└── README.md
```

A pasta tem também várias `.xlsx` de análises anteriores que não interferem.

## Validação dos cálculos

Cada módulo Python tem um `if __name__ == "__main__"` no fundo com um teste rápido. Para correr:

```
.venv\Scripts\activate.bat
python -m lib.taxes
python -m lib.engine
python -m lib.robustness
```

Deve imprimir números coerentes para o deal exemplo (T2 Almada 175k → 250k, obra 25k, ciclo 12m):

- IMT: 3 428,71 €
- IS: 1 400,00 €
- Equity total: 87 979 €
- Lucro líquido: 11 381 €
- ROI total: 12,9% — vermelho (abaixo do target 20%)

Verificação manual do IMT habitação secundária a 175k:
- Bracket 142.618 — 194.458, taxa marginal 5%, parcela 5.321,29 €
- IMT = 175.000 × 0,05 − 5.321,29 = **3.428,71 €** ✓

## Premissas e simplificações

1. **IMT**: tabelas oficiais 2025 (artigo 17.º CIMT). 2026 pode ter ligeira actualização via OE — conferir Portal das Finanças. Tabelas em `lib/constants.py`.
2. **IMI no ciclo**: pro-rata mensal sobre VPT. Em PT é cobrado em prestações com base no titular a 31 Dez. Para análise de viabilidade num F&F de 12-18m, pro-rata é aproximação suficiente.
3. **Financiamento**: amortização sistema francês. Para "interest-only" durante a obra (comum), o cálculo subestima ligeiramente os juros. Diferença pequena em ciclos curtos.
4. **IRC**: 21% + derrama municipal default 1,5%. Sem derrama estadual (só relevante para lucros >1,5M anuais).
5. **Mais-valia PF**: simplificada como 28% sobre 100% da mais-valia. Realidade PT: 50% × marginal IRS, mas para análise de viabilidade conservadora a 28% serve.
6. **Comissão imobiliária**: 5% + IVA 23% por default (configurável).
7. **Custos notário+registo**: 1500€ default (pode variar 800-2500€).
8. **Contingência obra**: 10% por default.

## Targets de referência (Núcleo Assets)

Em `lib/constants.py`:

- ROI total alvo F&F: 20%
- Margem absoluta mínima: 30 000 €
- Ciclo máximo: 18 meses

## Versões fixadas em requirements.txt

```
streamlit==1.32.2
pyarrow==18.1.0
```

Streamlit 1.32 ainda usa Tornado (sem uvicorn/httptools que dão problemas), e estas versões em x64 instalam só com wheels. Em ARM64 o `pyarrow` não tem wheels para nenhuma versão.

## Próximos passos

- v1.1 — Parsing de anúncio Idealista (BeautifulSoup, autofill do formulário). Em Python server-side é trivial — sem CORS issues.
- v1.2 — Integração Airtable (ler deal flow, gravar análises automaticamente)
- v2 — BnH side-by-side (yield bruto/líquido, refi aos 5 anos, equity build-up)
- v2.1 — Capital partner com waterfall configurável
- v3 — Split de prédio em propriedade horizontal (multi-fração)
