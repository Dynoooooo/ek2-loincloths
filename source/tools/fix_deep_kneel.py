"""Local garment fitting, executed in the live Blender app after refit_clothing.resume()."""
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import refit_clothing as fit

SOLIDS={}


class SolidBody:
    def __init__(self,points,faces):
        self.tree=BVHTree.FromPolygons(points.tolist(),faces)
        triangles=[(f[0],f[j],f[j+1]) for f in faces for j in range(1,len(f)-1)]
        self.tri=points[np.asarray(triangles)]

    def find_nearest(self,*args):return self.tree.find_nearest(*args)
    def ray_cast(self,*args):return self.tree.ray_cast(*args)

    def winding(self,point):
        # Solid angle avoids direction-dependent ray errors at open seams and
        # the reversed nearest normals of a folded, self-contacting skin mesh.
        a,b,c=np.moveaxis(self.tri-np.asarray(point),1,0)
        la=np.linalg.norm(a,axis=1);lb=np.linalg.norm(b,axis=1);lc=np.linalg.norm(c,axis=1)
        num=np.einsum('ij,ij->i',a,np.cross(b,c))
        den=la*lb*lc+np.einsum('ij,ij->i',a,b)*lc+np.einsum('ij,ij->i',b,c)*la+np.einsum('ij,ij->i',c,a)*lb
        return float(np.arctan2(num,den).sum()/(2*np.pi))


def bodies():
    key=(fit.BODY.as_pointer(),len(fit.POSES))
    if key not in SOLIDS:
        points=fit.deform(fit.coords(fit.BODY),fit.BODY_TF)
        SOLIDS[key]=[SolidBody(p,fit.BODY_FACES) for p in points]
    return SOLIDS[key]


def inside(tree,point):
    return abs(tree.winding(point))>.5


def contact(tree,point,margin):
    p=Vector(point);loc,normal,index,distance=tree.find_nearest(p,8)
    if loc is None:return None
    if (p-loc).dot(normal)>=margin:return None
    contained=inside(tree,p)
    if not contained and distance>=margin:return None
    signed=-distance if contained else distance
    outward=(loc-p) if contained else (p-loc)
    if outward.length<1e-6:outward=normal.copy()
    outward.normalize()
    return signed,outward


def set_weights(obj,w):
    for group in obj.vertex_groups:
        group.remove(list(range(len(w))))
    for b in np.nonzero(w.any(axis=0))[0]:
        group=obj.vertex_groups.get(fit.BONES[b]) or obj.vertex_groups.new(name=fit.BONES[b])
        for v in np.nonzero(w[:,b]>1e-6)[0]:
            group.add([int(v)],float(w[v,b]),'REPLACE')
    fit.WEIGHT_CHANGED.add(obj.name)
    fit.OBST.clear()


def clearance(name,margin=.18,sweeps=24,face_passes=0,layers=()):
    """Project local rest-mesh displacements onto contact constraints in every pose.

    Each translation is shared by lining/seam pairs. Unlike the older soft fit,
    a collision is a constraint rather than a penalty that may be traded for
    smoothness. A small smoothing pass is followed by contact projection again.
    """
    obj=bpy.data.objects[name];start=fit.coords(obj)
    tf=fit.transforms(obj);A=tf[:,:,:,:3];t=tf[:,:,:,3]
    gid=np.arange(len(start))
    assert '_leggings_' not in name, 'Use retopo_leggings.build() for the fitted leg surface'
    if name.endswith('_reach_hide_01'):
        for side in range(2):
            b=325+side*196
            gid[b+98:b+196]=np.arange(b,b+98)
    else:
        # Pair linings without chaining nearby rows into one rigid cluster.
        from mathutils.kdtree import KDTree
        kd=KDTree(len(start))
        for v,p in enumerate(start):kd.insert(Vector(p),v)
        kd.balance();nearest={}
        for v,p in enumerate(start):
            hits=[(d,i) for _,i,d in kd.find_n(Vector(p),3) if i!=v]
            if hits:nearest[v]=min(hits)
        for v,(d,i) in nearest.items():
            if d<.37 and nearest.get(i,(None,None))[1]==v:gid[v]=min(v,i)
    _,gid=np.unique(gid,return_inverse=True)
    ng=gid.max()+1;D=np.zeros((ng,3))
    obs=bodies()
    if layers:
        bodypoints=fit.deform(fit.coords(fit.BODY),fit.BODY_TF)
        polys=list(fit.BODY_FACES)
        for layer in layers:
            extra=bpy.data.objects['ek2lc_'+fit.SEX[0]+'_'+layer+'_01']
            off=bodypoints.shape[1]
            points=fit.deform(fit.coords(extra),fit.transforms(extra))
            if layer=='reach_hide':
                surface=[list(p.vertices) for p in extra.data.polygons if
                         all(325<=v<423 for v in p.vertices) or all(521<=v<619 for v in p.vertices)]
            elif layer=='leggings':surface=fit.outer_faces(extra)
            else:raise ValueError(layer)
            polys += [[i+off for i in f] for f in surface]
            bodypoints=np.concatenate([bodypoints,points],axis=1)
        obs=[SolidBody(p,polys) for p in bodypoints]
    faces=[np.array(p.vertices) for p in obj.data.polygons]
    edges=fit.ws.mesh_edges([f.tolist() for f in faces])
    first=None
    for sweep in range(sweeps):
        worst=0
        for pi,bt in enumerate(obs):
            points=np.einsum('vij,vj->vi',A[pi],start+D[gid])+t[pi]
            corr=np.zeros((ng,3));lack=np.zeros(ng)
            for v,p in enumerate(points):
                hit=contact(bt,p,margin)
                if hit is None:continue
                sd,n=hit;worst=max(worst,-sd)
                e=margin-sd
                if e>lack[gid[v]]:
                    a=A[pi,v].T@np.array(n)
                    corr[gid[v]]=e*a/max(float(a@a),1e-8)
                    lack[gid[v]]=e
            D+=corr*.9
        if first is None:first=worst
        # Spread the correction a little before the final exact contact passes.
        if sweep in (4,9):
            total=np.zeros_like(D);count=np.zeros(ng)
            for a,b in edges:
                ga,gb=gid[a],gid[b]
                total[ga]+=D[gb];total[gb]+=D[ga];count[ga]+=1;count[gb]+=1
            D=.8*D+.2*total/np.maximum(count[:,None],1)
        if sweep>=12 and worst<.01:break
    co=start+D[gid]
    # Surface contacts use the same projection, distributing a face's movement
    # over its contributing translations. Kept optional for dense leg tubes.
    for _ in range(face_passes):
        for pi,bt in enumerate(obs):
            for ids in faces:
                p=(np.einsum('vij,vj->vi',A[pi,ids],start[ids]+D[gid[ids]])+t[pi,ids]).mean(axis=0)
                hit=contact(bt,p,margin)
                if hit is None:continue
                sd,n=hit;e=margin-sd
                if e<=0:continue
                gradients={}
                for v in ids:
                    g=gid[v]
                    gradients[g]=gradients.get(g,np.zeros(3))+A[pi,v].T@np.array(n)/len(ids)
                norm=sum(a@a for a in gradients.values())
                for g,a in gradients.items():D[g]+=.85*e*a/max(norm,1e-8)
    co=start+D[gid]
    obj.data.shape_keys.key_blocks['Basis'].data.foreach_set('co',co.astype(np.float32).ravel())
    obj.data.vertices.foreach_set('co',co.astype(np.float32).ravel());obj.data.update()
    # Preserve each morph's authored shape and apply this local fitting stroke.
    delta=co-start
    for key in obj.data.shape_keys.key_blocks[1:]:
        shape=fit.coords(obj,key.name)+delta
        key.data.foreach_set('co',shape.astype(np.float32).ravel())
    fit.OBST.clear()
    print('CONTACT',name,'initial %.3f, final iteration %.3f cm; maximum local movement %.2f cm'%
          (first,worst,np.linalg.norm(D,axis=1).max()),flush=True)


def report(pieces):
    for pc in pieces:
        obj=bpy.data.objects['ek2lc_'+fit.SEX[0]+'_'+pc+'_01']
        points=fit.deform(fit.coords(obj),fit.transforms(obj));worst=(0,None,None)
        for pi,bt in enumerate(bodies()):
            for v,p in enumerate(points[pi]):
                loc,n,_,d=bt.find_nearest(Vector(p))
                if (Vector(p)-loc).dot(n)<0 and d>worst[0] and inside(bt,p):worst=(d,fit.POSES[pi][0],v)
        print('PENETRATION',pc,worst,flush=True)


def separate_aprons(amount=2):
    """Separate the royal panels from the base wrap without moving their ties."""
    for piece in ('reach_king','reach_duke'):
        obj=bpy.data.objects['ek2lc_'+fit.SEX[0]+'_'+piece+'_01'];co=fit.coords(obj)
        mask=np.zeros(len(co),bool)
        for poly in obj.data.polygons:
            for li in poly.loop_indices:
                uv=obj.data.uv_layers[0].data[li].uv
                if .02<=uv.x<=.48 and .01<=uv.y<=.49:mask[obj.data.loops[li].vertex_index]=True
        expected=270 if piece=='reach_king' else 90
        assert mask.sum()==expected,'Unexpected royal panel topology'
        fade=np.clip((fit.RIG.data.bones['body_root'].head_local.z+9-co[:,2])/8,0,1)*mask
        delta=np.zeros_like(co);delta[:,1]=amount*np.sign(co[:,1])*fade
        for key in obj.data.shape_keys.key_blocks:
            out=fit.coords(obj,key.name)+delta
            key.data.foreach_set('co',out.astype(np.float32).ravel())
            if key.name=='Basis':obj.data.vertices.foreach_set('co',out.astype(np.float32).ravel())
        obj.data.update()


def mark_surface(obj):
    attr=obj.data.attributes.get('ek2lc_outer')
    if attr:return attr
    attr=obj.data.attributes.new('ek2lc_outer','INT','FACE')
    co=fit.coords(obj)
    for poly in obj.data.polygons:
        ids=list(poly.vertices)
        if obj.name.endswith('_leggings_01'):outer=all(v<len(co)//2 for v in ids)
        elif obj.name.endswith('_reach_hide_01'):
            outer=all(325<=v<423 for v in ids) or all(521<=v<619 for v in ids)
        else:
            uv=[obj.data.uv_layers[0].data[i].uv for i in poly.loop_indices]
            outer=all(.02<=p.x<=.48 and .01<=p.y<=.49 for p in uv) and poly.normal.y*co[ids].mean(axis=0)[1]>0
        attr.data[poly.index].value=int(outer)
    return attr


def surface_contacts(name):
    obj=bpy.data.objects[name];flag=mark_surface(obj)
    points=fit.deform(fit.coords(obj),fit.transforms(obj));bad=set();worst=(0,None,None)
    faces=[(p.index,list(p.vertices)) for p in obj.data.polygons if flag.data[p.index].value]
    for pi,bt in enumerate(bodies()):
        if not any(n in fit.POSES[pi][0] for n in ('kneel','messenger','curtsey','ruler2','ruler3')):continue
        for fi,ids in faces:
            pp=points[pi,ids];samples=[pp.mean(axis=0)]+[(a+b)/2 for a,b in zip(pp,np.roll(pp,-1,axis=0))]
            for p in samples:
                hit=contact(bt,p,0)
                if hit is not None and -hit[0]>.03:
                    bad.add(fi)
                    if -hit[0]>worst[0]:worst=(-hit[0],fit.POSES[pi][0],fi)
    print('SURFACE CONTACTS',name,len(bad),'faces;',worst,flush=True)
    return bad


def finish_panels(name, passes=4):
    """Lift face interiors off the skin while keeping the waistband attached."""
    obj=bpy.data.objects[name];start=fit.coords(obj);co=start.copy()
    tf=fit.transforms(obj);flag=mark_surface(obj)
    faces=[list(p.vertices) for p in obj.data.polygons if flag.data[p.index].value]
    paired={};pinned=set()
    if name.endswith('_reach_hide_01'):
        for side in range(2):
            b=325+196*side
            for i in range(98):
                paired[b+i]=[b+i,b+98+i]
                paired[b+98+i]=paired[b+i]
            pinned.update(range(b,b+14));pinned.update(range(b+98,b+112))
    for _ in range(passes):
        for pi,bt in enumerate(bodies()):
            if not any(n in fit.POSES[pi][0] for n in ('kneel','messenger','curtsey','ruler2','ruler3')):continue
            for ids in faces:
                samples=[(ids,np.ones(len(ids))/len(ids))]
                samples += [([a,b],np.array([.5,.5])) for a,b in zip(ids,ids[1:]+ids[:1])]
                for indices,bary in samples:
                    points=np.einsum('vij,vj->vi',tf[pi,indices,:,:3],co[indices])+tf[pi,indices,:,3]
                    hit=contact(bt,bary@points,.12)
                    if hit is None:continue
                    distance,normal=hit;grads={}
                    for v,weight in zip(indices,bary):
                        if v in pinned:continue
                        group=tuple(paired.get(v,[v]))
                        grads[group]=grads.get(group,np.zeros(3))+weight*tf[pi,v,:,:3].T@np.asarray(normal)
                    length=sum(g@g for g in grads.values())
                    for group,g in grads.items():
                        movement=.8*(.12-distance)*g/max(length,1e-8)
                        norm=np.linalg.norm(movement)
                        if norm>.6:movement*=.6/norm
                        co[list(group)]+=movement
    delta=co-start
    for key in obj.data.shape_keys.key_blocks:
        out=fit.coords(obj,key.name)+delta
        key.data.foreach_set('co',out.astype(np.float32).ravel())
    obj.data.vertices.foreach_set('co',co.astype(np.float32).ravel());obj.data.update()
    fit.OBST.clear()
    print('PANEL FACE FINISH',name,'maximum stroke',np.linalg.norm(delta,axis=1).max(),flush=True)
