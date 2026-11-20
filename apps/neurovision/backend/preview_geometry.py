"""Non-diagnostic 3D MRI signal foreground outline; never an anatomical brain mask.
The binary operation is a visualization proxy, not a trained segmentation model.
"""
import numpy as np
from scipy.ndimage import binary_closing,binary_opening,binary_fill_holes,label
from skimage.measure import marching_cubes

METHOD="positive-signal-morphology-v1"
def preview(volume,affine,lo,hi):
    v=np.asarray(volume,dtype=np.float32)
    if v.ndim!=3 or not np.isfinite(v).all():
        raise ValueError("Finite 3D MRI intensities required")
    nonzero=v[v>0]
    if nonzero.size<100: return None
    # Intensity-defined foreground; cannot distinguish skull, scalp and brain.
    cut=max(float(np.percentile(nonzero,12))*0.5,float(np.percentile(nonzero,99))*0.06)
    mask=binary_opening(v>cut,iterations=1)
    mask=binary_closing(mask,iterations=2)
    regions,count=label(mask)
    if count==0: return None
    sizes=np.bincount(regions.ravel())
    sizes[0]=0
    main=int(np.argmax(sizes))
    mask=binary_fill_holes(regions==main)
    voxels=int(mask.sum())
    if voxels<100 or voxels>=v.size*0.98: return None
    # Coarsened 3D mesh is ONLY a preview, while voxel count is native grid.
    padded=np.pad(mask.astype(np.float32),1)
    result=None
    for step in (3,4,5,6,8):
        verts,faces,_,_=marching_cubes(padded,level=0.5,step_size=step,allow_degenerate=False)
        if len(faces)<=35000:
            result=(verts-1,faces,step)
            break
    if result is None:
        verts,faces,step=verts-1,faces,8
        select=np.linspace(0,len(faces)-1,35000,dtype=int)
        faces=faces[select]
        result=(verts,faces,step)
    verts,faces,step=result
    geom=np.asarray(affine,dtype=float)
    center=geom[:3,:3]@((np.asarray(v.shape,dtype=float)-1)/2)+geom[:3,3]
    world=verts@geom[:3,:3].T+geom[:3,3]-center
    voxel_ml=abs(float(np.linalg.det(geom[:3,:3])))/1000.0
    intensity=np.clip((v[tuple(np.clip(np.rint(verts).astype(int).T,0,np.asarray(v.shape)[:,None]-1))]-lo)/(hi-lo),0,1)
    surface={"id":-1,"name":"MRI signal foreground preview (not brain segmentation)","vertices_mm":np.round(world,2).tolist(),"center_mm":np.round(center,2).tolist(),"faces":faces.tolist(),"intensity":np.round(intensity,3).tolist(),"mesh_sampling_voxels":step,"status":"UNVALIDATED_IMAGE_FOREGROUND"}
    measurement={"id":"image_foreground_preview","name":"MRI signal foreground (not brain volume)","voxel_count":voxels,"volume_ml":float(voxels*voxel_ml),"fraction_of_mask_percent":None,"status":"Image-intensity foreground proxy; includes non-brain anatomy; never a clinical brain-volume measurement"}
    return {"surface":surface,"measurement":measurement,"cutoff":cut,"method":METHOD}
