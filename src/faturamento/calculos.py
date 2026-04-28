import pandas as pd

from .perfis import hour_overlap_frac


def monthly_energy(perf_u, perf_f, du, df):
    kwh_day_p_u = perf_u.loc[perf_u["Posto"] == "P", "kW"].sum()
    kwh_day_fp_u = perf_u.loc[perf_u["Posto"] == "FP", "kW"].sum()
    kwh_day_f_f = perf_f["kW"].sum()
    return kwh_day_p_u * du, kwh_day_fp_u * du + kwh_day_f_f * df


def dm_measured(perf_u, perf_f):
    dm_p = perf_u.loc[perf_u["Posto"] == "P", "kW"].max() if (perf_u["Posto"] == "P").any() else 0.0
    dm_fp = max(perf_u.loc[perf_u["Posto"] == "FP", "kW"].max() if (perf_u["Posto"] == "FP").any() else 0.0, perf_f["kW"].max())
    dm_g = max(perf_u["kW"].max(), perf_f["kW"].max())
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
            return (kw * perdas_factor) * ((0.92 / fpv) - 1.0) * max(0.0, min(1.0, weight))
        return 0.0

    ere_u_h = perfil_u.apply(ere_unit, axis=1)
    ere_f_h = perfil_f.apply(ere_unit, axis=1)
    ere_mes = ere_u_h.sum() * du + ere_f_h.sum() * df
    return ere_mes * vr_ere, ere_mes, ere_u_h, ere_f_h


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
        P = df["kW"].astype(float).fillna(0.0) * float(perdas_factor)
        FP = df["FP"].astype(float).clip(lower=1e-6, upper=1.0)
        return P * (fR / FP)

    if modo.startswith("Azul"):
        u_p = perfil_u[perfil_u["Posto"] == "P"]
        u_fp = perfil_u[perfil_u["Posto"] == "FP"]
        fp_all = pd.concat([u_fp, perfil_f], ignore_index=True)
        star_p = dam_star(u_p)
        star_fp = dam_star(fp_all)
        max_p = float(star_p.max())
        max_fp = float(star_fp.max())
        dre_p = max(0.0, max_p - (daf_p or 0.0)) * vr_dre_eff
        dre_fp = max(0.0, max_fp - (daf_fp or 0.0)) * vr_dre_eff
        return dre_p, dre_fp, 0.0, max_p, max_fp, 0.0, star_p, star_fp
    else:
        all_df = pd.concat([perfil_u, perfil_f], ignore_index=True)
        star_v = dam_star(all_df)
        max_v = float(star_v.max())
        dre_v = max(0.0, max_v - (daf_v or 0.0)) * vr_dre_eff
        return 0.0, 0.0, dre_v, 0.0, 0.0, max_v, star_v, star_v
