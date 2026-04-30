import numpy as np
import pandas as pd


def _center_in_window(h_float, start, end):
    """Retorna True se o centro da hora (h+0.5) estiver na janela [start,end). Suporta janelas com .5 e cruzando meia-noite."""
    c = float(h_float) + 0.5
    s = float(start)
    e = float(end)
    if s < e:
        return (c >= s) and (c < e)
    else:
        # janela cruza 24h
        return (c >= s) or (c < e)


def _fmt_h(h):
    return f"{int(h)}:30" if abs(h - int(h) - 0.5) < 1e-9 else f"{int(h)}:00"


def empty_profile(ps, pe, for_fds=False):
    hrs = np.arange(24)
    labels = [f"{h}-{h+1}" for h in hrs]
    posto = ["FP"] * 24 if for_fds else ["P" if (h >= ps and h < pe) else "FP" for h in hrs]
    return pd.DataFrame({"Hora": labels, "H": hrs, "kW": [0.0] * 24, "FP": [0.0] * 24, "Tipo_FP": ["Neutro"] * 24, "Posto": posto})


def default_profile(ps, pe, for_fds=False):
    hrs = np.arange(24)
    labels = [f"{h}-{h+1}" for h in hrs]
    kW = [35.8] + [40.0] * 5 + [110.0] * 6 + [150.0] * 5 + [160.0] * 3 + [110.0] * 4
    FP = [0.8] * 6 + [0.7] * 6 + [0.8] * 5 + [0.9, 1.0, 0.9] + [0.7] * 4
    TIPO = ["Indutivo"] * 24
    posto = ["FP"] * 24 if for_fds else ["P" if (h >= ps and h < pe) else "FP" for h in hrs]
    return pd.DataFrame({"Hora": labels, "H": hrs, "kW": kW, "FP": FP, "Tipo_FP": TIPO, "Posto": posto})


def apply_interval_values(df, hora_inicial, hora_final, kw=None, fp=None, tipo_fp=None):
    out = df.copy()
    hora_inicial = int(hora_inicial)
    hora_final = int(hora_final)
    if hora_inicial <= hora_final:
        mask = (out["H"] >= hora_inicial) & (out["H"] <= hora_final)
    else:
        mask = (out["H"] >= hora_inicial) | (out["H"] <= hora_final)
    if kw is not None:
        out.loc[mask, "kW"] = float(kw)
    if fp is not None:
        out.loc[mask, "FP"] = float(fp)
    if tipo_fp is not None:
        out.loc[mask, "Tipo_FP"] = tipo_fp
    return out


def copy_profile_values(source_df, target_df):
    out = target_df.copy()
    out["kW"] = source_df["kW"].tolist()
    out["FP"] = source_df["FP"].tolist()
    out["Tipo_FP"] = source_df["Tipo_FP"].tolist()
    return out


def hour_overlap(start, dur, h):
    end = (start + dur) % 24
    if dur >= 24:
        return True
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

    def overlap(a1, a2, b1, b2):
        lo = max(a1, b1)
        hi = min(a2, b2)
        return max(0.0, hi - lo)

    if end <= 24.0:
        ol = overlap(start, end, h, h + 1)
    else:
        ol = overlap(start, 24.0, h, h + 1) + overlap(0.0, end - 24.0, h, h + 1)
    return max(0.0, min(1.0, ol))
