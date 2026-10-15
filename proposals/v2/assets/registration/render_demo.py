"""Render the author's actual demo point clouds; no model inference is performed."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent
BG = '#F6F8FA'
BLUE = '#2857B8'
ORANGE = '#DF8650'
src = np.load(ROOT/'src.npy', allow_pickle=False)
ref = np.load(ROOT/'ref.npy', allow_pickle=False)
gt = np.load(ROOT/'gt.npy', allow_pickle=False)
aligned = src @ gt[:3,:3].T + gt[:3,3]

# All panels use one fixed projection, scale, and reference camera convention.
# Camera x right, y down, z forward -> display x right, z forward, -y up.
def display_frame(points):
    return points[:, [0,2,1]] * np.array([1,1,-1])

all_points = display_frame(np.concatenate([src, ref, aligned]))
CENTER = (all_points.min(0)+all_points.max(0))/2

def projection(azimuth, elevation):
    az, el = np.deg2rad([azimuth, elevation])
    view = np.array([np.cos(el)*np.cos(az), np.cos(el)*np.sin(az), np.sin(el)])
    right = np.cross(np.array([0.,0.,1.]), view)
    right /= np.linalg.norm(right)
    up = np.cross(view, right)
    return np.array([right, up, view]).T

def normals(points):
    neighbors = cKDTree(points).query(points, k=16)[1]
    local = points[neighbors]-points[neighbors].mean(1, keepdims=True)
    covariance = np.einsum('nki,nkj->nij', local, local)
    _, vectors = np.linalg.eigh(covariance)
    return vectors[:,:,0]

N_SRC, N_REF = normals(display_frame(src)), normals(display_frame(ref))
N_ALIGNED = normals(display_frame(aligned))

def render(ax, clouds, azimuth=-120, elevation=27, point_size=3.2):
    P = projection(azimuth, elevation)
    all_projected = (all_points-CENTER)@P
    lower, upper = all_projected[:,:2].min(0), all_projected[:,:2].max(0)
    midpoint = (lower+upper)/2
    span = upper-lower
    # 16:11 canvas; preserve full metric geometry without cropping or stretching.
    height = max(span[1], span[0]/(16/11))*1.10
    width = height*(16/11)
    pts, colors = [], []
    light = np.array([-.35,-.45,.82]); light /= np.linalg.norm(light)
    for points, norm, color in clouds:
        projected=(display_frame(points)-CENTER)@P
        base=np.array(to_rgb(color))
        brightness=.62+.38*np.abs(norm@light)
        shaded=base[None,:]*brightness[:,None]
        # A little reflected background light retains thin scanned surfaces.
        shaded=.88*shaded+.12*np.array(to_rgb(BG))[None,:]
        pts.append(projected); colors.append(shaded)
    pts,colors=np.concatenate(pts),np.concatenate(colors)
    order=np.argsort(pts[:,2], kind='stable')
    ax.scatter(pts[order,0],pts[order,1],c=colors[order],s=point_size,
               linewidths=0,edgecolors='none',rasterized=True,marker='o')
    ax.set_xlim(midpoint[0]-width/2,midpoint[0]+width/2)
    ax.set_ylim(midpoint[1]-height/2,midpoint[1]+height/2)
    ax.set_aspect('equal');ax.set_axis_off();ax.set_facecolor(BG)

def save(name,clouds,azimuth=-120,elevation=27):
    fig=plt.figure(figsize=(8,5.5),dpi=240,facecolor=BG)
    ax=fig.add_axes([0,0,1,1]);render(ax,clouds,azimuth,elevation)
    fig.savefig(ROOT/name,dpi=240,facecolor=BG)
    plt.close(fig)

panels={
    'source.png':[(src,N_SRC,BLUE)],
    'reference.png':[(ref,N_REF,ORANGE)],
    'before_overlay.png':[(src,N_SRC,BLUE),(ref,N_REF,ORANGE)],
    'aligned_gt.png':[(aligned,N_ALIGNED,BLUE),(ref,N_REF,ORANGE)],
}
src_overlap = cKDTree(ref).query(aligned)[0] < .1
ref_overlap = cKDTree(aligned).query(ref)[0] < .1
panels['overlap_gt.png'] = [
    (aligned[~src_overlap],N_ALIGNED[~src_overlap],'#B9C1CC'),
    (ref[~ref_overlap],N_REF[~ref_overlap],'#B9C1CC'),
    (aligned[src_overlap],N_ALIGNED[src_overlap],'#26866F'),
    (ref[ref_overlap],N_REF[ref_overlap],'#26866F'),
]
for name,clouds in panels.items():save(name,clouds)

fig,axes=plt.subplots(2,3,figsize=(15,7.5),dpi=120,facecolor=BG)
for ax,az in zip(axes.ravel(),[-120,-90,-72,-45,0,45]):
    render(ax,panels['aligned_gt.png'],azimuth=az,elevation=27,point_size=1.3)
    ax.set_title(f'View azimuth {az}',fontsize=12,color='#25354A')
fig.tight_layout();fig.savefig(ROOT/'view_candidates.png',facecolor=BG);plt.close(fig)

print(json.dumps({'source_points':len(src),'reference_points':len(ref),
                  'render_size':[1920,1320],'files':list(panels),
                  'convention':'x_ref = R @ x_src + t; row-array equivalent src @ R.T + t',
                  'model_run':False}))
