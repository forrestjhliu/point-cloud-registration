"""Record provenance for the real-data point-cloud registration proposal figures; no model inference."""
from pathlib import Path
import hashlib
import json
import pickle
from datetime import datetime, timezone
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

ROOT=Path(__file__).resolve().parent
GEO='e7a135af4c318ff3b8d7f6c963df094d7e4ea540'
PRED='8c78f125fc58d62ad7d149adf1fed43ed54937e4'
src,ref,gt=[np.load(ROOT/f'{name}.npy',allow_pickle=False) for name in ('src','ref','gt')]
aligned=src@gt[:3,:3].T+gt[:3,3]
log_lines=(ROOT/'redkitchen_gt.log').read_text().splitlines()
exact_matches=[]
for i in range(0,len(log_lines),5):
    header=[int(x) for x in log_lines[i].split()]
    matrix=np.array([[float(x) for x in log_lines[i+j].split()] for j in range(1,5)])
    if np.array_equal(matrix,gt):exact_matches.append(header)

class Restricted(pickle.Unpickler):
    def find_class(self,module,name):
        if (module,name) in {('numpy.core.multiarray','_reconstruct'),('numpy.core.multiarray','scalar'),('numpy','ndarray'),('numpy','dtype')}:
            return super().find_class(module,name)
        raise pickle.UnpicklingError((module,name))

metadata_root=ROOT.parents[2]/'research'/'registration_metadata'
memberships={}
for name in ['3DMatch','3DLoMatch']:
    with (metadata_root/(name+'.pkl')).open('rb') as stream:rows=Restricted(stream).load()
    matches=[row for row in rows if row['scene_name']=='7-scenes-redkitchen' and int(row['frag_id0'])==0 and int(row['frag_id1'])==6]
    memberships[name]={'pair_present':bool(matches),'associated_metadata_overlap':float(matches[0]['overlap']) if matches else None}

sources={
 'src.npy':f'https://raw.githubusercontent.com/qinzheng93/GeoTransformer/{GEO}/data/demo/src.npy',
 'ref.npy':f'https://raw.githubusercontent.com/qinzheng93/GeoTransformer/{GEO}/data/demo/ref.npy',
 'gt.npy':f'https://raw.githubusercontent.com/qinzheng93/GeoTransformer/{GEO}/data/demo/gt.npy',
 'redkitchen_gt.log':f'https://raw.githubusercontent.com/qinzheng93/GeoTransformer/{GEO}/data/3DMatch/metadata/benchmarks/3DMatch/7-scenes-redkitchen/gt.log',
 'predator_teaser_original.jpg':f'https://raw.githubusercontent.com/prs-eth/OverlapPredator/{PRED}/assets/teaser_predator.jpg',
 'predator_demo_original.png':f'https://raw.githubusercontent.com/prs-eth/OverlapPredator/{PRED}/assets/demo.png',
}
assets=[]
for name,url in sources.items():
    path=ROOT/name
    row={'file':name,'url':url,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'modified_after_download':False}
    if name.startswith('predator'):
        row.update({'kind':'original_author_figure','license':'PREDATOR repository states MIT; image has no separately stated license. Retain author/paper attribution; do not represent it as this project output.','license_url':f'https://github.com/prs-eth/OverlapPredator/blob/{PRED}/LICENSE','dimensions':list(Image.open(path).size)})
        if name=='predator_teaser_original.jpg':
            row.update({'caption':'PREDATOR 作者低重叠配准示例：输入点云、推断重叠区域、显著区域及作者方法结果。非本项目实验结果。','low_overlap_confirmed':'Author-presented low-overlap qualitative illustration; exact per-pair numerical overlap and fragment identity not provided.','source_page':'https://github.com/prs-eth/OverlapPredator','paper_caption_source':'https://openaccess.thecvf.com/content/CVPR2021/papers/Huang_Predator_Registration_of_3D_Point_Clouds_With_Low_Overlap_CVPR_2021_paper.pdf'})
        else:
            row.update({'caption':'PREDATOR 官方 demo 截图，含作者模型的配准与重叠区域预测。仅作作者示例，不是本项目运行结果。','low_overlap_confirmed':False,'source_page':'https://github.com/prs-eth/OverlapPredator#demo'})
    else:
        row.update({'kind':'original_author_data','license':'GeoTransformer repository states MIT; demo data has no separately stated license. Original scans derive from 3DMatch and retain applicable upstream dataset terms.','license_url':f'https://github.com/qinzheng93/GeoTransformer/blob/{GEO}/LICENSE'})
    assets.append(row)

captions={
 'source.png':'源点云 P：GeoTransformer 官方真实 demo，15,953 个点；原始局部坐标。',
 'reference.png':'参考点云 Q：GeoTransformer 官方真实 demo，18,977 个点；原始局部坐标。',
 'before_overlay.png':'直接叠加两片段的原始局部坐标：尚未应用配准变换。',
 'aligned_gt.png':'使用数据集提供的 GT 变换将源点云对齐到参考点云；仅展示标签含义，非模型预测结果。',
 'overlap_gt.png':'GT 对齐后，距另一片点云最近点小于 0.1 m 的点标为绿色，其余为灰色；仅为几何可视化，不等同官方 overlap 数值。',
}
for name,caption in captions.items():
    path=ROOT/name
    assets.append({'file':name,'kind':'original_render_of_author_point_data','source_files':['src.npy','ref.npy','gt.npy'],'url':f'https://github.com/qinzheng93/GeoTransformer/tree/{GEO}/data/demo','bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'dimensions':list(Image.open(path).size),'caption':caption,'license':'New data visualization generated for this course proposal from the attributed author demo data; upstream data terms apply.','low_overlap_confirmed':False,'is_model_prediction':False})

manifest={
 'created_at_utc':datetime.now(timezone.utc).isoformat(),
 'scope':'Downloaded only official small demo arrays, one small GT log and two original author figures. No model weights or dataset archive; no model inference.',
 'total_downloaded_bytes':sum((ROOT/name).stat().st_size for name in sources),
 'demo_data_bytes':sum((ROOT/name).stat().st_size for name in ['src.npy','ref.npy','gt.npy']),
 'point_counts':{'source':len(src),'reference':len(ref)},
 'data_dtype':{'source':str(src.dtype),'reference':str(ref.dtype),'ground_truth':str(gt.dtype)},
 'transform':{'direction':'source -> reference','column_vector_formula':'x_ref = R @ x_src + t','row_array_formula':'aligned_src = src @ gt[:3, :3].T + gt[:3, 3]','units':'meters','ground_truth_matrix':gt.tolist(),'verification':'Official demo applies estimated transform to source; dataset convention is ref = src @ R.T + t. Supplied GT is exactly equal to benchmark redkitchen gt.log entry [0, 6, 60].','demo_code_url':f'https://github.com/qinzheng93/GeoTransformer/blob/{GEO}/experiments/geotransformer.3dmatch.stage4.gse.k3.max.oacl.stage2.sinkhorn/demo.py'},
 'scene_identification':{'scene':'7-scenes-redkitchen','reference_fragment':0,'source_fragment':6,'exact_gt_log_matches':exact_matches,'evidence_level':'Exact 4x4 GT matrix match to the named benchmark pair. Point arrays were not independently compared against a full scene archive.','benchmark_pair_membership':memberships,'low_overlap_demo_claim':False,'interpretation':'Use as a real paired point-cloud/GT example; do not label it a 3DLoMatch example. The associated GeoTransformer overlap field is about 35%, not the custom nearest-neighbor statistic below.'},
 'overlap_visualization':{'distance_threshold_m':.1,'definition':'A point is green if nearest Euclidean distance to any point in the other cloud, after GT alignment, is < 0.1 m. Both directions are computed independently.','source_green_fraction':float(np.mean(cKDTree(ref).query(aligned)[0]<.1)),'reference_green_fraction':float(np.mean(cKDTree(aligned).query(ref)[0]<.1)),'not_official_benchmark_overlap':True},
 'rendering':{'script':'render_demo.py','background':'#F6F8FA','source_color':'#2857B8','reference_color':'#DF8650','green':'#26866F','nonoverlap_gray':'#B9C1CC','view_azimuth_degrees':-120,'view_elevation_degrees':27,'projection':'orthographic; identical view matrix and image bounds in all five panels','display_axis_convention':'[camera_x, camera_z, -camera_y] for visualization only','geometry_changes':'None beyond the given GT transform for aligned panels. All points retained; no invented surfaces. Local normal estimates control point-color shading only.','render_resolution':[1920,1320]},
 'assets':assets,
 'recommended_slide_credit':'Point data: GeoTransformer official demo / 3DMatch; visualization generated from provided GT, no model inference. Author figure: Huang et al., PREDATOR, CVPR 2021.',
}
assert manifest['total_downloaded_bytes']<20_000_000
with (ROOT/'manifest.json').open('x',encoding='utf-8') as stream:json.dump(manifest,stream,ensure_ascii=False,indent=2)
print(json.dumps({'manifest':str(ROOT/'manifest.json'),'downloaded_bytes':manifest['total_downloaded_bytes'],'demo_gt_exact_match':exact_matches,'rendered':list(captions)}))
