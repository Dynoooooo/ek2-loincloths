"""Reapply mesh fitting saved from the live Blender source files."""
import os
import numpy as np
from mathutils import Vector


def apply(pieces, sex, source, bone_names):
    path = os.path.join(source, 'fitting_' + sex + '.npz')
    if not os.path.exists(path):
        return
    pcs = {pc['name']: pc for pc in pieces}
    with np.load(path, allow_pickle=False) as data:
        for key in data.files:
            if not key.endswith('|original'):
                continue
            name = key.split('|')[0]
            before = np.array([p[:] for p in pcs[name]['pos']['basis']])
            assert before.shape == data[key].shape and np.max(np.abs(before-data[key])) < 0.002, (
                'Geometry changed since Blender fitting: ' + name + '; refit before exporting')
        for key in data.files:
            name, shape = key.split('|')
            if shape in ('original', 'bones'):
                continue
            pc = pcs[name]
            if shape == 'weights':
                bone_idx = {n: i for i, n in enumerate(bone_names)}
                names = data[name + '|bones'].tolist()
                w = data[key]
                assert len(w) == len(pc['pos']['basis']), 'Fitting weight topology mismatch: ' + name
                pc['vw'] = [[(bone_idx[names[b]], float(row[b])) for b in np.nonzero(row > 1e-6)[0]] for row in w]
                continue
            assert len(pc['pos'][shape]) == len(data[key]), 'Fitting topology mismatch: ' + key
            pc['pos'][shape] = [p + Vector(d) for p, d in zip(pc['pos'][shape], data[key])]
    print('Applied Blender fitting:', path)
