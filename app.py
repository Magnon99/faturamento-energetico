
# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os, shutil, subprocess
from src.faturamento.calculos import dm_measured, dre_calc, ere_calc, monthly_energy
from src.faturamento.formatacao import RS, latex_num
from src.faturamento.perfis import _center_in_window, _fmt_h, apply_interval_values, copy_profile_values, default_profile, empty_profile, hour_overlap, hour_overlap_frac
from src.faturamento.tarifas import TARIFAS, get_bandeiras, get_tarifas

# ====================================================
#  Aplicação de Faturamento de Energia Elétrica
#  - REN 1000 + NDU 002 (EMS)
#  - Ultrapassagem: seletor Franquia vs Degrau
#  - Seleção tarifária por vigência, subgrupo e classe
#  - Componentes do faturamento configuráveis
#  - Botão Calcular (nada reativa até submeter)
#  - Relatório LaTeX/PDF com números
# ====================================================

st.set_page_config(page_title="Faturamento de Energia Elétrica", page_icon="⚡", layout="wide")
st.markdown("### ⚡ Aplicação de Faturamento de Energia Elétrica")
st.caption("Desenvolvido por **Magnon Rychard Alexandre Silva de Faria**")
st.caption("Configuração tarifária baseada na estrutura EMS, com suporte a modalidade, subgrupo, classe e vigência. Regras: REN 1000 + NDU 002 (EMS).")

# ---------- Sidebar ----------
with st.sidebar:
    st.subheader("⚙️ Parâmetros gerais")
    input_mode = st.radio("Modo de entrada", ["Curva horária", "Valores resumidos por posto"], index=0,
                          help="Selecione se as grandezas de energia e demanda medida serão informadas por curva horária ou por valores consolidados por posto tarifário.")
    resumo_mode = input_mode == "Valores resumidos por posto"
    modalidade = st.selectbox("Modalidade", ["Verde", "Azul (DC único)", "Azul — 2 Contratos"], index=0,
                              help="Selecione a modalidade tarifária aplicável ao estudo.")
    modalidade_tarifaria = "Verde" if modalidade == "Verde" else "Azul"

    vigencias_disponiveis = list(TARIFAS["EMS"]["vigencias"].keys())
    vigencia_default = "2025-04-08"
    vigencia = st.selectbox(
        "Vigência tarifária",
        vigencias_disponiveis,
        index=(vigencias_disponiveis.index(vigencia_default) if vigencia_default in vigencias_disponiveis else 0),
        help="Selecione a vigência da tabela tarifária da EMS.",
    )
    vigencia_data = TARIFAS["EMS"]["vigencias"][vigencia]

    subgrupos_modalidade = vigencia_data["grupo_a"][modalidade_tarifaria]
    ordem_subgrupos = ["A2", "A3", "A3a", "A4"]
    subgrupos_disponiveis = [sg for sg in ordem_subgrupos if sg in subgrupos_modalidade]
    subgrupo_default = "A4"
    subgrupo = st.selectbox(
        "Subgrupo do Grupo A",
        subgrupos_disponiveis,
        index=(subgrupos_disponiveis.index(subgrupo_default) if subgrupo_default in subgrupos_disponiveis else 0),
        format_func=lambda sg: f"{sg} — {subgrupos_modalidade[sg]['label']}",
        help="Selecione o subgrupo tarifário para carregar os valores padrão da EMS.",
    )

    classes_disponiveis = list(subgrupos_modalidade[subgrupo]["classes"].keys())
    classe_default = "Demais Classes"
    classe = st.selectbox(
        "Classe",
        classes_disponiveis,
        index=(classes_disponiveis.index(classe_default) if classe_default in classes_disponiveis else 0),
        help="Selecione a classe tarifária para carregar os valores padrão da EMS.",
    )
    if modalidade_tarifaria == "Verde":
        st.caption("Para a modalidade Verde nesta vigência, os subgrupos tarifários disponíveis na base atual são os compatíveis cadastrados.")

    if not resumo_mode:
        ponta_start = st.number_input("Início da Ponta (h, aceita .5)", 0.0, 23.5, 17.0, step=0.5, help="Exemplo: 17h30–20h30 corresponde a 17.5 e 20.5.")
        ponta_end   = st.number_input("Fim da Ponta (h, aceita .5)", 1.0, 24.0, 20.0, step=0.5, help="Ex.: 20.5 significa centro até 20:30.")
        dias_uteis  = st.number_input("Dias Úteis do mês", 0, 27, 22)
        dias_fds    = st.number_input("Dias FDS/Feriados do mês", 0, 10, 8)
        perfil_mode = st.radio("Perfis de carga", ["Único (todo mês)", "Separados (Úteis x FDS)"], index=1,
                               help="Use 'Separados' se precisar perfis diferentes entre semana e FDS.")
        st.markdown("---")
        st.write("**Reativo / Fator de Potência** (NDU)")
        capacit_on = st.checkbox("Cobrar ERE capacitiva apenas em janela horária", value=True,
                                 help="Se marcado: **capacit.** só dentro da janela e **indutivo** só fora dela. A cobrança ocorre apenas quando **FP<0,92** (REN 1000).")
        cap_start  = st.number_input("Início janela capacitiva (h, aceita .5)", 0.0, 23.5, 0.0, step=0.5)
        cap_dur    = st.number_input("Duração janela capacitiva (h)", 0.5, 24.0, 6.0, step=0.5)
        isentar_ind_0_6 = st.checkbox("Isentar reativo INDUTIVO de 00–06h", value=False,
                                      help="Ative se o critério adotado para o estudo considerar isenção do indutivo entre 00h e 06h.")
        medir_sec = st.checkbox("Medição no secundário (<69 kV)? aplicar 2,5% nas quantidades de ERE/DRE", value=False,
                                 help="REN 1000 Art. 305: quando a medição é no secundário, aplica-se 2,5% às quantidades medidas (ERE/DRE).")
    else:
        ponta_start, ponta_end = 17.0, 20.0
        dias_uteis, dias_fds = 0, 0
        perfil_mode = "Separados (Úteis x FDS)"
        capacit_on = True
        cap_start = 0.0
        cap_dur = 6.0
        isentar_ind_0_6 = False
        medir_sec = False
    perdas_factor = 1.025 if medir_sec else 1.0
    st.markdown("---")
    if modalidade == "Azul (DC único)":
        dc_single = st.number_input("DC (kW) — vale para PONTA e FORA", 0.0, 100000.0, 130.0, step=1.0)
        dc_p, dc_fp = dc_single, dc_single
    elif modalidade == "Azul — 2 Contratos":
        dc_p = st.number_input("DC PONTA (kW)", 0.0, 100000.0, 150.0, step=1.0)
        dc_fp = st.number_input("DC FORA (kW)", 0.0, 100000.0, 120.0, step=1.0)
    else:
        dc_v = st.number_input("Demanda Contratada (kW) — Verde", 0.0, 100000.0, 130.0, step=1.0)

    aplica_tol = st.checkbox("Aplicar tolerância na ULTRAPASSAGEM [DC × (1 + tolerância)]", value=False,
                             help="Ative se a questão especificar uma tolerância (ex.: 5%).")
    toler = st.number_input("Tolerância (fração)", 0.0, 0.2, 0.05, step=0.01, help="0,05 = 5%")

    ultra_mode = st.radio("Regra da tolerância (Ultrapassagem)",
                          ["Franquia (DM − DC×(1+τ))", "Degrau (se passou: DM − DC)"],
                          index=0,
                          help="Selecione a metodologia de aplicação da tolerância para a ultrapassagem.")

    st.markdown("---")
    st.write("**GMG / Simulações**")
    sim_gmg = st.checkbox("Simular suprimento por GMG na ponta", value=False,
                          help="Quando ativo, a tarifa de energia na ponta (TE_P) passa a usar o custo informado para o GMG.")
    custo_gmg = st.number_input("Custo GMG — R$/kWh", 0.0, 10.0, 1.40, step=0.01)

    st.markdown("---")
    st.write("**Impostos**")
    pis    = st.number_input("PIS (%)", 0.0, 20.0, 1.08, step=0.01, help="Item (g): preencha aqui as alíquotas e o app aplica o gross-up.")
    cofins = st.number_input("COFINS (%)", 0.0, 20.0, 7.60, step=0.01)
    icms   = st.number_input("ICMS (%)", 0.0, 40.0, 17.0, step=0.1)
    ignorar_tributos = st.checkbox("Desprezar ICMS, PIS e COFINS (conta = subtotal)", value=False,
                                   help="Use para itens que pedem 'despreze os impostos'.")

    st.markdown("---")
    st.write("**Bandeira Tarifária**")
    st.caption("Cada bloco representa uma bandeira com seu consumo associado em kWh.")
    st.caption("Se houver apenas uma bandeira no período, preencha apenas um bloco e deixe os demais zerados.")
    st.caption("A soma dos blocos corresponde ao custo total das bandeiras aplicadas ao período faturado.")
    bandeiras_vigencia = get_bandeiras(distribuidora="EMS", vigencia=vigencia)
    opcoes_bandeira = list(bandeiras_vigencia.keys())
    aplicar_impostos_bandeira = st.checkbox(
        "Aplicar impostos sobre a bandeira",
        value=True,
        help="Se desmarcado, o custo total da bandeira é adicionado após o gross-up, fora da base de impostos.",
    )
    bandeira_blocos = []
    for idx in range(3):
        st.caption(f"Bloco {idx + 1}")
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            bloco_bandeira = st.selectbox(
                f"Tipo de bandeira — bloco {idx + 1}",
                opcoes_bandeira,
                index=(opcoes_bandeira.index("Verde") if "Verde" in opcoes_bandeira else 0),
                key=f"bandeira_tipo_{idx}",
            )
        with b_col2:
            bloco_kwh = st.number_input(
                f"Consumo associado (kWh) — bloco {idx + 1}",
                0.0,
                100000000.0,
                0.0,
                step=1.0,
                key=f"bandeira_kwh_{idx}",
            )
        bandeira_blocos.append(
            {
                "tipo": bloco_bandeira,
                "kwh": float(bloco_kwh),
                "tarifa": bandeiras_vigencia[bloco_bandeira]["adicional_r_kwh"],
            }
        )

    st.markdown("---")
    st.write("**Componentes Extras Manuais**")
    cip = st.number_input(
        "Contribuição de iluminação pública / CIP (R$)",
        0.0,
        100000000.0,
        0.0,
        step=0.01,
        format="%.2f",
        help="Valor opcional somado apenas ao final da conta.",
    )
    bonus_credito = st.number_input(
        "Bônus / crédito / ajuste manual (R$)",
        0.0,
        100000000.0,
        0.0,
        step=0.01,
        format="%.2f",
        help="Valor opcional subtraído apenas ao final da conta.",
    )

    st.divider()
    st.markdown("**Tarifas (editáveis)**")
    preset_vals = get_tarifas(
        distribuidora="EMS",
        vigencia=vigencia,
        modalidade=modalidade_tarifaria,
        subgrupo=subgrupo,
        classe=classe,
    )
    te_p_default = custo_gmg if sim_gmg else preset_vals["TE_P"]
    te_p = st.number_input("Energia (consumo) PONTA — R$/kWh", 0.0, 5.0,
                         te_p_default, step=0.00001, format="%.5f",
                         help="Se 'Simular GMG' estiver ativo, usa o custo do GMG na ponta.")
    te_fp  = st.number_input("Energia (consumo) FORA — R$/kWh", 0.0, 5.0, preset_vals["TE_FP"], step=0.00001, format="%.5f")
    td_p   = st.number_input("Demanda — PONTA (R$/kW)", 0.0, 1000.0, preset_vals["TD_P"], step=0.01,
                         help="Verde não usa Demanda de PONTA.")
    td_fp  = st.number_input("Demanda — FORA/Verde (R$/kW)", 0.0, 1000.0, preset_vals["TD_FP"], step=0.01)
    ul_p   = st.number_input("Ultrapassagem — PONTA (R$/kW)", 0.0, 1000.0, preset_vals["UL_P"], step=0.01)
    ul_fp  = st.number_input("Ultrapassagem — FORA/Verde (R$/kW)", 0.0, 1000.0, preset_vals["UL_FP"], step=0.01)
    vr_dre = st.number_input("VR_DRE — R$/kW (Demanda Reativa Excedente)", 0.0, 1000.0, preset_vals["VR_DRE"], step=0.01,
                          help="Valor de referência para cálculo da Demanda Reativa Excedente (DRE).")
    vr_ere = st.number_input("VR_ERE — R$/kWh (Energia Reativa Excedente)", 0.0, 10.0, preset_vals["VR_ERE"], step=0.00001)
    bdv    = st.number_input("BDV (R$/kWh)", 0.0, 2.0, 0.0, step=0.00001, format="%.5f",
                         help="Benefício de Desenvolvimento (se houver) aplicado sobre a energia total.")

    st.divider()
    st.markdown("**Componentes do Faturamento**")
    calc_dem_ener = st.checkbox("Incluir **Demanda e Energia**", value=True,
                                help="Mantém os componentes principais de demanda faturada e consumo de energia.")
    calc_ultra    = st.checkbox("Calcular **Ultrapassagem** (quando houver) — usa regra acima", value=True,
                                help="Inclui a cobrança de ultrapassagem conforme a regra selecionada acima.")
    if not resumo_mode:
        calc_ere      = st.checkbox("Calcular **ERE** (Energia Reativa Excedente)", value=True,
                                    help="Inclui a cobrança de Energia Reativa Excedente quando aplicável.")
        calc_dre      = st.checkbox("Calcular **DRE** (Demanda Reativa Excedente)", value=True,
                                    help="Inclui a cobrança de Demanda Reativa Excedente quando aplicável.")
    else:
        calc_ere = st.checkbox("Calcular **ERE simplificada por posto**", value=True,
                               help="No modo resumido, calcula a Energia Reativa Excedente a partir da energia e do fator de potência informados por posto tarifário.")
        if modalidade.startswith("Azul"):
            calc_dre = st.checkbox("Calcular **DRE simplificada por posto**", value=True,
                                   help="No modo resumido, calcula a Demanda Reativa Excedente a partir da demanda medida, do fator de potência por posto e da demanda faturável apurada pelo app.")
        else:
            calc_dre = False
    if resumo_mode:
        if modalidade.startswith("Azul"):
            st.info("No modo de valores resumidos por posto, ERE e DRE usam modelos simplificados por posto tarifário.")
        else:
            st.info("No modo de valores resumidos por posto, a ERE é calculada por modelo simplificado por posto tarifário. A DRE permanece indisponível nesta fase para a modalidade Verde.")

# ---------- Helpers ----------
def _make_initial_profile(ps, pe, perfil_inicial, for_fds=False):
    if perfil_inicial == "Zerado":
        return empty_profile(ps, pe, for_fds=for_fds)
    return default_profile(ps, pe, for_fds=for_fds)


def plot_barras(df, titulo, dc_lines=None):
    fig, ax = plt.subplots(figsize=(10.2,4.6))
    x = np.arange(24); ax.bar(x, df["kW"]); ax.set_xlim(-0.5, 23.5)
    ax.set_xticks(x); ax.set_xticklabels([f"{h}-{h+1}" if h%2==0 else "" for h in x], fontsize=8)
    ax.set_ylabel("Potência (kW)"); ax.set_title(titulo, fontsize=12, weight="bold")
    ax.grid(True, axis="y", alpha=0.25, linestyle="--", dashes=(2,2))
    if dc_lines:
        for val, label, style in dc_lines: ax.axhline(val, linestyle=style, linewidth=1.8, label=label)
        ax.legend(loc="upper left", fontsize=9, ncol=3, frameon=False)
    cell_text = [[f"{v:.1f}" for v in df["kW"].tolist()],
                 [f"{v:.2f}" for v in df["FP"].tolist()]]
    the_table = plt.table(cellText=cell_text, rowLabels=["Potência","Fat. Pot. (ind.)"],
                          colLabels=[f"{h}-{h+1}" for h in x],
                          loc="bottom", cellLoc="center", rowLoc="center")
    the_table.auto_set_font_size(False); the_table.set_fontsize(6.5); the_table.scale(1, 1.2)
    plt.subplots_adjust(left=0.05, right=0.995, top=0.88, bottom=0.28)
    return fig

# ---------- Formulário com tabelas ----------
if not resumo_mode:
    st.markdown("#### Configuração dos Perfis")
    perfil_inicial = st.radio("Perfil inicial", ["Zerado", "Padrão"], index=1,
                              help="Escolha se as tabelas devem iniciar zeradas ou com o perfil padrão do app.")

    perfil_editor_signature = (input_mode, perfil_mode, perfil_inicial, ponta_start, ponta_end)
    if st.session_state.get("perfil_editor_signature") != perfil_editor_signature:
        if perfil_mode == "Único (todo mês)":
            st.session_state.perfil_all = _make_initial_profile(ponta_start, ponta_end, perfil_inicial, for_fds=False)
            st.session_state.pop("perfil_u_edit", None)
            st.session_state.pop("perfil_f_edit", None)
        else:
            st.session_state.perfil_u_edit = _make_initial_profile(ponta_start, ponta_end, perfil_inicial, for_fds=False)
            st.session_state.perfil_f_edit = _make_initial_profile(ponta_start, ponta_end, perfil_inicial, for_fds=True)
            st.session_state.pop("perfil_all", None)
        st.session_state.perfil_editor_signature = perfil_editor_signature
        st.session_state.calc_done = False

    with st.form("form_tabelas"):
        st.markdown("#### Preenchimento por Intervalo")
        c_fill_1, c_fill_2, c_fill_3 = st.columns(3)
        with c_fill_1:
            if perfil_mode == "Único (todo mês)":
                destino_intervalo = "Perfil Único"
                st.caption("Aplicação em lote no perfil exibido.")
            else:
                destino_intervalo = st.selectbox("Aplicar em", ["Dias Úteis", "FDS / Feriados"], index=0)
        with c_fill_2:
            hora_inicial_lote = st.number_input("Hora inicial", 0, 23, 0, step=1)
            hora_final_lote = st.number_input("Hora final (inclusiva)", 0, 23, 23, step=1)
        with c_fill_3:
            kw_lote = st.number_input("kW do intervalo", 0.0, 100000.0, 0.0, step=1.0)
            fp_lote = st.number_input("FP do intervalo", 0.0, 1.0, 0.92, step=0.01, format="%.2f")
            tipo_fp_lote = st.selectbox("Tipo_FP do intervalo", ["Indutivo", "Capacitivo", "Neutro"], index=2)

        c_action_1, c_action_2, c_action_3, c_action_4 = st.columns(4)
        with c_action_1:
            aplicar_lote = st.form_submit_button("Aplicar intervalo")
        if perfil_mode == "Separados (Úteis x FDS)":
            with c_action_2:
                copiar_u_f = st.form_submit_button("Copiar Úteis -> FDS")
            with c_action_3:
                copiar_f_u = st.form_submit_button("Copiar FDS -> Úteis")
        else:
            copiar_u_f = False
            copiar_f_u = False
        with c_action_4:
            calc = st.form_submit_button("🚀 Calcular")

        if perfil_mode == "Único (todo mês)":
            st.markdown("#### Perfil de Carga — **Único** (vale para úteis e FDS)")
            if "perfil_all" not in st.session_state:
                st.session_state.perfil_all = _make_initial_profile(ponta_start, ponta_end, perfil_inicial, for_fds=False)
            perfil_all = st.data_editor(st.session_state.perfil_all, num_rows="fixed", use_container_width=True, hide_index=True,
                                        key="editor_all",
                                        column_config={
                                            "Tipo_FP": st.column_config.SelectboxColumn(options=["Indutivo","Capacitivo","Neutro"]),
                                            "Posto": st.column_config.SelectboxColumn(options=["P","FP"]),
                                        })
        else:
            st.markdown("#### Perfil — **Dias Úteis**")
            if "perfil_u_edit" not in st.session_state:
                st.session_state.perfil_u_edit = _make_initial_profile(ponta_start, ponta_end, perfil_inicial, for_fds=False)
            perfil_u_edit = st.data_editor(st.session_state.perfil_u_edit, num_rows="fixed", use_container_width=True, hide_index=True,
                                           key="editor_u",
                                           column_config={
                                               "Tipo_FP": st.column_config.SelectboxColumn(options=["Indutivo","Capacitivo","Neutro"]),
                                               "Posto": st.column_config.SelectboxColumn(options=["P","FP"]),
                                           })
            st.markdown("#### Perfil — **FDS / Feriados** (sempre fora de ponta)")
            if "perfil_f_edit" not in st.session_state:
                st.session_state.perfil_f_edit = _make_initial_profile(ponta_start, ponta_end, perfil_inicial, for_fds=True)
            perfil_f_edit = st.data_editor(st.session_state.perfil_f_edit, num_rows="fixed", use_container_width=True, hide_index=True,
                                           key="editor_f",
                                           column_config={"Tipo_FP": st.column_config.SelectboxColumn(options=["Indutivo","Capacitivo","Neutro"])})
else:
    perfil_inicial = "Padrão"
    aplicar_lote = copiar_u_f = copiar_f_u = False
    perfil_editor_signature = (input_mode,)
    if st.session_state.get("perfil_editor_signature") != perfil_editor_signature:
        st.session_state.perfil_editor_signature = perfil_editor_signature
        st.session_state.calc_done = False

    with st.form("form_resumido"):
        st.markdown("#### Valores Resumidos por Posto")
        r1, r2 = st.columns(2)
        with r1:
            resumo_energia_p = st.number_input("Energia PONTA (kWh)", 0.0, 100000000.0, 0.0, step=1.0)
        with r2:
            resumo_energia_fp = st.number_input("Energia FORA DE PONTA (kWh)", 0.0, 100000000.0, 0.0, step=1.0)

        if modalidade.startswith("Azul"):
            r3, r4 = st.columns(2)
            with r3:
                resumo_dm_p = st.number_input("Demanda medida PONTA (kW)", 0.0, 1000000.0, 0.0, step=1.0)
            with r4:
                resumo_dm_fp = st.number_input("Demanda medida FORA DE PONTA (kW)", 0.0, 1000000.0, 0.0, step=1.0)
            resumo_dm_g = max(resumo_dm_p, resumo_dm_fp)
        else:
            resumo_dm_g = st.number_input("Demanda medida geral (kW)", 0.0, 1000000.0, 0.0, step=1.0)
            resumo_dm_p = 0.0
            resumo_dm_fp = 0.0

        st.markdown("#### Fator de Potência — ERE simplificada por posto")
        r5, r6, r7 = st.columns(3)
        with r5:
            resumo_fp_p = st.number_input("FP na ponta", 0.01, 1.0, 0.92, step=0.01, format="%.2f")
        with r6:
            resumo_fp_fp = st.number_input("FP fora de ponta", 0.01, 1.0, 0.92, step=0.01, format="%.2f")
        with r7:
            resumo_fp_ref = st.number_input("FP de referência", 0.01, 1.0, 0.92, step=0.01, format="%.2f",
                                            help="Usado apenas na ERE simplificada por posto deste modo de entrada.")

        if modalidade.startswith("Azul"):
            st.info("Neste modo, energia e demanda medida são informadas diretamente por posto tarifário. ERE e DRE usam modelos simplificados por posto.")
        else:
            st.info("Neste modo, energia e demanda medida são informadas diretamente por posto tarifário. A ERE usa um modelo simplificado por posto. A DRE permanece indisponível nesta fase para a modalidade Verde.")
        calc = st.form_submit_button("🚀 Calcular")

if "calc_done" not in st.session_state: st.session_state.calc_done = False
if not resumo_mode and aplicar_lote:
    if perfil_mode == "Único (todo mês)":
        st.session_state.perfil_all = apply_interval_values(
            perfil_all.copy(),
            hora_inicial_lote,
            hora_final_lote,
            kw=kw_lote,
            fp=fp_lote,
            tipo_fp=tipo_fp_lote,
        )
    else:
        st.session_state.perfil_u_edit = perfil_u_edit.copy()
        st.session_state.perfil_f_edit = perfil_f_edit.copy()
        if destino_intervalo == "Dias Úteis":
            st.session_state.perfil_u_edit = apply_interval_values(
                st.session_state.perfil_u_edit,
                hora_inicial_lote,
                hora_final_lote,
                kw=kw_lote,
                fp=fp_lote,
                tipo_fp=tipo_fp_lote,
            )
        else:
            st.session_state.perfil_f_edit = apply_interval_values(
                st.session_state.perfil_f_edit,
                hora_inicial_lote,
                hora_final_lote,
                kw=kw_lote,
                fp=fp_lote,
                tipo_fp=tipo_fp_lote,
            )
    st.rerun()

if not resumo_mode and copiar_u_f:
    st.session_state.perfil_u_edit = perfil_u_edit.copy()
    st.session_state.perfil_f_edit = copy_profile_values(perfil_u_edit.copy(), perfil_f_edit.copy())
    st.rerun()

if not resumo_mode and copiar_f_u:
    st.session_state.perfil_f_edit = perfil_f_edit.copy()
    st.session_state.perfil_u_edit = copy_profile_values(perfil_f_edit.copy(), perfil_u_edit.copy())
    st.rerun()

if calc:
    if resumo_mode:
        st.session_state.resumo_inputs = {
            "kwh_p": float(resumo_energia_p),
            "kwh_fp": float(resumo_energia_fp),
            "dm_p": float(resumo_dm_p),
            "dm_fp": float(resumo_dm_fp),
            "dm_g": float(resumo_dm_g),
            "fp_p": float(resumo_fp_p),
            "fp_fp": float(resumo_fp_fp),
            "fp_ref": float(resumo_fp_ref),
        }
    else:
        if perfil_mode == "Único (todo mês)":
            df = perfil_all.copy()
            df["Posto"] = ["P" if _center_in_window(h, ponta_start, ponta_end) else "FP" for h in df["H"]]
            st.session_state.perfil_u = df.copy()
            st.session_state.perfil_f = df.copy(); st.session_state.perfil_f["Posto"] = "FP"
            st.session_state.perfil_all = df.copy()
        else:
            u = perfil_u_edit.copy(); u["Posto"] = ["P" if _center_in_window(h, ponta_start, ponta_end) else "FP" for h in u["H"]]
            f = perfil_f_edit.copy(); f["Posto"] = "FP"
            st.session_state.perfil_u = u; st.session_state.perfil_f = f
            st.session_state.perfil_u_edit = perfil_u_edit.copy(); st.session_state.perfil_f_edit = perfil_f_edit.copy()
    st.session_state.calc_done = True

if st.session_state.calc_done and not resumo_mode:
    perfil_u = st.session_state.perfil_u.copy()
    perfil_f = st.session_state.perfil_f.copy()
else:
    perfil_u = _make_initial_profile(ponta_start, ponta_end, perfil_inicial, for_fds=False)
    perfil_f = _make_initial_profile(ponta_start, ponta_end, perfil_inicial, for_fds=True)

if resumo_mode:
    st.info(f"**Modalidade:** {modalidade} — **Modo de entrada:** {input_mode}. A energia e a demanda medida são informadas diretamente por posto tarifário. A ERE usa modelo simplificado por posto quando habilitada.")
else:
    st.info(f"**Modalidade:** {modalidade} — Ponta **{_fmt_h(ponta_start)}–{_fmt_h(ponta_end)}** (úteis). FDS = sempre FP. Perfis: **{perfil_mode}**.")

# ---------- Cálculos principais ----------
if resumo_mode and st.session_state.calc_done:
    resumo_inputs = st.session_state.get("resumo_inputs", {})
    kwh_p = float(resumo_inputs.get("kwh_p", 0.0))
    kwh_fp = float(resumo_inputs.get("kwh_fp", 0.0))
    dm_p = float(resumo_inputs.get("dm_p", 0.0))
    dm_fp = float(resumo_inputs.get("dm_fp", 0.0))
    dm_g = float(resumo_inputs.get("dm_g", 0.0))
    resumo_fp_p = float(resumo_inputs.get("fp_p", 0.92))
    resumo_fp_fp = float(resumo_inputs.get("fp_fp", 0.92))
    resumo_fp_ref = float(resumo_inputs.get("fp_ref", 0.92))
else:
    kwh_p, kwh_fp = monthly_energy(perfil_u, perfil_f, dias_uteis, dias_fds)
    dm_p, dm_fp, dm_g = dm_measured(perfil_u, perfil_f)
    resumo_fp_p = resumo_fp_fp = resumo_fp_ref = 0.92
c_te_p, c_te_fp = (kwh_p*(custo_gmg if sim_gmg else te_p)), (kwh_fp*te_fp)
c_bdv = (kwh_p+kwh_fp)*bdv
c_bandeira = sum(bloco["kwh"] * bloco["tarifa"] for bloco in bandeira_blocos)
eP   = c_te_p  if calc_dem_ener else 0.0
eFP  = c_te_fp if calc_dem_ener else 0.0
bdvC = c_bdv   if calc_dem_ener else 0.0
bandeiraC = c_bandeira if calc_dem_ener else 0.0

# DAF (sem tolerância, por regra)
if modalidade.startswith("Azul"):
    daf_p, daf_fp = max(dm_p, dc_p), max(dm_fp, dc_fp)
else:
    daf_v = max(dm_g, dc_v)

# Ultrapassagem (regra selecionada)
if modalidade.startswith("Azul"):
    lim_test_p  = dc_p  * (1 + toler) if aplica_tol else dc_p
    lim_test_fp = dc_fp * (1 + toler) if aplica_tol else dc_fp
    if ultra_mode.startswith("Franquia"):
        ultra_p_kw  = max(dm_p  - lim_test_p,  0.0)
        ultra_fp_kw = max(dm_fp - lim_test_fp, 0.0)
    else:  # Degrau
        ultra_p_kw  = (dm_p  - dc_p)  if dm_p  > lim_test_p  else 0.0
        ultra_fp_kw = (dm_fp - dc_fp) if dm_fp > lim_test_fp else 0.0
    ultra_p  = (ultra_p_kw  * ul_p)  if calc_ultra else 0.0
    ultra_fp = (ultra_fp_kw * ul_fp) if calc_ultra else 0.0
    dem_p  = (daf_p * td_p)  if calc_dem_ener else 0.0
    dem_fp = (daf_fp * td_fp) if calc_dem_ener else 0.0
    dem_verde = 0.0
else:
    lim_test_v = dc_v * (1 + toler) if aplica_tol else dc_v
    if ultra_mode.startswith("Franquia"):
        ultra_v_kw = max(dm_g - lim_test_v, 0.0)
    else:
        ultra_v_kw = (dm_g - dc_v) if dm_g > lim_test_v else 0.0
    ultra_v = (ultra_v_kw * ul_fp) if calc_ultra else 0.0
    dem_verde = (daf_v * td_fp) if calc_dem_ener else 0.0
    dem_p = dem_fp = ultra_p = ultra_fp = 0.0

# ERE & DRE
if calc_ere and resumo_mode:
    ere_p = (kwh_p * ((resumo_fp_ref / resumo_fp_p) - 1.0)) if resumo_fp_p < resumo_fp_ref else 0.0
    ere_fp = (kwh_fp * ((resumo_fp_ref / resumo_fp_fp) - 1.0)) if resumo_fp_fp < resumo_fp_ref else 0.0
    ere_kwh = ere_p + ere_fp
    c_ere = ere_kwh * vr_ere
    ere_u_h = pd.Series([0.0] * len(perfil_u))
    ere_f_h = pd.Series([0.0] * len(perfil_f))
elif calc_ere and not resumo_mode:
    c_ere, ere_kwh, ere_u_h, ere_f_h = ere_calc(perfil_u, perfil_f, dias_uteis, dias_fds, vr_ere, capacit_on, isentar_ind_0_6, cap_start, cap_dur, perdas_factor)
else:
    c_ere, ere_kwh = 0.0, 0.0
    ere_p = ere_fp = 0.0
    ere_u_h = pd.Series([0.0]*len(perfil_u)); ere_f_h = pd.Series([0.0]*len(perfil_f))

if calc_dre and not resumo_mode:
    dre_p, dre_fp, dre_v, max_p_adj, max_fp_adj, max_v_adj, adj_u, adj_f = dre_calc(
        perfil_u, perfil_f,
        daf_p if modalidade.startswith("Azul") else 0.0,
        daf_fp if modalidade.startswith("Azul") else 0.0,
        daf_v if not modalidade.startswith("Azul") else 0.0,
        vr_dre, modalidade,
        perdas_factor=perdas_factor,
        vr_dre_fallback=td_fp
    )
elif calc_dre and resumo_mode and modalidade.startswith("Azul"):
    max_p_adj = dm_p * (resumo_fp_ref / resumo_fp_p)
    max_fp_adj = dm_fp * (resumo_fp_ref / resumo_fp_fp)
    dre_p = max(0.0, max_p_adj - daf_p) * vr_dre
    dre_fp = max(0.0, max_fp_adj - daf_fp) * vr_dre
    dre_v = 0.0
    max_v_adj = 0.0
    adj_u = perfil_u["kW"]; adj_f = perfil_f["kW"]
else:
    dre_p = dre_fp = dre_v = 0.0
    max_p_adj = max_fp_adj = max_v_adj = 0.0
    adj_u = perfil_u["kW"]; adj_f = perfil_f["kW"]

# Subtotais
if modalidade.startswith("Azul"):
    subtotal_sem_core = eP + eFP + dem_p + dem_fp + ultra_p + ultra_fp + bdvC
    subtotal_com_core = subtotal_sem_core + c_ere + (dre_p + dre_fp)
else:
    subtotal_sem_core = eP + eFP + dem_verde + ultra_v + bdvC
    subtotal_com_core = subtotal_sem_core + c_ere + dre_v

subtotal_sem = subtotal_sem_core + bandeiraC
subtotal_com = subtotal_com_core + bandeiraC

# Tributos (gross-up)
fator = (pis+cofins+icms)/100.0 if not ignorar_tributos else 0.0
base_tributavel_sem = subtotal_sem if aplicar_impostos_bandeira else subtotal_sem_core
base_tributavel_com = subtotal_com if aplicar_impostos_bandeira else subtotal_com_core
parcela_fora_base = 0.0 if aplicar_impostos_bandeira else bandeiraC
conta_sem  = (base_tributavel_sem /(1-fator) if (1-fator)>0 else 0.0) + parcela_fora_base
conta_com  = (base_tributavel_com /(1-fator) if (1-fator)>0 else 0.0) + parcela_fora_base
conta_final_base = conta_sem if not calc_ere and not calc_dre else conta_com
conta_final_ajustada = conta_final_base + cip - bonus_credito

# ---------- Resultado ----------
st.markdown(f"#### Resultado — **{modalidade}**")
if not st.session_state.calc_done:
    st.write({"Energia PONTA (kWh)":0,"Energia FORA (kWh)":0,"Energia PONTA (R$)":RS(0),"Energia FORA (R$)":RS(0),
              "Custo BDV (R$)":RS(0),"DM medida (kW) — ponta|fora|geral":(0,0,0),"DAF PONTA/FORA/Verde (kW)":(0,0),
              "Ultrapassagem (R$)":RS(0),"ERE (kVArh eq.)":0.0,"ERE (R$)":RS(0),"DRE (R$)":RS(0),
              "Subtotal (R$)":RS(0),"Conta final (R$)":RS(0),"CIP (R$)":RS(0),"Bônus / crédito (R$)":RS(0),"Conta final ajustada (R$)":RS(0)})
else:
    base = {
        "Energia PONTA (kWh)": int(kwh_p),
        "Energia FORA (kWh)": int(kwh_fp),
    }
    if calc_dem_ener:
        base.update({
            "Energia PONTA (R$)": RS(c_te_p),
            "Energia FORA (R$)": RS(c_te_fp),
            "Custo BDV (R$)": RS(c_bdv),
            "Custo da bandeira (R$)": RS(c_bandeira),
        })
    if modalidade == "Verde":
        base.update({
            "DM medida (kW) — geral": dm_g,
            "DAF Verde (kW)": (daf_v if calc_dem_ener else max(dm_g,dc_v)),
        })
        if calc_ultra: base["Ultrapassagem Verde (R$)"] = RS(ultra_v)
        if calc_ere:
            if resumo_mode:
                base["ERE simplificada por posto — ERE PONTA (kVArh eq.)"] = round(ere_p,3)
                base["ERE simplificada por posto — ERE FORA (kVArh eq.)"] = round(ere_fp,3)
                base["ERE simplificada por posto — ERE total (kVArh eq.)"] = round(ere_kwh,3)
                base["ERE simplificada por posto — ERE (R$)"] = RS(c_ere)
            else:
                base["Energia Reativa Excedente — ERE (kVArh eq.)"] = round(ere_kwh,3)
                base["Energia Reativa Excedente — ERE (R$)"] = RS(c_ere)
        if calc_dre: base["Demanda Reativa Excedente — DRE (Verde) (R$)"] = RS(dre_v)
    else:
        base.update({
            "DM medida (kW) — ponta|fora|geral": (dm_p, dm_fp, dm_g),
            "DAF PONTA/FORA (kW)": (daf_p if calc_dem_ener else max(dm_p,dc_p), daf_fp if calc_dem_ener else max(dm_fp,dc_fp)),
        })
        if calc_dem_ener:
            base[f"Demanda PONTA (R$)"] = RS(dem_p)
            base[f"Demanda FORA (R$)"] = RS(dem_fp)
        if calc_ultra:
            base["Ultrapassagem PONTA (R$)"] = RS(ultra_p)
            base["Ultrapassagem FORA (R$)"] = RS(ultra_fp)
        if calc_ere:
            if resumo_mode:
                base["ERE simplificada por posto — ERE PONTA (kVArh eq.)"] = round(ere_p,3)
                base["ERE simplificada por posto — ERE FORA (kVArh eq.)"] = round(ere_fp,3)
                base["ERE simplificada por posto — ERE total (kVArh eq.)"] = round(ere_kwh,3)
                base["ERE simplificada por posto — ERE (R$)"] = RS(c_ere)
            else:
                base["Energia Reativa Excedente — ERE (kVArh eq.)"] = round(ere_kwh,3)
                base["Energia Reativa Excedente — ERE (R$)"] = RS(c_ere)
        if calc_dre:
            if resumo_mode:
                base["DRE simplificada por posto — DRE PONTA (R$)"] = RS(dre_p)
                base["DRE simplificada por posto — DRE FORA (R$)"] = RS(dre_fp)
                base["DRE simplificada por posto — DRE total (R$)"] = RS(dre_p + dre_fp)
                base["DRE simplificada por posto — kW ajustado P/FP"] = (round(max_p_adj,3), round(max_fp_adj,3))
            else:
                base["Demanda Reativa Excedente — DRE (PONTA/FORA) (R$)"] = (RS(dre_p), RS(dre_fp))
                base["Max kW ajustado P/FP (0,92)"] = (round(max_p_adj,3), round(max_fp_adj,3))
    base["Subtotal (R$)"] = RS(subtotal_sem)
    base["Subtotal (com reativo) (R$)"] = RS(subtotal_com)
    base["Conta sem reativo (R$)"] = RS(conta_sem)
    base["Conta final (R$)"] = RS(conta_final_base)
    base["CIP (R$)"] = RS(cip)
    base["Bônus / crédito (R$)"] = RS(bonus_credito)
    base["Conta final ajustada (R$)"] = RS(conta_final_ajustada)
    st.write(base)

# ---------- Gráficos ----------
if st.session_state.calc_done and not resumo_mode:
    st.markdown("#### Curvas de demanda — barras")
    if modalidade == "Verde":
        dc_lines_u = [(dc_v, "DC (Verde)", "--")]; dc_lines_f = [(dc_v, "DC (Verde)", "--")]
    elif modalidade == "Azul (DC único)":
        dc_lines_u = [(dc_p, "DC (P/FP)", "--")]; dc_lines_f = [(dc_p, "DC (P/FP)", "--")]
    else:
        dc_lines_u = [(dc_p, "DC P", "--"), (dc_fp, "DC FP", ":")]
        dc_lines_f = [(dc_fp, "DC FP", ":")]
    if perfil_mode == "Único (todo mês)":
        st.pyplot(plot_barras(st.session_state.perfil_u, "Curva — Perfil Único", dc_lines_u if modalidade!="Azul — 2 Contratos" else [(dc_p,"DC P","--"),(dc_fp,"DC FP",":")]), use_container_width=True)
    else:
        c1, c2 = st.columns(2, gap="small")
        with c1: st.pyplot(plot_barras(st.session_state.perfil_u, "Curva — Dias Úteis", dc_lines_u), use_container_width=True)
        with c2: st.pyplot(plot_barras(st.session_state.perfil_f, "Curva — FDS/Feriados", dc_lines_f), use_container_width=True)

# ---------- Passo-a-passo (LaTeX) e Export ---------
if st.session_state.calc_done:
    if not resumo_mode:
        with st.expander("🔍 Passo-a-passo — ERE (mostra blocos positivos)"):
            if calc_ere:
                st.markdown("Só aparecem as horas com contribuição positiva. Se a isenção do indutivo entre 00h e 06h estiver ativa, essas horas são desconsideradas.")
                dfu = st.session_state.perfil_u.copy(); dfu["ERE_h"]=ere_u_h; dfu=dfu[dfu["ERE_h"]>0]
                for _,r in dfu.iterrows():
                    st.latex(rf"1\,h\times[{latex_num(r['kW'])}\cdot(\frac{{0.92}}{{{latex_num(r['FP'])}}}-1)]\times {latex_num(dias_uteis)} = {latex_num(r['ERE_h']*dias_uteis)}")
                dff = st.session_state.perfil_f.copy(); dff["ERE_h"]=ere_f_h; dff=dff[dff["ERE_h"]>0]
                for _,r in dff.iterrows():
                    st.latex(rf"1\,h\times[{latex_num(r['kW'])}\cdot(\frac{{0.92}}{{{latex_num(r['FP'])}}}-1)]\times {latex_num(dias_fds)} = {latex_num(r['ERE_h']*dias_fds)}")
                st.markdown(f"**Total mês (kVArh eq):** `{ere_kwh:.3f}` — **Valor ERE:** {RS(c_ere)}")
            else:
                st.info("ERE desabilitado nas opções da interface.")

        with st.expander("🔍 Passo-a-passo — DRE (kW ajustado 0,92)"):
            if calc_dre:
                if modalidade.startswith("Azul"):
                    st.latex(rf"P^{{adj}}_{{\max,P}}={latex_num(max_p_adj)},\ DAF_P={latex_num(daf_p)} \Rightarrow \text{{exc}}={latex_num(max(0,max_p_adj-daf_p))}")
                    st.latex(rf"P^{{adj}}_{{\max,FP}}={latex_num(max_fp_adj)},\ DAF_{{FP}}={latex_num(daf_fp)} \Rightarrow \text{{exc}}={latex_num(max(0,max_fp_adj-daf_fp))}")
                else:
                    st.latex(rf"P^{{adj}}_{{\max}}={latex_num(max_v_adj)},\ DAF={latex_num(daf_v)} \Rightarrow \text{{exc}}={latex_num(max(0,max_v_adj-daf_v))}")
            else:
                st.info("DRE desabilitado nas opções da interface.")
    elif calc_ere:
        with st.expander("🔍 Passo-a-passo — ERE simplificada por posto"):
            if resumo_fp_p < resumo_fp_ref:
                st.latex(rf"ERE_P = {latex_num(kwh_p)}\cdot\left(\frac{{{latex_num(resumo_fp_ref)}}}{{{latex_num(resumo_fp_p)}}}-1\right) = {latex_num(ere_p)}")
            else:
                st.latex(rf"FP_P={latex_num(resumo_fp_p)}\geq FP_{{ref}}={latex_num(resumo_fp_ref)} \Rightarrow ERE_P = 0")
            if resumo_fp_fp < resumo_fp_ref:
                st.latex(rf"ERE_{{FP}} = {latex_num(kwh_fp)}\cdot\left(\frac{{{latex_num(resumo_fp_ref)}}}{{{latex_num(resumo_fp_fp)}}}-1\right) = {latex_num(ere_fp)}")
            else:
                st.latex(rf"FP_{{FP}}={latex_num(resumo_fp_fp)}\geq FP_{{ref}}={latex_num(resumo_fp_ref)} \Rightarrow ERE_{{FP}} = 0")
            st.latex(rf"ERE_{{total}} = {latex_num(ere_p)} + {latex_num(ere_fp)} = {latex_num(ere_kwh)}")
            st.latex(rf"Custo_{{ERE}} = {latex_num(ere_kwh)}\cdot {latex_num(vr_ere)} = {latex_num(c_ere)}")
    if resumo_mode and calc_dre and modalidade.startswith("Azul"):
        with st.expander("🔍 Passo-a-passo — DRE simplificada por posto"):
            st.latex(rf"DRE_P = \max(0, {latex_num(dm_p)}\cdot\frac{{{latex_num(resumo_fp_ref)}}}{{{latex_num(resumo_fp_p)}}} - {latex_num(daf_p)})\cdot {latex_num(vr_dre)} = {latex_num(dre_p)}")
            st.latex(rf"DRE_{{FP}} = \max(0, {latex_num(dm_fp)}\cdot\frac{{{latex_num(resumo_fp_ref)}}}{{{latex_num(resumo_fp_fp)}}} - {latex_num(daf_fp)})\cdot {latex_num(vr_dre)} = {latex_num(dre_fp)}")
            st.latex(rf"DRE_{{total}} = {latex_num(dre_p)} + {latex_num(dre_fp)} = {latex_num(dre_p + dre_fp)}")

    with st.expander("🔍 Passo-a-passo — Ultrapassagem / Energia / Impostos"):
        if modalidade.startswith("Azul"):
            if ultra_mode.startswith("Franquia"):
                st.latex(rf"L_P={latex_num(dc_p)}(1+{latex_num(toler)})\,\textbf{{({ 'on' if aplica_tol else 'off' })}}={latex_num(lim_test_p)},\ UL_P=\max(0,{latex_num(dm_p)}-{latex_num(lim_test_p)})")
                st.latex(rf"L_{{FP}}={latex_num(dc_fp)}(1+{latex_num(toler)})\,\textbf{{({ 'on' if aplica_tol else 'off' })}}={latex_num(lim_test_fp)},\ UL_{{FP}}=\max(0,{latex_num(dm_fp)}-{latex_num(lim_test_fp)})")
            else:
                st.latex(rf"\text{{Se }} {latex_num(dm_p)}>{latex_num(lim_test_p)} \Rightarrow UL_P={latex_num(dm_p)}-{latex_num(dc_p)};\ \text{{senão }}0.")
                st.latex(rf"\text{{Se }} {latex_num(dm_fp)}>{latex_num(lim_test_fp)} \Rightarrow UL_{{FP}}={latex_num(dm_fp)}-{latex_num(dc_fp)};\ \text{{senão }}0.")
        else:
            if ultra_mode.startswith("Franquia"):
                st.latex(rf"L={latex_num(dc_v)}(1+{latex_num(toler)})\,\textbf{{({ 'on' if aplica_tol else 'off' })}}={latex_num(lim_test_v)},\ UL=\max(0,{latex_num(dm_g)}-{latex_num(lim_test_v)})")
            else:
                st.latex(rf"\text{{Se }} {latex_num(dm_g)}>{latex_num(lim_test_v)} \Rightarrow UL={latex_num(dm_g)}-{latex_num(dc_v)};\ \text{{senão }}0.")
        st.latex(rf"E_P={latex_num(kwh_p)},\ E_{{FP}}={latex_num(kwh_fp)},\ BDV=({latex_num(kwh_p)}+{latex_num(kwh_fp)})\cdot {latex_num(bdv)}={latex_num(c_bdv)}")
        if bandeiraC > 0:
            for idx, bloco in enumerate(bandeira_blocos, start=1):
                st.latex(rf"C_{{bandeira,{idx}}}={latex_num(bloco['kwh'])}\cdot {latex_num(bloco['tarifa'])}={latex_num(bloco['kwh'] * bloco['tarifa'])}")
            st.latex(rf"C_{{bandeira,total}}={latex_num(c_bandeira)}")
        else:
            st.markdown("**Bandeira**: sem blocos com consumo associado, custo total igual a zero.")
        if not ignorar_tributos:
            if aplicar_impostos_bandeira:
                st.latex(rf"\text{{Conta}}=\dfrac{{Subtotal}}{{1-{latex_num((pis+cofins+icms)/100.0)}}}")
            else:
                st.latex(rf"\text{{Conta}}=\dfrac{{Subtotal-C_{{bandeira,total}}}}{{1-{latex_num((pis+cofins+icms)/100.0)}}}+C_{{bandeira,total}}")
        else:
            st.markdown("**Impostos desprezados** → Conta = Subtotal.")
        st.markdown(f"**Conta final ajustada** = Conta final + CIP − Bônus/Crédito = {RS(conta_final_base)} + {RS(cip)} − {RS(bonus_credito)} = {RS(conta_final_ajustada)}")

# ---------- Exportar LaTeX/PDF ----------
def gerar_latex(tex_path):
    def num(x):
        if isinstance(x,(int,np.integer)): return f"{int(x)}"
        try: return f"{float(x):.5f}".rstrip('0').rstrip('.')
        except: return str(x)
    bandeira_desc = "; ".join(
        [f"Bloco {idx+1}: {bloco['tipo']} ({num(bloco['kwh'])} kWh x {num(bloco['tarifa'])})" for idx, bloco in enumerate(bandeira_blocos)]
    )
    doc  = r"\documentclass[11pt]{article}\usepackage{amsmath, amssymb, geometry, booktabs}\geometry{margin=1.8cm}\begin{document}"
    doc += r"\section*{Relatório de Cálculo}"
    doc += f"\nModalidade: {modalidade}. Ponta: {ponta_start}-{ponta_end}h. Úteis={dias_uteis}, FDS={dias_fds}.\\\\\n"
    if modalidade=="Verde":   doc += f"DC: {num(dc_v)} kW.\\\\\n"
    elif modalidade=="Azul (DC único)": doc += f"DC (P/FP): {num(dc_p)} kW.\\\\\n"
    else: doc += f"DC P: {num(dc_p)} kW; DC FP: {num(dc_fp)} kW.\\\\\n"
    doc += f"Tolerância: {'on' if aplica_tol else 'off'}; Regra: {ultra_mode}.\\\\\n"
    doc += f"Tarifas: TE_P={num(te_p)}, TE_FP={num(te_fp)}, TD_P={num(td_p)}, TD_FP={num(td_fp)}, UL_P={num(ul_p)}, UL_FP={num(ul_fp)}.\\\\\n"
    doc += f"ERE={num(vr_ere)}; DRE={num(vr_dre)}; BDV={num(bdv)}; Bandeiras={bandeira_desc}; Tributar bandeira={'sim' if aplicar_impostos_bandeira else 'não'}; CIP={num(cip)}; Bonus/Credito={num(bonus_credito)}; Tributos: PIS={num(pis)}\\%, COFINS={num(cofins)}\\%, ICMS={num(icms)}\\%.\\\\\n"
    doc += r"\subsection*{Totais}"
    doc += rf" Subtotal (sem reativo) = {num(subtotal_sem)}; Subtotal (com reativo) = {num(subtotal_com)}; Conta final = {num(conta_final_base)}; Conta final ajustada = {num(conta_final_ajustada)}."
    doc += r"\end{document}"
    with open(tex_path, "w", encoding="utf-8") as f: f.write(doc)

if st.session_state.calc_done:
    st.markdown("---")
    st.subheader("📄 Exportar relatório")
    if st.button("Gerar Relatório (LaTeX/PDF)"):
        tex_path = "Relatorio_EMS_v37H.tex"
        gerar_latex(tex_path)
        st.success("Arquivo .tex gerado.")
        with open(tex_path, "rb") as f:
            st.download_button("⬇️ Baixar .tex", data=f.read(), file_name=tex_path, mime="application/x-tex")
        pdflatex = shutil.which("pdflatex")
        if pdflatex:
            try:
                subprocess.run([pdflatex, "-interaction=nonstopmode", tex_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                pdf_name = tex_path.replace(".tex", ".pdf")
                if os.path.exists(pdf_name):
                    with open(pdf_name, "rb") as fpdf:
                        st.download_button("⬇️ Baixar PDF", data=fpdf.read(), file_name=pdf_name, mime="application/pdf")
            except Exception:
                st.info("pdflatex indisponível/erro. Baixe o .tex e compile localmente/Overleaf.")
        else:
            st.info("Sem pdflatex local. Baixe o .tex e compile no Overleaf.")
