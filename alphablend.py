# alphablend equation

if (-1 >> 1) < 0:
    def ALPHA_BLEND_COMP(sC, dC, sA):
        return ((((sC - dC) * sA + sC) >> 8) + dC)
else:
    def ALPHA_BLEND_COMP(sC, dC, sA):
        return (((dC << 8) + (sC - dC) * sA + sC) >> 8)

def ALPHA_BLEND(s, d):
    sR, sG, sB, sA = s
    dR, dG, dB, dA = d
    if dA:
        dR = ALPHA_BLEND_COMP(sR, dR, sA)
        dG = ALPHA_BLEND_COMP(sG, dG, sA)
        dB = ALPHA_BLEND_COMP(sB, dB, sA)
        dA = sA + dA - ((sA * dA) // 255)
    else:
        dR = sR
        dG = sG
        dB = sB
        dA = sA
    return dR, dG, dB, dA
