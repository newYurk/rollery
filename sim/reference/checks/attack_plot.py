import json, math, sys
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT='/Users/newyurk/Desktop/Home/Projects/rollery/sim/reference'
BG,RICE,NORI=0,1,2
KIND={3:'salmon',4:'cucumber',5:'tamago',6:'avocado',7:'shrimp'}
PX,NRAY=0.02,36
OUTD = sys.argv[1] if len(sys.argv)>1 else f'{ROOT}/out'
TAG  = sys.argv[2] if len(sys.argv)>2 else ''
fig,axs=plt.subplots(1,3,figsize=(19,6.6))
for ax,L in zip(axs,(1,2,4)):
    met=json.load(open(f'{OUTD}/metrics_{L}.json')); img=np.load(f'{OUTD}/material_{L}.npy')
    d=np.load(f'{OUTD}/particles_{L}.npz'); xs=d['x'].astype(float); cls=d['cls']; ncol=d['nori_col']
    npx=img.shape[0]; cen_w=np.array(met['window_center_xy'],float)
    rows,cols=np.nonzero(img!=BG); cr,cc=rows.mean(),cols.mean()
    cen=np.array([cen_w[0]+(cc-npx/2)*PX, cen_w[1]+(npx/2-cr)*PX])
    ax.imshow(img,origin='upper',cmap='Greys',vmin=0,vmax=7,alpha=.25,
              extent=[(0-cc)*PX,(npx-cc)*PX,(npx-cr)*PX,(0-cr)*PX])
    for c,col in ((RICE,'#d8cfae'),):
        m=cls==c; ax.scatter(xs[m,0]-cen[0],xs[m,1]-cen[1],s=.4,c=col,lw=0)
    m=cls==NORI
    o=np.argsort(ncol[m]); pn=xs[m][o]; cn=ncol[m][o]
    uc,st=np.unique(cn,return_index=True)
    cl=np.array([pn[s].mean(axis=0) for s in np.split(np.arange(len(cn)),st[1:])])
    ax.scatter(cl[:,0]-cen[0],cl[:,1]-cen[1],s=6,c=np.arange(len(cl)),cmap='viridis',lw=0,zorder=4)
    ax.plot(cl[0,0]-cen[0],cl[0,1]-cen[1],'o',ms=13,mfc='none',mec='red',mew=2.4,zorder=6)
    ax.plot(cl[-1,0]-cen[0],cl[-1,1]-cen[1],'s',ms=13,mfc='none',mec='blue',mew=2.4,zorder=6)
    for c in sorted(set(int(v) for v in np.unique(cls) if v>NORI)):
        mm=cls==c; ax.scatter(xs[mm,0]-cen[0],xs[mm,1]-cen[1],s=1.4,label=KIND[c],lw=0)
        ax.annotate(KIND[c],(xs[mm,0].mean()-cen[0],xs[mm,1].mean()-cen[1]),
                    fontsize=9,ha='center',weight='bold',zorder=7,
                    bbox=dict(fc='w',ec='k',alpha=.85,pad=1.2))
    angs=np.deg2rad(np.arange(0,360,10)); Rout=[]
    for a in angs:
        step=.25; nn=int(npx/2/step); dd=np.arange(nn)*step
        rr=np.round(cr-dd*math.sin(a)).astype(int); c2=np.round(cc+dd*math.cos(a)).astype(int)
        ok=(rr>=0)&(rr<npx)&(c2>=0)&(c2<npx); seq=img[rr[ok],c2[ok]]; dist=dd[ok]*PX
        nz=np.nonzero(seq!=BG)[0]; Rout.append(dist[nz[-1]] if len(nz) else 0.)
    Rout=np.array(Rout); Rs=np.array([np.median(Rout[np.arange(i-2,i+3)%NRAY]) for i in range(NRAY)])
    aa=np.append(angs,angs[0]); rr2=np.append(Rs,Rs[0])
    ax.plot(rr2*np.cos(aa),rr2*np.sin(aa),'k--',lw=1.2,zorder=5)
    ax.plot(0,0,'k+',ms=12,zorder=7)
    ax.set_aspect('equal'); ax.set_xlim(-6,6); ax.set_ylim(-6,6)
    ax.set_title(f'L{L}  crossings(raster-free)={json.load(open(f"{ROOT}/checks/attack_centerline.json"))[str(L)]["crossings_centreline_mean"] if TAG=="" else "?"}'
                 f'  ref nori_turns={met["nori_turns"]}\nred o = near edge (s=0), blue square = far flap (s=L)')
plt.tight_layout(); plt.savefig(f'{ROOT}/checks/attack_overview{TAG}.png',dpi=110)
print('wrote', f'{ROOT}/checks/attack_overview{TAG}.png')
