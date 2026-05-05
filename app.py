"""
Avaliador de Propriedades — Núcleo Assets (v2)

App Streamlit para análise de viabilidade Fix-and-Flip residencial em PT.

v2: enriquecido com tipo/tipologia/área, obra automática por estado,
comparáveis editáveis, integração INE (preços medianos por freguesia),
simulação preço máximo de aquisição, e parsers de anúncios (Idealista,
Remax, Imovirtual, Casa Sapo).

Correr: streamlit run app.py
"""

import streamlit as st
import pandas as pd

from lib import constants as C
from lib import engine as E
from lib import robustness as R
from lib import persistence as P
from lib import ine as INE
from lib import parsers
from lib import auth


st.set_page_config(
    page_title="Avaliador de Propriedades",
    page_icon="🏠",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Auth gate (skip se não configurado, e.g. desenvolvimento local)
# ---------------------------------------------------------------------------
ok, _user_name, _username = auth.login_screen()
if not ok:
    st.stop()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_eur(v):
    if v is None or v != v:  # NaN check
        return "—"
    return f"{v:,.0f} €".replace(",", " ")


def fmt_pct(v):
    if v is None or v != v:
        return "—"
    return f"{v*100:.1f}%"


def cor_emoji(cor):
    return {"verde": "🟢", "amarelo": "🟡", "vermelho": "🔴", "ok": "🟢"}.get(cor, "⚪")


def init_state():
    """Inicializa session state com defaults."""
    defaults = {
        "modo_app": "Completa",
        "imp_dados": None,         # Dados do parser de URL
        "comparaveis_df": pd.DataFrame([
            {"url": "", "preco": 0, "area_m2": 0, "tipologia": "T2", "comentario": ""},
        ]),
        "analise": None,
        "inputs_obj": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("Avaliador de Propriedades — F&F")
st.caption("v2 · Núcleo Assets · análise local com dados INE + comparáveis + parser de anúncios")

# ---------------------------------------------------------------------------
# Sidebar — modo de uso
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Modo")
    modo = st.radio(
        "Tipo de análise",
        ["Completa", "Rápida (equipa)"],
        index=0,
        help=(
            "Completa: todos os campos, comparáveis, estimativas detalhadas. "
            "Rápida: 3-4 inputs com defaults sensatos. Para triagem rápida."
        ),
    )
    st.session_state["modo_app"] = modo

    st.divider()
    st.caption(
        "Targets Núcleo:\n"
        f"- ROI {fmt_pct(C.TARGET_ROI_FIXANDFLIP)} | "
        f"Margem {fmt_eur(C.TARGET_MARGEM_ABS_MIN)} | "
        f"Ciclo ≤ {C.TARGET_CICLO_MAX_MESES}m"
    )

    backend = P.backend_em_uso()
    st.caption(
        f"Persistência: **{backend}**"
        + (" 🔗" if backend == "airtable" else " 💾")
    )

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_importar, tab_analise, tab_historico, tab_ine = st.tabs([
    "📥 Importar anúncio",
    "📊 Análise",
    "📂 Histórico",
    "📈 Consulta INE",
])

# ===========================================================================
# TAB IMPORTAR — parser de URL
# ===========================================================================

with tab_importar:
    st.subheader("Importar anúncio")
    st.caption(
        "Funciona com Idealista, Remax, Imovirtual, Casa Sapo, Era, Century 21 "
        "e qualquer outro site com SEO decente. Se o URL falhar (Cloudflare etc.), "
        "usa o modo 'Cola texto' — abre o anúncio no browser, Ctrl+A → Ctrl+C, e cola aqui."
    )

    modo_importar = st.radio(
        "Modo",
        ["Por URL", "Cola texto do anúncio"],
        horizontal=True,
        help=(
            "Por URL: tenta descarregar a página automaticamente. "
            "Cola texto: aceita o conteúdo da página (Ctrl+A no anúncio) — "
            "funciona em qualquer site, à prova de anti-bot."
        ),
    )

    if modo_importar == "Por URL":
        url = st.text_input(
            "URL do anúncio",
            placeholder="https://www.idealista.pt/imovel/... ou qualquer site",
        )
        if st.button("Importar", type="primary"):
            if not url:
                st.warning("Cola um URL primeiro.")
            else:
                with st.spinner("A descarregar e parsar..."):
                    dados = parsers.parse_url(url)
                st.session_state["imp_dados"] = dados
                if dados.get("erros"):
                    for e in dados["erros"]:
                        st.warning(e)
                else:
                    st.success(f"Importado de {dados['fonte']}.")
    else:
        # Modo texto livre
        url_origem = st.text_input(
            "URL de origem (opcional, para guardar como referência)",
            placeholder="https://...",
        )
        texto_colado = st.text_area(
            "Cola aqui o texto do anúncio (Ctrl+A na página → Ctrl+C → cola)",
            height=300,
            placeholder=(
                "Exemplo:\n"
                "Apartamento T2 em Olivais, Lisboa\n"
                "250 000 €\n"
                "Área: 77 m²\n"
                "Estado: bom\n"
                "Descrição: ..."
            ),
        )
        if st.button("Importar (texto)", type="primary"):
            if not texto_colado or len(texto_colado.strip()) < 20:
                st.warning("Cola pelo menos 20 caracteres do anúncio.")
            else:
                dados = parsers.parse_texto(texto_colado, url_origem)
                st.session_state["imp_dados"] = dados
                if dados.get("erros"):
                    for e in dados["erros"]:
                        st.warning(e)
                else:
                    st.success("Importado a partir de texto.")

    if st.session_state["imp_dados"]:
        d = st.session_state["imp_dados"]
        st.markdown("### Dados extraídos")
        cols = st.columns(3)
        cols[0].metric("Preço", fmt_eur(d.get("preco")))
        cols[1].metric("Área", f"{d.get('area_m2') or '—'} m²")
        cols[2].metric("Tipologia", d.get("tipologia") or "—")
        cols2 = st.columns(2)
        cols2[0].write(f"**Tipo:** {d.get('tipo_imovel') or '—'}")
        cols2[1].write(f"**Localização:** {d.get('localizacao') or '—'}")
        if d.get("descricao"):
            with st.expander("Descrição"):
                st.write(d["descricao"])
        st.info(
            "Os campos extraídos vão pré-preencher o formulário na tab **Análise**. "
            "Confirma e completa o que faltar (estado de conservação, freguesia INE, etc.)."
        )

# ===========================================================================
# TAB ANÁLISE — formulário + cálculo
# ===========================================================================

with tab_analise:
    imp = st.session_state.get("imp_dados") or {}

    if modo == "Rápida (equipa)":
        # ---- MODO RÁPIDO ----
        st.subheader("Análise rápida")
        st.caption("3 inputs essenciais. Tudo o resto usa defaults sensatos da Núcleo.")

        c1, c2, c3 = st.columns(3)
        with c1:
            preco = st.number_input(
                "Preço pedido (€)", min_value=0.0,
                value=float(imp.get("preco") or 175_000), step=1000.0,
            )
            area = st.number_input(
                "Área (m²)", min_value=0.0,
                value=float(imp.get("area_m2") or 70), step=1.0,
            )
        with c2:
            freguesia_opts = [""] + INE.listar_nomes()
            freguesia = st.selectbox(
                "Freguesia (INE)",
                options=freguesia_opts,
                index=0,
                help="Permite estimar o preço de venda automaticamente via INE.",
            )
            estado = st.selectbox("Estado conservação", C.ESTADOS_CONSERVACAO, index=2)
        with c3:
            ciclo = st.number_input("Ciclo (meses)", min_value=1, value=12)
            tipologia = st.selectbox(
                "Tipologia", C.TIPOLOGIAS,
                index=C.TIPOLOGIAS.index(imp.get("tipologia") or "T2"),
            )

        if st.button("Analisar (rápido)", type="primary", use_container_width=True):
            inputs = E.FFInputs(
                nome_deal=f"Quick {freguesia or 'sem-freguesia'}",
                freguesia=freguesia,
                tipo_imovel=imp.get("tipo_imovel") or "Apartamento",
                tipologia=tipologia,
                area_m2=area,
                estado_conservacao=estado,
                preco_aquisicao=preco,
                vpt=preco * 0.5,  # estimativa default conservadora
                obra_modo="auto",
                ciclo_meses=ciclo,
                venda_modo="ine" if freguesia else "manual",
                preco_venda_manual=preco * 1.4,  # fallback se sem freguesia
                comparaveis=[],
                estrutura="lda",
            )
            st.session_state["analise"] = R.analise_completa(inputs)
            st.session_state["inputs_obj"] = inputs

    else:
        # ---- MODO COMPLETO ----
        st.subheader("Inputs")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Identificação + Imóvel**")
            nome = st.text_input("Nome do deal", value=imp.get("localizacao") or "Deal sem nome")
            link = st.text_input("Link do anúncio", value=imp.get("url") or "")

            tipo = st.selectbox(
                "Tipo imóvel", C.TIPOS_IMOVEL,
                index=C.TIPOS_IMOVEL.index(imp.get("tipo_imovel") or "Apartamento"),
            )
            tipologia = st.selectbox(
                "Tipologia", C.TIPOLOGIAS,
                index=C.TIPOLOGIAS.index(imp.get("tipologia") or "T2"),
            )
            area = st.number_input(
                "Área (m²)", min_value=0.0,
                value=float(imp.get("area_m2") or 70), step=1.0,
            )
            estado = st.selectbox(
                "Estado conservação", C.ESTADOS_CONSERVACAO, index=2,
                help="Determina o custo de obra automático (€/m²).",
            )
            vendedor = st.selectbox("Vendedor", C.VENDEDORES, index=0)

            freguesia_opts = [""] + INE.listar_nomes()
            freg_default = imp.get("localizacao") or ""
            try:
                idx_freg = freguesia_opts.index(freg_default) if freg_default in freguesia_opts else 0
            except ValueError:
                idx_freg = 0
            freguesia = st.selectbox(
                "Freguesia (INE)", options=freguesia_opts, index=idx_freg,
                help="Lista de 121 freguesias/concelhos da AML com preços medianos INE.",
            )

            st.markdown("**Aquisição**")
            preco = st.number_input(
                "Preço aquisição (€)", min_value=0.0,
                value=float(imp.get("preco") or 175_000), step=1000.0,
            )
            vpt = st.number_input("VPT (€)", min_value=0.0, value=90_000.0, step=1000.0)
            tipo_imt = st.selectbox(
                "Tipo IMT", ["secundaria", "hpp", "outros_urbanos", "rustico"], index=0,
            )
            isencao_imt = st.checkbox("Isenção IMT (revenda art. 7º CIMT)")
            cust_not = st.number_input("Notário+registo (€)", value=1500.0, step=100.0)

        with col2:
            st.markdown("**Financiamento**")
            usa_fin = st.checkbox("Usa financiamento bancário", value=True)
            ltv = st.slider("LTV (%)", 0, 90, 70, 5, disabled=not usa_fin) / 100
            taxa_juro = st.number_input("Taxa juro anual (%)", value=5.5, step=0.1, disabled=not usa_fin) / 100
            prazo = st.number_input("Prazo (anos)", value=30, step=1, disabled=not usa_fin)
            comissoes_ab = st.number_input(
                "Comissões abertura+aval (€)", value=1500.0, step=100.0, disabled=not usa_fin,
            )
            seguros = st.number_input("Seguros anuais (€)", value=350.0, step=50.0, disabled=not usa_fin)

            st.markdown("**Obra**")
            obra_modo = st.radio(
                "Modo obra",
                ["auto", "manual"],
                horizontal=True,
                help="Auto = área × €/m² do estado. Manual = inseres o valor.",
            )
            if obra_modo == "auto":
                eur_m2 = C.OBRA_EUR_M2_POR_ESTADO[estado]
                custo_obra_auto = area * eur_m2
                st.caption(
                    f"Estado **{estado}** = {eur_m2} €/m² × {area} m² = "
                    f"**{fmt_eur(custo_obra_auto)}** sem IVA"
                )
                obra_manual = 0.0
            else:
                obra_manual = st.number_input("Custo obra sem IVA (€)", value=20000.0, step=500.0)

            regime_iva = st.selectbox(
                "Regime IVA obra",
                ["verba_2_23", "normal"],
                format_func=lambda x: "6% (Verba 2.23)" if x == "verba_2_23" else "23% (normal)",
            )
            cont = st.slider("Contingência obra (%)", 0, 30, 10, 5) / 100

            st.markdown("**Holding**")
            ciclo = st.number_input("Ciclo (meses)", value=12, step=1, min_value=1)
            taxa_imi = st.number_input("Taxa IMI (%)", value=0.35, step=0.05) / 100
            holding_mes = st.number_input("Custos holding /mês (€)", value=50.0, step=10.0)

        with col3:
            st.markdown("**Estimativa de Venda**")
            venda_modo = st.radio(
                "Modo cálculo venda",
                ["manual", "comparaveis", "ine", "max_comp_ine"],
                format_func=lambda x: {
                    "manual": "Manual (preço fixo)",
                    "comparaveis": "Comparáveis × factor",
                    "ine": "INE × área",
                    "max_comp_ine": "Máx(comparáveis, INE)",
                }[x],
            )

            if venda_modo == "manual":
                preco_venda_manual = st.number_input(
                    "Preço venda (€)", value=250_000.0, step=1000.0,
                )
            else:
                preco_venda_manual = 0.0

            if venda_modo in ("comparaveis", "max_comp_ine"):
                st.caption("Adiciona comparáveis (urls + preço + m² + tipologia)")
                edited_df = st.data_editor(
                    st.session_state["comparaveis_df"],
                    num_rows="dynamic",
                    use_container_width=True,
                    key="comparaveis_editor",
                )
                st.session_state["comparaveis_df"] = edited_df
                factor = st.selectbox(
                    "Ajuste vs imóvel",
                    list(C.COMPARAVEIS_FACTOR.keys()),
                    help="Comparáveis acima do nível do imóvel real → ajuste para baixo.",
                )
            else:
                factor = "Iguais a revenda"

            if venda_modo in ("ine", "max_comp_ine"):
                trims = INE.trimestres_disponiveis()
                trim = st.selectbox(
                    "Trimestre INE",
                    trims,
                    index=trims.index("Q1 2026") if "Q1 2026" in trims else 0,
                )
                # Mostrar preview
                if freguesia:
                    info = INE.get_preco_m2(freguesia, trim)
                    if info:
                        st.caption(
                            f"INE {freguesia} {trim}: **{info['preco_m2']} €/m²** "
                            f"(confidence {info['confidence']}, R²={info['r2']})"
                        )
            else:
                trim = "Q1 2026"

            comissao_imo = st.number_input("Comissão imobiliária (%)", value=5.0, step=0.5) / 100
            comissao_iva = st.checkbox("IVA 23% sobre comissão", value=True)

            st.markdown("**Saída fiscal**")
            estrutura = st.selectbox(
                "Estrutura",
                ["lda", "pf"],
                format_func=lambda x: "Lda (IRC + derrama)" if x == "lda" else "PF (mais-valia 28%)",
            )
            derrama = st.number_input(
                "Derrama municipal (%)", value=1.5, step=0.1, disabled=(estrutura != "lda"),
            ) / 100

        st.divider()
        if st.button("Analisar", type="primary", use_container_width=True):
            # Converter dataframe de comparáveis em lista de dicts
            comp_list = []
            if venda_modo in ("comparaveis", "max_comp_ine"):
                for _, row in st.session_state["comparaveis_df"].iterrows():
                    if row["preco"] and row["area_m2"]:
                        comp_list.append({
                            "url": row["url"],
                            "preco": float(row["preco"]),
                            "area_m2": float(row["area_m2"]),
                            "tipologia": row["tipologia"],
                            "comentario": row.get("comentario", ""),
                        })

            inputs = E.FFInputs(
                nome_deal=nome,
                freguesia=freguesia,
                link_anuncio=link,
                tipo_imovel=tipo,
                tipologia=tipologia,
                area_m2=area,
                estado_conservacao=estado,
                vendedor=vendedor,
                preco_aquisicao=preco,
                vpt=vpt,
                tipo_imt=tipo_imt,
                isencao_imt_revenda=isencao_imt,
                custos_notario_registo=cust_not,
                usa_financiamento=usa_fin,
                ltv=ltv,
                taxa_juro_anual=taxa_juro,
                prazo_anos=prazo,
                comissoes_abertura=comissoes_ab,
                seguros_anuais=seguros,
                obra_modo=obra_modo,
                custo_obra_sem_iva_manual=obra_manual,
                regime_iva_obra=regime_iva,
                contingencia_obra_pct=cont,
                ciclo_meses=ciclo,
                taxa_imi=taxa_imi,
                custos_holding_mensais=holding_mes,
                venda_modo=venda_modo,
                preco_venda_manual=preco_venda_manual,
                comparaveis=comp_list,
                factor_ajuste_comparaveis=factor,
                ine_trimestre=trim,
                comissao_imobiliaria_pct=comissao_imo,
                comissao_imobiliaria_iva=comissao_iva,
                estrutura=estrutura,
                derrama_municipal=derrama,
            )
            st.session_state["analise"] = R.analise_completa(inputs)
            st.session_state["inputs_obj"] = inputs

    # ---- RESULTADOS ----
    if st.session_state.get("analise"):
        a = st.session_state["analise"]
        out = a["outputs"]
        v = a["veredicto"]
        inp = st.session_state["inputs_obj"]

        st.divider()

        # Veredicto
        st.markdown(f"### {cor_emoji(v['cor'])} {v['rotulo']}")
        st.write(v["mensagem"])

        # KPIs
        st.markdown("#### Métricas-chave")
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Lucro líquido", fmt_eur(out["lucro_liquido"]))
        k2.metric("ROI total", fmt_pct(out["roi_total"]),
                  delta=f"target {fmt_pct(C.TARGET_ROI_FIXANDFLIP)}")
        k3.metric("CoC anual", fmt_pct(out["cash_on_cash_anual"]))
        k4.metric("IRR", fmt_pct(out["irr_aproximado"]))
        k5.metric("Equity total", fmt_eur(out["equity_total"]))

        # Preço/m² + venda
        st.markdown("#### Preços por m²")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Preço/m² compra", fmt_eur(out["preco_m2_compra"]))
        k2.metric("Preço/m² venda", fmt_eur(out["preco_m2_venda"]))
        k3.metric("Preço venda usado", fmt_eur(out["preco_venda_usado"]),
                  delta=f"origem: {out['preco_venda_origem']}")
        k4.metric("Margem bruta (% venda)", fmt_pct(out["margem_bruta_pct_venda"]))

        # Flags
        st.markdown("#### Flags")
        for f in a["flags"]:
            ic = {"ok": "🟢", "amarelo": "🟡", "vermelho": "🔴"}[f["nivel"]]
            st.write(f"{ic} {f['mensagem']}")

        # Estimativa de obra (se auto)
        if inp.obra_modo == "auto":
            with st.expander("Estimativa de obra"):
                eur_m2 = C.OBRA_EUR_M2_POR_ESTADO.get(inp.estado_conservacao, 0)
                st.write(
                    f"**{inp.estado_conservacao}** ({eur_m2} €/m²) × {inp.area_m2} m² = "
                    f"**{fmt_eur(out['obra_sem_iva'])}** sem IVA"
                )
                st.write(
                    f"Com IVA ({'6%' if inp.regime_iva_obra == 'verba_2_23' else '23%'}): "
                    f"{fmt_eur(out['obra_com_iva'])}"
                )
                st.write(
                    f"Com contingência ({int(inp.contingencia_obra_pct*100)}%): "
                    f"**{fmt_eur(out['obra_com_contingencia'])}**"
                )

        # Estimativa de venda (se auto)
        if inp.venda_modo != "manual" and "venda_estimativa" in out["breakdown"]:
            with st.expander("Estimativa de venda"):
                vest = out["breakdown"]["venda_estimativa"]
                st.write(f"Origem: **{vest.get('origem', '—')}**")
                if "comparaveis" in vest:
                    cinfo = vest["comparaveis"]
                    st.write(
                        f"Comparáveis: {cinfo['n_comparaveis_validos']} válidos. "
                        f"Média {fmt_eur(cinfo['preco_m2_medio'])}/m². "
                        f"Factor {cinfo['factor_aplicado']}. "
                        f"Ajustado: {fmt_eur(cinfo['preco_m2_ajustado'])}/m². "
                        f"× {inp.area_m2} m² = **{fmt_eur(cinfo['preco_venda'])}**"
                    )
                if "ine" in vest:
                    iinfo = vest["ine"]
                    st.write(
                        f"INE {iinfo['location']} ({iinfo['trimestre']}): "
                        f"**{iinfo['preco_m2']}** €/m² × {inp.area_m2} m² = "
                        f"**{fmt_eur(iinfo['preco_venda'])}** "
                        f"(confidence {iinfo['confidence']})"
                    )

        # Breakdown
        with st.expander("Breakdown de custos"):
            for label, val in [
                ("IMT", out["imt"]),
                ("IS (transmissão)", out["is_transmissao"]),
                ("Notário+registo", inp.custos_notario_registo),
                ("Custos compra total", out["custos_compra_total"]),
                ("Obra (final com IVA + cont.)", out["obra_com_contingencia"]),
                ("Juros ciclo (+comissões)", out["juros_pagos_ciclo"]),
                ("IMI ciclo", out["imi_ciclo"]),
                ("Holding (condomínio etc)", out["custos_holding_total"]),
                ("Seguros ciclo", out["seguros_ciclo"]),
                ("Custos venda (comissão)", out["custos_venda"]),
                ("Imposto saída", out["imposto_saida"]),
                ("**Lucro líquido**", out["lucro_liquido"]),
                ("Equity aquisição", out["equity_aquisicao"]),
                ("Equity obra", out["equity_obra"]),
                ("**Equity total**", out["equity_total"]),
                ("Valor empréstimo", out["valor_emprestimo"]),
            ]:
                st.write(f"**{label}:** {fmt_eur(val)}")

        # Stress tests
        st.markdown("#### Stress tests")
        s1, s2, s3 = st.columns(3)
        with s1:
            st.write("**Preço de venda**")
            st.dataframe(
                [{"Cenário": r["cenario"], "Preço": fmt_eur(r["preco_venda"]),
                  "Lucro": fmt_eur(r["lucro_liquido"]), "ROI": fmt_pct(r["roi_total"])}
                 for r in a["stress_preco"]],
                hide_index=True, use_container_width=True,
            )
        with s2:
            st.write("**Ciclo (atrasos)**")
            st.dataframe(
                [{"Cenário": r["cenario"], "Ciclo": f"{r['ciclo_meses']}m",
                  "Lucro": fmt_eur(r["lucro_liquido"]), "CoC": fmt_pct(r["cash_on_cash_anual"])}
                 for r in a["stress_ciclo"]],
                hide_index=True, use_container_width=True,
            )
        with s3:
            st.write("**Custo obra**")
            st.dataframe(
                [{"Cenário": r["cenario"], "Obra": fmt_eur(r["obra_sem_iva"]),
                  "Lucro": fmt_eur(r["lucro_liquido"]), "ROI": fmt_pct(r["roi_total"])}
                 for r in a["stress_obra"]],
                hide_index=True, use_container_width=True,
            )

        # Pessimista
        p = a["stress_pessimista"]
        st.write(f"**Cenário pessimista combinado** (V −10%, ciclo +6m, obra +40%): "
                 f"Lucro {fmt_eur(p['lucro_liquido'])} | ROI {fmt_pct(p['roi_total'])}")

        # Simulação preço máximo
        st.markdown("#### Simulação: preço máximo de aquisição por ROI alvo")
        try:
            sim = E.tabela_preco_max_aquisicao(inp)
            st.dataframe(
                [{
                    "ROI alvo": fmt_pct(r["roi_alvo"]),
                    "Preço máx aquisição": fmt_eur(r.get("preco_max")),
                    "Lucro líquido": fmt_eur(r.get("lucro_liquido")),
                    "ROI obtido": fmt_pct(r.get("roi_obtido")),
                } for r in sim],
                hide_index=True, use_container_width=True,
            )
            st.caption(
                "Dado o preço de venda estimado (e tudo o resto), quanto pagar no máximo "
                "para atingir cada ROI. Útil para negociar com o vendedor."
            )
        except Exception as e:
            st.warning(f"Simulação falhou: {e}")

        st.divider()
        # ---- Submeter ao Núcleo OS (Airtable) ou guardar local (dev) ----
        backend = P.backend_em_uso()
        if backend == "airtable":
            st.markdown("### Submeter ao Núcleo OS")
            st.caption(
                "Cria/actualiza Activo + Triagem I. Se houver dados do agente, "
                "cria/linka Contacto."
            )

            # Inputs do agente para popular Contactos
            ag1, ag2 = st.columns(2)
            with ag1:
                ag_nome = st.text_input(
                    "Agente — Primeiro Nome",
                    value=imp.get("agente_nome", "") if imp else "",
                )
                ag_apelido = st.text_input(
                    "Agente — Último Nome",
                    value=imp.get("agente_apelido", "") if imp else "",
                )
                ag_sou = st.selectbox(
                    "Sou",
                    ["Agente Imobiliário", "Proprietário"],
                    index=0,
                )
            with ag2:
                ag_tel = st.text_input("Agente — Telemóvel", value="")
                ag_email = st.text_input("Agente — Email", value="")
                ag_msg = st.text_input(
                    "Agente — Notas",
                    value=imp.get("agente_agencia", "") if imp else "",
                )

            canal_origem = st.selectbox(
                "Canal de origem",
                C.CANAIS_ORIGEM,
                index=C.CANAIS_ORIGEM.index(
                    C.PARSER_PARA_CANAL.get(
                        (imp.get("fonte") if imp else "outro"), "Outro"
                    )
                ) if imp else C.CANAIS_ORIGEM.index("Outro"),
            )

            if st.button("📤 Submeter ao Núcleo OS", type="primary"):
                # Anexar canal_origem e agente aos inputs antes de guardar
                inputs_completos = dict(a["inputs"])
                inputs_completos["canal_origem"] = canal_origem
                agente_dados = {
                    "primeiro_nome": ag_nome.strip(),
                    "ultimo_nome": ag_apelido.strip(),
                    "sou": ag_sou,
                    "telemovel": ag_tel.strip(),
                    "email": ag_email.strip(),
                    "mensagem": ag_msg.strip(),
                }

                try:
                    with st.spinner("A submeter ao Núcleo OS..."):
                        triagem_id = P.guardar_deal({
                            "inputs": inputs_completos,
                            "outputs": a["outputs"],
                            "flags": a["flags"],
                            "veredicto": a["veredicto"],
                            "agente_dados": agente_dados,
                        })
                    st.success(
                        f"✅ Submetido ao Núcleo OS. Triagem id: `{triagem_id}`. "
                        f"Vai à base Núcleo OS para ver/ajustar."
                    )
                except Exception as e:
                    st.error(f"Falha ao submeter: {type(e).__name__}: {e}")
        else:
            if st.button("💾 Guardar deal localmente"):
                deal_id = P.guardar_deal({
                    "inputs": a["inputs"], "outputs": a["outputs"],
                    "flags": a["flags"], "veredicto": a["veredicto"],
                    "stress_pessimista": a["stress_pessimista"],
                })
                st.success(f"Deal guardado localmente: {deal_id}")
                st.caption(
                    "Sem secrets Airtable configurados — modo desenvolvimento. "
                    "Em produção (Streamlit Cloud), submete ao Núcleo OS."
                )


# ===========================================================================
# TAB HISTÓRICO
# ===========================================================================

with tab_historico:
    st.subheader("Deals guardados")
    deals = P.listar_deals()
    if not deals:
        st.info("Sem deals guardados ainda.")
    else:
        st.write(f"{len(deals)} deal(s).")
        for d in reversed(deals):
            inp = d["inputs"]
            out = d["outputs"]
            ver = d["veredicto"]
            with st.expander(
                f"{cor_emoji(ver['cor'])} {inp.get('nome_deal', '?')} — "
                f"{inp.get('freguesia', '')} · "
                f"Lucro {fmt_eur(out.get('lucro_liquido'))} · "
                f"ROI {fmt_pct(out.get('roi_total'))} · "
                f"{d['criado_em']}"
            ):
                st.write(f"**Veredicto:** {ver['rotulo']} — {ver['mensagem']}")
                if st.button("🗑️ Eliminar", key=f"del_{d['id']}"):
                    P.eliminar_deal(d["id"])
                    st.rerun()

# ===========================================================================
# TAB CONSULTA INE
# ===========================================================================

with tab_ine:
    st.subheader("Preços medianos INE — consulta")
    st.caption(
        "Tabela com 121 freguesias/concelhos da AML. Séries históricas Q4 2022 → Q3 2025 "
        "+ estimativas lineares para 2026 (R² e confidence indicam qualidade da projecção)."
    )

    busca = st.text_input("Pesquisar freguesia ou concelho", placeholder="ex: Almada, Venteira")
    resultados = INE.procurar(busca) if busca else INE.listar_locais()

    st.write(f"{len(resultados)} resultados")
    df = pd.DataFrame([{
        "Local": r["location"],
        "NUTS": r["nuts_code"],
        "Tipo": r["level"],
        "Q3 2025": r["historico"].get("Q3 2025"),
        "Est. Q1 2026": r["estimativas_2026"].get("Q1 2026"),
        "Est. Q4 2026": r["estimativas_2026"].get("Q4 2026"),
        "Crescimento %": r.get("growth_pct"),
        "R²": r.get("r2"),
        "Confidence": r.get("confidence"),
    } for r in resultados[:50]])
    st.dataframe(df, hide_index=True, use_container_width=True)
