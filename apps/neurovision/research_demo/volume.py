"""Local, research-only MRI volume helpers. No patient database or network calls."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import numpy as np
from PIL import Image, ImageDraw

APP_VERSION = 'nv-research-workbench-0.1.0'

@dataclass
class Volume:
    intensity: np.ndarray  # x,y,z uint8
    labels: np.ndarray | None
    voxel_mm: tuple[float, float, float]
    descriptor: dict
    voxel_volume_mm3: float | None = None


def synthetic_volume(visit: int = 1, size=(128, 144, 112)) -> Volume:
    """Illustrative phantom, NOT any real subject/OASIS image or anatomical segmentation."""
    if visit not in (1, 2):
        raise ValueError('Synthetic visits are 1 or 2')
    nx, ny, nz = size
    x,y,z = np.ogrid[-1:1:complex(nx), -1:1:complex(ny), -1:1:complex(nz)]
    head = (x/0.87)**2 + ((y-0.05)/0.92)**2 + (z/0.90)**2 <= 1
    outer = (x/0.73)**2 + ((y+0.015)/0.79)**2 + (z/0.80)**2 <= 1
    inner = (x/0.62)**2 + ((y+0.015)/0.68)**2 + (z/0.70)**2 <= 1
    sulci = (np.sin(29*x + 7*z) + np.cos(34*y-12*x) + np.sin(21*z-5*y))
    ventl = ((x+0.13)/0.105)**2 + ((y+0.03)/0.12)**2 + ((z+0.04)/0.30)**2 <= 1
    ventr = ((x-0.13)/0.105)**2 + ((y+0.03)/0.12)**2 + ((z+0.04)/0.30)**2 <= 1
    ventricles = (ventl | ventr) & inner
    gm = outer & ~inner
    # Synthetic texture, deterministic and unrelated to actual MRI acquisition
    field = 7*np.sin(17*x+14*z) + 5*np.cos(21*y+3*x)+2*np.sin(31*z-13*y)
    arr = np.where(head, 32.0, 7.0)
    arr = np.where(outer, 128.0+field+7*sulci, arr)
    arr = np.where(inner, 175.0+field+6*sulci, arr)
    arr = np.where(gm, 115.0+field+9*sulci, arr)
    arr = np.where(ventricles, 30.0+field, arr)
    # Anomaly-like ellipse is DELIBERATELY synthetic; not lesion detection.
    roi = (((x-0.34)/0.13)**2 + ((y+0.28)/0.11)**2 + ((z-0.12)/(0.17 if visit == 1 else 0.20))**2 < 1) & outer
    arr = np.where(roi, 190+field, arr)
    labels = np.zeros(size, dtype=np.uint8)
    labels[gm] = 1
    labels[ventricles] = 2
    labels[roi] = 3
    desc = {
        'mode': 'SYNTHETIC',
        'source': 'Programmatically generated illustrative phantom; NOT OASIS-2 MRI',
        'sample_id': 'DEMO-SYN-01',
        'visit': f'SIM-MR{visit}',
        'orientation': 'Illustrative phantom coordinate axes (not anatomical RAS verified)',
        'source_checksum': None,
        'qc': 'SIMULATION_ONLY',
        'clinical_use': 'NOT_FOR_CLINICAL_USE',
        'model': 'None — overlay is generated ground truth, not a detection algorithm',
    }
    return Volume(np.clip(arr, 0, 255).astype('uint8'), labels, (1,1,1.25), desc, 1.25)


def load_local_mri(path: str, segmentation: str | None = None) -> Volume:
    """Optional NIfTI/Analyze/MGZ; nibabel must be separately installed.

    Reorients to canonical voxel axes from the header. This is NOT anatomical
    laterality verification; clinical acceptance requires visual review.
    """
    try:
        import nibabel as nib
    except ImportError as exc:
        raise RuntimeError('Real MRI requires nibabel: python -m pip install nibabel') from exc
    source = Path(path).expanduser().resolve(strict=True)
    image = nib.as_closest_canonical(nib.load(str(source)))
    if len(image.shape) != 3 or any(d < 16 or d > 1024 for d in image.shape):
        raise ValueError('Only 3D anatomical MRI, dimensions 16..1024 each, is supported')
    if int(np.prod(image.shape)) > 40_000_000:
        raise ValueError('Volume too large for this single-volume local prototype')
    data = np.asanyarray(image.dataobj, dtype=np.float32)
    if not np.isfinite(data).any():
        raise ValueError('No finite MRI intensity voxels')
    finite = data[np.isfinite(data)]
    lo,hi = [float(v) for v in np.percentile(finite, [2, 99.5])]
    if hi <= lo:
        raise ValueError('MRI image has no usable intensity range')
    scaled = np.uint8(np.clip((np.nan_to_num(data, nan=lo, posinf=hi, neginf=lo)-lo)/(hi-lo)*255, 0, 255))
    lbl = None
    if segmentation:
        segsrc=Path(segmentation).expanduser().resolve(strict=True)
        seg = nib.as_closest_canonical(nib.load(str(segsrc)))
        if seg.shape != image.shape or not np.allclose(seg.affine, image.affine, rtol=0, atol=0.02):
            raise ValueError('Segmentation grid/affine differs from MRI; no implicit resampling allowed')
        lbl_data=np.asanyarray(seg.dataobj)
        if not np.isfinite(lbl_data).all() or (lbl_data < 0).any() or not np.allclose(lbl_data, np.rint(lbl_data)):
            raise ValueError('Segmentation must contain finite nonnegative integer labels')
        if lbl_data.max() > 65535:
            raise ValueError('Segmentation label values outside supported 0..65535')
        lbl=np.asarray(lbl_data, dtype=np.uint16)
    vox=tuple(float(v) for v in image.header.get_zooms()[:3])
    if not all(0.05 <= v <= 20 for v in vox):
        raise ValueError('Voxel dimensions out of supported range')
    # Physical units are only claimed if explicitly present in metadata.
    # For oblique/sheared affine matrices use abs(det(3x3)), not prod(zooms).
    unit = image.header.get_xyzt_units()[0] if hasattr(image.header,'get_xyzt_units') else 'unknown'
    unit_to_mm={'mm':1.0,'micron':0.001,'meter':1000.0}
    conversion=unit_to_mm.get(unit)
    vol_mm3=float(abs(np.linalg.det(image.affine[:3,:3]))*conversion**3) if conversion is not None else None
    h=hashlib.sha256()
    # For Analyze .hdr/.img, hash BOTH files, not only the raw voxel bytes.
    sources=[source]
    if source.suffix.lower() in ('.img','.hdr'):
        partner=source.with_suffix('.hdr' if source.suffix.lower()=='.img' else '.img')
        if partner.is_file():sources.append(partner)
    for src in sorted(set(sources),key=lambda x:x.name):
        h.update(src.name.encode('utf8'))
        with src.open('rb') as f:
            for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return Volume(scaled, lbl, vox, {
        'mode': 'LOCAL_RESEARCH_MRI',
        'source': f'Local source {source.name}; data never uploaded to external services',
        'sample_id': 'LOCAL-MRI-REVIEW', 'visit':'LOCAL-01',
        'source_checksum':h.hexdigest(),
        'orientation':'Canonical orientation from image header; manual left/right and geometry review still required',
        'qc':'UNREVIEWED', 'clinical_use':'RESEARCH_ONLY',
        'physical_units_status':'VERIFIED_FROM_HEADER' if vol_mm3 is not None else 'UNKNOWN_UNITS_NO_PHYSICAL_VOLUME',
        'model':'None. Generic supplied segmentation labels are unreviewed, not automated lesion detection',
    }, vol_mm3)


def slice_image(vol:Volume, plane:str, index:int, xyz: tuple[int,int,int], opacity:float=0.43, label_filter: int=0) -> bytes:
    """Returns a PNG; orientation illustrative, anatomy must be visually validated."""
    from io import BytesIO
    nx,ny,nz=vol.intensity.shape
    xx,yy,zz=xyz
    if plane == 'axial':
        if not 0<=index<nz: raise ValueError('slice out of range')
        gray=vol.intensity[:,:,index].T[::-1, :]; mask=vol.labels[:,:,index].T[::-1,:] if vol.labels is not None else None
        cx,cy=xx,ny-1-yy
    elif plane == 'coronal':
        if not 0<=index<ny: raise ValueError('slice out of range')
        gray=vol.intensity[:,index,:].T[::-1,:]; mask=vol.labels[:,index,:].T[::-1,:] if vol.labels is not None else None
        cx,cy=xx,nz-1-zz
    elif plane == 'sagittal':
        if not 0<=index<nx: raise ValueError('slice out of range')
        gray=vol.intensity[index,:,:].T[::-1,:]; mask=vol.labels[index,:,:].T[::-1,:] if vol.labels is not None else None
        cx,cy=yy,nz-1-zz
    else: raise ValueError('invalid plane')
    rgb=np.stack([gray,gray,gray],axis=-1).astype(np.float32)
    if mask is not None and opacity>0:
        palettes={1:(31,213,165), 2:(75,150,248), 3:(255,147,58)}
        for lbl,color in palettes.items():
            if label_filter and lbl != label_filter: continue
            where=(mask==lbl)
            rgb[where]=rgb[where]*(1-opacity)+np.asarray(color,dtype=float)*opacity
        # If labels from an existing atlas are not 1..3, show those as neutral purple
        other=(mask>3)
        if not label_filter: rgb[other]=rgb[other]*(1-opacity)+np.array((182,137,251))*opacity
        elif label_filter>3: rgb[mask==label_filter]=rgb[mask==label_filter]*(1-opacity)+np.array((182,137,251))*opacity
    img=Image.fromarray(np.uint8(np.clip(rgb,0,255)),mode='RGB')
    # only upsample to visualize (never for measurements)
    scale=min(3,max(1,round(380/max(img.width,img.height))))
    if scale>1: img=img.resize((img.width*scale,img.height*scale),Image.Resampling.NEAREST)
    draw=ImageDraw.Draw(img,'RGBA')
    draw.line([(cx*scale,0),(cx*scale,img.height-1)],fill=(77,234,206,155),width=1)
    draw.line([(0,cy*scale),(img.width-1,cy*scale)],fill=(77,234,206,155),width=1)
    output=BytesIO(); img.save(output,format='PNG',optimize=True);return output.getvalue()


def meta_for(vol:Volume):
    labs=[]
    if vol.labels is not None:
        unique, counts=np.unique(vol.labels,return_counts=True)
        for i,n in zip(unique,counts):
            if int(i)==0:continue
            name= ('Synthetic cortical ribbon' if i==1 else 'Synthetic ventricles' if i==2 else 'Synthetic anomaly-shaped marker' if i==3 else 'Unreviewed imported label '+str(i)) if vol.descriptor['mode']=='SYNTHETIC' else 'Unreviewed imported label '+str(i)
            labs.append({'id':int(i),'name':name,'voxels':int(n), 'volume_mm3':(round(float(n)*vol.voxel_volume_mm3,1) if vol.voxel_volume_mm3 is not None else None), 'status':'SIMULATED' if vol.descriptor['mode']=='SYNTHETIC' else 'PROVISIONAL_NOT_ACCEPTED'})
    # Small, deterministic label point sample for a descriptive 3D preview.
    # This is NOT a reconstructed anatomical surface or accepted segmentation.
    cloud=[]
    if vol.labels is not None:
        present=[int(v) for v in np.unique(vol.labels) if v>0]
        display_labels=([v for v in (1,2,3) if v in present] if vol.descriptor['mode']=='SYNTHETIC' else present[:4])
        for label in display_labels:
            xyz=np.argwhere(vol.labels==label)
            limit=750 if label==1 else 280 if label==2 else 180
            if len(xyz):
                selection=np.linspace(0,len(xyz)-1,min(limit,len(xyz)),dtype=int)
                for point in xyz[selection]:
                    cloud.append([round(float(point[i])/(vol.intensity.shape[i]-1)*2-1,3) for i in range(3)]+[label])
    return {**vol.descriptor, 'shape':list(vol.intensity.shape), 'voxel_size_mm':list(vol.voxel_mm),
            'preview_point_cloud':cloud,
            'center':[int(n//2) for n in vol.intensity.shape], 'labels':labs,
            'software_version':APP_VERSION,'writes_to_participant_record':False,
            'no_automatic_diagnosis':True,
            'not_an_approved_segmentation':True,
            'supported_sequences':'3D structural MRI only. No FLAIR/PET/WMH processing in this demonstration.'}
