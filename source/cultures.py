"""Culture variants of the Reach pieces: same meshes, new diffuse textures, own names.

Used by build_reach_hide.py (textures and .asset files) and tools/gen_script_files.py
(genes, accessories, portrait modifiers, barbershop entries, localisation).

A palette maps a colour role to that culture's colour. ROLES holds the Reach colour each role
replaces, exactly as written in the texture code; a role a palette leaves out keeps the Reach
colour. "motif" picks the painted band on the plain loincloth's flaps.
"""

ROLES = {
    "hide": (0.52, 0.37, 0.24), "cord": (0.33, 0.22, 0.14),            # plain loincloth
    "hide_fine": (0.50, 0.30, 0.18), "cord_fine": (0.40, 0.12, 0.07),  # county and duke
    "hide_royal": (0.21, 0.15, 0.11), "cord_royal": (0.36, 0.09, 0.06),  # king and emperor
    "red": (0.42, 0.07, 0.05), "ochre": (0.62, 0.38, 0.12), "black": (0.06, 0.045, 0.035), "bone": (0.84, 0.78, 0.64),
    "band": (0.50, 0.13, 0.08),                                         # painted band on the plain flaps
    "girdle": (0.27, 0.18, 0.11), "stitch": (0.62, 0.52, 0.38), "war_paint": (0.55, 0.12, 0.07),
    "bead": (0.82, 0.77, 0.64), "trophy": (0.84, 0.79, 0.66), "claw": (0.16, 0.13, 0.10), "sinew": (0.55, 0.44, 0.30),
    "armour_hide": (0.31, 0.21, 0.13), "armour_stitch": (0.6, 0.5, 0.36), "lame": (0.83, 0.78, 0.64), "hole": (0.12, 0.08, 0.05),
    "metal": (0.70, 0.50, 0.22), "gem": (0.45, 0.03, 0.07),             # emperor's trim and accent
    "duke_base": (0.46, 0.25, 0.15), "king_base": (0.17, 0.12, 0.09),
    "feather": (0.12, 0.12, 0.13), "shaft": (0.75, 0.72, 0.66),         # royal ornament feather
    "fur": (0.80, 0.77, 0.70), "feather_dark": (0.085, 0.085, 0.095), "shaft_dark": (0.52, 0.50, 0.46),
    "lining": (0.30, 0.055, 0.055),                                      # mantle
}

# key: used in file and template names. inputs: EK2 clothing-gfx culture inputs (portrait_<input>_clothing_trigger).
# names: what the barbershop shows. bare_f: adult women may go bare-chested while "Show nudity" is on.
CULTURES = {
    "ashlander": dict(
        inputs=["ek_ashlander"], adj="Ashlander", mat="Netch-Leather", lames="Chitin-Plated", metal="Chitin and Glass",
        mantle="Kagouti-Fur and Racer-Plume",
        pal=dict(motif="steps",
                 hide=(0.47, 0.41, 0.33), cord=(0.30, 0.25, 0.19), hide_fine=(0.44, 0.31, 0.20), cord_fine=(0.42, 0.17, 0.06),
                 hide_royal=(0.19, 0.16, 0.13), cord_royal=(0.40, 0.15, 0.05), red=(0.48, 0.17, 0.05), ochre=(0.70, 0.50, 0.17),
                 band=(0.52, 0.20, 0.06), girdle=(0.25, 0.21, 0.16), war_paint=(0.62, 0.22, 0.06), armour_hide=(0.28, 0.23, 0.17),
                 lame=(0.55, 0.33, 0.10), metal=(0.58, 0.36, 0.10), gem=(0.16, 0.50, 0.22), duke_base=(0.44, 0.30, 0.18),
                 king_base=(0.16, 0.14, 0.12), feather=(0.16, 0.14, 0.22), feather_dark=(0.12, 0.10, 0.15),
                 fur=(0.72, 0.64, 0.50), lining=(0.36, 0.20, 0.07))),
    "bosmer": dict(
        inputs=["ek_bosmeri"], adj="Bosmer", mat="Hide", lames="Bone-Plated", metal="Horn and Amber",
        mantle="Wolf-Fur and Feather",
        pal=dict(motif="leaves",
                 hide=(0.43, 0.34, 0.22), cord=(0.28, 0.22, 0.13), hide_fine=(0.32, 0.30, 0.17), cord_fine=(0.20, 0.28, 0.12),
                 hide_royal=(0.13, 0.17, 0.10), cord_royal=(0.30, 0.20, 0.08), red=(0.16, 0.32, 0.12), ochre=(0.72, 0.50, 0.12),
                 band=(0.18, 0.34, 0.13), girdle=(0.24, 0.20, 0.12), war_paint=(0.20, 0.38, 0.12), armour_hide=(0.28, 0.24, 0.14),
                 metal=(0.78, 0.70, 0.52), gem=(0.82, 0.48, 0.08), duke_base=(0.30, 0.27, 0.15), king_base=(0.10, 0.14, 0.08),
                 feather=(0.10, 0.16, 0.09), feather_dark=(0.07, 0.11, 0.06), fur=(0.58, 0.46, 0.32), lining=(0.12, 0.24, 0.10))),
    "argonian": dict(
        inputs=["ek_argonian"], adj="Argonian", mat="Hide", lames="Scale-Plated", metal="Hist Amber and Jade",
        mantle="Reed and Feather", bare_f=True,
        pal=dict(motif="scales",
                 hide=(0.44, 0.40, 0.26), cord=(0.36, 0.33, 0.18), hide_fine=(0.20, 0.34, 0.30), cord_fine=(0.62, 0.42, 0.10),
                 hide_royal=(0.07, 0.20, 0.19), cord_royal=(0.60, 0.38, 0.08), red=(0.06, 0.40, 0.38), ochre=(0.72, 0.48, 0.10),
                 band=(0.08, 0.42, 0.38), girdle=(0.22, 0.22, 0.13), war_paint=(0.10, 0.46, 0.40), armour_hide=(0.25, 0.25, 0.15),
                 lame=(0.38, 0.46, 0.30), metal=(0.76, 0.50, 0.10), gem=(0.05, 0.55, 0.50), duke_base=(0.20, 0.32, 0.28),
                 king_base=(0.06, 0.14, 0.13), feather=(0.08, 0.30, 0.26), feather_dark=(0.05, 0.18, 0.16),
                 fur=(0.68, 0.64, 0.40), lining=(0.06, 0.26, 0.24))),
    "khajiit": dict(
        inputs=["ek_anequinan", "ek_pellitinian"], adj="Khajiiti", mat="Cotton", lames="Bone-Plated", metal="Gold and Moonstone",
        mantle="Silk-Fringed Feather",
        pal=dict(motif="moons",
                 hide=(0.68, 0.58, 0.40), cord=(0.45, 0.30, 0.12), hide_fine=(0.70, 0.45, 0.12), cord_fine=(0.26, 0.12, 0.36),
                 hide_royal=(0.16, 0.08, 0.24), cord_royal=(0.75, 0.55, 0.18), red=(0.30, 0.10, 0.40), ochre=(0.82, 0.56, 0.14),
                 band=(0.20, 0.16, 0.42), girdle=(0.36, 0.24, 0.12), war_paint=(0.62, 0.30, 0.06), armour_hide=(0.35, 0.25, 0.13),
                 metal=(0.80, 0.62, 0.22), gem=(0.62, 0.70, 0.85), duke_base=(0.62, 0.40, 0.12), king_base=(0.14, 0.07, 0.20),
                 feather=(0.16, 0.10, 0.22), feather_dark=(0.12, 0.08, 0.18), fur=(0.82, 0.70, 0.40), lining=(0.20, 0.10, 0.30))),
}

# Pieces each culture gets: kind -> (Reach piece whose mesh it uses, Reach texture set whose normal and
# properties maps it reuses). The mesh names take the body letter: ek2lc_<m|f>_reach_<mesh>_01.
KINDS = {
    "hide": ("hide", "hide"), "fine": ("hide", "fine"), "royal": ("hide", "royal"),
    "band": ("band", "hide"), "band_fine": ("band", "fine"), "band_royal": ("band", "royal"),  # women only
    "war": ("war", "war"), "armour": ("armour", "armour"),
    "duke": ("duke", "duke"), "king": ("king", "king"), "emperor": ("king", "emperor"),
    "mantle": ("mantle", "mantle"),
}
# texture set each kind's diffuse comes from (the band shares the loincloth's sets)
TEX_OF = {"hide": "hide", "fine": "fine", "royal": "royal", "band": "hide", "band_fine": "fine", "band_royal": "royal",
          "war": "war", "armour": "armour", "duke": "duke", "king": "king", "emperor": "emperor", "mantle": "mantle"}
