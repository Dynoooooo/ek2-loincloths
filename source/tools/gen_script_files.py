"""Write the mod's game script files for the Reach and every culture in cultures.py:
genes, accessories, portrait modifiers (who wears what), barbershop entries and English names.

    python3 source/tools/gen_script_files.py

Template indices are fixed by their order here (gene_rows()): the Reach's first (as before), then each
culture in cultures.py order, then the lich's burial regalia, then the grave wraps; a culture added
later goes after those. Only ever add at the end, or saved characters change pieces.

EK2's undead (scripted triggers in common/scripted_triggers/ek2lc_triggers.txt; neither while a ritual
conceals them): a lich gets every modifier's lich twin (same rule, lich textures) instead of the
modifier; other undead get their culture's rotted grave wrap, whatever their rank.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(MOD, "source"))
from cultures import CULTURES, LICH  # noqa: E402
from colour import entity_name  # noqa: E402

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
WOMEN_ONLY = {"band", "band_fine", "band_royal", "grave_band"}
# EK2's undead. Liches: every kind in lich textures (template culture "lich"). Other undead: the
# culture's plain loincloth and chest band, rotted (kinds "grave", "grave_band").
GRAVE = {"gene_ek2lc_loincloth": "grave", "gene_ek2lc_top": "grave_band"}
EARLY = ("reach", "ashlander", "bosmer", "argonian", "khajiit", "orc", "goblin", "kothringi", "lilmothiit")  # before the undead
assert tuple(ALL)[:len(EARLY)] == EARLY
LICH_TAG = "ek2lc_lich"    # set by the lich's loincloths: the extras draw their lich version
GRAVE_TAG = "ek2lc_grave"  # set by the grave wraps: the extras draw nothing
# Culture-independent extras: gene -> (none template, [(kind, barbershop name, game rule)], barbershop
# group name, its "none" name, tags that hide it). Their accessories draw only while one of our
# loincloths is worn (LOINCLOTH_TAG) and none of their hiding tags is set, so the game rule needs no
# culture or look: anyone 14+ qualifies, and EK2 clothes simply hide nothing. Over a grave wrap
# (GRAVE_TAG) they draw nothing; over a lich's loincloth (LICH_TAG), their lich version.
LOINCLOTH_TAG = "ek2lc_loincloth"
GIRDLE_TAG = "ek2lc_girdle"  # set by every piece of gene_ek2lc_war (war, armoured and royal girdles)
MANTLE_TAG = "ek2lc_mantle"  # set by the emperor's mantle
EXTRA = {"gene_ek2lc_trophy": ("ek2lc_no_trophy", [
    ("trophy_1", "Trophy Belt: Two Trophies", "prowess >= 8\n\t\t\t\tprowess < 12"),
    ("trophy_2", "Trophy Belt: Four Trophies", "prowess >= 12\n\t\t\t\tprowess < 16"),
    ("trophy_3", "Trophy Belt: Four Trophies and Beads", "prowess >= 16")], "Trophy Belt", "No Trophy Belt", []),
    # tournament fighters who have fought on foot (melee, wrestling, duels): one guard on the left shoulder
    "gene_ek2lc_arena": ("ek2lc_no_arena", [
        ("arena_guard", "Hide-and-Bone Shoulder Guard",
         "has_trait = tourney_participant\n\t\t\t\thas_trait_xp = { trait = tourney_participant track = foot value > 0 }")],
        "Shoulder Guard", "No Shoulder Guard", [MANTLE_TAG]),  # the mantle's collar covers that shoulder
    # non-fighters who travel with an army (ek2lc_camp_follower_trigger); the sash sits where a girdle does
    "gene_ek2lc_camp": ("ek2lc_no_camp", [("camp_wrap", "Patched Camp Wrap", "ek2lc_camp_follower_trigger = yes")],
                        "Camp Follower's Wrap", "No Camp Wrap", [GIRDLE_TAG]),
}


def xacc(s, k):  # an extra's accessory: ek2lc_m_trophy_1_01
    return "ek2lc_%s_%s_01" % (s, k)


def tmpl(c, kind):  # gene template; the Reach's plain loincloth was named "hide", so is everyone's
    return "ek2lc_%s_%s" % (c, kind)


def acc(s, c, kind):
    return "ek2lc_%s_%s_%s_01" % (s, c, kind)


def gene_rows(gene):
    """[(template, culture, kind)] after "none", in index order."""
    kinds, g = GENES[gene][1], GRAVE.get(gene)
    rows = [(tmpl(c, k), c, k) for c in EARLY for k in kinds] + [(tmpl("lich", k), "lich", k) for k in kinds]
    rows += [(tmpl(c, g), c, g) for c in EARLY if g]
    for c in ALL:
        if c not in EARLY:
            rows += [(tmpl(c, k), c, k) for k in kinds] + ([(tmpl(c, g), c, g)] if g else [])
    return rows


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
        rows = [(none, None, None)] + gene_rows(gene)
        for i, (t, c, k) in enumerate(rows):
            m = "empty" if c is None or k in WOMEN_ONLY else acc("m", c, k)
            f = "empty" if c is None else acc("f", c, k)
            out.append("""			%s = {
				index = %d
				male = { 1 = %s }
				female = { 1 = %s }
				boy = { 1 = %s }
				girl = { 1 = %s }
			}""" % (t, i, m, f, m, f))  # children: the same pieces (every piece has the infant shape)
        out.append("\t\t}")
    for gene, (none, kinds, *_) in EXTRA.items():
        out.append("\t\t%s = {" % gene)
        for i, k in enumerate([None] + [k for k, _, _ in kinds]):
            m, f = ("empty", "empty") if k is None else (xacc("m", k), xacc("f", k))
            out.append("""			%s = {
				index = %d
				male = { 1 = %s }
				female = { 1 = %s }
				boy = { 1 = %s }
				girl = { 1 = %s }
			}""" % (none if k is None else "ek2lc_" + k, i, m, f, m, f))
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
    for gene in GENES:  # the undead's, after the cultures'
        for _, c, k in gene_rows(gene):
            for s in ("m", "f"):
                if (c == "lich" or k in GRAVE.values()) and not (s == "m" and k in WOMEN_ONLY):
                    order.append((c, s, k))
    for c, s, k in order:
        a = acc(s, c, k)
        tag = LOINCLOTH_TAG if k in GENES["gene_ek2lc_loincloth"][1] else GIRDLE_TAG if k in GENES["gene_ek2lc_war"][1] \
            else MANTLE_TAG if k in GENES["gene_ek2lc_mantle"][1] else None
        if k == "grave":
            tag = LOINCLOTH_TAG + "," + GRAVE_TAG
        elif c == "lich" and tag == LOINCLOTH_TAG:
            tag += "," + LICH_TAG
        tags = '\tset_tags = "%s"\n' % tag if tag else ""
        out.append("%s = {\n%s\tentity = { required_tags = \"\"\t\tshared_pose_entity = torso\t\tentity = %s }\n}" % (a, tags, entity_name(a)))
    for gene, (none, kinds, _, _, hide) in EXTRA.items():
        for k, _, _ in kinds:
            for s in ("m", "f"):
                a = xacc(s, k)
                out.append("%s = {\n%s\tentity = { required_tags = \"%s\"\t\tshared_pose_entity = torso\t\tentity = %s }\n"
                           "\tentity = { required_tags = \"%s\"\t\tshared_pose_entity = torso\t\tentity = %s }\n"
                           "\tentity = { required_tags = \"\"\t\tshared_pose_entity = torso }\n}"
                           % (a, "".join('\tentity = { required_tags = "%s"\t\tshared_pose_entity = torso }\n' % h for h in hide + [GRAVE_TAG]),
                              LICH_TAG, entity_name(xacc(s, "lich_" + k)), LOINCLOTH_TAG, entity_name(a)))
    write("gfx/portraits/accessories/ek2lc_accessories.txt", "\n".join(out))



def figleaf():
    # The clothes gene's no_clothes template (which our wearers use) draws vanilla's fig leaf mesh in front of
    # the hips; from the side it peeks out beside our loincloth. Redefine its two accessories with a first variant
    # that draws nothing while one of our loincloths sets LOINCLOTH_TAG (the vanilla required_tags pattern,
    # as on ccp4's khanty hood). The fallback entity is vanilla's, so nobody else changes.
    # The "zz_" name sorts after vanilla's clothes.txt, so this definition is read last.
    out = [BOM + "# EK2 Loincloths: under our loincloths, hide vanilla's fig leaf (adults) and bedchamber nightshirt (children).\n# Vanilla definitions: gfx/portraits/accessories/clothes.txt; the fallback lines are vanilla's own."]
    for sex in ("male", "female"):
        a = "%s_clothes_secular_western_nudity_01" % sex
        out.append("%s = {\n\tentity = { required_tags = \"%s\"\t\tshared_pose_entity = torso }\n"
                   "\tentity = { required_tags = \"\"\t\tshared_pose_entity = torso\t\tentity = %s_entity }\n}" % (a, LOINCLOTH_TAG, a))
    # For children (boy/girl) the same no_clothes template gives vanilla's bedchamber nightshirt instead, which
    # would sit under our pieces. Same trick: nothing while our loincloth is worn (its strip covers the groin,
    # the band covers girls). set_tags is per accessory, so vanilla's shrink tags stay;
    # our modifiers switch the shrinking itself off (dna(unshrink=True)).
    for sex in ("male", "female"):
        a = "%s_clothes_situational_western_bedchamber_01_common" % sex
        out.append("%s = {\n\tset_tags = \"shrink_arms,shrink_chest,shrink_belly\"\n"
                   "\tentity = { required_tags = \"%s\"\t\tshared_pose_entity = torso }\n"
                   "\tentity = { required_tags = \"\"\t\tshared_pose_entity = torso\t\tentity = %s_entity }\n}" % (a, LOINCLOTH_TAG, a))
    write("gfx/portraits/accessories/zz_ek2lc_figleaf.txt", "\n".join(out) + "\n")


# ------------------------------------------------------------------ portrait modifiers (who wears what)
def dna(pairs, unshrink=False):
    lines = ["\t\tdna_modifiers = {"]
    if unshrink:
        # Clothes accessories set shrink tags (children's nightshirt: arms, chest, belly) and EK2's
        # special_shrink_body turns them into body shapes. Our wearers are bare under our pieces
        # (the nightshirt is hidden, see figleaf()), so switch the shrinking off for them.
        # (mode = add: special genes take no replace; our group is applied after EK2's, so this wins.)
        lines.append("""			morph = {
				mode = add
				gene = gene_shrink_body
				template = shrink_all
				value = 0
			}""")
    for gene, t in pairs:
        lines.append("""			accessory = {
				mode = add
				gene = %s
				template = %s
				range = { 0 1 }
			}""" % (gene, t))
    lines.append("\t\t}")
    return "\n".join(lines)


KIDS = "\t\t\t\tscope:age >= 4"   # under 4: vanilla's small-children clothes
TEENS = "\t\t\t\tscope:age >= 14"  # war and armour looks (brief: teens 14+ in war roles)


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


def modifier(name, comment, pieces, mods, last=()):
    """pieces: (loincloth, top, war, mantle) kinds or None; mods: list of (add, [condition lines]);
    last: weight-modifier bodies applied after the adds."""
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
    for body in last:
        w.append("\t\t\tmodifier = {\n%s\n\t\t\t}" % body)
    w.append("\t\t}")
    return "\t# %s\n\t%s = {\n%s\n%s\n\t}\n" % (comment, name, dna(pairs, unshrink=True), "\n".join(w))


UNDEAD_OFF = "\t\t\t\tfactor = 0  # EK2's undead: the lich twin below, or the grave wrap\n\t\t\t\tek2lc_undead_look_trigger = yes"


def with_lich(c, name, comment, pieces, mods):
    """The modifier, for everyone but EK2's undead, and its lich twin: the same rule and weights for
    liches, every piece in the lich's burial textures."""
    lich = tuple(None if t is None else tmpl("lich", t[len(tmpl(c, "")):]) for t in pieces)
    return [modifier(name, comment, pieces, mods, [UNDEAD_OFF]),
            modifier(name.replace("ek2lc_", "ek2lc_lich_", 1), "Lich twin of %s: the same, for liches (lich's burial regalia)." % name,
                     lich, [(add, conds + ["\t\t\t\tek2lc_lich_look_trigger = yes"]) for add, conds in mods])]


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
            com = base + [KIDS, culture_cond(cd, True), "\t\t\t\tek2lc_royal_trigger = no", "\t\t\t\tek2lc_war_role_trigger = no"]
            if look != "hide":
                pass
            elif s == "f" and cd.get("bare_f"):
                out.extend(with_lich(c, "ek2lc_%s_hide_f" % c, "%s women and girls (4+) who are commoners: the loincloth and the chest band; adult women only: "
                                    "while \"Show nudity\" is on, one in three goes bare-chested (next modifier)." % adj,
                                    (T("hide"), T("band"), None, None),
                                    [(100, com + ["\t\t\t\tshould_show_nudity = no"]), (60, com + ["\t\t\t\tshould_show_nudity = yes"])]))  # girls: 60 here, 0 for bare
                out.extend(with_lich(c, "ek2lc_%s_hide_f_bare" % c, "Adult %s women who are commoners, bare-chested, only while \"Show nudity\" is on." % adj,
                                    (T("hide"), None, None, None), [(30, com + ["\t\t\t\tis_adult = yes", "\t\t\t\tshould_show_nudity = yes"])]))
            else:
                out.extend(with_lich(c, "ek2lc_%s_hide_%s" % (c, s), "%s %s and children (4+) who are commoners%s. EK2's commoner rule already leaves out armour."
                                    % (adj, people, ": the loincloth and always the chest band" if s == "f" else ""),
                                    (T("hide"), top("band"), None, None), [(100, com)]))
            cul = culture_cond(cd, False)
            if look == "hide":
                out.extend(with_lich(c, "ek2lc_%s_camp_%s" % (c, s), "%s %s (14+) who follow an army without fighting (ek2lc_camp_follower_trigger): the plain "
                                    "loincloth%s, under the camp follower's wrap. EK2 dresses an adventurer's camp as low nobility, "
                                    "so the commoner rule alone would miss them." % (adj, people, " and the chest band" if s == "f" else ""),
                                    (T("hide"), top("band"), None, None),
                                    [(100, base + [TEENS, cul, "\t\t\t\tek2lc_royal_trigger = no", "\t\t\t\tek2lc_camp_follower_trigger = yes"])]))
            if look == "war":
                out.extend(with_lich(c, "ek2lc_%s_war_%s" % (c, s), "%s %s (14+) in a war role while their realm is at war: the loincloth with the "
                                "war girdle and trophies%s, instead of EK2's armour." % (adj, people, ", and always the chest band" if s == "f" else ""),
                                (T("hide"), top("band"), T("war"), None),
                                [(100, base + [TEENS, cul, "\t\t\t\tek2lc_war_role_trigger = yes", "\t\t\t\tek2lc_armour_role_trigger = no"])]))
            if look == "armour":
                out.extend(with_lich(c, "ek2lc_%s_armour_%s" % (c, s), "%s %s (14+) among the best fighters (knights, or prowess 12+) while their realm "
                                "is at war: the loincloth with the war girdle and the strip skirt%s." % (adj, people, ", and always the chest band" if s == "f" else ""),
                                (T("hide"), top("band"), T("armour"), None),
                                [(100, base + [TEENS, cul, "\t\t\t\tek2lc_armour_role_trigger = yes"])]))
        for tier, lo, hi, lk, bk, wk, desc in TIERS:
            for s, sex, fem, people in SEXES:
                top = T("band" if bk == "hide" else "band_" + bk) if s == "f" else None
                out.extend(with_lich(c, "ek2lc_%s_royal_%s_%s" % (c, tier, s),
                                    "%s %s, rulers and their spouses (higher of the two top title tiers), %s." % (adj, people, desc),
                                    (T(lk), top, T(wk) if wk else None, T("mantle") if tier == "emperor" else None),
                                    [('2  # against 1 for "no loincloth": two in three %s rulers wear it' % adj,
                                      ["\t\t\t\tis_female = %s" % fem, KIDS, cul, "\t\t\t\tek2lc_war_role_trigger = no",
                                       "\t\t\t\tek2lc_royal_tier_trigger = { LOW = %s HIGH = %s }" % (lo, hi)])]))
        cul = culture_cond(cd, False)
        for s, sex, fem, people in SEXES:
            grave = ["\t\t\t\tis_female = %s" % fem, KIDS, cul, "\t\t\t\tek2lc_grave_look_trigger = yes"]
            out.append(modifier("ek2lc_%s_grave_%s" % (c, s), "%s %s and children (4+) among EK2's undead (not liches), whatever their rank: "
                                "the rotted plain loincloth%s, nothing else of ours. 1000 wins over \"no loincloth\"."
                                % (adj, people, " and the rotted chest band" if s == "f" else ""),
                                (T("grave"), T("grave_band") if s == "f" else None, None, None), [(1000, grave)]))
            if s == "f" and cd.get("bare_f"):
                out.append(modifier("ek2lc_%s_grave_f_bare" % c, "Adult %s undead women who are commoners, bare-chested, only while "
                                    "\"Show nudity\" is on: one in three, as for the living (ek2lc_%s_hide_f_bare)." % (adj, c),
                                    (T("grave"), None, None, None),
                                    [(500, grave + [culture_cond(cd, True), "\t\t\t\tek2lc_royal_trigger = no", "\t\t\t\tek2lc_war_role_trigger = no",
                                                    "\t\t\t\tis_adult = yes", "\t\t\t\tshould_show_nudity = yes"])]))
    out.append("}\n")
    for gene, (none, kinds, *_) in EXTRA.items():
        g = gene.replace("gene_", "")
        out.append("""# %s: drawn only over one of our loincloths (see EXTRA in gen_script_files.py).
%s = {
	usage = game
	selection_behavior = weighted_random
	priority = 101

	%s_none = {
%s
		weight = {
			base = 1
		}
	}
""" % (gene, g, g, dna([(gene, none)])))
        for k, _, rule in kinds:
            out.append("""	%s = {
%s
		weight = {
			base = 0
			modifier = {
				add = 1000
				scope:age >= 14
				%s
			}
		}
	}
""" % ("ek2lc_" + k, dna([(gene, "ek2lc_" + k)]), rule))
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


LICH_PIECES = {"hide": "Loincloth", "fine": "Fine Loincloth", "royal": "Royal Loincloth", "band": "Chest Band",
               "band_fine": "Fine Chest Band", "band_royal": "Royal Chest Band", "war": "War Girdle with Trophies",
               "armour": "Strip Skirt", "duke": "Ducal Girdle with Apron", "king": "Royal Girdle with Long Aprons",
               "emperor": "Imperial Girdle", "mantle": "Imperial Mantle"}


def row_name(c, k):
    if c == "lich":
        return "%s %s" % (LICH["adj"], LICH_PIECES[k])
    if k == "grave":
        return "%s Grave Wrap" % ALL[c]["adj"]
    if k == "grave_band":
        return "%s Grave-Wrap Chest Band" % ALL[c]["adj"]
    return piece_name(ALL[c], k)


def barbershop():
    out = [BOM + "# EK2 Loincloths: barbershop entries, one group per gene, the vanilla way (add_accessory_modifiers).",
           "# Written by source/tools/gen_script_files.py.",
           "# Priority 102 puts a barbershop choice after our game group (101), so it wins on our genes.",
           "# Chest pieces only list for women.", ""]
    loc = [BOM + "l_english:"]
    for grp, pos, gene, title, none in CUSTOM:
        none_t = GENES[gene][0]
        rows = gene_rows(gene)
        out += ["%s = {" % grp, "\tusage = customization", "\tinterface_position = %d" % pos, "\tpriority = 102", ""]
        valid = "\t\tis_valid_custom = { is_female = yes }" if gene == "gene_ek2lc_top" else None
        for t in [none_t] + [t for t, _, _ in rows]:
            out += ["\tadd_accessory_modifiers = {", "\t\tgene = %s" % gene, "\t\ttemplate = %s" % t] + ([valid] if valid else []) + ["\t}"]
        out += ["}", ""]
        loc.append(' PORTRAIT_MODIFIER_%s: "%s"' % (grp, title))
        loc.append(' PORTRAIT_MODIFIER_%s_none: "%s"' % (grp, none))
        for s in ("male", "female", "boy", "girl"):
            loc.append(' PORTRAIT_MODIFIER_%s_%s_empty: "$PORTRAIT_MODIFIER_%s_none$"' % (grp, s, grp))
        for _, c, k in rows:
            m, f = acc("m", c, k), acc("f", c, k)
            if k in WOMEN_ONLY:
                loc.append(' PORTRAIT_MODIFIER_%s_%s: "%s"' % (grp, f, row_name(c, k)))
            else:
                loc.append(' PORTRAIT_MODIFIER_%s_%s: "%s"' % (grp, m, row_name(c, k)))
                loc.append(' PORTRAIT_MODIFIER_%s_%s: "$PORTRAIT_MODIFIER_%s_%s$"' % (grp, f, grp, m))
    for pos, (gene, (none, kinds, title, none_title, _)) in enumerate(EXTRA.items(), start=13):
        grp = "ek2lc_custom_" + gene.replace("gene_ek2lc_", "")
        out += ["%s = {" % grp, "\tusage = customization", "\tinterface_position = %d" % pos, "\tpriority = 102", ""]
        for tm in [none] + ["ek2lc_" + k for k, _, _ in kinds]:
            out += ["\tadd_accessory_modifiers = {", "\t\tgene = %s" % gene, "\t\ttemplate = %s" % tm, "\t}"]
        out += ["}", ""]
        loc.append(' PORTRAIT_MODIFIER_%s: "%s"' % (grp, title))
        loc.append(' PORTRAIT_MODIFIER_%s_none: "%s"' % (grp, none_title))
        for s in ("male", "female", "boy", "girl"):
            loc.append(' PORTRAIT_MODIFIER_%s_%s_empty: "$PORTRAIT_MODIFIER_%s_none$"' % (grp, s, grp))
        for k, name, _ in kinds:
            loc.append(' PORTRAIT_MODIFIER_%s_%s: "%s"' % (grp, xacc("m", k), name))
            loc.append(' PORTRAIT_MODIFIER_%s_%s: "$PORTRAIT_MODIFIER_%s_%s$"' % (grp, xacc("f", k), grp, xacc("m", k)))
    write("gfx/portraits/portrait_modifiers/ek2lc_custom.txt", "\n".join(out))
    write("localization/english/ek2lc_l_english.yml", "\n".join(loc) + "\n")


if __name__ == "__main__":
    genes()
    accessories()
    figleaf()
    modifiers()
    barbershop()
