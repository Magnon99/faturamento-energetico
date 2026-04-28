
# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os, shutil, subprocess

# ====================================================
#  Industriais II — EMS A4 (v3.7H‑rev10)
#  - REN 1000 + NDU 002 (EMS)
#  - Ultrapassagem: seletor Franquia vs Degrau
#  - Presets de tarifas (EMS atual / Prova do Professor)
#  - "Modo Prova": checkboxes com dicas do que ativar para cada item
#  - Botão Calcular (nada reativa até submeter)
#  - Relatório LaTeX/PDF com números
# ====================================================

st.set_page_config(page_title="Industriais II - EMS A4 (v3.7H‑rev10)", page_icon="⚡", layout="wide")
st.markdown("### ⚡ Industriais II — Calculadora de Faturamento (EMS) — v3.7H‑rev10")
st.caption("Desenvolvido por **Magnon R.** e **Assistente**")
st.caption("A4 — Demais Classes. Modalidades: **Verde**, **Azul (DC único)**, **Azul — 2 Contratos**. Regras: REN 1000 + NDU 002 (EMS).")

# ---------- Presets de tarifas ----------
PRESETS = {
    "EMS Atual (base)": {
        "Azul":  {"TE_P":0.57619, "TE_FP":0.39961, "TD_P":69.16, "TD_FP":34.69, "UL_P":138.32, "UL_FP":69.38, "VR_DRE":34.69, "VR_ERE":0.28602},
        "Azul2": {"TE_P":0.57619, "TE_FP":0.39961, "TD_P":69.16, "TD_FP":34.69, "UL_P":138.32, "UL_FP":69.38, "VR_DRE":34.69, "VR_ERE":0.28602},
        "Verde": {"TE_P":2.25614, "TE_FP":0.39961, "TD_P":0.00,  "TD_FP":34.69, "UL_P":0.00,   "UL_FP":69.38, "VR_DRE":34.69, "VR_ERE":0.28602}
    }
}


def RS(x):
    try:
        return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(x)

# ---------- Sidebar ----------
with st.sidebar:
    st.subheader("⚙️ Parâmetros gerais")
    preset = st.selectbox("Preset de Tarifas", list(PRESETS.keys()), index=0, help="Troca todos os valores padrão de tarifas/valores de referência de ERE/DRE.")

    modalidade = st.selectbox("Modalidade", ["Verde", "Azul (DC único)", "Azul — 2 Contratos"], index=0,
                              help="Escolha a modalidade pedida no item da prova.")
    ponta_start = st.number_input("Início da Ponta (h, aceita .5)", 0.0, 23.5, 17.0, step=0.5, help="Para a prova: 17h30–20h30 → use 17.5 e 20.5.")
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
                                  help="Na correção do professor eles costumam não cobrar indutivo 0–6h.")
    medir_sec = st.checkbox("Medição no secundário (<69 kV)? aplicar 2,5% nas quantidades de ERE/DRE", value=False,
                             help="REN 1000 Art. 305: quando a medição é no secundário, aplica-se 2,5% às quantidades medidas (ERE/DRE).")
    perdas_factor = 1.025 if medir_sec else 1.0
    st.markdown("---")
    if modalidade == "Azul (DC único)":
        dc_single = st.number_input("DC (kW) — vale para PONTA e FORA", 0.0, 100000.0, 130.0, step=1.0)
        dc_p, dc_fp = dc_single, dc_single
        tarifa_key = "Azul"
    elif modalidade == "Azul — 2 Contratos":
        dc_p = st.number_input("DC PONTA (kW)", 0.0, 100000.0, 150.0, step=1.0)
        dc_fp = st.number_input("DC FORA (kW)", 0.0, 100000.0, 120.0, step=1.0)
        tarifa_key = "Azul2"
    else:
        dc_v = st.number_input("Demanda Contratada (kW) — Verde", 0.0, 100000.0, 130.0, step=1.0)
        tarifa_key = "Verde"

    aplica_tol = st.checkbox("Aplicar tolerância na ULTRAPASSAGEM [DC × (1 + tolerância)]", value=False,
                             help="Ative se a questão especificar uma tolerância (ex.: 5%).")
    toler = st.number_input("Tolerância (fração)", 0.0, 0.2, 0.05, step=0.01, help="0,05 = 5%")

    ultra_mode = st.radio("Regra da tolerância (Ultrapassagem)",
                          ["Franquia (DM − DC×(1+τ))", "Degrau (se passou: DM − DC)"],
                          index=0,
                          help="⚠️ O professor costuma usar **Degrau** (passou → DM−DC). Franquia reduz a multa ao descontar a tolerância.")

    st.markdown("---")
    st.write("**GMG / Simulações**")
    sim_gmg = st.checkbox("Simular GMG na PONTA (TE_P = custo GMG)", value=False,
                          help="Itens (e) e (f). Substitui TE_P pelo custo do gerador.")
    custo_gmg = st.number_input("Custo GMG — R$/kWh", 0.0, 10.0, 1.40, step=0.01)

    st.markdown("---")
    st.write("**Impostos**")
    pis    = st.number_input("PIS (%)", 0.0, 20.0, 1.08, step=0.01, help="Item (g): preencha aqui as alíquotas e o app aplica o gross-up.")
    cofins = st.number_input("COFINS (%)", 0.0, 20.0, 7.60, step=0.01)
    icms   = st.number_input("ICMS (%)", 0.0, 40.0, 17.0, step=0.1)
    ignorar_tributos = st.checkbox("Desprezar ICMS, PIS e COFINS (conta = subtotal)", value=False,
                                   help="Use para itens que pedem 'despreze os impostos'.")

    st.divider()
    st.markdown("**Tarifas (editáveis)**")
    preset_vals = PRESETS[preset][tarifa_key]
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
                          help="Na prova, ele usa o valor da demanda de FP como VR_DRE.")
    vr_ere = st.number_input("VR_ERE — R$/kWh (Energia Reativa Excedente)", 0.0, 10.0, preset_vals["VR_ERE"], step=0.00001)
    bdv    = st.number_input("BDV (R$/kWh)", 0.0, 2.0, 0.0, step=0.00001, format="%.5f",
                         help="Benefício de Desenvolvimento (se houver) aplicado sobre a energia total.")

    st.divider()
    st.markdown("**Modo Prova — o que calcular?**")
    calc_dem_ener = st.checkbox("Calcular **Demanda e Energia** (itens a, c)", value=True,
                                help="Deixe ligado para os itens de faturamento sem multas.")
    calc_ultra    = st.checkbox("Calcular **Ultrapassagem** (quando houver) — usa regra acima", value=True,
                                help="Se a questão não pedir, desligue.")
    calc_ere      = st.checkbox("Calcular **ERE** (multa por baixo/alto FP) (itens b, d)", value=True,
                                help="Se a questão despreza excedente reativo, desligue.")
    calc_dre      = st.checkbox("Calcular **DRE** (Demanda Reativa Excedente)", value=True,
                                help="Nos gabaritos ele usa VR_DRE=Demanda_FP. Desligue se não pedir.")
    calc_impostos = st.checkbox("Aplicar **impostos** (gross-up) (item g)", value=True,
                                help="Se 'Desprezar impostos' estiver marcado acima, este é ignorado.")

# ---------- Helpers ----------
def _center_in_window(h_float, start, end):
    """Retorna True se o centro da hora (h+0.5) estiver na janela [start,end). Suporta janelas com .5 e cruzando meia-noite."""
    c = float(h_float) + 0.5
    s = float(start); e = float(end)
    if s < e:
        return (c >= s) and (c < e)
    else:
        # janela cruza 24h
        return (c >= s) or (c < e)

def _fmt_h(h):
    return f"{int(h)}:30" if abs(h - int(h) - 0.5) < 1e-9 else f"{int(h)}:00"

def default_profile(ps, pe, for_fds=False):
    hrs = np.arange(24); labels = [f"{h}-{h+1}" for h in hrs]
    kW = [35.8] + [40.0]*5 + [110.0]*6 + [150.0]*5 + [160.0]*3 + [110.0]*4
    FP = [0.8]*6 + [0.7]*6 + [0.8]*5 + [0.9,1.0,0.9] + [0.7]*4
    TIPO = ["Indutivo"]*24
    posto = ["FP"]*24 if for_fds else ["P" if (h>=ps and h<pe) else "FP" for h in hrs]
    return pd.DataFrame({"Hora":labels,"H":hrs,"kW":kW,"FP":FP,"Tipo_FP":TIPO,"Posto":posto})

def hour_overlap(start, dur, h):
    end = (start + dur) % 24
    if dur >= 24: return True
    return (start <= h < end) if start < end else (h >= start or h < end)


def hour_overlap_frac(start, dur, h):
    """
    Fração de sobreposição entre a janela [start, start+dur) (em horas, podendo ter .5)
    e a hora inteira [h, h+1). Retorna valor entre 0 e 1.
    """
    if dur <= 0:
        return 0.0
    start = float(start) % 24.0
    dur = float(dur)
    end = start + dur
    # Função auxiliar: comprimento da interseção
    def overlap(a1, a2, b1, b2):
        lo = max(a1, b1); hi = min(a2, b2)
        return max(0.0, hi - lo)
    # Sem volta de dia
    if end <= 24.0:
        ol = overlap(start, end, h, h+1)
    else:
        ol = overlap(start, 24.0, h, h+1) + overlap(0.0, end-24.0, h, h+1)
    return max(0.0, min(1.0, ol))
def monthly_energy(perf_u, perf_f, du, df):
    kwh_day_p_u  = perf_u.loc[perf_u["Posto"]=="P","kW"].sum()
    kwh_day_fp_u = perf_u.loc[perf_u["Posto"]=="FP","kW"].sum()
    kwh_day_f_f  = perf_f["kW"].sum()
    return kwh_day_p_u * du, kwh_day_fp_u * du + kwh_day_f_f * df

def dm_measured(perf_u, perf_f):
    dm_p  = perf_u.loc[perf_u["Posto"]=="P","kW"].max() if (perf_u["Posto"]=="P").any() else 0.0
    dm_fp = max(perf_u.loc[perf_u["Posto"]=="FP","kW"].max() if (perf_u["Posto"]=="FP").any() else 0.0, perf_f["kW"].max())
    dm_g  = max(perf_u["kW"].max(), perf_f["kW"].max())
    return dm_p or 0.0, dm_fp or 0.0, dm_g or 0.0


def ere_calc(perfil_u, perfil_f, du, df, vr_ere, capacit_on_flag, isentar_ind_0_6, cap_start, cap_dur, perdas_factor=1.0):
    def ere_unit(row):
        kw, fpv, tipo, h = row["kW"], row["FP"], row["Tipo_FP"], int(row["H"])
        if pd.isna(kw) or pd.isna(fpv) or fpv == 0:
            return 0.0
        # Exceção didática: isentar INDUTIVO 00–06
        if isentar_ind_0_6 and (0 <= h < 6) and tipo == "Indutivo":
            return 0.0
        # Peso da janela capacitiva (fração na hora)
        weight = 1.0
        if capacit_on_flag:
            frac = hour_overlap_frac(cap_start, cap_dur, h)
            if tipo == "Capacitivo":
                weight = frac
            elif tipo == "Indutivo":
                weight = 1.0 - frac
        # REN 1000: só há excedente se FP < 0,92
        if tipo in ("Indutivo", "Capacitivo") and fpv < 0.92:
            return (kw * perdas_factor) * ((0.92/fpv) - 1.0) * max(0.0, min(1.0, weight))
        return 0.0
    ere_u_h = perfil_u.apply(ere_unit, axis=1)
    ere_f_h = perfil_f.apply(ere_unit, axis=1)
    ere_mes = ere_u_h.sum()*du + ere_f_h.sum()*df
    return ere_mes*vr_ere, ere_mes, ere_u_h, ere_f_h


def dre_calc(perfil_u, perfil_f, daf_p, daf_fp, daf_v, vr_dre, modo, perdas_factor=1.0, vr_dre_fallback=None):
    """
    REN 1000 — DRE(p) = ( max_T [ DAM_T * (0.92/f_T) ] - DAF(p) )_+ * VR_DRE
    Azul: por posto; Verde: global.
    """
    fR = 0.92
    # Fallback do VR_DRE se 0
    vr_dre_eff = float(vr_dre or 0.0)
    if vr_dre_eff <= 0.0 and (vr_dre_fallback is not None):
        vr_dre_eff = float(vr_dre_fallback)
    def dam_star(df):
        if df is None or len(df) == 0:
            return pd.Series([0.0])
        P  = df["kW"].astype(float).fillna(0.0) * float(perdas_factor)
        FP = df["FP"].astype(float).clip(lower=1e-6, upper=1.0)
        return P * (fR/FP)
    if modo.startswith("Azul"):
        u_p  = perfil_u[perfil_u["Posto"]=="P"]
        u_fp = perfil_u[perfil_u["Posto"]=="FP"]
        fp_all = pd.concat([u_fp, perfil_f], ignore_index=True)
        star_p  = dam_star(u_p)
        star_fp = dam_star(fp_all)
        max_p  = float(star_p.max())
        max_fp = float(star_fp.max())
        dre_p  = max(0.0, max_p  - (daf_p  or 0.0)) * vr_dre_eff
        dre_fp = max(0.0, max_fp - (daf_fp or 0.0)) * vr_dre_eff
        return dre_p, dre_fp, 0.0, max_p, max_fp, 0.0, star_p, star_fp
    else:
        all_df = pd.concat([perfil_u, perfil_f], ignore_index=True)
        star_v = dam_star(all_df)
        max_v  = float(star_v.max())
        dre_v  = max(0.0, max_v - (daf_v or 0.0)) * vr_dre_eff
        return 0.0, 0.0, dre_v, 0.0, 0.0, max_v, star_v, star_v

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

def latex_num(x):
    if isinstance(x, (int, np.integer)): return f"{int(x)}"
    try: return f"{float(x):.5f}".rstrip('0').rstrip('.')
    except: return str(x)

# ---------- Formulário com tabelas ----------
with st.form("form_tabelas"):
    if perfil_mode == "Único (todo mês)":
        st.markdown("#### Perfil de Carga — **Único** (vale para úteis e FDS)")
        if "perfil_all" not in st.session_state:
            st.session_state.perfil_all = default_profile(ponta_start, ponta_end, for_fds=False)
        perfil_all = st.data_editor(st.session_state.perfil_all, num_rows="fixed", use_container_width=True, hide_index=True,
                                    key="editor_all",
                                    column_config={
                                        "Tipo_FP": st.column_config.SelectboxColumn(options=["Indutivo","Capacitivo","Neutro"]),
                                        "Posto": st.column_config.SelectboxColumn(options=["P","FP"]),
                                    })
    else:
        st.markdown("#### Perfil — **Dias Úteis**")
        if "perfil_u_edit" not in st.session_state:
            st.session_state.perfil_u_edit = default_profile(ponta_start, ponta_end, for_fds=False)
        perfil_u_edit = st.data_editor(st.session_state.perfil_u_edit, num_rows="fixed", use_container_width=True, hide_index=True,
                                       key="editor_u",
                                       column_config={
                                           "Tipo_FP": st.column_config.SelectboxColumn(options=["Indutivo","Capacitivo","Neutro"]),
                                           "Posto": st.column_config.SelectboxColumn(options=["P","FP"]),
                                       })
        st.markdown("#### Perfil — **FDS / Feriados** (sempre fora de ponta)")
        if "perfil_f_edit" not in st.session_state:
            st.session_state.perfil_f_edit = default_profile(ponta_start, ponta_end, for_fds=True)
        perfil_f_edit = st.data_editor(st.session_state.perfil_f_edit, num_rows="fixed", use_container_width=True, hide_index=True,
                                       key="editor_f",
                                       column_config={"Tipo_FP": st.column_config.SelectboxColumn(options=["Indutivo","Capacitivo","Neutro"])})

    calc = st.form_submit_button("🚀 Calcular")

if "calc_done" not in st.session_state: st.session_state.calc_done = False
if calc:
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

if st.session_state.calc_done:
    perfil_u = st.session_state.perfil_u.copy()
    perfil_f = st.session_state.perfil_f.copy()
else:
    hrs = np.arange(24)
    perfil_u = pd.DataFrame({"Hora":[f"{h}-{h+1}" for h in hrs], "H":hrs, "kW":[0.0]*24, "FP":[0.0]*24, "Tipo_FP":["Neutro"]*24, "Posto":["FP"]*24})
    perfil_f = perfil_u.copy()

st.info(f"**Modalidade:** {modalidade} — Ponta **{_fmt_h(ponta_start)}–{_fmt_h(ponta_end)}** (úteis). FDS = sempre FP. Perfis: **{perfil_mode}**.")

# ---------- Cálculos principais ----------
kwh_p, kwh_fp = monthly_energy(perfil_u, perfil_f, dias_uteis, dias_fds)
c_te_p, c_te_fp = (kwh_p*(custo_gmg if sim_gmg else te_p)), (kwh_fp*te_fp)
c_bdv = (kwh_p+kwh_fp)*bdv
eP   = c_te_p  if calc_dem_ener else 0.0
eFP  = c_te_fp if calc_dem_ener else 0.0
bdvC = c_bdv   if calc_dem_ener else 0.0

dm_p, dm_fp, dm_g = dm_measured(perfil_u, perfil_f)

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
if calc_ere:
    c_ere, ere_kwh, ere_u_h, ere_f_h = ere_calc(perfil_u, perfil_f, dias_uteis, dias_fds, vr_ere, capacit_on, isentar_ind_0_6, cap_start, cap_dur, perdas_factor)
else:
    c_ere, ere_kwh = 0.0, 0.0
    ere_u_h = pd.Series([0.0]*len(perfil_u)); ere_f_h = pd.Series([0.0]*len(perfil_f))

if calc_dre:
    dre_p, dre_fp, dre_v, max_p_adj, max_fp_adj, max_v_adj, adj_u, adj_f = dre_calc(
        perfil_u, perfil_f,
        daf_p if modalidade.startswith("Azul") else 0.0,
        daf_fp if modalidade.startswith("Azul") else 0.0,
        daf_v if not modalidade.startswith("Azul") else 0.0,
        vr_dre, modalidade,
        perdas_factor=perdas_factor,
        vr_dre_fallback=td_fp
    )
else:
    dre_p = dre_fp = dre_v = 0.0
    max_p_adj = max_fp_adj = max_v_adj = 0.0
    adj_u = perfil_u["kW"]; adj_f = perfil_f["kW"]

# Subtotais
if modalidade.startswith("Azul"):
    subtotal_sem = eP + eFP + dem_p + dem_fp + ultra_p + ultra_fp + bdvC
    subtotal_com = subtotal_sem + c_ere + (dre_p + dre_fp)
else:
    subtotal_sem = eP + eFP + dem_verde + ultra_v + bdvC
    subtotal_com = subtotal_sem + c_ere + dre_v

# Tributos (gross-up)
fator = (pis+cofins+icms)/100.0 if not ignorar_tributos else 0.0
conta_sem  = subtotal_sem /(1-fator) if (1-fator)>0 else 0.0
conta_com  = subtotal_com /(1-fator) if (1-fator)>0 else 0.0

# ---------- Resultado ----------
st.markdown(f"#### Resultado — **{modalidade}**")
if not st.session_state.calc_done:
    st.write({"Energia PONTA (kWh)":0,"Energia FORA (kWh)":0,"Energia PONTA (R$)":RS(0),"Energia FORA (R$)":RS(0),
              "Custo BDV (R$)":RS(0),"DM medida (kW) — ponta|fora|geral":(0,0,0),"DAF PONTA/FORA/Verde (kW)":(0,0),
              "Ultrapassagem (R$)":RS(0),"ERE (kVArh eq.)":0.0,"ERE (R$)":RS(0),"DRE (R$)":RS(0),
              "Subtotal (R$)":RS(0),"Conta final (R$)":RS(0)})
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
        })
    if modalidade == "Verde":
        base.update({
            "DM medida (kW) — geral": dm_g,
            "DAF Verde (kW)": (daf_v if calc_dem_ener else max(dm_g,dc_v)),
        })
        if calc_ultra: base["Ultrapassagem Verde (R$)"] = RS(ultra_v)
        if calc_ere: base["Energia Reativa Excedente — ERE (kVArh eq.)"] = round(ere_kwh,3); base["Energia Reativa Excedente — ERE (R$)"] = RS(c_ere)
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
            base["Energia Reativa Excedente — ERE (kVArh eq.)"] = round(ere_kwh,3); base["Energia Reativa Excedente — ERE (R$)"] = RS(c_ere)
        if calc_dre:
            base["Demanda Reativa Excedente — DRE (PONTA/FORA) (R$)"] = (RS(dre_p), RS(dre_fp))
            base["Max kW ajustado P/FP (0,92)"] = (round(max_p_adj,3), round(max_fp_adj,3))
    base["Subtotal (R$)"] = RS(subtotal_sem)
    base["Subtotal (com reativo) (R$)"] = RS(subtotal_com)
    base["Conta sem reativo (R$)"] = RS(conta_sem)
    base["Conta final (R$)"] = RS(conta_sem if not calc_ere and not calc_dre else conta_com)
    st.write(base)

# ---------- Gráficos ----------
if st.session_state.calc_done:
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
    with st.expander("🔍 Passo-a-passo — ERE (mostra blocos positivos)"):
        if calc_ere:
            st.markdown("Só aparecem as horas com contribuição positiva. Se 'Isentar 00–06h indutivo' estiver ligado, essas horas são ignoradas.")
            dfu = st.session_state.perfil_u.copy(); dfu["ERE_h"]=ere_u_h; dfu=dfu[dfu["ERE_h"]>0]
            for _,r in dfu.iterrows():
                st.latex(rf"1\,h\times[{latex_num(r['kW'])}\cdot(\frac{{0.92}}{{{latex_num(r['FP'])}}}-1)]\times {latex_num(dias_uteis)} = {latex_num(r['ERE_h']*dias_uteis)}")
            dff = st.session_state.perfil_f.copy(); dff["ERE_h"]=ere_f_h; dff=dff[dff["ERE_h"]>0]
            for _,r in dff.iterrows():
                st.latex(rf"1\,h\times[{latex_num(r['kW'])}\cdot(\frac{{0.92}}{{{latex_num(r['FP'])}}}-1)]\times {latex_num(dias_fds)} = {latex_num(r['ERE_h']*dias_fds)}")
            st.markdown(f"**Total mês (kVArh eq):** `{ere_kwh:.3f}` — **Valor ERE:** {RS(c_ere)}")
        else:
            st.info("ERE desligado nas opções.")

    with st.expander("🔍 Passo-a-passo — DRE (kW ajustado 0,92)"):
        if calc_dre:
            if modalidade.startswith("Azul"):
                st.latex(rf"P^{{adj}}_{{\max,P}}={latex_num(max_p_adj)},\ DAF_P={latex_num(daf_p)} \Rightarrow \text{{exc}}={latex_num(max(0,max_p_adj-daf_p))}")
                st.latex(rf"P^{{adj}}_{{\max,FP}}={latex_num(max_fp_adj)},\ DAF_{{FP}}={latex_num(daf_fp)} \Rightarrow \text{{exc}}={latex_num(max(0,max_fp_adj-daf_fp))}")
            else:
                st.latex(rf"P^{{adj}}_{{\max}}={latex_num(max_v_adj)},\ DAF={latex_num(daf_v)} \Rightarrow \text{{exc}}={latex_num(max(0,max_v_adj-daf_v))}")
        else:
            st.info("DRE desligado nas opções.")

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
        if calc_impostos and not ignorar_tributos:
            st.latex(rf"\text{{Conta}}=\dfrac{{Subtotal}}{{1-{latex_num((pis+cofins+icms)/100.0)}}}")
        elif ignorar_tributos:
            st.markdown("**Impostos desprezados** → Conta = Subtotal.")
        else:
            st.markdown("Impostos desligados nas opções.")

# ---------- Exportar LaTeX/PDF ----------
def gerar_latex(tex_path):
    def num(x):
        if isinstance(x,(int,np.integer)): return f"{int(x)}"
        try: return f"{float(x):.5f}".rstrip('0').rstrip('.')
        except: return str(x)
    doc  = r"\documentclass[11pt]{article}\usepackage{amsmath, amssymb, geometry, booktabs}\geometry{margin=1.8cm}\begin{document}"
    doc += r"\section*{Relatório de Cálculo (EMS A4)}"
    doc += f"\nModalidade: {modalidade}. Ponta: {ponta_start}-{ponta_end}h. Úteis={dias_uteis}, FDS={dias_fds}.\\\\\n"
    if modalidade=="Verde":   doc += f"DC: {num(dc_v)} kW.\\\\\n"
    elif modalidade=="Azul (DC único)": doc += f"DC (P/FP): {num(dc_p)} kW.\\\\\n"
    else: doc += f"DC P: {num(dc_p)} kW; DC FP: {num(dc_fp)} kW.\\\\\n"
    doc += f"Tolerância: {'on' if aplica_tol else 'off'}; Regra: {ultra_mode}.\\\\\n"
    doc += f"Tarifas: TE_P={num(te_p)}, TE_FP={num(te_fp)}, TD_P={num(td_p)}, TD_FP={num(td_fp)}, UL_P={num(ul_p)}, UL_FP={num(ul_fp)}.\\\\\n"
    doc += f"ERE={num(vr_ere)}; DRE={num(vr_dre)}; BDV={num(bdv)}; Tributos: PIS={num(pis)}\\%, COFINS={num(cofins)}\\%, ICMS={num(icms)}\\%.\\\\\n"
    doc += r"\subsection*{Totais}"
    doc += rf" Subtotal (sem reativo) = {num(subtotal_sem)}; Subtotal (com reativo) = {num(subtotal_com)}; Conta final = {num(conta_com if (calc_ere or calc_dre) else conta_sem)}."
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