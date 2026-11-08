"""Fit existing authored meshes in the live Blender app, then save artist corrections.

This operates on the source .blend, never on the user's game bodies. Corrections are
stored independently of the procedural builder so a rebuild retains the fitted mesh.
Use prepare(sex), fit_piece(name), then inspect in Blender before save_corrections().
"""
import os
import sys
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from mathutils.interpolate import poly_3d_calc

MOD = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME = os.path.expanduser('~/Library/Application Support/Steam/steamapps/common/Crusader Kings III/game')
sys.path.insert(0, MOD + '/source')
import weight_solver as ws
WEIGHT_CHANGED = globals().get('WEIGHT_CHANGED', set())

ANIMS = ['idle_1', 'idle_2', 'idle_3', 'AI_callous_1', 'emotion_angry',
         'emotion_grief', 'emotion_happy', 'emotion_sadness', 'emotion_scheme'] + [
    'throneRoom_' + a for a in ('kneel1_1', 'kneel2_1', 'messenger1_1', 'ruler1_1',
        'ruler2_1', 'ruler3_1', 'bow1_1', 'bow2_1', 'bow3_1', 'cheer1_1',
        'applaud1_1', 'conversation1_1', 'conversation2_1', 'chancellor_1',
        'oneHandedPassive1_1', 'twoHandedPassive1_1')]


def coords(obj, shape='Basis'):
    return np.array([v.co[:] for v in obj.data.shape_keys.key_blocks[shape].data])


def weights(obj):
    out = np.zeros((len(obj.data.vertices), len(BONES)))
    for v in obj.data.vertices:
        for g in v.groups:
            name = obj.vertex_groups[g.group].name
            if name in BI:
                out[v.index, BI[name]] = g.weight
    return out


def transforms(obj):
    w = weights(obj)
    use = np.nonzero(w.any(axis=0))[0]
    return np.einsum('vb,pbij->pvij', w[:, use], MATS[:, use, :3, :])


def deform(co, tf):
    return np.einsum('pvij,vj->pvi', tf, np.c_[co, np.ones(len(co))])


def prepare(sex):
    global SEX, BODY, RIG, BONES, BI, MATS, POSES, BODY_TF, BODY_FACES, ORIGINAL, OBST
    SEX = sex
    BODY = bpy.data.objects[sex + '_body']
    RIG = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
    BONES = [b.name for b in RIG.data.bones]
    BI = {n: i for i, n in enumerate(BONES)}
    names = ANIMS + (['throneRoom_curtsey1_1'] if sex == 'female' else [])
    POSES = [('REST', 'ref', np.repeat(np.eye(4)[None], len(BONES), axis=0))]
    POSES += ws.sample_poses(RIG, bpy.context.scene, GAME, sex, names, BONES)
    MATS = np.array([p[2] for p in POSES])
    BODY_TF = transforms(BODY)
    gi = {g.index for g in BODY.vertex_groups if any(k in g.name for k in
          ('elbow', 'forearm', 'wrist', '_fi_', 'finger', 'thumb', 'hand', 'prop', 'sleeve'))}
    arms = {v.index for v in BODY.data.vertices if sum(g.weight for g in v.groups if g.group in gi) > 0.5}
    BODY_FACES = [tuple(p.vertices) for p in BODY.data.polygons if not arms.intersection(p.vertices)]
    ORIGINAL = {o.name: {k.name: coords(o, k.name) for k in o.data.shape_keys.key_blocks}
                for o in bpy.context.scene.objects if o.type == 'MESH' and o.name.startswith('ek2lc_')}
    OBST = {}
    print('Prepared', sex, len(POSES), 'poses;', len(ORIGINAL), 'garments')


def resume(sex):
    """Resume a saved v02 source without baking its corrections a second time."""
    prepare(sex)
    WEIGHT_CHANGED.clear()
    with np.load(MOD+'/source/fitting_'+sex+'.npz',allow_pickle=False) as data:
        for key in data.files:
            name,shape=key.split('|')
            if shape=='weights':
                WEIGHT_CHANGED.add(name)
            elif shape=='original':
                ORIGINAL[name]['Basis']=data[key].astype(float)
            elif shape!='bones':
                label='Basis' if shape=='basis' else shape
                if label!='Basis':ORIGINAL[name][label]-=data[key]


def fit_weights(name, iterations=180, cap=0.8, hands=False, layers=()):
    obj = bpy.data.objects[name]
    co = coords(obj)
    allw = weights(obj)
    pelvis = RIG.data.bones['body_root'].head_local.z
    cape = 'mantle' in name
    choices = [i for i, n in enumerate(BONES) if ('_cloak' in n if cape else
               ('_skirt' in n and n[-1] in '123')) or n in
               ('body_root', 'bn_sp_lumbar', 'bn_sp_thoracic', 'bn_l_hip', 'bn_r_hip')]
    used = sorted(set(choices) | set(np.nonzero(allw.any(axis=0))[0]))
    w = allw[:, used]
    free = co[:, 2] < pelvis + (50 if cape else 14)
    allowed = w > 0
    for b in choices:
        allowed[:, used.index(b)] |= free
    faces = [list(p.vertices) for p in obj.data.polygons]
    edges = ws.mesh_edges(faces) + ws.bend_pairs(co, faces)
    # Lining and outer surface must deform together.
    for ids in linked_vertices(co):
        edges.extend((ids[0], i) for i in ids[1:])
    obs = obstacles('Basis', hands=hands, layers=layers)
    margin = np.array([min(cap, max(0.05, 0.6 * (Vector(p)-obs[0].find_nearest(Vector(p))[0]).dot(
                      obs[0].find_nearest(Vector(p))[1]))) for p in co])
    poses = [dict(name=nm, mats=mat[used], obst=obs[i],
                  ref=ws.lbs(co,w,mat[used]) if kind == 'ref' else None,
                  w=1 if kind == 'ref' else 4) for i,(nm,kind,mat) in enumerate(POSES)]
    prob = ws.Problem(co, edges, w, free, allowed, poses, margin)
    prob.surface_faces = [np.array(f) for f in faces if any(free[f])]
    before = prob.penetration()[:2]
    lam = dict(pen=100.0, ref=2.0, len=8.0, smooth=50.0, stick=0.0, down=0.0, grav=0.0)
    prob.run(lam, iters=iterations, max_dw=.02, decay=.996)
    prob.prune(4,.008)
    prob.run(lam, iters=50, max_dw=.008, decay=.99)
    after=prob.penetration()
    if after and after[0][0] > (before[0][0] if before else 0)+.2:
        print('REJECTED weight fit',name,before,'->',after[:3],flush=True)
        return
    for group in obj.vertex_groups:
        group.remove(list(range(len(co))))
    for bi,b in enumerate(used):
        if not prob.W[:,bi].any():
            continue
        group = obj.vertex_groups.get(BONES[b]) or obj.vertex_groups.new(name=BONES[b])
        for v in np.nonzero(prob.W[:,bi] > 1e-6)[0]:
            group.add([int(v)],float(prob.W[v,bi]),'REPLACE')
    WEIGHT_CHANGED.add(name)
    print('WEIGHTS',name,before,'->',prob.penetration()[:3],flush=True)


def outer_faces(obj):
    # The leggings have an explicit lining. Only the outward-facing hide is a
    # collision surface for the skin and the layers worn over it.
    assert 'leggings' in obj.name and len(obj.data.polygons) == 2592, 'Unexpected leggings topology'
    return [list(p.vertices) for p in obj.data.polygons if
            (p.index % 1296 < 1248 and p.index % 2 == 0)]


def obstacles(shape, hands=False, layers=()):
    key = (shape, hands, tuple(layers))
    if key not in OBST:
        faces = [tuple(p.vertices) for p in BODY.data.polygons] if hands else list(BODY_FACES)
        points = deform(coords(BODY, shape), BODY_TF)
        for name in layers:
            obj = bpy.data.objects[name]
            off = points.shape[1]
            points = np.concatenate([points, deform(coords(obj, shape), transforms(obj))],axis=1)
            faces += [[i+off for i in f] for f in outer_faces(obj)]
        OBST[key] = [BVHTree.FromPolygons(c.tolist(), faces) for c in points]
    return OBST[key]


def linked_vertices(co):
    # Pair each lining point to its nearest outer point; coincide UV seams too.
    # Moving the two sides together preserves the thickness of hide and capes.
    kd = KDTree(len(co))
    for i, p in enumerate(co):
        kd.insert(Vector(p), i)
    kd.balance()
    parent = list(range(len(co)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i, p in enumerate(co):
        for _, j, d in kd.find_range(Vector(p), 0.37):
            parent[root(j)] = root(i)
    groups = {}
    for i in range(len(co)):
        groups.setdefault(root(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1]


def fit_piece(name, shapes=('Basis',), iterations=22, margin=0.35, limit=4.0, hands=False, layers=()):
    obj = bpy.data.objects[name]
    tf = transforms(obj)
    inv = np.linalg.pinv(tf[:, :, :, :3])
    faces = [list(p.vertices) for p in obj.data.polygons]
    edges = np.array(ws.mesh_edges(faces))
    groups = linked_vertices(coords(obj))
    # Face centres catch a knee passing between the garment's vertices.
    fi = np.array([f + [f[-1]] * (4-len(f)) for f in faces if len(f) <= 4])
    for shape in shapes:
        start = coords(obj, shape)
        co = start.copy()
        obs = obstacles(shape, hands=hands, layers=layers)
        covered = []
        if 'leggings' in name:
            outer = outer_faces(obj)
            shell = BVHTree.FromPolygons(start.tolist(),outer)
            rest_body = coords(BODY,shape)
            for v,p in enumerate(rest_body):
                loc,n,idx,d=shell.find_nearest(Vector(p),3.0)
                if loc is not None and d > .02 and (Vector(p)-loc).dot(n) < -.4*d:
                    covered.append(v)
            posed_body = deform(rest_body,BODY_TF)
        first = None
        for it in range(iterations):
            posed = deform(co, tf)
            delta = np.zeros_like(co)
            severity = np.zeros(len(co))
            worst = 0.0
            for pi, (points, bvh) in enumerate(zip(posed, obs)):
                for v, p in enumerate(points):
                    loc, nor, _, d = bvh.find_nearest(Vector(p), 6.0)
                    if loc is None:
                        continue
                    depth = margin - (Vector(p)-loc).dot(nor)
                    worst = max(worst, depth-margin)
                    if depth > severity[v]:
                        delta[v] = inv[pi, v] @ (np.array(nor) * depth)
                        severity[v] = depth
                for ids in fi:
                    p = points[ids].mean(axis=0)
                    loc, nor, _, d = bvh.find_nearest(Vector(p), 6.0)
                    if loc is None:
                        continue
                    depth = margin - (Vector(p)-loc).dot(nor)
                    worst = max(worst, depth-margin)
                    if depth > 0:
                        for v in ids:
                            if depth > severity[v]:
                                delta[v] = inv[pi, v] @ (np.array(nor) * depth)
                                severity[v] = depth
                if covered:
                    shell = BVHTree.FromPolygons(points.tolist(),outer)
                    for bv in covered:
                        q = Vector(posed_body[pi,bv])
                        loc,n,idx,d = shell.find_nearest(q,4.0)
                        if loc is None:
                            continue
                        depth = (q-loc).dot(n) + margin
                        if depth > 0:
                            for v in outer[idx]:
                                if depth > severity[v]:
                                    delta[v] = inv[pi,v] @ (np.array(n)*depth)
                                    severity[v] = depth
            if first is None:
                first = worst
            for ids in groups:
                v = max(ids, key=lambda j: severity[j])
                delta[ids] = delta[v]
            # A conservative brush stroke; smooth the displacement, not the mesh.
            lengths = np.linalg.norm(delta, axis=1)
            delta *= np.minimum(1, 0.4 / np.maximum(lengths, 1e-9))[:, None]
            total = co - start + delta * 0.65
            adj = np.zeros_like(total)
            count = np.zeros(len(co))
            for a, b in edges:
                adj[a] += total[b]; adj[b] += total[a]
                count[a] += 1; count[b] += 1
            total = 0.9 * total + 0.1 * adj / np.maximum(count[:, None], 1)
            for ids in groups:
                total[ids] = total[ids].mean(axis=0)
            length = np.linalg.norm(total, axis=1)
            total *= np.minimum(1, limit / np.maximum(length, 1e-9))[:, None]
            co = start + total
            if worst < 0.03 and it >= 3:
                break
        key = obj.data.shape_keys.key_blocks[shape]
        if worst > first+.2:
            print('REJECTED geometry fit',name,shape,first,'->',worst,flush=True)
            continue
        key.data.foreach_set('co', co.astype(np.float32).ravel())
        if shape == 'Basis':
            obj.data.vertices.foreach_set('co', co.astype(np.float32).ravel())
        print('FIT', name, shape, 'inside %.2f -> %.2f cm; moved max %.2f cm' %
              (first, worst, np.linalg.norm(co-start, axis=1).max()), flush=True)
    obj.data.update()
    OBST.clear()


def apply_basis_to_shapes(name):
    obj = bpy.data.objects[name]
    d = coords(obj) - ORIGINAL[name]['Basis']
    groups = linked_vertices(coords(obj))
    for key in obj.data.shape_keys.key_blocks[1:]:
        co = ORIGINAL[name][key.name] + d
        bt = BVHTree.FromPolygons(coords(BODY,key.name).tolist(),BODY_FACES)
        # An adult fit must not sink a smaller race/child shape into its skin.
        # Correct paired lining points together, retaining the hide's thickness.
        for _ in range(3):
            push = np.zeros_like(co)
            for i,p in enumerate(co):
                loc,n,_,dist=bt.find_nearest(Vector(p))
                sd=(Vector(p)-loc).dot(n)
                if sd < .06:
                    push[i]=np.array(n)*(.08-sd)
            for ids in groups:
                v=max(ids,key=lambda i:np.linalg.norm(push[i]))
                push[ids]=push[v]
            co += push
        key.data.foreach_set('co', co.astype(np.float32).ravel())
    obj.data.update()


def rebuild_leggings():
    """Regular hide tubes around a smooth skeletal axis, preserving the UV layout.

    The former axis averaged unevenly distributed skin vertices at each height;
    it jumped sideways by up to eight cm between rows and folded the mesh.
    """
    name = 'ek2lc_' + SEX[0] + '_leggings_01'
    obj = bpy.data.objects[name]
    bodyco = coords(BODY)
    BODY.data.calc_loop_triangles()
    allowed = {i for f in BODY_FACES for i in f}
    tris = [list(t.vertices) for t in BODY.data.loop_triangles if all(i in allowed for i in t.vertices)]
    tree = BVHTree.FromPolygons(bodyco.tolist(),tris,all_triangles=True)
    knee=np.array(RIG.data.bones['bn_l_knee'].head_local)
    ankle=np.array(RIG.data.bones['bn_l_ankle'].head_local)
    hip=np.array(RIG.data.bones['bn_l_hip'].head_local)
    root=RIG.data.bones['body_root'].head_local.z
    crotch=min(p[2] for p in bodyco if abs(p[0])<1 and 40<p[2]<root+5)
    low,high,bottom=crotch-4.5,root-2,ankle[2]+1
    rows=[0,.012,.035]+[.035+(.955-.035)*k/20 for k in range(1,21)]+[.97,.985,.995,1]
    left=1 if hip[0]>0 else -1
    binding=[]
    normals={}
    for key in BODY.data.shape_keys.key_blocks:
        c=coords(BODY,key.name); n=np.zeros_like(c)
        for ids in tris:
            a,b,d=c[ids]; normal=np.cross(b-a,d-a)
            n[ids]+=normal
        weld={}
        for i,p in enumerate(bodyco): weld.setdefault(tuple(np.round(p,3)),[]).append(i)
        for ids in weld.values(): n[ids]=n[ids].sum(axis=0)
        n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-9)
        normals[key.name]=n
    for side in (left,-left):
        for layer in (0,1):
            for v in rows:
                for col in range(25):
                    phi=1.5*np.pi+2*np.pi*(col%24)/24
                    top=low+(high-low)*((1+np.sin(phi))/2)**2
                    z=bottom+(top-bottom)*v
                    az=min(z,crotch-3)
                    a,b=(ankle,knee) if az<knee[2] else (knee,hip)
                    t=np.clip((az-a[2])/(b[2]-a[2]),0,1)
                    axis=a+(b-a)*t
                    axis=axis.copy();axis[0]*=side/left;axis[2]=z
                    direction=Vector((side*np.sin(phi),-np.cos(phi),0))
                    loc,n,idx,dist=tree.ray_cast(Vector(axis),direction,60)
                    if loc is None: raise RuntimeError('Leg ray missed: '+str((side,z,col)))
                    ids=tris[idx]
                    bary=np.array(poly_3d_calc([Vector(bodyco[i]) for i in ids],loc))
                    ease=np.clip((knee[2]-z)/(knee[2]-bottom),0,1)
                    offset=.95+.7*ease
                    if v<.035: offset+=.15
                    if v>.97: offset+=.18*np.sin(np.pi*(v-.97)/.03)
                    binding.append((ids,bary,offset-.30*layer))
    for key in obj.data.shape_keys.key_blocks:
        c=coords(BODY,key.name);n=normals[key.name]
        out=[]
        for ids,bary,off in binding:
            normal=(n[ids]*bary[:,None]).sum(axis=0)
            normal/=max(np.linalg.norm(normal),1e-9)
            out.append((c[ids]*bary[:,None]).sum(axis=0)+normal*off)
        key.data.foreach_set('co',np.array(out,np.float32).ravel())
        if key.name=='Basis': obj.data.vertices.foreach_set('co',np.array(out,np.float32).ravel())
    bw=weights(BODY)
    for g in obj.vertex_groups:g.remove(list(range(len(binding))))
    for v,(ids,bary,off) in enumerate(binding):
        row=(bw[ids]*bary[:,None]).sum(axis=0)
        idx=np.argsort(-row)[:4];total=row[idx].sum()
        for b in idx:
            if row[b]>1e-6:
                group=obj.vertex_groups.get(BONES[b]) or obj.vertex_groups.new(name=BONES[b])
                group.add([v],float(row[b]/total),'REPLACE')
    obj.data.update();OBST.clear();WEIGHT_CHANGED.add(name)
    print('Rebuilt smooth leggings with all',len(obj.data.shape_keys.key_blocks),'body shapes',flush=True)


def ease_cape_back():
    """Give the hanging cape room behind the arms, keeping its collar attached."""
    obj=bpy.data.objects['ek2lc_'+SEX[0]+'_reach_mantle_01']
    start=coords(obj);co=start.copy();tf=transforms(obj)
    nrows=(len(co)-336)//18
    active=[i for i in range(336,len(co)) if ((i-336)//9)%nrows>=3]
    obs=obstacles('Basis',hands=True)
    disp=np.zeros(len(co))
    for _ in range(6):
        points=deform(co,tf)
        demand=np.zeros(len(co))
        for pi,bt in enumerate(obs):
            for v in active:
                direction=Vector(tf[pi,v,:,1]);length=direction.length
                if length<.15:continue
                direction.normalize();p=Vector(points[pi,v])
                loc,n,idx,dist=bt.ray_cast(p+direction*40,-direction,80)
                if loc is not None and dist<40.4:
                    demand[v]=max(demand[v],(40.4-dist)/length)
        disp+=np.minimum(demand,1.2)
        grid=disp[336:].reshape(2,nrows,9).mean(axis=0)
        for _ in range(2):
            pad=np.pad(grid,((1,1),(1,1)),mode='edge')
            avg=(pad[1:-1,:-2]+pad[1:-1,2:]+pad[:-2,1:-1]+pad[2:,1:-1])/4
            grid=np.maximum(grid,.3*grid+.7*avg)
        grid[:2]=0
        grid[2]*=.25
        disp[336:]=np.tile(grid.ravel(),2)
        disp=np.minimum(disp,7.0)
        co=start.copy();co[:,1]+=disp
    obj.data.shape_keys.key_blocks['Basis'].data.foreach_set('co',co.astype(np.float32).ravel())
    obj.data.vertices.foreach_set('co',co.astype(np.float32).ravel())
    obj.data.update();OBST.clear()
    apply_basis_to_shapes(obj.name)
    print('Cape back allowance maximum',round(float(disp.max()),2),'cm',flush=True)


def smooth_cape_weights():
    """Ease abrupt weight changes across the broad cape; share both linings."""
    obj=bpy.data.objects['ek2lc_'+SEX[0]+'_reach_mantle_01']
    w=weights(obj)
    nr=(len(w)-336)//18
    grid=w[336:].reshape(2,nr,9,len(BONES)).mean(axis=0)
    # The six yoke rows follow the back's skin, holding the cape to the collar.
    # Blurring those into the hanging cape opens a gap when the wearer bows.
    before=set(bpy.data.objects)
    try:
        with bpy.data.libraries.load(MOD+'/source/reach_hide_'+SEX[0]+'_v01.blend',link=False) as (src,dst):
            dst.objects=[obj.name]
        original=weights(dst.objects[0])[336:].reshape(2,nr,9,len(BONES)).mean(axis=0)
        fixed=original[:6].copy()
    finally:
        for added in set(bpy.data.objects)-before:bpy.data.objects.remove(added,do_unlink=True)
    for _ in range(12):
        pad=np.pad(grid,((1,1),(1,1),(0,0)),mode='edge')
        grid=(4*grid+pad[:-2,1:-1]+pad[2:,1:-1]+pad[1:-1,:-2]+pad[1:-1,2:])/8
        grid[:6]=fixed
    w[336:]=np.tile(grid.reshape(-1,len(BONES)),(2,1))
    for v in range(336,len(w)):
        keep=np.argsort(-w[v])[:4];row=np.zeros(len(BONES));row[keep]=w[v,keep]
        w[v]=row/max(row.sum(),1e-9)
    for g in obj.vertex_groups:g.remove(list(range(len(w))))
    for b in np.nonzero(w.any(axis=0))[0]:
        group=obj.vertex_groups.get(BONES[b]) or obj.vertex_groups.new(name=BONES[b])
        for v in np.nonzero(w[:,b]>1e-6)[0]:group.add([int(v)],float(w[v,b]),'REPLACE')
    WEIGHT_CHANGED.add(obj.name);OBST.clear()


def refit_female_flaps():
    """Keep the women's pose-solved weights and taper the raised-thigh edge."""
    assert SEX=='female', 'The male set keeps its fitted panels; this cut was checked on the female body'
    obj=bpy.data.objects['ek2lc_'+SEX[0]+'_reach_hide_01']
    w=weights(obj);start=len(w)-392
    assert start==325,'Unexpected loincloth topology'
    before=set(bpy.data.objects)
    try:
        with bpy.data.libraries.load(MOD+'/source/reach_hide_'+SEX[0]+'_v01.blend',link=False) as (src,dst):
            dst.objects=[obj.name]
        w[start:]=weights(dst.objects[0])[start:]
    finally:
        for added in set(bpy.data.objects)-before:bpy.data.objects.remove(added,do_unlink=True)
    for v in range(start,len(w)):
        keep=np.argsort(-w[v])[:4];row=np.zeros(len(BONES));row[keep]=w[v,keep]
        w[v]=row/max(row.sum(),1e-9)
    for g in obj.vertex_groups:g.remove(list(range(len(w))))
    for b in np.nonzero(w.any(axis=0))[0]:
        group=obj.vertex_groups.get(BONES[b]) or obj.vertex_groups.new(name=BONES[b])
        for v in np.nonzero(w[:,b]>1e-6)[0]:group.add([int(v)],float(w[v,b]),'REPLACE')
    for key in obj.data.shape_keys.key_blocks:
        co=coords(obj,key.name)
        for side in range(2):
            b=start+side*196
            co[b:b+196]=ORIGINAL[obj.name][key.name][b:b+196]
            for layer in range(2):
                for row in range(14):
                    delta=.8*min(1,max(0,(row-1)/4))*(-1 if side==0 else 1)
                    ids=slice(b+layer*98+row*7,b+layer*98+(row+1)*7)
                    co[ids,1]+=delta
                    co[ids,0]*=1-.32*min(1,max(0,(row-1)/5))
        key.data.foreach_set('co',co.astype(np.float32).ravel())
        if key.name=='Basis':obj.data.vertices.foreach_set('co',co.astype(np.float32).ravel())
    obj.data.update();WEIGHT_CHANGED.add(obj.name);OBST.clear()


def show_pose(action, frame, pieces):
    ws._rest_pose(RIG)
    if action:
        path = '%s/gfx/models/portraits/%s_body/%s_body_%s.anim' % (GAME, SEX, SEX, action)
        act = bpy.data.actions.get('FIT_' + action)
        if act is None:
            act, _ = ws.import_anim(RIG, path)
            act.name = 'FIT_' + action
            act.use_fake_user = True
        RIG.animation_data.action = act
        bpy.context.scene.frame_set(frame)
        ws.game_pose(RIG)
    else:
        RIG.animation_data.action = None
        bpy.context.view_layer.update()
    for o in bpy.context.scene.objects:
        o.hide_set(o.type != 'MESH' or (o != BODY and o.name not in pieces))


def save_corrections():
    data = {}
    for name, original in ORIGINAL.items():
        obj = bpy.data.objects[name]
        if name in WEIGHT_CHANGED:
            data[name + '|weights'] = weights(obj).astype(np.float32)
            data[name + '|bones'] = np.array(BONES)
            data[name + '|original'] = original['Basis'].astype(np.float32)
        for shape, before in original.items():
            d = coords(obj, shape) - before
            if np.max(np.abs(d)) > 1e-5:
                data[name + '|' + shape.lower()] = d.astype(np.float32)
                data[name + '|original'] = original['Basis'].astype(np.float32)
    path = MOD + '/source/fitting_' + SEX + '.npz'
    np.savez_compressed(path, **data)
    print('Saved', len(data), 'shape corrections to', path)


def export_changed(only=None):
    """Export reviewed pieces and every matching blendshape through the live exporter."""
    ws._rest_pose(RIG)
    RIG.animation_data.action = None
    # Some animation imports leave body_root detached from the zero ground bone.
    # The exporter walks only the first root's hierarchy; rejoin that hierarchy.
    RIG.hide_set(False)
    bpy.context.view_layer.objects.active=RIG
    if RIG.data.bones[0].name=='ground_joint' and RIG.data.bones['body_root'].parent is None:
        bpy.ops.object.mode_set(mode='EDIT')
        RIG.data.edit_bones['body_root'].parent=RIG.data.edit_bones['ground_joint']
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    out = MOD + '/gfx/models/portraits/ek2lc/reach_hide_01'
    def emit(obj, path, shape=False):
        for other in bpy.context.view_layer.objects:
            other.select_set(False)
        obj.hide_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.io_pdx_mesh.export_mesh(filepath=path, chk_mesh=True, chk_skel=not shape,
            chk_locs=False, chk_selected=True, chk_mesh_blendshape=shape)
    for name, original in ORIGINAL.items():
        if only is not None and name not in only:
            continue
        obj = bpy.data.objects[name]
        if name not in WEIGHT_CHANGED and all(np.max(np.abs(coords(obj, s)-old)) < 1e-5 for s, old in original.items()):
            continue
        for key in obj.data.shape_keys.key_blocks:
            key.value = 0
        emit(obj, out + '/' + name + '.mesh')
        node = obj.data.name
        obj.data.name = node + '_base'
        try:
            for key in obj.data.shape_keys.key_blocks[1:]:
                mesh = obj.data.copy()
                tmp = bpy.data.objects.new('fitting_shape', mesh)
                bpy.context.scene.collection.objects.link(tmp)
                tmp.shape_key_clear()
                mesh.vertices.foreach_set('co', coords(obj, key.name).astype(np.float32).ravel())
                mesh.name = node
                mesh.update()
                emit(tmp, out + '/' + name + '_bs_' + key.name + '.mesh', True)
                bpy.data.objects.remove(tmp, do_unlink=True)
                bpy.data.meshes.remove(mesh)
        finally:
            obj.data.name = node
        print('EXPORTED', name, flush=True)
