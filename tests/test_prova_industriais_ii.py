import pandas as pd
import pytest

from src.faturamento.calculos import dm_measured, dre_calc, ere_calc, monthly_energy
from src.faturamento.perfis import _center_in_window
from src.faturamento.tarifas import get_tarifas


VIGENCIA = "2025-04-08"
SUBGRUPO = "A4"
CLASSE = "Demais Classes"
DIAS_UTEIS = 22
DIAS_FDS = 8
PONTA_START = 17.0
PONTA_END = 20.0
PIS = 1.08
COFINS = 7.60
ICMS = 17.0
FATOR_TRIBUTOS = (PIS + COFINS + ICMS) / 100.0


def build_prova_profiles():
    perfil_u = []
    perfil_f = []

    for h in range(24):
        if 0 <= h < 6:
            kw_u, fp_u, tipo_u = 28.0, 0.77, "Indutivo"
        elif 6 <= h < 12:
            kw_u, fp_u, tipo_u = 138.0, 0.93, "Indutivo"
        elif 12 <= h < 18:
            kw_u, fp_u, tipo_u = 215.0, 0.72, "Indutivo"
        else:
            kw_u, fp_u, tipo_u = 52.0, 0.88, "Capacitivo"

        perfil_u.append(
            {
                "Hora": f"{h}-{h+1}",
                "H": h,
                "kW": kw_u,
                "FP": fp_u,
                "Tipo_FP": tipo_u,
                "Posto": "P" if _center_in_window(h, PONTA_START, PONTA_END) else "FP",
            }
        )

        if 6 <= h < 18:
            kw_f, fp_f, tipo_f = 13.0, 0.65, "Capacitivo"
        else:
            kw_f, fp_f, tipo_f = 26.0, 0.83, "Capacitivo"

        perfil_f.append(
            {
                "Hora": f"{h}-{h+1}",
                "H": h,
                "kW": kw_f,
                "FP": fp_f,
                "Tipo_FP": tipo_f,
                "Posto": "FP",
            }
        )

    return pd.DataFrame(perfil_u), pd.DataFrame(perfil_f)


def test_prova_industriais_ii_curva_horaria():
    perfil_u, perfil_f = build_prova_profiles()

    energia_ponta, energia_fora = monthly_energy(perfil_u, perfil_f, DIAS_UTEIS, DIAS_FDS)
    dm_p, dm_fp, dm_g = dm_measured(perfil_u, perfil_f)

    tarifas_verde = get_tarifas(
        vigencia=VIGENCIA,
        modalidade="Verde",
        subgrupo=SUBGRUPO,
        classe=CLASSE,
    )
    tarifas_azul = get_tarifas(
        vigencia=VIGENCIA,
        modalidade="Azul",
        subgrupo=SUBGRUPO,
        classe=CLASSE,
    )

    # Verde
    dc_verde = 160.0
    daf_verde = max(dm_g, dc_verde)
    subtotal_verde = (
        energia_ponta * tarifas_verde["TE_P"]
        + energia_fora * tarifas_verde["TE_FP"]
        + daf_verde * tarifas_verde["TD_FP"]
        + max(0.0, dm_g - dc_verde) * tarifas_verde["UL_FP"]
    )
    final_verde_sem_reativo = subtotal_verde / (1.0 - FATOR_TRIBUTOS)

    ere_verde_rs, _, _, _ = ere_calc(
        perfil_u,
        perfil_f,
        DIAS_UTEIS,
        DIAS_FDS,
        tarifas_verde["VR_ERE"],
        capacit_on_flag=True,
        isentar_ind_0_6=False,
        cap_start=0.0,
        cap_dur=6.0,
        perdas_factor=1.0,
    )
    _, _, dre_verde_rs, _, _, _, _, _ = dre_calc(
        perfil_u,
        perfil_f,
        daf_p=0.0,
        daf_fp=0.0,
        daf_v=daf_verde,
        vr_dre=tarifas_verde["VR_DRE"],
        modo="Verde",
        perdas_factor=1.0,
        vr_dre_fallback=tarifas_verde["TD_FP"],
    )

    # Azul com 2 contratos
    dc_p_azul = 160.0
    dc_fp_azul = 140.0
    daf_p_azul = max(dm_p, dc_p_azul)
    daf_fp_azul = max(dm_fp, dc_fp_azul)
    subtotal_azul = (
        energia_ponta * tarifas_azul["TE_P"]
        + energia_fora * tarifas_azul["TE_FP"]
        + daf_p_azul * tarifas_azul["TD_P"]
        + daf_fp_azul * tarifas_azul["TD_FP"]
        + max(0.0, dm_p - dc_p_azul) * tarifas_azul["UL_P"]
        + max(0.0, dm_fp - dc_fp_azul) * tarifas_azul["UL_FP"]
    )
    final_azul_sem_reativo = subtotal_azul / (1.0 - FATOR_TRIBUTOS)

    dre_azul_p, dre_azul_fp, _, _, _, _, _, _ = dre_calc(
        perfil_u,
        perfil_f,
        daf_p=daf_p_azul,
        daf_fp=daf_fp_azul,
        daf_v=0.0,
        vr_dre=tarifas_azul["VR_DRE"],
        modo="Azul — 2 Contratos",
        perdas_factor=1.0,
        vr_dre_fallback=tarifas_azul["TD_FP"],
    )
    dre_azul_total = dre_azul_p + dre_azul_fp
    final_azul_com_reativo = (subtotal_azul + ere_verde_rs + dre_azul_total) / (1.0 - FATOR_TRIBUTOS)

    assert energia_ponta + energia_fora == 60900
    assert energia_ponta == 7018
    assert energia_fora == 53882

    assert subtotal_verde == pytest.approx(48639.63, abs=1e-2)
    assert final_verde_sem_reativo == pytest.approx(65446.21, abs=1e-2)
    assert ere_verde_rs == pytest.approx(2293.50, abs=1e-2)
    assert dre_verde_rs == pytest.approx(2071.76, abs=1e-2)

    assert subtotal_azul == pytest.approx(60714.34, abs=1e-2)
    assert final_azul_sem_reativo == pytest.approx(81693.13, abs=1e-2)
    assert dre_azul_total == pytest.approx(4143.53, abs=1e-2)
    assert final_azul_com_reativo == pytest.approx(90354.36, abs=1e-2)
