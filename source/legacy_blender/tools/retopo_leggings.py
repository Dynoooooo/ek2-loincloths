"""Build the fitted hide surface on the body's leg triangles in live Blender."""
import bpy
import numpy as np
from mathutils import Vector
import refit_clothing as fit
from fix_deep_kneel import set_weights


def build():
    obj=bpy.data.objects['ek2lc_'+fit.SEX[0]+'_leggings_01']
    body=fit.coords(fit.BODY);bw=fit.weights(fit.BODY)
    fit.BODY.data.calc_loop_triangles()
    triangles=[list(t.vertices) for t in fit.BODY.data.loop_triangles]
    normals={};weld={}
    for i,p in enumerate(body):weld.setdefault(tuple(np.round(p,3)),[]).append(i)
    for key in fit.BODY.data.shape_keys.key_blocks:
        p=fit.coords(fit.BODY,key.name);n=np.zeros_like(p)
        for ids in triangles:
            a,b,c=p[ids];normal=np.cross(b-a,c-a);n[ids]+=normal
        for ids in weld.values():n[ids]=n[ids].sum(axis=0)
        n/=np.maximum(np.linalg.norm(n,axis=1)[:,None],1e-9);normals[key.name]=n
    rig=fit.RIG
    hip=np.array(rig.data.bones['bn_l_hip'].head_local)
    knee=np.array(rig.data.bones['bn_l_knee'].head_local)
    ankle=np.array(rig.data.bones['bn_l_ankle'].head_local)
    root=rig.data.bones['body_root'].head_local.z
    crotch=min(p[2] for p in body if abs(p[0])<1 and 40<p[2]<root+5)
    bottom=ankle[2]+2.2;high=root-2;low=crotch-4.5;lside=1 if hip[0]>0 else -1

    def axis(z,side):
        z=min(z,crotch-3);a,b=(ankle,knee) if z<knee[2] else (knee,hip)
        t=np.clip((z-a[2])/(b[2]-a[2]),0,1);p=a+t*(b-a);p=p.copy();p[0]*=side/lside
        return p

    def polar(p,side):
        a=axis(p[2],side)
        return np.arctan2(side*(p[0]-a[0]),-(p[1]-a[1]))

    def top(p,side):
        phi=polar(p,side)
        return low+(high-low)*((1+np.sin(phi))/2)**2

    def hem(p,side):
        # An arched front opening leaves room for the foot in a deep kneel.
        return bottom+15*max(0,float(np.cos(polar(p,side))))

    def clip(poly,fn):
        out=[]
        for a,b in zip(poly,poly[1:]+poly[:1]):
            pa=sum((body[i]*w for i,w in a.items()),np.zeros(3));pb=sum((body[i]*w for i,w in b.items()),np.zeros(3))
            fa,fb=fn(pa),fn(pb)
            if fa<=0:out.append(a)
            if (fa<0 and fb>0) or (fa>0 and fb<0):
                t=fa/(fa-fb);d={}
                for i,w in a.items():d[i]=d.get(i,0)+(1-t)*w
                for i,w in b.items():d[i]=d.get(i,0)+t*w
                out.append(d)
        return out

    bindings=[];faces=[];uv=[];lookup={};sides=[]
    for side in (lside,-lside):
        localfaces=[]
        for ids in triangles:
            points=body[ids]
            if np.any(points[:,0]*side<=0) or np.min(points[:,2])>high+3 or np.max(np.abs(points[:,0]))>28:continue
            poly=[{i:1.0} for i in ids]
            poly=clip(poly,lambda p:hem(p,side)-p[2])
            if len(poly)<3:continue
            poly=clip(poly,lambda p:p[2]-top(p,side))
            if len(poly)<3:continue
            indices=[]
            for bind in poly:
                p=sum((body[i]*w for i,w in bind.items()),np.zeros(3))
                key=(side,)+tuple(np.round(p,4))
                if key not in lookup:
                    lookup[key]=len(bindings);bindings.append(bind);sides.append(side)
                indices.append(lookup[key])
            for j in range(1,len(indices)-1):localfaces.append([indices[0],indices[j],indices[j+1]])
        faces+=localfaces
    n=len(bindings);outer=list(faces);faces+=[[i+n for i in reversed(f)] for f in outer]
    edges={}
    for f in outer:
        for a,b in zip(f,f[1:]+f[:1]):edges.setdefault(tuple(sorted((a,b))),[]).append((a,b))
    for items in edges.values():
        if len(items)==1:
            a,b=items[0];faces += [[a,b+n,b],[a,a+n,b+n]]
    pos={}
    for key in fit.BODY.data.shape_keys.key_blocks:
        skin=fit.coords(fit.BODY,key.name);ns=normals[key.name];out=[];lining=[]
        for bind,side in zip(bindings,sides):
            p=sum((skin[i]*w for i,w in bind.items()),np.zeros(3))
            normal=sum((ns[i]*w for i,w in bind.items()),np.zeros(3));normal/=max(np.linalg.norm(normal),1e-9)
            base=sum((body[i]*w for i,w in bind.items()),np.zeros(3))
            flare=np.clip((knee[2]-5-base[2])/(knee[2]-5-bottom),0,1)
            off=.8+.25*flare
            if abs(base[2]-hem(base,side))<.05:off+=.2
            if abs(base[2]-top(base,side))<.1:off+=.15
            out.append(p+normal*off);lining.append(p+normal*(off-.15))
        pos[key.name]=np.array(out+lining)
    basis=pos['Basis'];vv=[]
    for i,(bind,side) in enumerate(zip(bindings,sides)):
        base=sum((body[j]*w for j,w in bind.items()),np.zeros(3));phi=polar(base,side)
        lu=((phi-1.5*np.pi)%(2*np.pi))/(2*np.pi)
        u0=.01 if side==lside else .51
        vv.append((u0+.48*lu,.01+.89*(base[2]-(ankle[2]+1))/(high-(ankle[2]+1)),lu))
    vv+=list(vv)
    for f in faces:
        seam=max(vv[i][2] for i in f)-min(vv[i][2] for i in f)>.5
        uv.append([(vv[i][0] if not seam or vv[i][2]>.5 else (.49 if sides[i%n]==lside else .99),vv[i][1]) for i in f])
    weights=[]
    for bind in bindings:
        w=sum((bw[i]*v for i,v in bind.items()),np.zeros(len(fit.BONES)))
        keep=np.argsort(-w)[:4];row=np.zeros(len(w));row[keep]=w[keep];weights.append(row/row.sum())
    weights=np.array(weights+weights)
    mat=obj.data.materials[0];old=obj.data;name=old.name;old.name=name+'_old'
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(basis.tolist(),[],faces);mesh.update();obj.data=mesh;mesh.materials.append(mat)
    flag=mesh.attributes.new('ek2lc_outer','INT','FACE')
    for i,value in enumerate(flag.data):value.value=1 if i<len(outer) else 0
    obj['ek2lc_pairs']=[i for v in range(n) for i in (v,v+n)]
    layer=mesh.uv_layers.new(name='map1')
    for poly,corners in zip(mesh.polygons,uv):
        poly.use_smooth=True
        for loop,tex in zip(poly.loop_indices,corners):layer.data[loop].uv=tex
    for key,points in pos.items():
        kb=obj.shape_key_add(name=key)
        kb.data.foreach_set('co',points.astype(np.float32).ravel());kb.value=0
    obj.modifiers.clear();obj.modifiers.new('Armature','ARMATURE').object=rig
    set_weights(obj,weights)
    bpy.data.meshes.remove(old)
    print('RETOPO LEGGINGS',fit.SEX,len(basis),'vertices',len(faces),'triangles',len(pos),'body shapes',flush=True)
