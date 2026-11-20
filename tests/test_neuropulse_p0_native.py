import copy
from pathlib import Path
import tempfile
import unittest
import numpy as np
import mne
from neuropulse_p0.core import (
    ResearchBlocked, sha256_file, inventory, parse_chb_summary,
    load_chb_events, spectral_features_microvolts, qc_window,
    process_raw, compare_baselines, atomic_json, audit_project)


class NeuroPulseP0Tests(unittest.TestCase):
    def test_hash_streaming_integrity(self):
        import hashlib
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'S001R01.edf';p.write_bytes(b'not actual EEG')
            self.assertEqual(sha256_file(p),hashlib.sha256(b'not actual EEG').hexdigest())
            r=inventory(td,hash_files=True)
            self.assertEqual(r['files'][0]['sha256'],sha256_file(p))
            self.assertEqual(r['files'][0]['condition_hint_not_verified'],'eyes_open')
            self.assertEqual(p.read_bytes(),b'not actual EEG')

    def test_inventory_does_not_claim_verification_without_hash(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td)/'a.edf').write_bytes(b'dummy')
            r=inventory(td,hash_files=False)
            self.assertIsNone(r['files'][0]['sha256'])
            self.assertFalse(r['files'][0]['source_hash_verified'])

    def test_parse_chb_only_correct_file(self):
        text='''File Name: chb01_02.edf\nNumber of Seizures in File: 0\nFile Name: chb01_03.edf\nNumber of Seizures in File: 1\nSeizure Start Time: 2996 seconds\nSeizure End Time: 3036 seconds\nFile Name: chb01_04.edf\nNumber of Seizures in File: 0\n'''
        e=parse_chb_summary(text,'chb01_03.edf')
        self.assertEqual(len(e),1)
        self.assertEqual(e[0]['onset_sec'],2996.)
        self.assertEqual(e[0]['end_sec'],3036.)
        self.assertEqual(e[0]['label_origin'],'REFERENCE_ANNOTATION')
        self.assertEqual(parse_chb_summary(text,'chb01_02.edf'),[])

    def test_chb_event_bounds(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'summary.txt'
            p.write_text('File Name: x.edf\nSeizure Start Time: 29 seconds\nSeizure End Time: 35 seconds\n')
            with self.assertRaisesRegex(ResearchBlocked,'EXCEEDS'):
                load_chb_events(p,'x.edf',30)

    def test_synthetic_alpha_psd(self):
        sfreq=160
        t=np.arange(sfreq*12)/sfreq
        data=np.array([25*np.sin(2*np.pi*10*t),15*np.sin(2*np.pi*10*t)])
        r=spectral_features_microvolts(data,sfreq)
        bands=r['band_power_median_uv2']
        self.assertGreater(bands['alpha_8_13'],bands['theta_4_8']*50)
        self.assertEqual(r['n_channels_analyzed'],2)

    def test_qc_flags_flat_and_amplitude_for_review_not_approval(self):
        a=np.vstack([np.zeros(500),np.full(500,600.0)])
        r=qc_window(a,100.,['a','b'])
        self.assertEqual(r['decision'],'QC_REVIEW_REQUIRED')
        self.assertIn('a',r['flat_channel_names_ptp_below_0_5_uv'])
        self.assertIn('b',r['large_amplitude_channels_over_500_uv'])

    def raw(self):
        fs=160.; t=np.arange(160*12)/fs
        data=np.array([20e-6*np.sin(2*np.pi*10*t),30e-6*np.sin(2*np.pi*9*t)])
        return mne.io.RawArray(data,mne.create_info(['C3','C4'],fs,['eeg','eeg']),verbose='ERROR')

    def test_raw_processing_explicit_prohibitions(self):
        raw=self.raw()
        x=process_raw(raw,source_meta={'dataset':'test','subject_within_dataset':'001','condition':'eyes_open','sha256':'x'},
                      start_sec=0,duration_sec=10)
        self.assertFalse(x['participant_identity_linked'])
        self.assertEqual(x['research_status'],'PRELIMINARY_QC_REVIEW_REQUIRED')
        self.assertEqual(x['source_meta']['condition'],'eyes_open')
        self.assertEqual(x['acquisition']['eeg_channels'],2)
        self.assertFalse(x['clinical_clearance'])

    def test_bounds_enforced(self):
        raw=self.raw()
        with self.assertRaisesRegex(ResearchBlocked,'WINDOW_EXCEEDS'):
            process_raw(raw,source_meta={},start_sec=10,duration_sec=10)
        with self.assertRaisesRegex(ResearchBlocked,'OUT_OF_RANGE'):
            process_raw(raw,source_meta={},start_sec=0,duration_sec=121)

    def test_comparison_rejects_cross_subject(self):
        meta={'dataset':'ds','subject_within_dataset':'001','condition':'eyes_open','sha256':'x'}
        a=process_raw(self.raw(),source_meta=meta,start_sec=0,duration_sec=10)
        b=copy.deepcopy(a);b['source_meta']['subject_within_dataset']='002';b['source_meta']['condition']='eyes_closed'
        with self.assertRaisesRegex(ResearchBlocked,'NOT_SAME_DATASET_SUBJECT'):
            compare_baselines(a,b)

    def test_comparison_rejects_longitudinal_claim(self):
        meta={'dataset':'ds','subject_within_dataset':'001','condition':'eyes_open','sha256':'x'}
        a=process_raw(self.raw(),source_meta=meta,start_sec=0,duration_sec=10)
        b=copy.deepcopy(a);b['source_meta']['condition']='eyes_closed'
        r=compare_baselines(a,b)
        self.assertFalse(r['longitudinal_progression'])
        self.assertIsNone(r['clinical_interpretation'])

    def test_report_creation_refuses_existing_non_json_file(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'r.json'
            p.write_bytes(b'USER DATA, NOT A REPORT')
            with self.assertRaises(FileExistsError):
                atomic_json(p, {'new': True})
            self.assertEqual(p.read_bytes(), b'USER DATA, NOT A REPORT')

    def test_atomic_report_never_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'r.json'
            atomic_json(p,{'a':1})
            with self.assertRaises(FileExistsError):atomic_json(p,{'a':2})
            self.assertEqual(p.read_text().splitlines()[1].strip(),'"a": 1')

    def test_project_audit_read_only(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'apps'/'neuropulse'/'backend'
            p.mkdir(parents=True)
            (p/'worker.py').write_text('hello')
            r=audit_project(td)
            self.assertTrue(r['modules']['neuropulse']['directory_exists'])
            self.assertEqual(len(r['modules']['neuropulse']['source_files']),1)
            self.assertEqual((p/'worker.py').read_text(),'hello')

if __name__ == '__main__': unittest.main()


def _make_test_edf(path, seconds=12, sfreq=160):
    """Create a minimal EDF fixture in tests ONLY. Never use as research data."""
    def field(v, width):
        text = str(v)
        assert len(text) <= width, (v, width)
        return text.ljust(width)
    labels = ['C3', 'C4']
    header = ''.join([
        field('0',8), field('SYNTHETIC-TEST-ONLY',80), field('SYNTHETIC',80),
        field('19.11.26',8), field('12.00.00',8),
        field(256+2*256,8), field('',44), field(seconds,8), field(1,8), field(2,4),
    ])
    fields = [
        (16, labels), (80,['','']), (8,['uV','uV']), (8,[-100,-100]),
        (8,[100,100]), (8,[-32768,-32768]), (8,[32767,32767]),
        (80,['','']), (8,[sfreq,sfreq]), (32,['',''])]
    signal_header = ''.join(field(v,width) for width, values in fields for v in values)
    assert len(header) == 256 and len(signal_header) == 512
    t=np.arange(seconds*sfreq)/sfreq
    d=np.vstack([np.rint(25000*np.sin(2*np.pi*10*t)),
                 np.rint(20000*np.sin(2*np.pi*9*t))]).astype('<i2')
    with open(path,'wb') as stream:
        stream.write((header+signal_header).encode('ascii'))
        for sec in range(seconds):
            for ch in range(2):
                stream.write(d[ch,sec*sfreq:(sec+1)*sfreq].tobytes())


class EDFIntegrationTests(unittest.TestCase):
    def test_full_edf_decode_and_readonly_integrity(self):
        from neuropulse_p0.core import process_edf
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/'raw'/'S001R01.edf'; source.parent.mkdir()
            output=root/'derived'; output.mkdir()
            _make_test_edf(source)
            digest=sha256_file(source)
            result=process_edf(source,dataset='synthetic_fixture',subject='S001',
                condition='eyes_open',start_sec=0,duration_sec=10,
                summary=None,expected_sha256=digest,authorization_affirmed=True)
            self.assertEqual(result['acquisition']['eeg_channels'],2)
            self.assertEqual(result['acquisition']['sfreq_hz'],160.0)
            self.assertEqual(result['source_meta']['sha256'],digest)
            self.assertEqual(sha256_file(source),digest)
            self.assertEqual(result['research_status'],'PRELIMINARY_QC_REVIEW_REQUIRED')
            self.assertGreater(result['spectral_features']['band_power_median_uv2']['alpha_8_13'],10)

    def test_edf_wrong_hash_or_permission_blocked(self):
        from neuropulse_p0.core import process_edf
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'s.edf';_make_test_edf(source)
            args=dict(dataset='test',subject='S001',condition='eyes_open',
                      start_sec=0,duration_sec=10,summary=None,expected_sha256=None)
            with self.assertRaisesRegex(ResearchBlocked,'AUTHORIZATION'):
                process_edf(source,authorization_affirmed=False,**args)
            with self.assertRaisesRegex(ResearchBlocked,'SHA256_MISMATCH'):
                process_edf(source,authorization_affirmed=True,
                            **{**args,'expected_sha256':'0'*64})
