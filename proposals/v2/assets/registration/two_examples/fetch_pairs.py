"""Read ZIP ranges to fetch three small point-cloud members, never the full ZIP."""
from pathlib import Path
import hashlib
import io
import json
import struct
import zlib
import requests

ROOT = Path(__file__).resolve().parent
URL = 'https://share.phys.ethz.ch/~gseg/Predator/data.zip'
CAP = 60_000_000
session = requests.Session()
session.headers['Accept-Encoding'] = 'identity'
transfers=[]

def fetch_range(start,end):
    if sum(row['bytes'] for row in transfers)+(end-start+1)>CAP:
        raise RuntimeError('60 MB total transfer cap exceeded')
    with session.get(URL,headers={'Range':f'bytes={start}-{end}'},stream=True,timeout=40) as response:
        if response.status_code!=206:
            raise RuntimeError(f'Range not honored: HTTP {response.status_code}; full body not read')
        expected=f'bytes {start}-{end}/'
        if not response.headers.get('Content-Range','').startswith(expected):
            raise RuntimeError(f'Unexpected Content-Range: {response.headers.get("Content-Range")}')
        data=response.content
        if len(data)!=end-start+1:raise RuntimeError('Truncated range')
        transfers.append({'start':start,'end':end,'bytes':len(data),'content_range':response.headers['Content-Range']})
        return data

def main():
    response=session.head(URL,timeout=30)
    response.raise_for_status()
    size=int(response.headers['Content-Length'])
    tail=fetch_range(size-65557,size-1)
    eocd_pos=tail.rfind(b'PK\x05\x06')
    if eocd_pos<0:raise RuntimeError('No standard ZIP end record')
    fields=struct.unpack_from('<4s4H2LH',tail,eocd_pos)
    _,disk,central_disk,disk_count,entry_count,central_size,central_offset,comment_len=fields
    if disk or central_disk or central_size==0xffffffff:raise RuntimeError('Unsupported multi-volume/ZIP64 archive')
    central=fetch_range(central_offset,central_offset+central_size-1)
    entries=[];offset=0
    while offset<len(central):
        f=struct.unpack_from('<4s6H3L5H2L',central,offset)
        if f[0]!=b'PK\x01\x02':raise RuntimeError('Invalid central-directory signature')
        name_len,extra_len,comment_len=f[10:13]
        name=central[offset+46:offset+46+name_len].decode('utf-8')
        entries.append({'name':name,'flags':f[3],'method':f[4],'crc32':f[7],'compressed_bytes':f[8],'uncompressed_bytes':f[9],'local_offset':f[16]})
        offset+=46+name_len+extra_len+comment_len
    assert len(entries)==entry_count
    wanted=[]
    for fragment in (0,12,30):
        suffix=f'/test/7-scenes-redkitchen/cloud_bin_{fragment}.pth'
        matches=[row for row in entries if row['name'].endswith(suffix)]
        if len(matches)!=1:raise RuntimeError(f'Expected one member for {suffix}: {matches}')
        wanted.append(matches[0])
    print(json.dumps({'archive_bytes':size,'directory_bytes':central_size,'entry_count':entry_count,'selected':wanted}),flush=True)
    for row in wanted:
        local=fetch_range(row['local_offset'],row['local_offset']+29)
        h=struct.unpack('<4s5H3L2H',local)
        if h[0]!=b'PK\x03\x04':raise RuntimeError('Invalid local header')
        if row['flags']&1:raise RuntimeError('Encrypted members unsupported')
        data_start=row['local_offset']+30+h[-2]+h[-1]
        compressed=fetch_range(data_start,data_start+row['compressed_bytes']-1)
        if row['method']==0:payload=compressed
        elif row['method']==8:payload=zlib.decompress(compressed,-15)
        else:raise RuntimeError('Unsupported compression method')
        if len(payload)!=row['uncompressed_bytes'] or (zlib.crc32(payload)&0xffffffff)!=row['crc32']:
            raise RuntimeError('ZIP integrity verification failed')
        target=ROOT/Path(row['name']).name
        with target.open('xb') as stream:stream.write(payload)
        row['saved_file']=target.name
        row['sha256']=hashlib.sha256(payload).hexdigest()
        print(json.dumps({'saved':target.name,'bytes':len(payload),'sha256':row['sha256']}),flush=True)
    report={'url':URL,'archive_content_length':size,'downloaded_range_bytes':sum(row['bytes'] for row in transfers),'ranges':transfers,'members':wanted,'full_archive_downloaded':False}
    with (ROOT/'range_fetch_manifest.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps({'downloaded_range_bytes':report['downloaded_range_bytes'],'complete':True}),flush=True)

if __name__=='__main__':main()
