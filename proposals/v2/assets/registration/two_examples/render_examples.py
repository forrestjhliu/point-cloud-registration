"""Render two actual benchmark pairs. Colors are illustrative; no model is run."""
from pathlib import Path
import json
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent
BG, BLUE, ORANGE, GREEN = '#F6F8FA', '#2857B8', '#DF8650', '#008D70'
GROUPS = ['high_3dmatch', 'low_3dlomatch']
THRESHOLD_M = 0.05


def display_frame(points):
    return points[:, [0, 2, 1]] * [1, 1, -1]


def projection(azimuth, elevation):
    az, el = np.deg2rad([azimuth, elevation])
    view = np.array([np.cos(el)*np.cos(az), np.cos(el)*np.sin(az), np.sin(el)])
    right = np.cross([0., 0., 1.], view)
    right /= np.linalg.norm(right)
    up = np.cross(view, right)
    return np.array([right, up, view]).T


def shade(points, color):
    coords = display_frame(points)
    neighbors = cKDTree(coords).query(coords, k=16)[1]
    local = coords[neighbors] - coords[neighbors].mean(1, keepdims=True)
    _, eigenvectors = np.linalg.eigh(np.einsum('nki,nkj->nij', local, local))
    normals = eigenvectors[:, :, 0]
    light = np.array([-.35, -.45, .82]); light /= np.linalg.norm(light)
    brightness = .66 + .34*np.abs(normals@light)
    return .93*np.array(to_rgb(color))*brightness[:, None] + .07*np.array(to_rgb(BG))


data, panels, report = {}, {}, {}
for group in GROUPS:
    src, ref, gt = [np.load(ROOT/group/(name+'.npy'), allow_pickle=False)
                    for name in ['src', 'ref', 'gt']]
    aligned = src @ gt[:3, :3].T + gt[:3, 3]
    mask_src = cKDTree(ref).query(aligned)[0] < THRESHOLD_M
    mask_ref = cKDTree(aligned).query(ref)[0] < THRESHOLD_M
    data[group] = dict(src=src, ref=ref, aligned=aligned)
    source_color, target_color = shade(src, BLUE), shade(ref, ORANGE)
    aligned_color = shade(aligned, BLUE)
    gt_source_color, gt_target_color = aligned_color.copy(), target_color.copy()
    # Highlight only after applying GT. These masks are not given to the model.
    gt_source_color[mask_src] = shade(aligned, GREEN)[mask_src]
    gt_target_color[mask_ref] = shade(ref, GREEN)[mask_ref]
    panels[group] = {
        'input_source': [(src, source_color)],
        'input_reference': [(ref, target_color)],
        'gt_alignment': [(aligned, aligned_color), (ref, target_color)],
        'gt_common_surface': [(aligned, gt_source_color), (ref, gt_target_color)],
    }
    report[group] = {
        'source_points': len(src), 'reference_points': len(ref),
        'display_mask_threshold_m': THRESHOLD_M,
        'display_mask_source_fraction': float(mask_src.mean()),
        'display_mask_reference_fraction': float(mask_ref.mean()),
        'display_mask_is_benchmark_overlap': False,
    }


def bounds(azimuth, elevation):
    proj = projection(azimuth, elevation)
    # Both GT panels share center, viewing direction and metric scale.
    union = np.concatenate([data[g]['aligned'] for g in GROUPS] + [data[GROUPS[0]]['ref']])
    projected = display_frame(union) @ proj
    gt_center = (projected[:, :2].min(0) + projected[:, :2].max(0))/2
    extents = [np.ptp(projected[:, :2], axis=0)]
    for group in GROUPS:
        for key in ['src', 'ref']:
            pts = display_frame(data[group][key]) @ proj
            extents.append(np.ptp(pts[:, :2], axis=0))
    extent = np.max(extents, axis=0)
    height = max(extent[1], extent[0]/1.43)*1.07
    return proj, gt_center, np.array([height*1.43, height])


def render(ax, group, name, azimuth=-120, elevation=27, size=2.2):
    proj, gt_center, extent = bounds(azimuth, elevation)
    points, colors = panels[group][name][0]
    for more_points, more_colors in panels[group][name][1:]:
        points = np.concatenate([points, more_points])
        colors = np.concatenate([colors, more_colors])
    pts = display_frame(points) @ proj
    center = gt_center if name.startswith('gt_') else (pts[:, :2].min(0)+pts[:, :2].max(0))/2
    order = np.argsort(pts[:, 2], kind='stable')
    ax.scatter(pts[order, 0], pts[order, 1], c=colors[order], s=size,
               linewidths=0, edgecolors='none', rasterized=True)
    ax.set_xlim(center[0]-extent[0]/2, center[0]+extent[0]/2)
    ax.set_ylim(center[1]-extent[1]/2, center[1]+extent[1]/2)
    ax.set_aspect('equal'); ax.set_axis_off(); ax.set_facecolor(BG)


def candidates():
    angles = [-150, -120, -90, -60, -30, 15]
    fig, axes = plt.subplots(2, 6, figsize=(24, 6.4), dpi=90, facecolor=BG)
    for i, group in enumerate(GROUPS):
        for j, angle in enumerate(angles):
            render(axes[i, j], group, 'gt_common_surface', angle, 27, .5)
            axes[i, j].set_title(f'{group}: {angle}', fontsize=10, color='#172B3A')
    fig.tight_layout(pad=.3)
    fig.savefig(ROOT/'view_candidates.jpg', facecolor=BG, dpi=90)
    plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidates', action='store_true')
    parser.add_argument('--azimuth', type=float, default=-120)
    parser.add_argument('--elevation', type=float, default=27)
    args = parser.parse_args()
    if args.candidates:
        candidates()
    else:
        for group in GROUPS:
            for name in panels[group]:
                fig = plt.figure(figsize=(7.15, 5), dpi=210, facecolor=BG)
                ax = fig.add_axes([0, 0, 1, 1])
                render(ax, group, name, args.azimuth, args.elevation)
                fig.savefig(ROOT/group/(name+'.png'), facecolor=BG, dpi=210)
                plt.close(fig)
        assert np.array_equal(data[GROUPS[0]]['ref'], data[GROUPS[1]]['ref'])
        report.update({
            'azimuth_deg': args.azimuth, 'elevation_deg': args.elevation,
            'shared_metric_scale': True, 'shared_reference_camera': True,
            'shared_gt_camera': True, 'input_panels_centered_for_display': True,
            'all_points_rendered': True, 'model_run': False,
            'point_color': 'illustrative, not RGB input or a prediction',
            'transform': 'aligned = src @ gt[:3,:3].T + gt[:3,3]',
        })
        (ROOT/'render_manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
