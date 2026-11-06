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
    "orc": dict(
        inputs=["ek_orc"], adj="Orcish", mat="Leather", lames="Iron-Plated", metal="Iron and Tusk",
        mantle="Bear-Fur and Raven-Feather",
        pal=dict(motif="steps",
                 hide=(0.28, 0.23, 0.19), cord=(0.16, 0.13, 0.11), hide_fine=(0.30, 0.20, 0.16), cord_fine=(0.44, 0.12, 0.08),
                 hide_royal=(0.12, 0.11, 0.10), cord_royal=(0.46, 0.15, 0.10), red=(0.50, 0.13, 0.08), ochre=(0.58, 0.38, 0.18),
                 bone=(0.88, 0.82, 0.65), band=(0.58, 0.23, 0.12), girdle=(0.18, 0.15, 0.12), stitch=(0.64, 0.55, 0.40),
                 war_paint=(0.60, 0.18, 0.10), bead=(0.74, 0.70, 0.60), trophy=(0.90, 0.84, 0.68), claw=(0.12, 0.10, 0.08),
                 armour_hide=(0.22, 0.18, 0.14), lame=(0.42, 0.44, 0.43), metal=(0.55, 0.57, 0.55), gem=(0.62, 0.19, 0.08),
                 duke_base=(0.30, 0.20, 0.16), king_base=(0.10, 0.09, 0.08), feather=(0.09, 0.10, 0.11),
                 feather_dark=(0.055, 0.06, 0.065), fur=(0.44, 0.35, 0.26), lining=(0.32, 0.09, 0.07))),
    "goblin": dict(
        inputs=["ek_goblin"], adj="Goblin", mat="Scavenged Hide", lames="Bone-Lashed", metal="Scavenged Iron and Bone",
        mantle="Rag-and-Feather",
        pal=dict(motif="zigzag",
                 hide=(0.48, 0.42, 0.30), cord=(0.30, 0.26, 0.19), hide_fine=(0.40, 0.36, 0.25), cord_fine=(0.55, 0.27, 0.09),
                 hide_royal=(0.22, 0.25, 0.17), cord_royal=(0.60, 0.32, 0.12), red=(0.60, 0.28, 0.08), ochre=(0.70, 0.54, 0.18),
                 bone=(0.79, 0.74, 0.58), band=(0.60, 0.29, 0.09), girdle=(0.29, 0.27, 0.20), stitch=(0.65, 0.58, 0.40),
                 war_paint=(0.68, 0.35, 0.08), bead=(0.74, 0.68, 0.51), trophy=(0.85, 0.79, 0.61), sinew=(0.58, 0.51, 0.35),
                 armour_hide=(0.34, 0.30, 0.22), lame=(0.74, 0.69, 0.52), metal=(0.45, 0.43, 0.36), gem=(0.46, 0.60, 0.18),
                 duke_base=(0.38, 0.33, 0.22), king_base=(0.18, 0.21, 0.14), feather=(0.34, 0.25, 0.13),
                 feather_dark=(0.16, 0.19, 0.12), fur=(0.58, 0.53, 0.40), lining=(0.32, 0.29, 0.22))),
    "kothringi": dict(
        inputs=["ek_nedic_south"], adj="Kothringi", mat="Reed-Cloth", lames="Silver-and-Reed", metal="Silver and River Pearl",
        mantle="Reed-Fringed Feather", bare_f=True,
        pal=dict(motif="scales",
                 hide=(0.57, 0.59, 0.39), cord=(0.37, 0.40, 0.23), hide_fine=(0.30, 0.43, 0.32), cord_fine=(0.73, 0.77, 0.73),
                 hide_royal=(0.12, 0.26, 0.21), cord_royal=(0.80, 0.83, 0.78), red=(0.18, 0.44, 0.32), ochre=(0.65, 0.66, 0.34),
                 bone=(0.90, 0.89, 0.80), band=(0.23, 0.43, 0.28), girdle=(0.30, 0.34, 0.21), stitch=(0.75, 0.77, 0.57),
                 war_paint=(0.23, 0.49, 0.33), bead=(0.93, 0.91, 0.84), trophy=(0.87, 0.89, 0.83), sinew=(0.53, 0.58, 0.33),
                 armour_hide=(0.34, 0.39, 0.24), lame=(0.65, 0.72, 0.66), metal=(0.77, 0.82, 0.80), gem=(0.94, 0.91, 0.82),
                 duke_base=(0.29, 0.40, 0.29), king_base=(0.10, 0.22, 0.18), feather=(0.22, 0.37, 0.27),
                 feather_dark=(0.10, 0.23, 0.17), fur=(0.77, 0.79, 0.56), lining=(0.15, 0.32, 0.24))),
    "lilmothiit": dict(
        inputs=["ek_lilmothiit"], adj="Lilmothiit", mat="Woven-Fibre", lames="Shell-Plated", metal="Shell and Bright Bead",
        mantle="Fibre-Fringed Feather", bare_f=True,
        pal=dict(motif="leaves",
                 hide=(0.70, 0.61, 0.42), cord=(0.45, 0.36, 0.20), hide_fine=(0.58, 0.38, 0.18), cord_fine=(0.08, 0.43, 0.50),
                 hide_royal=(0.11, 0.26, 0.30), cord_royal=(0.84, 0.48, 0.15), red=(0.08, 0.48, 0.55), ochre=(0.88, 0.53, 0.13),
                 bone=(0.94, 0.86, 0.70), band=(0.12, 0.46, 0.50), girdle=(0.37, 0.30, 0.18), stitch=(0.79, 0.69, 0.44),
                 war_paint=(0.18, 0.50, 0.55), bead=(0.12, 0.65, 0.70), trophy=(0.95, 0.87, 0.72), sinew=(0.63, 0.52, 0.31),
                 armour_hide=(0.43, 0.35, 0.21), lame=(0.89, 0.80, 0.65), metal=(0.92, 0.83, 0.70), gem=(0.84, 0.31, 0.13),
                 duke_base=(0.57, 0.37, 0.17), king_base=(0.09, 0.22, 0.25), feather=(0.10, 0.42, 0.45),
                 feather_dark=(0.08, 0.23, 0.27), fur=(0.86, 0.73, 0.43), lining=(0.13, 0.34, 0.37))),
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

# EK2's liches (trait lich_character) wear their rank's pieces in these burial colours, whatever their
# culture: one texture set per piece type (ek2lc_lich_<kind>_01), then undead.lich_finish() over it.
# Not in CULTURES: it has no culture inputs of its own.
LICH = dict(
    adj="Lich's Burial",
    pal=dict(motif="zigzag",
             hide=(0.085, 0.080, 0.075), cord=(0.035, 0.033, 0.030), hide_fine=(0.075, 0.064, 0.058),
             cord_fine=(0.045, 0.036, 0.034), hide_royal=(0.045, 0.040, 0.045), cord_royal=(0.050, 0.040, 0.042),
             red=(0.58, 0.57, 0.54), ochre=(0.46, 0.44, 0.40), black=(0.025, 0.024, 0.023), bone=(0.70, 0.63, 0.45),
             band=(0.60, 0.59, 0.56), girdle=(0.060, 0.055, 0.050), stitch=(0.22, 0.21, 0.20), war_paint=(0.56, 0.55, 0.52),
             bead=(0.66, 0.59, 0.42), trophy=(0.72, 0.65, 0.47), claw=(0.10, 0.09, 0.07), sinew=(0.060, 0.055, 0.050),
             armour_hide=(0.070, 0.065, 0.060), armour_stitch=(0.21, 0.20, 0.19), lame=(0.64, 0.58, 0.42),
             hole=(0.015, 0.014, 0.013), metal=(0.42, 0.33, 0.12), gem=(0.20, 0.06, 0.26), duke_base=(0.080, 0.070, 0.065),
             king_base=(0.040, 0.035, 0.040), feather=(0.050, 0.050, 0.055), shaft=(0.45, 0.44, 0.42),
             fur=(0.42, 0.41, 0.39), feather_dark=(0.035, 0.035, 0.040), shaft_dark=(0.32, 0.31, 0.30),
             lining=(0.09, 0.04, 0.11)))
