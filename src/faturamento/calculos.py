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

