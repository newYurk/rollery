"""Independent falsification of nori_turns: a ray crossing at radius r costs r*dphi of sheet.
Summing over the 36 rays gives the sheet length implied by the crossing count. Compare with the
true nori centreline arclength (~L_SHEET = 38.7 T). An over-counted crossing metric demands
more nori than exists."""
import json, math, sys
import numpy as np
ROOT='/Users/newyurk/Desktop/Home/Projects/rollery/sim/reference'
OUTD = sys.argv[1] if len(sys.argv)>1 else f'{ROOT}/out'
BG,NORI=0,2; PX,NRAY=0.02,36; DA=2*math.pi/NRAY; L_SHEET=38.7

def ray(img,cr,cc,a,step=0.25):
    n=int(img.shape[0]/2/step); d=np.arange(n)*step
    rr=np.round(cr-d*math.sin(a)).astype(int); c2=np.round(cc+d*math.cos(a)).astype(int)
    ok=(rr>=0)&(rr<img.shape[0])&(c2>=0)&(c2<img.shape[1])
    return d[ok]*PX, img[rr[ok],c2[ok]]

print(f'{"L":>2} {"arclen_true":>11} {"impl_raw":>9} {"impl_rob":>9} {"impl_cline":>11} '
      f'{"raw/true":>8} {"rob/true":>8}  nori_turns  cross_rob  cross_cline')
for L in (1,2,4):
    met=json.load(open(f'{OUTD}/metrics_{L}.json')); img=np.load(f'{OUTD}/material_{L}.npy')
    d=np.load(f'{OUTD}/particles_{L}.npz'); xs=d['x'].astype(float); cls=d['cls']; ncol=d['nori_col']
    npx=img.shape[0]; rows,cols=np.nonzero(img!=BG); cr,cc=rows.mean(),cols.mean()
    cen_w=np.array(met['window_center_xy'],float)
    cen=np.array([cen_w[0]+(cc-npx/2)*PX, cen_w[1]+(npx/2-cr)*PX])
    m=cls==NORI; o=np.argsort(ncol[m]); pn=xs[m][o]; cn=ncol[m][o]
    uc,st=np.unique(cn,return_index=True)
    cl=np.array([pn[s].mean(axis=0) for s in np.split(np.arange(len(cn)),st[1:])])
    arclen=float(np.hypot(*np.diff(cl,axis=0).T).sum())
    rel=cl-cen; r=np.hypot(rel[:,0],rel[:,1]); ph=np.unwrap(np.arctan2(rel[:,1],rel[:,0]))
    impl_cline=float(np.sum(0.5*(r[1:]+r[:-1])*np.abs(np.diff(ph))))   # int r|dphi|
    sraw=srob=0.0; nraw=nrob=0
    for a in np.arange(0,2*math.pi,DA):
        dd,seq=ray(img,cr,cc,a); idx=np.nonzero(seq==NORI)[0]
        if not len(idx): continue
        gr=np.split(idx,np.nonzero(np.diff(idx)>1)[0]+1)
        seg=[(dd[g[0]],dd[g[-1]]) for g in gr]
        mg=[list(seg[0])]
        for a2,b in seg[1:]:
            if a2-mg[-1][1]<0.04: mg[-1][1]=b
            else: mg.append([a2,b])
        mg=[s for s in mg if s[1]-s[0]>=0.04]
        sraw+=sum(0.5*(a2+b) for a2,b in seg)*DA; nraw+=len(seg)
        srob+=sum(0.5*(a2+b) for a2,b in mg)*DA;  nrob+=len(mg)
    print(f'{L:>2} {arclen:>11.2f} {sraw:>9.2f} {srob:>9.2f} {impl_cline:>11.2f} '
          f'{sraw/arclen:>8.2f} {srob/arclen:>8.2f}  {met["nori_turns"]:>9} {nrob/NRAY:>9.3f} ')
