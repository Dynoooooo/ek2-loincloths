# Vanilla Clothes row reads "No Outfit"; stale preset errors gone

**Done** (Claude Code; this commit)
- The user's lobby preset `player/game_rules/presets.txt` no longer lists the 7 removed `ek2lc_*` game-rule options (user approved). Launch after: no `ek2lc` lines in error.log at all.
- Clothes row: loincloth wearers showed EK2's "No Clothes (Default)". Research (Exa; CK3 wiki mirror jesec/ck3-modding-wiki, EU5/Vic3 wikis, the CK3 1.20 binary and script_docs):
  - CK3 1.20 has no INJECT:/REPLACE: entry modes (EU5 and Victoria 3 only; not in the ck3 binary), so nothing can be added to EK2's `custom_clothes` list or the `clothes` gene without copying EK2's whole files.
  - No trigger or data function reads a worn accessory (`has_gene` is morph genes only), so the label can't vary per character.
  - Single loc keys can be overridden from `localization/replace/english/`.
- The user chose "No Outfit" for everyone. `gen_script_files.py` writes `localization/replace/english/ek2lc_replace_l_english.yml`, overriding EK2's `PORTRAIT_MODIFIER_custom_clothes_{male,female}_clothes_secular_western_nudity_01` and vanilla's `..._no_clothes`. Seen in game: "No Outfit (Default)".

**Known quirk**
- Children in loincloths: the Clothes row shows "Nightgown (Default)", because no_clothes gives children the bedchamber nightshirt, which we hide under the loincloth. Not renamed: real nightgowns use the same entry.

**Next step**
- Same as `2026-11-06_1745_undead.md`.
