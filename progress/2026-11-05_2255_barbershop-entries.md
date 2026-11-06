# Barbershop entries and English names (seen in game)

**Done** (commit: the one that adds this file)
- `gfx/portraits/portrait_modifiers/ek2lc_custom.txt`: four barbershop groups, one per gene, the vanilla way (`add_accessory_modifiers`), priority 102 so a pick wins over our game group (101):
  - Loincloth (`ek2lc_custom_loincloth`, position 9): No Loincloth, Reach Hide / Fine Hide / Royal Hide Loincloth.
  - Chest Piece (`ek2lc_custom_top`, 10): women only (`is_valid_custom = { is_female = yes }`; the group is hidden for men).
  - Girdle (`ek2lc_custom_girdle`, 11): war girdle, strip skirt, ducal, royal, imperial girdles.
  - Mantle (`ek2lc_custom_mantle`, 12): the imperial fur-and-feather mantle.
- `localization/english/ek2lc_l_english.yml`: keys are `PORTRAIT_MODIFIER_<group>`, `..._<group>_<accessory>`, and `..._<group>_{male,female,boy,girl}_empty` for "none".
- In game (Aldrydd, and a new Reach woman): groups listed under EK2's own ones with the names; the current pieces show as "(Default)"; picking "No Loincloth" removed the loincloth and kept the girdle (fig leaf showed). error.log: nothing about the new files.

**In progress**
- Nothing half-made.

**Next step**
- Step 5, other cultures. User: "Number 1. Then number 2. Back to back. No stopping."
- Each new culture's pieces need adding to `ek2lc_custom.txt` and the loc file.

**Problems and workarounds**
- EK2's barbershop is one long list of dropdowns; mouse-wheel scrolling barely moves it, drag the scrollbar.
- Closing the barbershop with the X leaves a "Discard Changes" dialog; Confirm closes it.
- The first barbershop opening may show a "No Social Profile" popup; Return/Escape close the barbershop too. Reopening it showed no popup.
- An empty default shows as "None (Default)", not our "No ..." text; the "No ..." text shows in the list.

**How to test**
- As before (`source/tools/ck3_test.sh start/wait/stop`, `ck3ctl` keys). Console `effect open_view_data = barbershop`.
