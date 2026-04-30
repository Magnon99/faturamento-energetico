import pytest

from src.faturamento.calculos import dm_measured, dre_calc, ere_calc, monthly_energy
from src.faturamento.perfis import default_profile
from src.faturamento.tarifas import PRESETS


PONTA_START = 17.0
PONTA_END = 20.0
DIAS_UTEIS = 22
DIAS_FDS = 8
DC_VERDE = 130.0
DC_AZUL = 130.0


def build_default_profiles():
    perfil_u = default_profile(PONTA_START, PONTA_END, for_fds=False)
    perfil_f = default_profile(PONTA_START, PONTA_END, for_fds=True)
    return perfil_u, perfil_f


def test_snapshot_monthly_energy_default_profile():
    perfil_u, perfil_f = build_default_profiles()

    energia_ponta, energia_fora = monthly_energy(perfil_u, perfil_f, DIAS_UTEIS, DIAS_FDS)

    assert energia_ponta == 10560
    assert energia_fora == 66414


def test_snapshot_dm_measured_default_profile():
    perfil_u, perfil_f = build_default_profiles()

    dm_p, dm_fp, dm_g = dm_measured(perfil_u, perfil_f)

    assert dm_p == 160
    assert dm_fp == 160
    assert dm_g == 160


def test_snapshot_ere_default_profile():
    perfil_u, perfil_f = build_default_profiles()
    vr_ere = PRESETS["EMS Atual (base)"]["Verde"]["VR_ERE"]

    ere_rs, ere_kvarh_eq, _, _ = ere_calc(
        perfil_u,
        perfil_f,
        DIAS_UTEIS,
        DIAS_FDS,
        vr_ere,
        capacit_on_flag=True,
        isentar_ind_0_6=False,
        cap_start=0.0,
        cap_dur=6.0,
        perdas_factor=1.0,
    )

    assert ere_kvarh_eq == pytest.approx(13959.762, abs=1e-3)
    assert ere_rs == pytest.approx(3992.77, abs=1e-2)


def test_snapshot_dre_verde_default_profile():
    perfil_u, perfil_f = build_default_profiles()
    _, _, dm_g = dm_measured(perfil_u, perfil_f)
    daf_v = max(dm_g, DC_VERDE)
    vr_dre = PRESETS["EMS Atual (base)"]["Verde"]["VR_DRE"]

    dre_p, dre_fp, dre_v, max_p_adj, max_fp_adj, max_v_adj, _, _ = dre_calc(
        perfil_u,
        perfil_f,
        daf_p=0.0,
        daf_fp=0.0,
        daf_v=daf_v,
        vr_dre=vr_dre,
        modo="Verde",
        perdas_factor=1.0,
        vr_dre_fallback=PRESETS["EMS Atual (base)"]["Verde"]["TD_FP"],
    )

    assert dre_p == 0.0
    assert dre_fp == 0.0
    assert max_p_adj == 0.0
    assert max_fp_adj == 0.0
    assert max_v_adj == pytest.approx(172.5, abs=1e-9)
    assert dre_v == pytest.approx(433.625, abs=1e-3)


def test_snapshot_dre_azul_default_profile():
    perfil_u, perfil_f = build_default_profiles()
    dm_p, dm_fp, _ = dm_measured(perfil_u, perfil_f)
    daf_p = max(dm_p, DC_AZUL)
    daf_fp = max(dm_fp, DC_AZUL)
    vr_dre = PRESETS["EMS Atual (base)"]["Azul"]["VR_DRE"]

    dre_p, dre_fp, dre_v, max_p_adj, max_fp_adj, max_v_adj, _, _ = dre_calc(
        perfil_u,
        perfil_f,
        daf_p=daf_p,
        daf_fp=daf_fp,
        daf_v=0.0,
        vr_dre=vr_dre,
        modo="Azul (DC único)",
        perdas_factor=1.0,
        vr_dre_fallback=PRESETS["EMS Atual (base)"]["Azul"]["TD_FP"],
    )

    assert dre_v == 0.0
    assert max_v_adj == 0.0
    assert max_p_adj == pytest.approx(163.55555555555554, abs=1e-9)
    assert max_fp_adj == pytest.approx(172.5, abs=1e-9)
    assert dre_p == pytest.approx(123.34, abs=1e-2)
    assert dre_fp == pytest.approx(433.625, abs=1e-3)
