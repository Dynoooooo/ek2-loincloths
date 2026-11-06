"""Write the mod's game script files for the Reach and every culture in cultures.py:
genes, accessories, portrait modifiers (who wears what), barbershop entries and English names.

    python3 source/tools/gen_script_files.py

Template indices are fixed by their order here: the Reach's first (as before), then each culture
in cultures.py order. Only ever add cultures at the end, or saved characters change pieces.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(MOD, "source"))
from cultures import CULTURES  # noqa: E402

REACH = dict(inputs=["ek_nedic_reach"], adj="Reach", mat="Hide", lames="Hide-and-Bone", metal="Bronze and Garnet",
             mantle="Fur-and-Feather")
ALL = {"reach": REACH, **CULTURES}
BOM = "﻿"
SEXES = (("m", "male", "no", "men"), ("f", "female", "yes", "women"))

# gene -> (none template, [kinds in index order])
GENES = {
    "gene_ek2lc_loincloth": ("ek2lc_no_loincloth", ["hide", "fine", "royal"]),
    "gene_ek2lc_top": ("ek2lc_no_top", ["band", "band_fine", "band_royal"]),
    "gene_ek2lc_war": ("ek2lc_no_war", ["war", "armour", "duke", "king", "emperor"]),
    "gene_ek2lc_mantle": ("ek2lc_no_mantle", ["mantle"]),
}
WOMEN_ONLY = {"band", "band_fine", "band_royal"}


def tmpl(c, kind):  # gene template; the Reach's plain loincloth was named "hide", so is everyone's
    return "ek2lc_%s_%s" % (c, kind)


def acc(s, c, kind):
    return "ek2lc_%s_%s_%s_01" % (s, c, kind)


def write(rel, text):
    p = os.path.join(MOD, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote", rel)


# ------------------------------------------------------------------ genes
def genes():
    out = [BOM + """# EK2 Loincloths genes. Template 0 of each gene is "none". Written by source/tools/gen_script_files.py.
#   gene_ek2lc_loincloth: the loincloth itself (plain; fine and royal for rulers)
#   gene_ek2lc_top: chest pieces, kept separate so a culture can drop them for some women
#   gene_ek2lc_war: war add-ons worn over the loincloth (war girdle, or girdle with the armoured strip skirt;
#     for rulers the royal girdle with aprons and ornaments by title tier)
#   gene_ek2lc_mantle: the emperor's collar and feather cape, worn with the emperor's war-slot pieces
special_genes = {
	accessory_genes = {"""]
    for gene, (none, kinds) in GENES.items():
        out.append("\t\t%s = {" % gene)
        rows = [(none, None, None)] + [(tmpl(c, k), c, k) for c in ALL for k in kinds]
        for i, (t, c, k) in enumerate(rows):
            m = "empty" if c is None or k in WOMEN_ONLY else acc("m", c, k)
            f = "empty" if c is None else acc("f", c, k)
            out.append("""			%s = {
				index = %d
				male = { 1 = %s }
				female = { 1 = %s }
				boy = { 1 = empty }
				girl = { 1 = empty }
			}""" % (t, i, m, f))
        out.append("\t\t}")
    out.append("\t}\n}\n")
    write("common/genes/ek2lc_genes.txt", "\n".join(out))


# ------------------------------------------------------------------ accessories
REACH_ORDER = [("m", "hide"), ("f", "hide"), ("f", "band"), ("m", "war"), ("f", "war"), ("m", "armour"), ("f", "armour"),
               ("m", "fine"), ("f", "fine"), ("m", "royal"), ("f", "royal"), ("m", "duke"), ("f", "duke"),
               ("m", "king"), ("f", "king"), ("m", "emperor"), ("f", "emperor"), ("f", "band_fine"), ("f", "band_royal"),
               ("m", "mantle"), ("f", "mantle")]


def accessories():
    out = [BOM + "# EK2 Loincloths accessories"]
    order = [("reach", s, k) for s, k in REACH_ORDER]
    for c in CULTURES:
        for _, kinds in GENES.values():
            for k in kinds:
                for s in ("m", "f"):
                    if not (s == "m" and k in WOMEN_ONLY):
                        order.append((c, s, k))
    for c, s, k in order:
        a = acc(s, c, k)
        out.append("%s = {\n\tentity = { required_tags = \"\"\t\tshared_pose_entity = torso\t\tentity = %s_entity }\n}" % (a, a))
    write("gfx/portraits/accessories/ek2lc_accessories.txt", "\n".join(out))


# ------------------------------------------------------------------ portrait modifiers (who wears what)
def dna(pairs):
    lines = ["\t\tdna_modifiers = {"]
    for gene, t in pairs:
        lines.append("""			accessory = {
				mode = add
				gene = %s
				template = %s
				range = { 0 1 }
			}""" % (gene, t))
    lines.append("\t\t}")
    return "\n".join(lines)


NUDE = """				NOR = {
					should_be_fully_naked_portrait_trigger = yes
					should_be_topless_portrait_trigger = yes
				}"""


def culture_cond(cd, commoner):
    if commoner:
        one = ["portrait_commoner_clothing_trigger = {\n\t\t\t\t\tCULTURE_INPUT = %s\n\t\t\t\t}" % i for i in cd["inputs"]]
    else:
        one = ["portrait_%s_clothing_trigger = yes" % i for i in cd["inputs"]]
    if len(one) == 1:
        return "\t\t\t\t" + one[0]
    return "\t\t\t\tOR = {\n" + "\n".join("\t\t\t\t\t" + o.replace("\n", "\n\t") for o in one) + "\n\t\t\t\t}"


def modifier(name, comment, pieces, mods):
    """pieces: (loincloth, top, war, mantle) kinds or None; mods: list of (add, [condition lines])."""
    pairs = [("clothes", "no_clothes"), ("legwear", "no_legwear"), ("cloaks", "no_cloak")]
    for gene, k in zip(GENES, pieces):
        pairs.append((gene, GENES[gene][0] if k is None else k))
    w = ["\t\tweight = {", "\t\t\tbase = 0"]
    for add, conds in mods:
        w.append("\t\t\tmodifier = {")
        w.append("\t\t\t\tadd = %s" % add)
        w.extend(conds)
        w.append(NUDE)
        w.append("\t\t\t}")
    w.append("\t\t}")
    return "\t# %s\n\t%s = {\n%s\n%s\n\t}\n" % (comment, name, dna(pairs), "\n".join(w))


TIERS = [("county", "barony", "county", "fine", "fine", None, "county and below: the loincloth (and chest band) in finer dyed material"),
         ("duke", "duchy", "duchy", "fine", "fine", "duke", "duke: the fine loincloth, the royal girdle, a short front apron, beads"),
         ("king", "kingdom", "kingdom", "royal", "royal", "king", "king: royal loincloth, long front and back aprons, feathers"),
         ("emperor", "empire", "hegemony", "royal", "royal", "emperor", "emperor: the king's pieces in precious trim, and the mantle")]


def modifiers():
    out = [BOM + """# EK2 Loincloths: who wears a loincloth. Written by source/tools/gen_script_files.py.
# Priority 101 applies this after every EK2 outfit group (EK2's highest is 100), so a
# loincloth wearer never gets an EK2 outfit, legwear or cloak on top of the loincloth.
# Every modifier sets all of our genes, so nothing is left over from another choice.
ek2lc_loincloth = {
	usage = game
	selection_behavior = weighted_random
	priority = 101

	ek2lc_none = {
""" + dna([(g, n) for g, (n, _) in GENES.items()]) + """
		weight = {
			base = 1
		}
	}
"""]
    for c, cd in ALL.items():
        adj = cd["adj"]
        T = lambda k: tmpl(c, k)  # noqa: E731
        for look in ("hide", "war", "armour"):
          for s, sex, fem, people in SEXES:
            top = (lambda k: T(k)) if s == "f" else (lambda k: None)
            base = ["\t\t\t\tis_female = %s" % fem]
            com = base + ["\t\t\t\tis_adult = yes", culture_cond(cd, True), "\t\t\t\tek2lc_royal_trigger = no", "\t\t\t\tek2lc_war_role_trigger = no"]
            if look != "hide":
                pass
            elif s == "f" and cd.get("bare_f"):
                out.append(modifier("ek2lc_%s_hide_f" % c, "Adult %s women who are commoners: the loincloth and the chest band; "
                                    "while \"Show nudity\" is on, one in three goes bare-chested (next modifier)." % adj,
                                    (T("hide"), T("band"), None, None),
                                    [(100, com + ["\t\t\t\tshould_show_nudity = no"]), (60, com + ["\t\t\t\tshould_show_nudity = yes"])]))
                out.append(modifier("ek2lc_%s_hide_f_bare" % c, "Adult %s women who are commoners, bare-chested, only while \"Show nudity\" is on." % adj,
                                    (T("hide"), None, None, None), [(30, com + ["\t\t\t\tshould_show_nudity = yes"])]))
            else:
                out.append(modifier("ek2lc_%s_hide_%s" % (c, s), "Adult %s %s who are commoners%s. EK2's commoner rule already leaves out armour."
                                    % (adj, people, ": the loincloth and always the chest band" if s == "f" else ""),
                                    (T("hide"), top("band"), None, None), [(100, com)]))
            cul = culture_cond(cd, False)
            if look == "war":
                out.append(modifier("ek2lc_%s_war_%s" % (c, s), "Adult %s %s in a war role while their realm is at war: the loincloth with the "
                                "war girdle and trophies%s, instead of EK2's armour." % (adj, people, ", and always the chest band" if s == "f" else ""),
                                (T("hide"), top("band"), T("war"), None),
                                [(100, base + [cul, "\t\t\t\tek2lc_war_role_trigger = yes", "\t\t\t\tek2lc_armour_role_trigger = no"])]))
            if look == "armour":
                out.append(modifier("ek2lc_%s_armour_%s" % (c, s), "Adult %s %s among the best fighters (knights, or prowess 12+) while their realm "
                                "is at war: the loincloth with the war girdle and the strip skirt%s." % (adj, people, ", and always the chest band" if s == "f" else ""),
                                (T("hide"), top("band"), T("armour"), None),
                                [(100, base + [cul, "\t\t\t\tek2lc_armour_role_trigger = yes"])]))
        for tier, lo, hi, lk, bk, wk, desc in TIERS:
            for s, sex, fem, people in SEXES:
                top = T("band" if bk == "hide" else "band_" + bk) if s == "f" else None
                out.append(modifier("ek2lc_%s_royal_%s_%s" % (c, tier, s),
                                    "%s %s, rulers and their spouses (higher of the two top title tiers), %s." % (adj, people, desc),
                                    (T(lk), top, T(wk) if wk else None, T("mantle") if tier == "emperor" else None),
                                    [('2  # against 1 for "no loincloth": two in three %s rulers wear it' % adj,
                                      ["\t\t\t\tis_female = %s" % fem, cul, "\t\t\t\tek2lc_war_role_trigger = no",
                                       "\t\t\t\tek2lc_royal_tier_trigger = { LOW = %s HIGH = %s }" % (lo, hi)])]))
    out.append("}\n")
    write("gfx/portraits/portrait_modifiers/ek2lc_loincloths.txt", "\n".join(out))


# ------------------------------------------------------------------ barbershop and names
CUSTOM = [("ek2lc_custom_loincloth", 9, "gene_ek2lc_loincloth", "Loincloth", "No Loincloth"),
          ("ek2lc_custom_top", 10, "gene_ek2lc_top", "Chest Piece", "No Chest Piece"),
          ("ek2lc_custom_girdle", 11, "gene_ek2lc_war", "Girdle", "No Girdle"),
          ("ek2lc_custom_mantle", 12, "gene_ek2lc_mantle", "Mantle", "No Mantle")]


def piece_name(cd, k):
    a, m = cd["adj"], cd["mat"]
    return {"hide": "%s %s Loincloth" % (a, m), "fine": "%s Fine %s Loincloth" % (a, m), "royal": "%s Royal %s Loincloth" % (a, m),
            "band": "%s %s Chest Band" % (a, m), "band_fine": "%s Fine Chest Band" % a, "band_royal": "%s Royal Chest Band" % a,
            "war": "%s War Girdle with Trophies" % a, "armour": "%s %s Strip Skirt" % (a, cd["lames"]),
            "duke": "%s Ducal Girdle with Apron" % a, "king": "%s Royal Girdle with Long Aprons" % a,
            "emperor": "%s Imperial Girdle in %s" % (a, cd["metal"]), "mantle": "%s Imperial %s Mantle" % (a, cd["mantle"])}[k]


def barbershop():
    out = [BOM + "# EK2 Loincloths: barbershop entries, one group per gene, the vanilla way (add_accessory_modifiers).",
           "# Written by source/tools/gen_script_files.py.",
           "# Priority 102 puts a barbershop choice after our game group (101), so it wins on our genes.",
           "# Chest pieces only list for women.", ""]
    loc = [BOM + "l_english:"]
    for grp, pos, gene, title, none in CUSTOM:
        none_t, kinds = GENES[gene]
        out += ["%s = {" % grp, "\tusage = customization", "\tinterface_position = %d" % pos, "\tpriority = 102", ""]
        valid = "\t\tis_valid_custom = { is_female = yes }" if gene == "gene_ek2lc_top" else None
        for t in [none_t] + [tmpl(c, k) for c in ALL for k in kinds]:
            out += ["\tadd_accessory_modifiers = {", "\t\tgene = %s" % gene, "\t\ttemplate = %s" % t] + ([valid] if valid else []) + ["\t}"]
        out += ["}", ""]
        loc.append(' PORTRAIT_MODIFIER_%s: "%s"' % (grp, title))
        loc.append(' PORTRAIT_MODIFIER_%s_none: "%s"' % (grp, none))
        for s in ("male", "female", "boy", "girl"):
            loc.append(' PORTRAIT_MODIFIER_%s_%s_empty: "$PORTRAIT_MODIFIER_%s_none$"' % (grp, s, grp))
        for c, cd in ALL.items():
            for k in kinds:
                m, f = acc("m", c, k), acc("f", c, k)
                if k in WOMEN_ONLY:
                    loc.append(' PORTRAIT_MODIFIER_%s_%s: "%s"' % (grp, f, piece_name(cd, k)))
                else:
                    loc.append(' PORTRAIT_MODIFIER_%s_%s: "%s"' % (grp, m, piece_name(cd, k)))
                    loc.append(' PORTRAIT_MODIFIER_%s_%s: "$PORTRAIT_MODIFIER_%s_%s$"' % (grp, f, grp, m))
    write("gfx/portraits/portrait_modifiers/ek2lc_custom.txt", "\n".join(out))
    write("localization/english/ek2lc_l_english.yml", "\n".join(loc) + "\n")


if __name__ == "__main__":
    genes()
    accessories()
    modifiers()
    barbershop()
