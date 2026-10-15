"""Safely decode three NumPy-valued legacy torch files and export two real pairs.

No torch imports, arbitrary pickle globals, model inference, or synthetic point
cloud changes are used. Outputs are regular numerical .npy files.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import io
import json
import pickle
import numpy as np

ROOT=Path(__file__).resolve().parent
WORKSPACE=ROOT.parents[4]
META=WORKSPACE/'proposals'/'research'/'registration_metadata'
GEO='e7a135af4c318ff3b8d7f6c963df094d7e4ea540'
PRED='8c78f125fc58d62ad7d149adf1fed43ed54937e4'

class SafeNumpyUnpickler(pickle.Unpickler):
    def find_class(self,module,name):
        if (module,name) in {('numpy.core.multiarray','_reconstruct'),('numpy.core.multiarray','scalar'),('numpy','ndarray'),('numpy','dtype')}:
            return super().find_class(module,name)
        if (module,name)==('_codecs','encode'):
            def restricted_encode(value,encoding):
                if not isinstance(value,str) or encoding!='latin1':
                    raise pickle.UnpicklingError('Unexpected bytes encoding')
                return value.encode('latin1')
            return restricted_encode
        raise pickle.UnpicklingError(f'Forbidden global: {module}.{name}')

    def persistent_load(self,pid):
        raise pickle.UnpicklingError('Persistent objects/storage are not permitted')

def load_metadata(name):
    with (META/name).open('rb') as stream:return SafeNumpyUnpickler(stream).load()

def load_legacy_numpy(name):
    stream=io.BytesIO((ROOT/name).read_bytes())
    magic=SafeNumpyUnpickler(stream).load()
    protocol=SafeNumpyUnpickler(stream).load()
    system=SafeNumpyUnpickler(stream).load()
    assert magic==119547037146038801333356 and protocol==1001
    assert system['protocol_version']==1001 and system['little_endian']
    points=SafeNumpyUnpickler(stream).load()
    storages=SafeNumpyUnpickler(stream).load()
    assert storages==[] and stream.read()==b''
    assert isinstance(points,np.ndarray) and points.ndim==2 and points.shape[1]==3
    assert points.dtype.kind=='f' and np.isfinite(points).all()
    return points

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def save_array(path,array):
    if not path.exists():
        with path.open('xb') as stream:np.save(stream,array,allow_pickle=False)
    reloaded=np.load(path,allow_pickle=False)
    assert np.array_equal(reloaded,array)
    return {'file':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':sha(path),'shape':list(array.shape),'dtype':str(array.dtype)}

def main():
    out=ROOT/'examples.json'
    if out.exists():raise FileExistsError(out)
    arrays={fragment:load_legacy_numpy(f'cloud_bin_{fragment}.pth') for fragment in [0,12,30]}
    benchmark_data={name:load_metadata(name+'.pkl') for name in ['3DMatch','3DLoMatch']}
    fetch=json.loads((ROOT/'range_fetch_manifest.json').read_text())
    examples=[]
    for folder,benchmark,src_id in [('high_3dmatch','3DMatch',12),('low_3dlomatch','3DLoMatch',30)]:
        ref_path='test/7-scenes-redkitchen/cloud_bin_0.pth'
        src_path=f'test/7-scenes-redkitchen/cloud_bin_{src_id}.pth'
        rows=[r for r in benchmark_data[benchmark] if r['pcd0']==ref_path and r['pcd1']==src_path]
        assert len(rows)==1
        row=rows[0]
        other='3DLoMatch' if benchmark=='3DMatch' else '3DMatch'
        assert not any(r['pcd0']==ref_path and r['pcd1']==src_path for r in benchmark_data[other])
        predator=load_metadata('predator_'+benchmark+'.pkl')
        indices=[i for i,(ref,src) in enumerate(zip(predator['tgt'],predator['src'])) if ref==ref_path and src==src_path]
        assert len(indices)==1
        idx=indices[0]
        assert np.array_equal(row['rotation'],predator['rot'][idx])
        assert np.array_equal(row['translation'],np.asarray(predator['trans'][idx]).reshape(3))
        transform=np.eye(4,dtype=np.float64)
        transform[:3,:3]=row['rotation'];transform[:3,3]=row['translation']
        destination=ROOT/folder
        destination.mkdir(exist_ok=True)
        files={name:save_array(destination/(name+'.npy'),value) for name,value in [('src',arrays[src_id]),('ref',arrays[0]),('gt',transform)]}
        record={
            'id':folder,'benchmark':benchmark,'scene':'7-scenes-redkitchen',
            'reference_fragment':0,'source_fragment':src_id,
            'point_counts':{'source':len(arrays[src_id]),'reference':len(arrays[0])},
            'overlap':float(row['overlap']),
            'overlap_definition_label':'GeoTransformer author metadata overlap field; not a separately recomputed occlusion fraction',
            'predator_metadata_overlap':float(predator['overlap'][idx]),
            'metadata_overlap_note':'The original PREDATOR and GeoTransformer files agree exactly on pair identity and R/t, but their overlap fields use different values. Slides comparing the examples must use one stated source consistently.',
            'metadata_source':f'https://raw.githubusercontent.com/qinzheng93/GeoTransformer/{GEO}/data/3DMatch/metadata/{benchmark}.pkl',
            'metadata_sha256':sha(META/(benchmark+'.pkl')),
            'predator_metadata_source':f'https://raw.githubusercontent.com/prs-eth/OverlapPredator/{PRED}/configs/indoor/{benchmark}.pkl',
            'predator_metadata_sha256':sha(META/('predator_'+benchmark+'.pkl')),
            'benchmark_identity_verified':True,
            'also_in_other_benchmark_pair_list':False,
            'point_cloud_sources':{
                'archive_url':fetch['url'],
                'reference_member':'data/indoor/'+ref_path,
                'source_member':'data/indoor/'+src_path,
                'member_extraction':'HTTP Range; exact ZIP member CRC32 and uncompressed length verified',
            },
            'ground_truth':{'direction':'source -> reference','formula':'x_ref = R @ x_src + t','numpy_formula':'aligned_src = src @ gt[:3,:3].T + gt[:3,3]','units':'meters','matrix':transform.tolist(),'exact_match_between_author_metadata':True},
            'files':files,
            'caption':f'RedKitchen: source fragment {src_id} to reference fragment 0; {benchmark}; author metadata overlap {100*row["overlap"]:.1f}%. GT-aligned visualization is label illustration, not model output.',
        }
        pair_file=destination/'pair.json'
        if pair_file.exists():
            assert json.loads(pair_file.read_text())==record, 'Existing pair manifest differs; refusing overwrite'
        else:
            with pair_file.open('x',encoding='utf-8') as stream:json.dump(record,stream,indent=2)
        examples.append(record)
    old_ref=ROOT.parent/'ref.npy'
    report={
        'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'purpose':'Two genuine, distinct benchmark pairs with the same reference scan to illustrate ordinary and low-overlap registration.',
        'downloaded_range_bytes':fetch['downloaded_range_bytes'],
        'full_archive_bytes_not_downloaded':fetch['archive_content_length'],
        'reference_identical_between_examples':True,
        'reference_identical_to_prior_official_demo':bool(np.array_equal(arrays[0],np.load(old_ref,allow_pickle=False))),
        'no_model_inference':True,
        'no_synthetic_cropping_or_geometry_changes':True,
        'no_original_assets_modified':True,
        'license_note':'Point clouds were extracted from the PREDATOR-preprocessed 3DMatch distribution. Respect upstream 3DMatch/7-Scenes research data terms; PREDATOR/GeoTransformer code MIT licenses do not independently establish an unrestricted scan-data license.',
        'sources':['https://github.com/prs-eth/OverlapPredator#datasets-and-pretrained-models','https://github.com/qinzheng93/GeoTransformer#3dmatch','https://3dmatch.cs.princeton.edu/'],
        'examples':examples,
    }
    with out.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps({'manifest':str(out),'downloaded_bytes':report['downloaded_range_bytes'],'same_reference_as_demo':report['reference_identical_to_prior_official_demo'],'pairs':[{key:record[key] for key in ['id','benchmark','reference_fragment','source_fragment','overlap','point_counts']} for record in examples]}))

if __name__=='__main__':main()
