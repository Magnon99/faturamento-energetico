import numpy as np


def RS(x):
    try:
        return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(x)


def latex_num(x):
    if isinstance(x, (int, np.integer)):
        return f"{int(x)}"
    try:
        return f"{float(x):.5f}".rstrip("0").rstrip(".")
    except:
        return str(x)

