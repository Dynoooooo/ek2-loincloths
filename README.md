# EK2 Loincloths

A clothing mod for [Elder Kings 2](https://steamcommunity.com/sharedfiles/filedetails/?id=2887120253), the Elder Scrolls total conversion for Crusader Kings III. It adds loincloths, wraps and chest bands for the peoples of Tamriel who would plausibly wear them, with the script to make them show up in play.

- Mod version: 0.1.0
- Game version: CK3 1.20
- Requires: Elder Kings 2

## What it adds

- **Clothing** for men and women: Reach hide pieces, culture-specific pieces (Giant, Keptu, Nedic, Yokudan and others), undead and lich looks. Every piece has its own mesh and textures; no vanilla or EK2 art is reused.
- **Body-shape support**: each piece follows the vanilla and EK2 body shapes, and has its own shapes for sitting on a throne and for kneeling, so the cloth drapes over the legs.
- **Eight regalia artifacts**, commissioned by decision: Champion's Apron, Malacath's Iron Fauld, Feather Girdle of the Ancestors, Briarheart Girdle, Hist-Amber Wrap, Green Pact Bone Apron, Ancestor-Ash Tassets and Mane's Moon Silk.
- **Decisions**: commission regalia, hold a loincloth festival, go native (and end it), plus one gathering for each of four peoples.
- **A court position**, the Loincloth Maker, with a three-level trait.
- **Events**: life events, regalia events and events for the four peoples.
- **Game rules** for how often the clothing appears, whether nobles wear it, war looks and events.

## Install

The repository is the mod folder itself. Large files (`.mesh`, `.dds`, Meshy sources) are in Git LFS, so install [Git LFS](https://git-lfs.com) first.

```bash
cd ~/Documents/Paradox\ Interactive/Crusader\ Kings\ III/mod
git clone git@github.com:Dynoooooo/ek2-loincloths.git ek2_loincloths
```

Then create `ek2_loincloths.mod` next to the folder (CK3 needs it, and it is not part of the repository):

```
version="0.1.0"
tags={
	"Graphics"
}
name="EK2 Loincloths"
supported_version="1.20.*"
dependencies={
	"Elder Kings 2"
}
path="mod/ek2_loincloths"
```

Enable it in the launcher after Elder Kings 2. On Windows and Linux the mod folder is in the matching `Paradox Interactive/Crusader Kings III/mod` location.

The full history is about 9 GB of LFS data. To play, a shallow clone is enough: add `--depth 1` to the clone command.

## Layout

| Folder | Contents |
|---|---|
| `common/`, `events/`, `localization/` | Game script and English text |
| `gfx/` | Meshes, textures, icons, portrait modifiers and genes |
| `source/maya/` | Maya 2027 tools that fit, weight, audit and export the pieces |
| `source/tools/` | Texture, validation and test-launch scripts |
| `source/meshy/` | Source models and concept images generated with Meshy |
| `source/legacy_blender/` | The old Blender pipeline, kept as a reference; no longer run |
| `progress/` | Dated working notes |

## Building from source

You only need this to change the meshes or textures; the built files are in the repository.

The tools were written on macOS and default to a standard Steam and Maya 2027 install there. Override the defaults with environment variables:

| Variable | Meaning |
|---|---|
| `CK3_GAME` | CK3's `game` folder |
| `CK3_USER_DIR` | The `Crusader Kings III` folder in Documents |
| `EK2_DIR` | Elder Kings 2's workshop folder (`.../workshop/content/1158310/2887120253`) |
| `MAYAPY` | Path to Maya's `mayapy` |
| `MAGICK` | Path to ImageMagick's `magick` |
| `CK3_TIGER` | Path to `ck3-tiger` |

Other requirements: [io_pdx_mesh](https://github.com/ross-g/io_pdx_mesh) in Maya (with PyMEL), ImageMagick and, for validation, [ck3-tiger](https://github.com/amtep/tiger):

```bash
source/tools/tiger.sh
```

`CLAUDE.md` holds the detailed toolchain notes. Only macOS has been tested.

## Credits

- Models and 2D art were generated with [Meshy](https://www.meshy.ai), then fitted, weighted and exported in Maya.
- Much of the script and tooling was written with [Claude Code](https://claude.com/claude-code).
- Elder Kings 2 is the work of the Elder Kings team. Crusader Kings III is by Paradox Interactive. The Elder Scrolls belongs to Bethesda Softworks / ZeniMax Media. This mod is not affiliated with or endorsed by any of them.

## License

[MIT](LICENSE). It covers this mod's own files, not Crusader Kings III, Elder Kings 2 or The Elder Scrolls.
