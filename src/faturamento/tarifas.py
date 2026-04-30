from copy import deepcopy


TARIFAS = {
    "EMS": {
        "distribuidora": "Energisa Mato Grosso do Sul",
        "sigla": "EMS",
        "vigencias": {
            "2025-04-08": {
                "resolucao_aneel": "3.441/2025",
                "vigencia_label": "08/04/2025",
                "fonte": "Quadro de Tarifas EMS Atual",
                "bandeiras": {
                    "Verde": {"adicional_r_kwh": 0.0},
                    "Amarela": {"adicional_r_kwh": 0.01885},
                    "Vermelha P1": {"adicional_r_kwh": 0.04463},
                    "Vermelha P2": {"adicional_r_kwh": 0.07877},
                },
                "grupo_a": {
                    "Azul": {
                        "A2": {
                            "label": "A2 (88 kV a 138 kV)",
                            "classes": {
                                "Rural Irrigação": {
                                    "TE_P": 0.52738,
                                    "TE_FP": 0.07016,
                                    "TD_P": 49.09,
                                    "TD_FP": 14.73,
                                    "UL_P": 98.18,
                                    "UL_FP": 29.46,
                                    "VR_DRE": 14.73,
                                    "VR_ERE": 0.28602,
                                    "TUSD_P": 0.08321,
                                    "TUSD_FP": 0.01664,
                                    "BDV_TE_P": 0.44417,
                                    "BDV_TE_FP": 0.05351,
                                },
                                "Demais Classes": {
                                    "TE_P": 0.52738,
                                    "TE_FP": 0.35080,
                                    "TD_P": 49.09,
                                    "TD_FP": 14.73,
                                    "UL_P": 98.18,
                                    "UL_FP": 29.46,
                                    "VR_DRE": 14.73,
                                    "VR_ERE": 0.28602,
                                    "TUSD_P": 0.08321,
                                    "TUSD_FP": 0.08321,
                                    "BDV_TE_P": 0.44417,
                                    "BDV_TE_FP": 0.26759,
                                },
                            },
                        },
                        "A3a": {
                            "label": "A3a (30 kV a 44 kV)",
                            "classes": {
                                "Rural Irrigação": {
                                    "TE_P": 0.57619,
                                    "TE_FP": 0.07992,
                                    "TD_P": 69.16,
                                    "TD_FP": 34.69,
                                    "UL_P": 138.32,
                                    "UL_FP": 69.38,
                                    "VR_DRE": 34.69,
                                    "VR_ERE": 0.28602,
                                    "TUSD_P": 0.12998,
                                    "TUSD_FP": 0.02599,
                                    "BDV_TE_P": 0.44621,
                                    "BDV_TE_FP": 0.05392,
                                },
                                "Demais Classes": {
                                    "TE_P": 0.57619,
                                    "TE_FP": 0.39961,
                                    "TD_P": 69.16,
                                    "TD_FP": 34.69,
                                    "UL_P": 138.32,
                                    "UL_FP": 69.38,
                                    "VR_DRE": 34.69,
                                    "VR_ERE": 0.28602,
                                    "TUSD_P": 0.12998,
                                    "TUSD_FP": 0.12998,
                                    "BDV_TE_P": 0.44621,
                                    "BDV_TE_FP": 0.26963,
                                },
                            },
                        },
                        "A3": {
                            "label": "A3 (69 kV)",
                            "classes": {
                                "Rural Irrigação": {
                                    "TE_P": 0.53278,
                                    "TE_FP": 0.07124,
                                    "TD_P": 65.43,
                                    "TD_FP": 20.72,
                                    "UL_P": 130.86,
                                    "UL_FP": 41.44,
                                    "VR_DRE": 20.72,
                                    "VR_ERE": 0.28602,
                                    "TUSD_P": 0.08861,
                                    "TUSD_FP": 0.01772,
                                    "BDV_TE_P": 0.44417,
                                    "BDV_TE_FP": 0.05351,
                                },
                                "Demais Classes": {
                                    "TE_P": 0.53278,
                                    "TE_FP": 0.35620,
                                    "TD_P": 65.43,
                                    "TD_FP": 20.72,
                                    "UL_P": 130.86,
                                    "UL_FP": 41.44,
                                    "VR_DRE": 20.72,
                                    "VR_ERE": 0.28602,
                                    "TUSD_P": 0.08861,
                                    "TUSD_FP": 0.08861,
                                    "BDV_TE_P": 0.44417,
                                    "BDV_TE_FP": 0.26759,
                                },
                            },
                        },
                        "A4": {
                            "label": "A4 (13,8 kV)",
                            "classes": {
                                "Rural Irrigação": {
                                    "TE_P": 0.57619,
                                    "TE_FP": 0.07992,
                                    "TD_P": 69.16,
                                    "TD_FP": 34.69,
                                    "UL_P": 138.32,
                                    "UL_FP": 69.38,
                                    "VR_DRE": 34.69,
                                    "VR_ERE": 0.28602,
                                    "TUSD_P": 0.12998,
                                    "TUSD_FP": 0.02599,
                                    "BDV_TE_P": 0.44621,
                                    "BDV_TE_FP": 0.05392,
                                },
                                "Demais Classes": {
                                    "TE_P": 0.57619,
                                    "TE_FP": 0.39961,
                                    "TD_P": 69.16,
                                    "TD_FP": 34.69,
                                    "UL_P": 138.32,
                                    "UL_FP": 69.38,
                                    "VR_DRE": 34.69,
                                    "VR_ERE": 0.28602,
                                    "TUSD_P": 0.12998,
                                    "TUSD_FP": 0.12998,
                                    "BDV_TE_P": 0.44621,
                                    "BDV_TE_FP": 0.26963,
                                },
                            },
                        },
                    },
                    "Verde": {
                        "A3a": {
                            "label": "A3a (30 kV a 44 kV)",
                            "classes": {
                                "Rural Irrigação": {
                                    "TE_P": 2.25614,
                                    "TE_FP": 0.07992,
                                    "TD_P": 0.0,
                                    "TD_FP": 34.69,
                                    "UL_P": 0.0,
                                    "UL_FP": 69.38,
                                    "VR_DRE": 34.69,
                                    "VR_ERE": 0.28602,
                                    "TUSD_P": 1.80993,
                                    "TUSD_FP": 0.02599,
                                    "BDV_TE_P": 0.44621,
                                    "BDV_TE_FP": 0.05392,
                                },
                                "Demais Classes": {
                                    "TE_P": 2.25614,
                                    "TE_FP": 0.39961,
                                    "TD_P": 0.0,
                                    "TD_FP": 34.69,
                                    "UL_P": 0.0,
                                    "UL_FP": 69.38,
                                    "VR_DRE": 34.69,
                                    "VR_ERE": 0.28602,
                                    "TUSD_P": 1.80993,
                                    "TUSD_FP": 0.12998,
                                    "BDV_TE_P": 0.44621,
                                    "BDV_TE_FP": 0.26963,
                                },
                            },
                        },
                        "A4": {
                            "label": "A4 (13,8 kV)",
                            "classes": {
                                "Rural Irrigação": {
                                    "TE_P": 2.25614,
                                    "TE_FP": 0.07992,
                                    "TD_P": 0.0,
                                    "TD_FP": 34.69,
                                    "UL_P": 0.0,
                                    "UL_FP": 69.38,
                                    "VR_DRE": 34.69,
                                    "VR_ERE": 0.28602,
                                    "TUSD_P": 1.80993,
                                    "TUSD_FP": 0.02599,
                                    "BDV_TE_P": 0.44621,
                                    "BDV_TE_FP": 0.05392,
                                },
                                "Demais Classes": {
                                    "TE_P": 2.25614,
                                    "TE_FP": 0.39961,
                                    "TD_P": 0.0,
                                    "TD_FP": 34.69,
                                    "UL_P": 0.0,
                                    "UL_FP": 69.38,
                                    "VR_DRE": 34.69,
                                    "VR_ERE": 0.28602,
                                    "TUSD_P": 1.80993,
                                    "TUSD_FP": 0.12998,
                                    "BDV_TE_P": 0.44621,
                                    "BDV_TE_FP": 0.26963,
                                },
                            },
                        },
                    },
                },
            }
        },
    }
}


def get_tarifas(
    distribuidora="EMS",
    vigencia="2025-04-08",
    modalidade="Azul",
    subgrupo="A4",
    classe="Demais Classes",
):
    return deepcopy(
        TARIFAS[distribuidora]["vigencias"][vigencia]["grupo_a"][modalidade][subgrupo]["classes"][classe]
    )


def get_bandeiras(distribuidora="EMS", vigencia="2025-04-08"):
    return deepcopy(TARIFAS[distribuidora]["vigencias"][vigencia]["bandeiras"])


def build_legacy_presets():
    return {
        "EMS Atual (base)": {
            "Azul": get_tarifas(modalidade="Azul", subgrupo="A4", classe="Demais Classes"),
            "Azul2": get_tarifas(modalidade="Azul", subgrupo="A4", classe="Demais Classes"),
            "Verde": get_tarifas(modalidade="Verde", subgrupo="A4", classe="Demais Classes"),
        }
    }


PRESETS = build_legacy_presets()
