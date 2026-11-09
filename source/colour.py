"""Barbershop recolouring (vanilla's colour picker, which Better Barbershop also uses).

CK3 1.20 lets the barbershop recolour a piece only when its entity name starts with one of the
prefixes in vanilla's common/defines/jomini/portraits.txt (ACCESSORY_PREFIXES_BLOCK_0..3), and the
entity uses the pattern shader with a mask and a variation. So every entity gets:
  - a vanilla prefix by what the piece is: clothes (loincloths, chest bands), legwear (girdles,
    war and royal aprons, camp wrap, trophies) or cloak (mantle, shoulder guard); pieces in the same
    block share the picked colours (loincloth and band match);
  - shader portrait_attachment_pattern_alpha_to_coverage;
  - game_data.portrait_entity_user_data with the texture set's mask and variation.
Masks, palettes and the variation file are made by tools/make_colour.py.

Used by build_reach_hide.py (write_asset) and tools/make_colour.py (both patch .asset text the
same way) and tools/gen_script_files.py (accessories point at the prefixed entity names).
"""
import re

MODEL_DIR = "gfx/models/portraits/ek2lc/reach_hide_01"
PATTERN_DIR = "gfx/portraits/accessory_variations/textures/ek2lc"
SHADER_OLD = "portrait_attachment_alpha_to_coverage"
SHADER_NEW = "portrait_attachment_pattern_alpha_to_coverage"


def block(name):
    """Vanilla colour block of an accessory/asset name such as ek2lc_f_reach_war_01."""
    if re.search(r"_(mantle|arena_guard|fur_robe|victor_sash)_01$", name):
        return "cloak"
    if re.search(r"_(war|armour|duke|king|emperor|camp_wrap|trophy_\d|leggings|kid_charm|art_[a-z]+|wrestler_belt|hunter_gear|priest_apron|cowrie_\d|holy_tabard)_01$", name):
        return "legwear"
    return "clothes"


def entity_name(name):
    """Entity name for accessory/asset `name`, starting with vanilla's prefix (f_clothes, m_legwear, ...)."""
    sex = "m" if name.startswith("ek2lc_m_") else "f"
    return "%s_%s_%s_entity" % (sex, block(name), name)


def mask_path(mask):
    return "%s/%s_masks.dds" % (MODEL_DIR, mask)


def variation_name(tset):
    return tset  # texture-set names are already ours (ek2lc_...)


def user_data(mask, tset):
    return ("\tgame_data = {\n\t\tportrait_entity_user_data = {\n\t\t\tportrait_accessory = {\n"
            "\t\t\t\tpattern_mask = \"%s\"\n\t\t\t\tvariation = \"%s\"\n\t\t\t}\n\t\t}\n\t}\n"
            % (mask_path(mask), variation_name(tset)))


def patch_asset(text, name, mask, tset):
    """Asset text with the prefixed entity name, the pattern shader and the user data. Idempotent."""
    text = text.replace('shader = "%s"' % SHADER_OLD, 'shader = "%s"' % SHADER_NEW)
    text = re.sub(r'(\bentity = \{\s*name = )"[^"]*"', lambda m: '%s"%s"' % (m.group(1), entity_name(name)), text)
    text = re.sub(r"\tgame_data = \{.*?\n\t\}\n", "", text, flags=re.S)  # drop an old block, then add the current one
    head, tail = text.rstrip().rsplit("}", 1)  # the entity block is last in the file
    return head + user_data(mask, tset) + "}" + tail + "\n"
