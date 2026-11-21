"""Mandatory blind benchmarks, plus stage and provenance contracts."""
import json
import shutil
from pathlib import Path
import subprocess
import sys
import pytest

np = pytest.importorskip('numpy')
cv2 = pytest.importorskip('cv2')
pytest.importorskip('scipy')
pytest.importorskip('skimage')
from hube_tag.io import read_json
from hube_tag.pipeline import build
from hube_tag.registration import register
from hube_tag.synthetic import CASES, create_video, score

pytestmark = pytest.mark.skipif(not shutil.which('ffprobe'),reason='FFprobe required for original PTS')


@pytest.fixture(scope='module')
def runs(tmp_path_factory):
    root = tmp_path_factory.mktemp('synthetic')
    results = {}
    for case in CASES:
        source,truth = create_video(case,root/case)
        output = root/case/'output'
        report = build(source,output,sample_hz=20,persistence=2)
        recovered = read_json(output/'trajectories.json')
        results[case] = (source,truth,output,report,score(truth,recovered))
    return results


@pytest.mark.parametrize('case',CASES)
def test_known_video_geometry_direction_and_gesture_count(runs,case):
    _,_,_,report,metrics = runs[case]
    # Tolerances expressed in SOURCE pixels / seconds, not subjective appearance.
    assert metrics['chamfer_pixels'] < 1.5, metrics
    assert metrics['hausdorff_pixels'] <= 3.5, metrics
    assert metrics['time_mae_seconds'] < 0.15, metrics
    assert metrics['direction_accuracy'] >= 0.9, metrics
    assert metrics['stroke_count_error'] == 0, metrics
    assert metrics['stroke_order_inversions'] == 0, metrics
    assert report['segmentation']['foreground_monotone']
    assert report['video']['registration_unreliable_frames'] == 0
    assert report['rasterization'] and all(r['occupancy_ratio']>0 for r in report['rasterization'])
    assert report['visual_inspection_performed'] is False
    if case in ('figure_eight','intersecting','self_intersecting'):
        assert metrics['ambiguity_count'] > 0  # competing intersection/pen-contact explanations


def test_intermediate_stage_outputs_and_repeatability(runs,tmp_path):
    source,_,output,_,_ = runs['line']
    second = tmp_path/'second'
    build(source,second,sample_hz=20,persistence=2)
    for name in ('frames.json','segmentation.json','trajectories.json','diagnostics.json',
                 'birth_times.npy','final_ascii.txt','final_unicode.txt','final_braille.txt'):
        assert (output/name).read_bytes() == (second/name).read_bytes(), name
    # Stage commands work directly on the documented frames/ and masks/ paths.
    for stage,folder in [('segment','frames'),('reconstruct','masks')]:
        run = subprocess.run([sys.executable,'-m','hube_tag',stage,str(second/folder),
                              *(['--persistence','2'] if stage=='segment' else [])],capture_output=True,text=True)
        assert run.returncode == 0, run.stderr
    assert (output/'frames.json').exists() and (output/'segmentation.json').exists()
    with pytest.raises(ValueError,match='already contains'):
        build(source,second)


def test_camera_registration_recovers_known_translation():
    rng = np.random.default_rng(1729)
    image = rng.integers(30,180,(160,192,3),dtype=np.uint8)
    moving = cv2.warpAffine(image,np.float32([[1,0,4],[0,1,-3]]),(192,160))
    aligned,valid,metrics = register(moving,image)
    assert metrics['reliable'] and metrics['inliers'] >= 8
    assert np.median(abs(aligned[valid].astype(float)-image[valid])) < 5
    transform = np.array(metrics['camera_transform'])
    assert transform[0,2] == pytest.approx(-4,abs=0.5)
    assert transform[1,2] == pytest.approx(3,abs=0.5)


def test_static_footage_cannot_establish_deposition(tmp_path):
    from hube_tag.segmentation import segment
    from hube_tag.video import extract
    source,truth = create_video('line',tmp_path)
    capture = cv2.VideoCapture(str(source))
    ok,frame = capture.read()
    capture.release()
    assert ok
    still = tmp_path/'static.avi'
    writer = cv2.VideoWriter(str(still),cv2.VideoWriter_fourcc(*'MJPG'),20,(192,160))
    for _ in range(12):
        writer.write(frame)
    writer.release()
    output=tmp_path/'static'
    extract(still,output,sample_hz=20)
    result = segment(output/'frames.json',persistence=2)
    assert result['frames'][-1]['foreground_pixels'] == 0
    assert result['warnings']


def test_original_nonuniform_presentation_timestamps_are_preserved(tmp_path):
    from hube_tag.video import extract
    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg required to create VFR fixture')
    entries = []
    rng = np.random.default_rng(1729)
    for i,duration in enumerate((0.04,0.12,0.08,0.2,0.04)):
        image = rng.integers(10,100,(80,96,3),dtype=np.uint8)
        name = tmp_path/f'{i}.png'
        cv2.imwrite(str(name),image)
        entries += [f"file '{name}'",f'duration {duration}']
    entries.append(f"file '{name}'")
    manifest = tmp_path/'concat.txt'
    manifest.write_text('\n'.join(entries)+'\n')
    video = tmp_path/'variable.mkv'
    subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(manifest),
                    '-fps_mode','vfr','-c:v','ffv1',str(video)],check=True)
    result = extract(video,tmp_path/'vfr',sample_hz=100)
    times = [r['timestamp'] for r in result['frames']]
    assert len(set(np.round(np.diff(times),3))) > 1
    assert times[:4] == pytest.approx([0,0.04,0.16,0.24])


def test_photograph_selects_finished_scene_before_unrelated_tail(runs,tmp_path):
    from hube_tag.video import extract
    source,_,_,_,_ = runs['line']
    capture = cv2.VideoCapture(str(source))
    video = tmp_path/'with-outro.avi'
    writer = cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),20,(192,160))
    count=0
    while True:
        ok,frame=capture.read()
        if not ok:
            break
        writer.write(frame)
        last = frame
        count+=1
    capture.release()
    photo = tmp_path/'photo.jpg'
    cv2.imwrite(str(photo),last)
    rng=np.random.default_rng(37)
    unrelated=rng.integers(0,255,(160,192,3),dtype=np.uint8)
    for _ in range(20):
        writer.write(unrelated)
    writer.release()
    report=extract(video,tmp_path/'outro',sample_hz=20,reference_photo=photo)
    assert report['reference_frame_id'] < count
    assert report['reference_selection']['method']=='latest_photo_supported_video_frame'
    assert report['reference_selection']['excluded_tail_seconds']>=0.9


def test_bad_baseline_does_not_turn_a_cut_into_new_paint(runs,tmp_path):
    from hube_tag.segmentation import segment
    source,_,output,_,_=runs['line']
    manifest=read_json(output/'frames.json')
    manifest['frames'][0]['reliable']=False
    manifest['reference_path']=str(output/manifest['reference_path'])
    # Leave the input paths referring to the original frame directory.
    for frame in manifest['frames']:
        frame['registered_path']=str(output/frame['registered_path'])
        frame['valid_path']=str(output/frame['valid_path'])
    path=tmp_path/'frames.json'
    path.write_text(json.dumps(manifest))
    result=segment(path,persistence=2)
    assert result['frames'][-1]['foreground_pixels']==0
    assert any('Baseline registration' in w for w in result['warnings'])


def test_registration_supports_different_canvas_size_and_exposure():
    rng=np.random.default_rng(1709)
    reference=rng.integers(20,150,(180,220,3),dtype=np.uint8)
    # Use textured, mildly smoothed surfaces so feature scales remain comparable.
    reference=cv2.GaussianBlur(reference,(3,3),0)
    image=np.clip(reference.astype(float)+50,0,255).astype(np.uint8)
    target=cv2.resize(reference,(330,270))
    aligned,valid,metrics=register(image,target)
    assert metrics['reliable'],metrics
    assert metrics['registration_residual']>30
    assert metrics['photometric_residual']<15
    matrix=np.array(metrics['camera_transform'])
    assert matrix[0,0]==pytest.approx(1.5,abs=0.07)
    assert matrix[1,1]==pytest.approx(1.5,abs=0.07)
    assert aligned.shape==target.shape and valid.mean()>0.9
