"""Register moving frames to one reference; expose failure, never hide it."""
import cv2
import numpy as np


def configure():
    cv2.setNumThreads(1)
    cv2.setRNGSeed(1729)


def register(image, reference, *, orb_reference_features=None, sift_reference_features=None):
    """Return warped BGR, valid pixels, and JSON diagnostics (source -> ref)."""
    configure()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    target = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    h, w = target.shape
    source_h,source_w = gray.shape
    orb = cv2.ORB_create(nfeatures=2000, fastThreshold=12)
    kp, desc = orb.detectAndCompute(gray, None)
    kr, dr = orb_reference_features if orb_reference_features is not None else orb.detectAndCompute(target, None)
    matrix = np.eye(3)
    inliers = 0
    matches = []
    method = 'identity_unverified'
    if desc is not None and dr is not None and len(dr) >= 2:
        pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(desc, dr, k=2)
        matches = [a for pair in pairs if len(pair) == 2 for a,b in [pair] if a.distance < 0.72*b.distance]
        if len(matches) >= 8:
            source = np.float32([kp[m.queryIdx].pt for m in matches])
            dest = np.float32([kr[m.trainIdx].pt for m in matches])
            fitted, mask = cv2.findHomography(source, dest, cv2.RANSAC, 2.5)
            if fitted is not None:
                corners = np.float32([[[0,0],[source_w,0],[source_w,source_h],[0,source_h]]])
                polygon = cv2.perspectiveTransform(corners, fitted)[0]
                ratio = abs(cv2.contourArea(polygon))/(source_w*source_h)
                inliers = int(mask.sum())
                if inliers >= 8 and 0.4 < ratio < 2.5 and np.isfinite(polygon).all():
                    matrix, method = fitted, 'orb_homography'
    if method == 'orb_homography':
        preview = cv2.warpPerspective(gray,matrix,(w,h))
        if float(np.median(np.abs(preview.astype(float)-target.astype(float))))>25:
            method,matrix = 'identity_unverified',np.eye(3)
    if method == 'identity_unverified':
        fitted,n_matches,n_inliers = sift_transform(image,reference,sift_reference_features)
        if fitted is not None and n_inliers>=8 and n_inliers/max(1,n_matches)>=0.4:
            corners = np.float32([[[0,0],[source_w,0],[source_w,source_h],[0,source_h]]])
            polygon = cv2.perspectiveTransform(corners,fitted)[0]
            ratio = abs(cv2.contourArea(polygon))/(source_w*source_h)
            if 0.2<ratio<5 and np.isfinite(polygon).all():
                matrix,method,inliers = fitted,'sift_homography',n_inliers
                matches = [None]*n_matches
    # Identity is trustworthy when robust residual is already low (static camera).
    direct = float(np.median(np.abs(gray.astype(float)-target.astype(float)))) if gray.shape==target.shape else 255.0
    if method == 'identity_unverified' and direct < 3:
        method = 'identity_static'
    warped = cv2.warpPerspective(image, matrix, (w,h))
    valid = cv2.warpPerspective(np.ones(gray.shape, np.uint8), matrix, (w,h), flags=cv2.INTER_NEAREST).astype(bool)
    residuals = np.abs(cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY).astype(float)-target.astype(float))[valid]
    residual = float(np.median(residuals)) if len(residuals) else 255.0
    photometric = {'photometric_gains':[1,1,1],'photometric_offsets':[0,0,0],
                   'photometric_residual':residual}
    if residual>=30 and method in ('orb_homography','sift_homography') and inliers>=20 and inliers/max(1,len(matches))>=0.5 and valid.any():
        warped,photometric = normalize_photometry(warped,reference,valid)
    effective_residual = photometric['photometric_residual']
    corners = np.float32([[[0,0],[source_w,0],[source_w,source_h],[0,source_h]]])
    motion = float(np.mean(np.linalg.norm(cv2.perspectiveTransform(corners,matrix)-corners,axis=2)))
    return warped, valid, {'camera_transform': matrix.round(9).tolist(), 'method': method,
                          'matches': len(matches), 'inliers': inliers,
                          'registration_residual': residual, 'camera_motion_pixels': motion,
                          'valid_fraction': float(valid.mean()),
                          **photometric,
                          'reliable': method != 'identity_unverified' and (residual < 30 or effective_residual < 35)}


def sift_transform(image, reference, reference_features=None):
    """Scale-invariant fallback; also supports photo-assisted reference selection."""
    detector = cv2.SIFT_create(nfeatures=3000,contrastThreshold=0.02)
    gray = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    kp,desc = detector.detectAndCompute(gray,None)
    kr,dr = reference_features if reference_features is not None else detector.detectAndCompute(cv2.cvtColor(reference,cv2.COLOR_BGR2GRAY),None)
    if desc is None or dr is None or len(dr)<2:
        return None,0,0
    pairs = cv2.BFMatcher().knnMatch(desc,dr,k=2)
    matches = [a for pair in pairs if len(pair)==2 for a,b in [pair] if a.distance<0.7*b.distance]
    if len(matches)<8:
        return None,len(matches),0
    source = np.float32([kp[m.queryIdx].pt for m in matches])
    dest = np.float32([kr[m.trainIdx].pt for m in matches])
    fitted,mask = cv2.findHomography(source,dest,cv2.RANSAC,2.5)
    return fitted,len(matches),int(mask.sum()) if mask is not None else 0


def photo_reference(records, root, photo_path):
    """Choose the latest frame matching the supplied finished-scene photograph.

    Match background geometry only: the photograph never supplies arrival times
    or replaces observed video paint. Sparse scan followed by local refinement.
    """
    from pathlib import Path
    root = Path(root)
    photo = cv2.imread(str(photo_path))
    if photo is None:
        raise ValueError('cannot decode reference photograph')
    h,w = photo.shape[:2]
    factor = min(1,900/max(h,w))
    photo = cv2.resize(photo,(round(w*factor),round(h*factor)))
    detector = cv2.SIFT_create(nfeatures=3000,contrastThreshold=0.02)
    features = detector.detectAndCompute(cv2.cvtColor(photo,cv2.COLOR_BGR2GRAY),None)
    checked = {}
    def check(record):
        frame = cv2.imread(str(root/record['path']))
        matrix,matches,inliers = sift_transform(frame,photo,features)
        ratio = inliers/max(1,matches)
        checked[record['frame_id']] = {'frame_id':record['frame_id'],'timestamp':record['timestamp'],
                                      'photo_matches':matches,'photo_inliers':inliers,'inlier_fraction':ratio}
        return inliers,ratio
    sparse = []
    last = -float('inf')
    for record in records:
        if record['timestamp']-last>=1 or record is records[-1]:
            check(record)
            sparse.append(record)
            last = record['timestamp']
    threshold = max(20,max((r['photo_inliers'] for r in checked.values()),default=0)*0.25)
    usable = [r for r in sparse if checked[r['frame_id']]['photo_inliers']>=threshold and checked[r['frame_id']]['inlier_fraction']>=0.5]
    if not usable:
        return None,{'method':'photo_matching_failed','checked':list(checked.values())}
    candidate = usable[-1]
    for record in records:
        if candidate['timestamp'] < record['timestamp'] <= candidate['timestamp']+1:
            inliers,fraction = check(record)
            if inliers>=threshold and fraction>=0.5:
                candidate = record
    return candidate,{'method':'latest_photo_supported_video_frame','minimum_photo_inliers':threshold,
                      'checked':list(checked.values()),
                      'excluded_tail_seconds':records[-1]['timestamp']-candidate['timestamp']}


def normalize_photometry(warped, reference, valid):
    """Robust per-channel exposure mapping; diagnostics retain the raw residual.

    Quantiles use only geometrically valid overlap, not black warp padding.
    This compensates rephotographed paper/exposure, not arbitrary scene changes.
    """
    corrected = warped.astype(float)
    gains,offsets = [],[]
    for channel in range(3):
        a = warped[:,:,channel][valid].astype(float)
        b = reference[:,:,channel][valid].astype(float)
        aq,bq = np.quantile(a,[0.2,0.5,0.8]),np.quantile(b,[0.2,0.5,0.8])
        gain = float(np.clip((bq[2]-bq[0])/max(1,aq[2]-aq[0]),0.5,2))
        offset = float(bq[1]-gain*aq[1])
        corrected[:,:,channel] = corrected[:,:,channel]*gain+offset
        gains.append(gain)
        offsets.append(offset)
    corrected = np.clip(corrected,0,255).astype(np.uint8)
    corrected[~valid] = 0
    error = np.abs(cv2.cvtColor(corrected,cv2.COLOR_BGR2GRAY).astype(float)-cv2.cvtColor(reference,cv2.COLOR_BGR2GRAY).astype(float))
    return corrected,{'photometric_gains':gains,'photometric_offsets':offsets,
                      'photometric_residual':float(np.median(error[valid]))}
